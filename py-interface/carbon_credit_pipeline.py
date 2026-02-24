"""
Main carbon credit calculation pipeline with change detection
"""

import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict
import geopandas as gpd
from sentinelhub import Geometry
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS

from config_loader import Config
from satellite_data import SatelliteDataAcquisition
from raster_processing import RasterProcessor
from data_quality import DataQualityAssessor, calculate_statistics
from carbon_calculator import CarbonCalculator
from eligibility import EligibilityChecker, EligibilityCriterion
from visualization import Visualizer, generate_text_report

# NEW: Import change detection
try:
    from change_detection import ChangeDetectionAnalyzer

    CHANGE_DETECTION_AVAILABLE = True
except ImportError:
    CHANGE_DETECTION_AVAILABLE = False
    print("Warning: change_detection.py not found. Change detection will be skipped.")


class CarbonCreditPipeline:
    """Main pipeline for carbon credit calculation"""

    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize pipeline

        Args:
            config_path: Path to configuration file
        """
        # Load configuration
        self.config = Config(config_path)

        # Setup logging
        self._setup_logging()

        # Initialize components
        self.satellite_data = SatelliteDataAcquisition(
            {
                "client_id": self.config.get("sentinel_hub", "client_id"),
                "client_secret": self.config.get("sentinel_hub", "client_secret"),
                "cache_dir": self.config.get("project", "cache_dir"),
                "enable_cache": self.config.get("processing", "enable_cache"),
                "max_retries": self.config.get("processing", "max_retries"),
                "retry_delay_seconds": self.config.get(
                    "processing", "retry_delay_seconds"
                ),
            }
        )

        self.raster_processor = RasterProcessor()

        self.quality_assessor = DataQualityAssessor(
            min_coverage=self.config.get("quality", "min_coverage_percent")
        )

        self.carbon_calculator = CarbonCalculator(self.config.get("carbon_model"))

        self.eligibility_checker = EligibilityChecker(self.config.get("eligibility"))

        # NEW: Initialize change detection if enabled
        if CHANGE_DETECTION_AVAILABLE and self.config.get("change_detection", "enable"):
            self.change_analyzer = ChangeDetectionAnalyzer(
                self.config.get("change_detection")
            )
        else:
            self.change_analyzer = None

        if self.config.get("processing", "create_visualizations"):
            self.visualizer = Visualizer(self.config.get("project", "output_dir"))
        else:
            self.visualizer = None

        # Initialize results dictionary
        self.results = {
            "project": {
                "name": self.config.get("project", "name"),
                "aoi_file": self.config.get("project", "aoi_file"),
                "time_period": self.config.get("acquisition", "time_intervals"),
            }
        }

        self.start_time = None
        self.end_time = None

        self.logger = logging.getLogger(__name__)

    def _setup_logging(self):
        """Configure logging"""
        log_dir = Path(self.config.get("project", "log_dir"))
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / f"carbon_calc_{datetime.now():%Y%m%d_%H%M%S}.log"

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
        )

        logging.info(f"Logging initialized: {log_file}")

    def run(self) -> Dict:
        """
        Execute the complete pipeline

        Returns:
            Dictionary with all results
        """
        self.start_time = datetime.now()
        self.logger.info("=" * 80)
        self.logger.info("Starting Carbon Credit Calculation Pipeline")
        if self.change_analyzer:
            self.logger.info("Change Detection: ENABLED")
        self.logger.info("=" * 80)

        try:
            # Step 1: Load AOI
            self.logger.info("\n[STEP 1/10] Loading Area of Interest...")
            gdf, geometry, aoi_polygon = self._load_aoi()

            # Step 2: Determine UTM CRS
            self.logger.info("\n[STEP 2/10] Determining UTM Coordinate System...")
            utm_crs = self.raster_processor.determine_utm_crs(aoi_polygon)
            aoi_utm = gdf.to_crs(utm_crs).geometry.iloc[0]
            self.results["utm_crs"] = str(utm_crs)

            # Step 3: Request current satellite data
            self.logger.info("\n[STEP 3/10] Requesting Current Satellite Data...")
            ndvi, ndwi = self._get_satellite_data(geometry)

            # NEW STEP 3.5: Historical baseline & change detection
            if self.change_analyzer:
                self.logger.info("\n[STEP 3.5/10] Analyzing Historical Baseline...")
                baseline_ndvi, baseline_ndwi = self._get_historical_baseline(geometry)
                change_results = self._analyze_change(ndvi, baseline_ndvi)
                self.results["change_detection"] = change_results

                # Log important findings
                if change_results["percent_improved"] < 30:
                    self.logger.warning(
                        f"⚠ Low improvement detected: {change_results['percent_improved']:.1f}% "
                        "(may affect additionality requirements)"
                    )
                else:
                    self.logger.info(
                        f"✓ Good improvement: {change_results['percent_improved']:.1f}% of area"
                    )

            # Step 4: Assess data quality
            self.logger.info("\n[STEP 4/10] Assessing Data Quality...")
            quality = self._assess_data_quality(ndvi, ndwi)
            self.results["quality"] = quality

            if not quality["overall_passed"]:
                raise ValueError("Data quality assessment failed")

            # Step 5: Save WGS84 rasters
            self.logger.info("\n[STEP 5/10] Saving WGS84 Rasters...")
            ndvi_wgs84, ndwi_wgs84 = self._save_wgs84_rasters(ndvi, ndwi, geometry)

            # Step 6: Reproject to UTM
            self.logger.info("\n[STEP 6/10] Reprojecting to UTM...")
            ndvi_utm, ndwi_utm = self._reproject_to_utm(ndvi_wgs84, ndwi_wgs84, utm_crs)

            # Step 7: Calculate statistics
            self.logger.info("\n[STEP 7/10] Calculating Zonal Statistics...")
            ndvi_stats, ndwi_stats = self._calculate_statistics(
                ndvi_utm, ndwi_utm, aoi_utm
            )
            self.results["ndvi_stats"] = ndvi_stats
            self.results["ndwi_stats"] = ndwi_stats

            # Step 8: Calculate carbon credits
            self.logger.info("\n[STEP 8/10] Calculating Carbon Credits...")
            carbon = self._calculate_carbon(ndvi_utm, ndwi_utm, aoi_utm)
            self.results["carbon"] = carbon

            # Step 9: Check eligibility
            self.logger.info("\n[STEP 9/10] Checking Eligibility...")
            eligibility = self._check_eligibility(ndvi_stats, ndwi_stats, carbon)
            self.results["eligibility"] = eligibility

            # Step 10: Create visualizations & reports
            self.logger.info("\n[STEP 10/10] Generating Outputs...")

            # Create visualizations
            if self.visualizer:
                self._create_visualizations(ndvi_utm, ndwi_utm)

            # Generate reports
            self._generate_reports()

            self.logger.info("\n" + "=" * 80)
            self.logger.info("Pipeline completed successfully!")
            self.logger.info("=" * 80)

            return self.results

        except Exception as e:
            self.logger.error(f"\nPipeline failed: {str(e)}", exc_info=True)
            self.results["error"] = str(e)
            raise

        finally:
            self.end_time = datetime.now()
            duration = (self.end_time - self.start_time).total_seconds()
            self.logger.info(f"\nTotal pipeline duration: {duration:.2f} seconds")
            self._save_results()

    def _load_aoi(self):
        """Load area of interest"""
        aoi_file = self.config.get_required("project", "aoi_file")

        try:
            gdf = gpd.read_file(aoi_file)

            if gdf.empty:
                raise ValueError("GeoJSON contains no features")

            self.logger.info(f"Loaded {len(gdf)} feature(s) from {aoi_file}")
            self.logger.info(f"Original CRS: {gdf.crs}")

            # Convert to WGS84
            gdf = gdf.to_crs(epsg=4326)
            self.logger.info("Converted to EPSG:4326 (WGS84)")

            # Get geometry
            aoi_polygon = gdf.geometry.iloc[0]
            geometry = Geometry(aoi_polygon, crs="EPSG:4326")

            return gdf, geometry, aoi_polygon

        except FileNotFoundError:
            self.logger.error(f"AOI file not found: {aoi_file}")
            raise
        except Exception as e:
            self.logger.error(f"Error loading AOI: {str(e)}")
            raise

    def _get_satellite_data(self, geometry):
        """Request current satellite data"""
        time_intervals = self.config.get("acquisition", "time_intervals")
        output_size = tuple(self.config.get("acquisition", "output_size"))

        ndvi, ndwi = self.satellite_data.get_data(
            geometry=geometry,
            time_intervals=time_intervals,
            output_size=output_size,
            composite_method="median",
        )

        return ndvi, ndwi

    def _get_historical_baseline(self, geometry):
        """
        NEW METHOD: Request historical baseline satellite data

        Args:
            geometry: Sentinel Hub Geometry object

        Returns:
            Tuple of (baseline_ndvi, baseline_ndwi) arrays
        """
        # Get baseline period from change analyzer
        months_back = self.change_analyzer.baseline_period_months
        baseline_start, baseline_end = self.change_analyzer.get_baseline_period(
            datetime.now(), months_back=months_back
        )

        self.logger.info(f"Baseline period: {baseline_start} to {baseline_end}")

        # Download baseline imagery
        output_size = tuple(self.config.get("acquisition", "output_size"))

        baseline_ndvi, baseline_ndwi = self.satellite_data.get_data(
            geometry=geometry,
            time_intervals=[(baseline_start, baseline_end)],
            output_size=output_size,
            composite_method="median",
        )

        return baseline_ndvi, baseline_ndwi

    def _analyze_change(self, current_ndvi, baseline_ndvi):
        """
        NEW METHOD: Analyze changes between baseline and current

        Args:
            current_ndvi: Current NDVI array
            baseline_ndvi: Historical baseline NDVI array

        Returns:
            Dictionary with change detection results
        """
        change_results = self.change_analyzer.calculate_ndvi_change(
            current_ndvi=current_ndvi, baseline_ndvi=baseline_ndvi
        )

        return change_results

    def _assess_data_quality(self, ndvi, ndwi):
        """Assess data quality"""
        quality = self.quality_assessor.assess_multiple((ndvi, "NDVI"), (ndwi, "NDWI"))

        return quality

    def _save_wgs84_rasters(self, ndvi, ndwi, geometry):
        """Save rasters in WGS84"""
        output_dir = Path(self.config.get("project", "output_dir"))

        ndvi_path = output_dir / "ndvi_wgs84.tif"
        ndwi_path = output_dir / "ndwi_wgs84.tif"

        # Create transform
        bounds = geometry.geometry.bounds
        height, width = ndvi.shape
        transform = from_bounds(*bounds, width, height)

        # Save rasters
        self.raster_processor.save_geotiff(
            str(ndvi_path), ndvi, CRS.from_epsg(4326), transform
        )
        self.raster_processor.save_geotiff(
            str(ndwi_path), ndwi, CRS.from_epsg(4326), transform
        )

        return str(ndvi_path), str(ndwi_path)

    def _reproject_to_utm(self, ndvi_wgs84, ndwi_wgs84, utm_crs):
        """Reproject rasters to UTM"""
        output_dir = Path(self.config.get("project", "output_dir"))

        ndvi_utm = output_dir / "ndvi_utm.tif"
        ndwi_utm = output_dir / "ndwi_utm.tif"

        self.raster_processor.reproject_raster(ndvi_wgs84, str(ndvi_utm), utm_crs)
        self.raster_processor.reproject_raster(ndwi_wgs84, str(ndwi_utm), utm_crs)

        return str(ndvi_utm), str(ndwi_utm)

    def _calculate_statistics(self, ndvi_path, ndwi_path, polygon):
        """
        Calculate statistics from raster data.
        AOI already applied upstream — no polygon needed for masking.
        """
        ndvi_stats = calculate_statistics(rasterio.open(ndvi_path).read(1))

        ndwi_stats = calculate_statistics(rasterio.open(ndwi_path).read(1))

        return ndvi_stats, ndwi_stats

    def _calculate_carbon(self, ndvi_path, ndwi_path, polygon):
        """Calculate carbon credits"""
        carbon = self.carbon_calculator.calculate_from_rasters(
            ndvi_path, ndwi_path, polygon
        )

        return carbon

    def _check_eligibility(self, ndvi_stats, ndwi_stats, carbon):
        """Check project eligibility"""
        # Run eligibility checks
        self.eligibility_checker.check_data_quality(
            self.results["quality"]["NDVI"]["coverage_percent"]
        )

        self.eligibility_checker.check_hydrological_condition(ndwi_stats["mean"])

        self.eligibility_checker.check_minimum_biomass(ndvi_stats["mean"])

        self.eligibility_checker.check_minimum_area(carbon["total_area_ha"])

        # NEW: Check additionality if change detection was performed
        if "change_detection" in self.results:
            change_results = self.results["change_detection"]

            min_improvement = self.config.get(
                "change_detection", "min_improvement_percent", default=30
            )

            additionality_passed = change_results["percent_improved"] >= min_improvement

            self.eligibility_checker.criteria["additionality"] = EligibilityCriterion(
                name="Vegetation Trend Indicator",
                passed=additionality_passed,
                value=change_results["percent_improved"],
                threshold=min_improvement,
                message=(
                    f"Vegetation improvement observed over "
                    f"{change_results['percent_improved']:.1f}% of area "
                    "(indicator only – not formal additionality proof)"
                    if additionality_passed
                    else f"Insufficient improvement ({change_results['percent_improved']:.1f}% < {min_improvement}%)"
                ),
            )

        # Get final status
        status = self.eligibility_checker.get_final_status()

        # Print report
        print(self.eligibility_checker.generate_report())

        return self.eligibility_checker.to_dict()

    def _create_visualizations(self, ndvi_path, ndwi_path):
        """Create all visualizations"""
        try:
            # Index maps
            self.visualizer.create_index_maps(ndvi_path, ndwi_path)

            # Histograms
            ndwi_threshold = self.config.get("eligibility", "ndwi_threshold")
            self.visualizer.create_histograms(ndvi_path, ndwi_path, ndwi_threshold)

            # Forest type map
            biomass_models = self.config.get("carbon_model", "biomass_models")
            self.visualizer.create_forest_type_map(ndvi_path, ndwi_path, biomass_models)

            # Carbon breakdown
            breakdown = self.results["carbon"].get("breakdown")
            if breakdown:
                self.visualizer.create_carbon_breakdown_chart(breakdown)

            self.logger.info("All visualizations created successfully")

        except Exception as e:
            self.logger.warning(f"Visualization creation failed: {e}")

    def _generate_reports(self):
        """Generate text reports"""
        output_dir = Path(self.config.get("project", "output_dir"))

        # Text report
        report_path = output_dir / "carbon_credit_report.txt"
        report_text = generate_text_report(self.results, str(report_path))

        # Print summary
        print("\n" + report_text)

    def _save_results(self):
        """Save results to JSON"""
        output_dir = Path(self.config.get("project", "log_dir"))
        output_file = output_dir / f"results_{datetime.now():%Y%m%d_%H%M%S}.json"

        # Prepare serializable results
        results_to_save = {
            "timestamp": self.start_time.isoformat() if self.start_time else None,
            "duration_seconds": (
                (self.end_time - self.start_time).total_seconds()
                if self.end_time and self.start_time
                else None
            ),
            "config": {
                "project_name": self.config.get("project", "name"),
                "aoi_file": self.config.get("project", "aoi_file"),
                "time_intervals": self.config.get("acquisition", "time_intervals"),
                "change_detection_enabled": self.change_analyzer is not None,
            },
            "results": self.results,
        }

        try:
            with open(output_file, "w") as f:
                json.dump(results_to_save, f, indent=2, default=str)

            self.logger.info(f"Results saved to {output_file}")
        except Exception as e:
            self.logger.warning(f"Failed to save results: {e}")
