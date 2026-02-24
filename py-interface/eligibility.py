"""
Carbon credit eligibility assessment
"""

import logging
from typing import Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class EligibilityCriterion:
    """Single eligibility criterion"""

    name: str
    passed: bool
    value: Any
    threshold: Any
    message: str
    weight: float = 1.0  # For weighted eligibility if needed


class EligibilityChecker:
    """Comprehensive eligibility checker for carbon credit projects"""

    def __init__(self, config: Dict):
        """
        Initialize eligibility checker

        Args:
            config: Configuration dictionary with eligibility criteria
        """
        self.config = config
        self.criteria: Dict[str, EligibilityCriterion] = {}
        self.status = "PENDING"

    def check_hydrological_condition(
        self, ndwi_mean: float, threshold: float = None
    ) -> bool:
        """
        Check if water availability is sufficient

        Args:
            ndwi_mean: Mean NDWI value
            threshold: NDWI threshold (uses config if not provided)

        Returns:
            True if passed, False otherwise
        """
        if threshold is None:
            threshold = self.config.get("ndwi_threshold", -0.4)

        passed = ndwi_mean >= threshold

        self.criteria["hydrology"] = EligibilityCriterion(
            name="Hydrological Condition",
            passed=passed,
            value=ndwi_mean,
            threshold=threshold,
            message=(
                f"Adequate water availability (NDWI: {ndwi_mean:.3f})"
                if passed
                else f"Insufficient water (NDWI: {ndwi_mean:.3f} < {threshold})"
            ),
        )

        logger.info(f"Hydrology check: {'PASSED' if passed else 'FAILED'}")
        return passed

    def check_minimum_biomass(self, ndvi_mean: float, min_ndvi: float = None) -> bool:
        """
        Check if vegetation is sufficient for carbon project

        Args:
            ndvi_mean: Mean NDVI value
            min_ndvi: Minimum NDVI threshold (uses config if not provided)

        Returns:
            True if passed, False otherwise
        """
        if min_ndvi is None:
            min_ndvi = self.config.get("min_ndvi", 0.3)

        passed = ndvi_mean >= min_ndvi

        self.criteria["biomass"] = EligibilityCriterion(
            name="Minimum Biomass",
            passed=passed,
            value=ndvi_mean,
            threshold=min_ndvi,
            message=(
                f"Sufficient vegetation (NDVI: {ndvi_mean:.3f})"
                if passed
                else f"Insufficient vegetation (NDVI: {ndvi_mean:.3f} < {min_ndvi})"
            ),
        )

        logger.info(f"Biomass check: {'PASSED' if passed else 'FAILED'}")
        return passed

    def check_minimum_area(self, area_ha: float, min_area: float = None) -> bool:
        """
        Check if project area meets minimum requirements

        Args:
            area_ha: Area in hectares
            min_area: Minimum area threshold (uses config if not provided)

        Returns:
            True if passed, False otherwise
        """
        if min_area is None:
            min_area = self.config.get("min_area_ha", 1.0)

        passed = area_ha >= min_area

        self.criteria["area"] = EligibilityCriterion(
            name="Minimum Area",
            passed=passed,
            value=area_ha,
            threshold=min_area,
            message=(
                f"Area adequate ({area_ha:.2f} ha)"
                if passed
                else f"Area too small ({area_ha:.2f} ha < {min_area} ha)"
            ),
        )

        logger.info(f"Area check: {'PASSED' if passed else 'FAILED'}")
        return passed

    def check_data_quality(
        self, coverage_percent: float, min_coverage: float = None
    ) -> bool:
        """
        Check if data quality is sufficient

        Args:
            coverage_percent: Percentage of valid pixels
            min_coverage: Minimum coverage threshold (uses config if not provided)

        Returns:
            True if passed, False otherwise
        """
        if min_coverage is None:
            min_coverage = self.config.get("min_coverage_percent", 80)

        passed = coverage_percent >= min_coverage

        self.criteria["data_quality"] = EligibilityCriterion(
            name="Data Quality",
            passed=passed,
            value=coverage_percent,
            threshold=min_coverage,
            message=(
                f"Good data coverage ({coverage_percent:.1f}%)"
                if passed
                else f"Insufficient coverage ({coverage_percent:.1f}% < {min_coverage}%)"
            ),
        )

        logger.info(f"Data quality check: {'PASSED' if passed else 'FAILED'}")
        return passed

    def check_temporal_stability(self, cv: float, max_cv: float = None) -> bool:
        """
        Check if vegetation is temporally stable (forest vs cropland)

        Args:
            cv: Coefficient of variation from temporal analysis
            max_cv: Maximum acceptable CV (uses config if not provided)

        Returns:
            True if passed, False otherwise
        """
        if max_cv is None:
            max_cv = self.config.get("max_temporal_cv", 0.3)

        passed = cv <= max_cv

        self.criteria["stability"] = EligibilityCriterion(
            name="Temporal Stability",
            passed=passed,
            value=cv,
            threshold=max_cv,
            message=(
                f"Stable vegetation (CV: {cv:.3f})"
                if passed
                else f"High variability detected (CV: {cv:.3f} > {max_cv})"
            ),
        )

        logger.info(f"Stability check: {'PASSED' if passed else 'FAILED'}")
        return passed

    def get_final_status(self) -> str:
        """
        Determine overall eligibility status

        Returns:
            Eligibility status string
        """
        if not self.criteria:
            return "NO CHECKS PERFORMED"

        all_passed = all(c.passed for c in self.criteria.values())

        if all_passed:
            self.status = "ELIGIBLE"
        else:
            failed = [c.name for c in self.criteria.values() if not c.passed]
            self.status = f"INELIGIBLE (Failed: {', '.join(failed)})"

        logger.info(f"Final eligibility status: {self.status}")
        return self.status

    def generate_report(self) -> str:
        """
        Generate detailed eligibility report

        Returns:
            Formatted report string
        """
        report_lines = [
            "",
            "=" * 70,
            "CARBON CREDIT ELIGIBILITY ASSESSMENT REPORT",
            "=" * 70,
            "",
        ]

        if not self.criteria:
            report_lines.append("No eligibility checks have been performed.")
            report_lines.append("")
            return "\n".join(report_lines)

        # Individual criteria
        for criterion in self.criteria.values():
            status_symbol = "✓ PASS" if criterion.passed else "✗ FAIL"
            report_lines.extend(
                [
                    f"{criterion.name.upper()}: {status_symbol}",
                    f"  {criterion.message}",
                    f"  Value: {criterion.value:.4f} | Threshold: {criterion.threshold}",
                    "",
                ]
            )

        # Summary
        passed_count = sum(1 for c in self.criteria.values() if c.passed)
        total_count = len(self.criteria)

        report_lines.extend(
            [
                "-" * 70,
                f"Summary: {passed_count}/{total_count} criteria passed",
                f"FINAL STATUS: {self.status}",
                "=" * 70,
                "",
            ]
        )

        return "\n".join(report_lines)

    def to_dict(self) -> Dict:
        """
        Export eligibility results as dictionary

        Returns:
            Dictionary with all eligibility data
        """
        return {
            "status": self.status,
            "criteria": {
                name: {
                    "name": c.name,
                    "passed": c.passed,
                    "value": c.value,
                    "threshold": c.threshold,
                    "message": c.message,
                }
                for name, c in self.criteria.items()
            },
            "passed_count": sum(1 for c in self.criteria.values() if c.passed),
            "total_count": len(self.criteria),
        }
