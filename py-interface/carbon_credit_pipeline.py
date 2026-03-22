"""
Main carbon credit calculation pipeline
"""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict
import geopandas as gpd
from sentinelhub import Geometry
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS

from config_loader import Config
from satellite_data import SatelliteDataAcquisition
from raster_processing import save_geotiff, reproject_raster, determine_utm_crs
from data_quality import DataQualityAssessor, calculate_statistics
from carbon_calculator import CarbonCalculator
from eligibility import EligibilityChecker


def generate_text_report(results: Dict, output_path: str = None) -> str:
    lines = [
        "CARBON CREDIT ASSESSMENT REPORT",
        f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",
        "",
        f"Project Name: {results.get('project', {}).get('name', 'N/A')}",
        f"Time Period: {results.get('project', {}).get('time_period', 'N/A')}",
        "",
        "NDVI Statistics:",
        f"  mean: {results.get('ndvi_stats', {}).get('mean', 0):.4f}",
        "",
        "NDWI Statistics:",
        f"  mean: {results.get('ndwi_stats', {}).get('mean', 0):.4f}",
        "",
        "CARBON CALCULATION",
        f"Total Area: {results.get('carbon', {}).get('total_area_ha', 0):.2f} hectares",
        f"Total CO2e: {results.get('carbon', {}).get('total_co2e', 0):.2f} tonnes",
        f"Credits Issued: {results.get('carbon', {}).get('credits_issued', 0)}",
        "",
        "ELIGIBILITY",
        f"Status: {results.get('eligibility', {}).get('status', 'UNKNOWN')}"
    ]
    report_text = "\n".join(lines)
    if output_path:
        with open(output_path, 'w') as f:
            f.write(report_text)
    return report_text


class CarbonCreditPipeline:
    """Pipeline for carbon credit calculation"""
    def __init__(self, config_path: str = 'config.yaml'):
        self.config = Config(config_path)
        self._setup_logging()
        
        self.satellite_data = SatelliteDataAcquisition({
            'client_id': self.config.get('sentinel_hub', 'client_id'),
            'client_secret': self.config.get('sentinel_hub', 'client_secret'),
            'max_retries': self.config.get('processing', 'max_retries'),
            'retry_delay_seconds': self.config.get('processing', 'retry_delay_seconds')
        })
        
        self.quality_assessor = DataQualityAssessor(
            min_coverage=self.config.get('quality', 'min_coverage_percent')
        )
        self.carbon_calculator = CarbonCalculator(self.config.get('carbon_model'))
        self.eligibility_checker = EligibilityChecker(self.config.get('eligibility'))
        
        self.results = {
            'project': {
                'name': self.config.get('project', 'name'),
                'aoi_file': self.config.get('project', 'aoi_file'),
                'time_period': self.config.get('acquisition', 'time_intervals')
            }
        }
        self.start_time = None
        self.end_time = None
        self.logger = logging.getLogger(__name__)

    def _setup_logging(self):
        log_dir = Path(self.config.get('project', 'log_dir'))
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f'carbon_calc_{datetime.now():%Y%m%d_%H%M%S}.log'
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.FileHandler(log_file), logging.StreamHandler()]
        )
        logging.info(f"Logging initialized: {log_file}")

    def run(self) -> Dict:
        self.start_time = datetime.now()
        self.logger.info("Starting Carbon Credit Pipeline")
        
        try:
            # Step 1: Load AOI
            gdf, geometry, aoi_polygon = self._load_aoi()
            
            # Step 2: Determine UTM CRS
            utm_crs = determine_utm_crs(aoi_polygon)
            aoi_utm = gdf.to_crs(utm_crs).geometry.iloc[0]
            self.results['utm_crs'] = str(utm_crs)
            
            # Step 3: Request Satellite Data
            ndvi, ndwi = self.satellite_data.get_data(
                geometry=geometry,
                time_intervals=self.config.get('acquisition', 'time_intervals'),
                output_size=tuple(self.config.get('acquisition', 'output_size'))
            )
            
            # Step 4: Assess Data Quality
            quality = self.quality_assessor.assess_multiple((ndvi, 'NDVI'), (ndwi, 'NDWI'))
            self.results['quality'] = quality
            if not quality['overall_passed']:
                raise ValueError("Data quality assessment failed")
            
            # Step 5: Save and Reproject Rasters
            output_dir = Path(self.config.get('project', 'output_dir'))
            output_dir.mkdir(parents=True, exist_ok=True)
            
            ndvi_wgs84 = output_dir / 'ndvi_wgs84.tif'
            ndwi_wgs84 = output_dir / 'ndwi_wgs84.tif'
            
            bounds = geometry.geometry.bounds
            h, w = ndvi.shape
            transform = from_bounds(*bounds, w, h)
            
            save_geotiff(str(ndvi_wgs84), ndvi, CRS.from_epsg(4326), transform)
            save_geotiff(str(ndwi_wgs84), ndwi, CRS.from_epsg(4326), transform)
            
            ndvi_utm = output_dir / 'ndvi_utm.tif'
            ndwi_utm = output_dir / 'ndwi_utm.tif'
            
            reproject_raster(str(ndvi_wgs84), str(ndvi_utm), utm_crs)
            reproject_raster(str(ndwi_wgs84), str(ndwi_utm), utm_crs)
            
            # Step 6: Statistics and Carbon
            ndvi_stats, ndwi_stats = self._calculate_statistics(str(ndvi_utm), str(ndwi_utm))
            self.results['ndvi_stats'] = ndvi_stats
            self.results['ndwi_stats'] = ndwi_stats
            
            carbon = self.carbon_calculator.calculate_from_rasters(str(ndvi_utm), str(ndwi_utm), aoi_utm)
            self.results['carbon'] = carbon
            
            # Step 7: Eligibility
            self.eligibility_checker.check_data_quality(quality['NDVI']['coverage_percent'])
            self.eligibility_checker.check_hydrological_condition(ndwi_stats['mean'])
            self.eligibility_checker.check_minimum_biomass(ndvi_stats['mean'])
            self.eligibility_checker.check_minimum_area(carbon['total_area_ha'])
            
            self.eligibility_checker.get_final_status()
            self.results['eligibility'] = self.eligibility_checker.to_dict()
            
            # Reports
            report_path = output_dir / 'carbon_credit_report.txt'
            report_text = generate_text_report(self.results, str(report_path))
            print("\n" + report_text)
            
            self.logger.info("Pipeline completed successfully!")
            return self.results
            
        except Exception as e:
            self.logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
            self.results['error'] = str(e)
            raise
        finally:
            self.end_time = datetime.now()
            self._save_results()

    def _load_aoi(self):
        aoi_file = self.config.get_required('project', 'aoi_file')
        gdf = gpd.read_file(aoi_file)
        if gdf.empty:
            raise ValueError("GeoJSON contains no features")
        gdf = gdf.to_crs(epsg=4326)
        aoi_polygon = gdf.geometry.iloc[0]
        geometry = Geometry(aoi_polygon, crs="EPSG:4326")
        return gdf, geometry, aoi_polygon

    def _calculate_statistics(self, ndvi_path, ndwi_path):
        with rasterio.open(ndvi_path) as ndvi_src, rasterio.open(ndwi_path) as ndwi_src:
            return calculate_statistics(ndvi_src.read(1)), calculate_statistics(ndwi_src.read(1))

    def _save_results(self):
        output_dir = Path(self.config.get('project', 'log_dir'))
        output_file = output_dir / f'results_{datetime.now():%Y%m%d_%H%M%S}.json'
        
        results_to_save = {
            'timestamp': self.start_time.isoformat() if self.start_time else None,
            'results': self.results
        }
        with open(output_file, 'w') as f:
            json.dump(results_to_save, f, indent=2, default=str)
