"""
Carbon credit calculation with forest type stratification
"""

import numpy as np
import rasterio
from rasterio.mask import mask
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class CarbonCalculator:
    """Calculate carbon credits with forest type stratification"""

    def __init__(self, config: Dict):
        """
        Initialize carbon calculator

        Args:
            config: Configuration dictionary with carbon model parameters
        """
        self.config = config
        self.carbon_fraction = config.get("carbon_fraction", 0.48)
        self.co2_to_c_ratio = config.get("co2_to_c_ratio", 3.67)
        self.uncertainty = config.get("uncertainty", 0.15)
        self.biomass_models = config.get("biomass_models", {})

    def classify_forest_type(self, ndvi: np.ndarray, ndwi: np.ndarray) -> np.ndarray:
        """
        Deterministic forest classification with enforced priority.
        Higher priority models are applied first and cannot be overwritten.
        """

        # Sort models by explicit priority (higher first)
        priority_models = sorted(
            self.biomass_models.items(),
            key=lambda x: x[1].get("priority", 0),
            reverse=True,
        )

        # -1 means unclassified
        forest_type = np.full(ndvi.shape, fill_value=-1, dtype=np.int8)

        for idx, (type_name, model) in enumerate(priority_models):
            ndvi_min = model.get("ndvi_min", -1)
            ndvi_max = model.get("ndvi_max", 1)

            mask = (
                (ndvi >= ndvi_min)
                & (ndvi < ndvi_max)
                & (forest_type == -1)  # prevent overwrite
            )

            if type_name == "dense_forest":
                mask &= ndwi > -0.2
            elif type_name == "moderate_forest":
                mask &= ndwi > -0.3

            forest_type[mask] = idx

        return forest_type

    def ndvi_to_agb(self, ndvi: float, model: Dict) -> float:
        """
        Convert NDVI to Above Ground Biomass using linear model

        Args:
            ndvi: NDVI value
            model: Model parameters with 'a' and 'b' coefficients

        Returns:
            Above ground biomass in tonnes/ha
        """
        a = model.get("a", 0)
        b = model.get("b", 0)
        agb = a * ndvi + b
        return max(0.0, agb)  # Biomass cannot be negative

    def agb_to_carbon(self, agb: float) -> float:
        """
        Convert biomass to carbon mass

        Args:
            agb: Above ground biomass in tonnes/ha

        Returns:
            Carbon mass in tonnes/ha
        """
        return agb * self.carbon_fraction

    def carbon_to_co2e(self, carbon: float) -> float:
        """
        Convert carbon to CO2 equivalent

        Args:
            carbon: Carbon mass in tonnes

        Returns:
            CO2 equivalent in tonnes
        """
        return carbon * self.co2_to_c_ratio

    def calculate_pixel_area(
        self, transform: rasterio.Affine, crs: rasterio.crs.CRS
    ) -> float:
        """
        Calculate area of a pixel in hectares.
        Requires projected CRS (e.g. UTM).
        """
        if crs is None or not crs.is_projected:
            raise ValueError("Pixel area calculation requires a projected CRS (UTM).")

        pixel_width = abs(transform.a)
        pixel_height = abs(transform.e)

        pixel_area_m2 = pixel_width * pixel_height
        return pixel_area_m2 / 10000

    def calculate_from_rasters(self, ndvi_path: str, ndwi_path: str, polygon) -> Dict:
        """
        Calculate carbon credits from raster files

        Args:
            ndvi_path: Path to NDVI raster
            ndwi_path: Path to NDWI raster
            polygon: Shapely polygon for masking

        Returns:
            Dictionary with calculation results
        """
        logger.info("Starting carbon calculation from rasters...")

        with rasterio.open(ndvi_path) as ndvi_src, rasterio.open(ndwi_path) as ndwi_src:

            # Mask to polygon
            ndvi_masked, _ = mask(ndvi_src, [polygon], crop=True)
            ndwi_masked, _ = mask(ndwi_src, [polygon], crop=True)

            ndvi_data = ndvi_masked[0]
            ndwi_data = ndwi_masked[0]

            # Remove NaN values
            valid_mask = ~(np.isnan(ndvi_data) | np.isnan(ndwi_data))
            ndvi_valid = ndvi_data[valid_mask]
            ndwi_valid = ndwi_data[valid_mask]

            logger.info(f"Valid pixels: {len(ndvi_valid):,}")

            # Classify forest types
            forest_types = self.classify_forest_type(ndvi_valid, ndwi_valid)

            # Calculate pixel area
            pixel_area_ha = self.calculate_pixel_area(ndvi_src.transform, ndvi_src.crs)

            # Calculate carbon for each forest type
            total_carbon = 0.0
            breakdown = {}

            # Use same priority-sorted order as classify_forest_type
            priority_models = sorted(
                self.biomass_models.items(),
                key=lambda x: x[1].get("priority", 0),
                reverse=True,
            )

            for idx, (type_name, model) in enumerate(priority_models):
                type_mask = forest_types == idx
                count = np.sum(type_mask)

                if count == 0:
                    continue

                ndvi_type = ndvi_valid[type_mask]

                # Calculate biomass for each pixel
                agb_array = np.array(
                    [self.ndvi_to_agb(ndvi_val, model) for ndvi_val in ndvi_type]
                )

                # Convert to carbon
                carbon_array = agb_array * self.carbon_fraction

                # Convert to CO2e
                co2e_array = carbon_array * self.co2_to_c_ratio

                # Total for this type
                type_area_ha = count * pixel_area_ha
                type_total_co2e = np.sum(co2e_array) * pixel_area_ha

                total_carbon += type_total_co2e

                breakdown[model["name"]] = {
                    "area_ha": float(type_area_ha),
                    "pixel_count": int(count),
                    "mean_ndvi": float(np.mean(ndvi_type)),
                    "mean_agb_per_ha": float(np.mean(agb_array)),
                    "mean_carbon_per_ha": float(np.mean(carbon_array)),
                    "mean_co2e_per_ha": float(np.mean(co2e_array)),
                    "total_co2e": float(type_total_co2e),
                }

                logger.info(
                    f"{model['name']}: {type_area_ha:.2f} ha, "
                    f"{type_total_co2e:.2f} tonnes CO2e"
                )

            # Calculate total area
            total_area_ha = len(ndvi_valid) * pixel_area_ha

            # Calculate uncertainty bounds
            uncertainty_bounds = self.calculate_uncertainty(total_carbon)

            results = {
                "total_area_ha": float(total_area_ha),
                "total_co2e": float(total_carbon),
                "credits_issued": int(np.floor(total_carbon)),
                "co2e_per_ha": (
                    float(total_carbon / total_area_ha) if total_area_ha > 0 else 0.0
                ),
                "breakdown": breakdown,
                "uncertainty": uncertainty_bounds,
            }

            logger.info(
                f"Total: {total_area_ha:.2f} ha, {total_carbon:.2f} tonnes CO2e, "
                f"{results['credits_issued']} credits"
            )

            return results

    def calculate_from_means(self, ndvi_mean: float, area_ha: float) -> Dict:
        """
        Simple calculation from mean NDVI (legacy method)

        Args:
            ndvi_mean: Mean NDVI value
            area_ha: Area in hectares

        Returns:
            Dictionary with calculation results
        """
        # Use moderate forest model as default
        model = self.biomass_models.get("moderate_forest", {"a": 120.3, "b": -35.4})

        agb_per_ha = self.ndvi_to_agb(ndvi_mean, model)
        carbon_per_ha = self.agb_to_carbon(agb_per_ha)
        co2e_per_ha = self.carbon_to_co2e(carbon_per_ha)
        total_co2e = co2e_per_ha * area_ha

        uncertainty_bounds = self.calculate_uncertainty(total_co2e)

        return {
            "total_area_ha": float(area_ha),
            "mean_ndvi": float(ndvi_mean),
            "agb_per_ha": float(agb_per_ha),
            "carbon_per_ha": float(carbon_per_ha),
            "co2e_per_ha": float(co2e_per_ha),
            "total_co2e": float(total_co2e),
            "credits_issued": int(np.floor(total_co2e)),
            "uncertainty": uncertainty_bounds,
        }

    def calculate_uncertainty(self, total_co2e: float) -> Dict:
        """
        Calculate uncertainty bounds for carbon estimate

        Args:
            total_co2e: Total CO2 equivalent

        Returns:
            Dictionary with uncertainty bounds
        """
        lower_bound = total_co2e * (1 - self.uncertainty)
        upper_bound = total_co2e * (1 + self.uncertainty)

        return {
            "uncertainty_percent": float(self.uncertainty * 100),
            "lower_bound": float(lower_bound),
            "upper_bound": float(upper_bound),
            "confidence_interval": f"±{int(self.uncertainty * 100)}%",
        }
