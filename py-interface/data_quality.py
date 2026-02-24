"""
Data quality assessment utilities
"""

import numpy as np
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class DataQualityAssessor:
    """Assess quality of satellite imagery data"""

    def __init__(self, min_coverage: float = 80.0):
        """
        Initialize quality assessor

        Args:
            min_coverage: Minimum acceptable coverage percentage
        """
        self.min_coverage = min_coverage

    def assess(self, data: np.ndarray, data_name: str = "data") -> Dict:
        """
        Assess data quality by checking for NaN values and coverage

        Args:
            data: Numpy array to assess
            data_name: Name of the data for logging

        Returns:
            Dictionary with quality metrics
        """
        total_pixels = data.size
        valid_pixels = np.count_nonzero(~np.isnan(data))
        invalid_pixels = total_pixels - valid_pixels
        coverage_percent = (valid_pixels / total_pixels) * 100

        quality = {
            "total_pixels": int(total_pixels),
            "valid_pixels": int(valid_pixels),
            "invalid_pixels": int(invalid_pixels),
            "coverage_percent": float(coverage_percent),
            "passed": coverage_percent >= self.min_coverage,
            "data_name": data_name,
        }

        if quality["passed"]:
            logger.info(
                f"{data_name} quality: {coverage_percent:.1f}% coverage "
                f"({valid_pixels:,} valid pixels) - PASSED"
            )
        else:
            logger.warning(
                f"{data_name} quality: {coverage_percent:.1f}% coverage "
                f"({valid_pixels:,} valid pixels) - FAILED (minimum: {self.min_coverage}%)"
            )

        return quality

    def assess_multiple(self, *datasets: Tuple[np.ndarray, str]) -> Dict:
        """
        Assess multiple datasets

        Args:
            *datasets: Tuples of (array, name)

        Returns:
            Dictionary with quality metrics for each dataset
        """
        results = {}
        all_passed = True

        for data, name in datasets:
            quality = self.assess(data, name)
            results[name] = quality
            all_passed = all_passed and quality["passed"]

        results["overall_passed"] = all_passed

        return results


def calculate_statistics(data: np.ndarray, mask_nans: bool = True) -> Dict:
    """
    Calculate comprehensive statistics for an array

    Args:
        data: Input array
        mask_nans: Whether to ignore NaN values

    Returns:
        Dictionary with statistical metrics
    """
    if mask_nans:
        clean_data = data[~np.isnan(data)]
    else:
        clean_data = data

    if len(clean_data) == 0:
        logger.warning("No valid data for statistics calculation")
        return {
            "count": 0,
            "mean": np.nan,
            "std": np.nan,
            "min": np.nan,
            "max": np.nan,
            "median": np.nan,
            "q25": np.nan,
            "q75": np.nan,
        }

    stats = {
        "count": int(len(clean_data)),
        "mean": float(np.mean(clean_data)),
        "std": float(np.std(clean_data)),
        "min": float(np.min(clean_data)),
        "max": float(np.max(clean_data)),
        "median": float(np.median(clean_data)),
        "q25": float(np.percentile(clean_data, 25)),
        "q75": float(np.percentile(clean_data, 75)),
    }

    return stats


def create_temporal_composite(data_list: list, method: str = "median") -> np.ndarray:
    """
    Create temporal composite from multiple images

    Args:
        data_list: List of numpy arrays (same shape)
        method: Compositing method ('median', 'mean', 'max', 'min')

    Returns:
        Composite array
    """
    if not data_list:
        raise ValueError("Empty data list provided")

    if len(data_list) == 1:
        logger.info("Single image provided, no compositing needed")
        return data_list[0]

    # Stack arrays
    stack = np.stack(data_list, axis=0)

    # Apply compositing method
    if method == "median":
        composite = np.nanmedian(stack, axis=0)
    elif method == "mean":
        composite = np.nanmean(stack, axis=0)
    elif method == "max":
        composite = np.nanmax(stack, axis=0)
    elif method == "min":
        composite = np.nanmin(stack, axis=0)
    else:
        raise ValueError(f"Unknown compositing method: {method}")

    logger.info(
        f"Created {method} composite from {len(data_list)} images. "
        f"Valid pixels: {np.count_nonzero(~np.isnan(composite)):,}"
    )

    return composite


def assess_temporal_stability(ndvi_history: list) -> Dict:
    """
    Assess temporal stability to distinguish forest from cropland

    Args:
        ndvi_history: List of NDVI mean values over time

    Returns:
        Dictionary with stability metrics
    """
    if len(ndvi_history) < 2:
        return {
            "stable": True,
            "cv": None,
            "message": "Insufficient temporal data for stability assessment",
        }

    ndvi_array = np.array(ndvi_history)
    mean_ndvi = np.mean(ndvi_array)
    std_ndvi = np.std(ndvi_array)
    cv = std_ndvi / mean_ndvi if mean_ndvi != 0 else np.inf

    # Low CV indicates stable forest, high CV indicates cropland
    stable = cv <= 0.3  # 30% coefficient of variation threshold

    return {
        "stable": stable,
        "cv": float(cv),
        "mean": float(mean_ndvi),
        "std": float(std_ndvi),
        "n_observations": len(ndvi_history),
        "message": (
            "Stable vegetation (likely forest)"
            if stable
            else "High variability (likely cropland or seasonal vegetation)"
        ),
    }
