"""
Historical baseline comparison and change detection module

This implements the "Historical Baseline" concept from the screenshots:
- Compares current imagery with 6-12 months ago
- Detects vegetation changes (positive/negative)
- Proves additionality for carbon credits
"""

import numpy as np
import logging
from typing import Dict, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ChangeDetectionAnalyzer:
    """Analyze vegetation changes over time for additionality verification"""

    def __init__(self, config: Dict):
        self.config = config
        self.change_threshold = config.get("change_threshold", 0.1)
        self.baseline_period_months = config.get("baseline_period_months", 12)

    def get_baseline_period(
        self, current_date: datetime, months_back: int = 12
    ) -> Tuple[str, str]:
        """Calculate baseline time period"""
        baseline_end = current_date - timedelta(days=30 * months_back)
        baseline_start = baseline_end - timedelta(days=60)
        return (baseline_start.strftime("%Y-%m-%d"), baseline_end.strftime("%Y-%m-%d"))

    def calculate_ndvi_change(
        self, current_ndvi: np.ndarray, baseline_ndvi: np.ndarray
    ) -> Dict:
        """
        NDVI change analysis using shared valid-pixel mask.
        """

        valid_mask = ~np.isnan(current_ndvi) & ~np.isnan(baseline_ndvi)

        valid_count = np.count_nonzero(valid_mask)
        if valid_count == 0:
            raise ValueError("No valid pixels for change detection")

        delta = current_ndvi[valid_mask] - baseline_ndvi[valid_mask]

        improved = delta > self.change_threshold
        degraded = delta < -self.change_threshold

        results = {
            "mean_change": float(np.mean(delta)),
            "pixels_improved": int(np.sum(improved)),
            "pixels_degraded": int(np.sum(degraded)),
            "percent_improved": float(np.sum(improved) / valid_count * 100),
            "percent_degraded": float(np.sum(degraded) / valid_count * 100),
            "valid_pixel_percent": float(valid_count / current_ndvi.size * 100),
        }

        if results["percent_improved"] > 60:
            results["trend"] = "SIGNIFICANT_IMPROVEMENT"
        elif results["percent_improved"] > 40:
            results["trend"] = "MODERATE_IMPROVEMENT"
        else:
            results["trend"] = "STABLE"

        logger.info(
            f"Change: {results['trend']}, Improved: {results['percent_improved']:.1f}%"
        )
        return results
