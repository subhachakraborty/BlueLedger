"""
Visualization and reporting utilities
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import rasterio
from rasterio.plot import show
from pathlib import Path
import logging
from datetime import datetime
from typing import Dict

logger = logging.getLogger(__name__)


class Visualizer:
    """Create visualizations for carbon credit assessment"""

    def __init__(self, output_dir: str = "outputs"):
        """
        Initialize visualizer

        Args:
            output_dir: Directory for saving visualizations
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Set style
        plt.style.use("seaborn-v0_8-darkgrid")

    def create_index_maps(
        self, ndvi_path: str, ndwi_path: str, title_prefix: str = ""
    ) -> Path:
        """
        Create side-by-side maps of NDVI and NDWI

        Args:
            ndvi_path: Path to NDVI raster
            ndwi_path: Path to NDWI raster
            title_prefix: Prefix for title

        Returns:
            Path to saved visualization
        """
        logger.info("Creating index maps visualization...")

        fig, axes = plt.subplots(1, 2, figsize=(16, 7))

        # NDVI map
        with rasterio.open(ndvi_path) as src:
            ndvi = src.read(1)
            show(ndvi, ax=axes[0], cmap="RdYlGn", vmin=-0.2, vmax=1.0)
            axes[0].set_title(
                f"{title_prefix}Normalized Difference Vegetation Index (NDVI)",
                fontsize=14,
                fontweight="bold",
            )
            axes[0].set_xlabel("Easting (m)")
            axes[0].set_ylabel("Northing (m)")

        # NDWI map
        with rasterio.open(ndwi_path) as src:
            ndwi = src.read(1)
            show(ndwi, ax=axes[1], cmap="Blues", vmin=-1, vmax=0.5)
            axes[1].set_title(
                f"{title_prefix}Normalized Difference Water Index (NDWI)",
                fontsize=14,
                fontweight="bold",
            )
            axes[1].set_xlabel("Easting (m)")
            axes[1].set_ylabel("Northing (m)")

        plt.tight_layout()

        output_path = self.output_dir / "index_maps.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info(f"Saved index maps: {output_path}")
        return output_path

    def create_histograms(
        self, ndvi_path: str, ndwi_path: str, ndwi_threshold: float = -0.4
    ) -> Path:
        """
        Create distribution histograms

        Args:
            ndvi_path: Path to NDVI raster
            ndwi_path: Path to NDWI raster
            ndwi_threshold: NDWI threshold for eligibility

        Returns:
            Path to saved visualization
        """
        logger.info("Creating distribution histograms...")

        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        # Load data
        with rasterio.open(ndvi_path) as src:
            ndvi = src.read(1)
            ndvi_clean = ndvi[~np.isnan(ndvi)]

        with rasterio.open(ndwi_path) as src:
            ndwi = src.read(1)
            ndwi_clean = ndwi[~np.isnan(ndwi)]

        # NDVI histogram
        axes[0].hist(ndvi_clean, bins=50, color="#2ecc71", alpha=0.7, edgecolor="black")
        mean_ndvi = np.mean(ndvi_clean)
        axes[0].axvline(
            mean_ndvi,
            color="red",
            linestyle="--",
            linewidth=2,
            label=f"Mean: {mean_ndvi:.3f}",
        )
        axes[0].set_xlabel("NDVI Value", fontsize=12)
        axes[0].set_ylabel("Frequency", fontsize=12)
        axes[0].set_title("NDVI Distribution", fontsize=14, fontweight="bold")
        axes[0].legend(fontsize=11)
        axes[0].grid(alpha=0.3)

        # NDWI histogram
        axes[1].hist(ndwi_clean, bins=50, color="#3498db", alpha=0.7, edgecolor="black")
        mean_ndwi = np.mean(ndwi_clean)
        axes[1].axvline(
            mean_ndwi,
            color="red",
            linestyle="--",
            linewidth=2,
            label=f"Mean: {mean_ndwi:.3f}",
        )
        axes[1].axvline(
            ndwi_threshold,
            color="orange",
            linestyle="--",
            linewidth=2,
            label=f"Threshold: {ndwi_threshold}",
        )
        axes[1].set_xlabel("NDWI Value", fontsize=12)
        axes[1].set_ylabel("Frequency", fontsize=12)
        axes[1].set_title("NDWI Distribution", fontsize=14, fontweight="bold")
        axes[1].legend(fontsize=11)
        axes[1].grid(alpha=0.3)

        plt.tight_layout()

        output_path = self.output_dir / "distribution_histograms.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info(f"Saved histograms: {output_path}")
        return output_path

    def create_forest_type_map(
        self, ndvi_path: str, ndwi_path: str, biomass_models: Dict
    ) -> Path:
        """
        Create map showing forest type classification

        Args:
            ndvi_path: Path to NDVI raster
            ndwi_path: Path to NDWI raster
            biomass_models: Dictionary of biomass models

        Returns:
            Path to saved visualization
        """
        logger.info("Creating forest type map...")

        # Load data
        with rasterio.open(ndvi_path) as src:
            ndvi = src.read(1)

        with rasterio.open(ndwi_path) as src:
            ndwi = src.read(1)

        # Classify forest types
        forest_type = np.zeros_like(ndvi, dtype=np.int8)

        for i, (type_name, model) in enumerate(biomass_models.items()):
            ndvi_min = model.get("ndvi_min", -1)
            ndvi_max = model.get("ndvi_max", 1)

            mask = (ndvi >= ndvi_min) & (ndvi < ndvi_max)

            if type_name == "dense_forest":
                mask = mask & (ndwi > -0.2)
            elif type_name == "moderate_forest":
                mask = mask & (ndwi > -0.3)

            forest_type[mask] = i

        # Create figure
        fig, ax = plt.subplots(figsize=(12, 10))

        # Define colors for each type
        colors = [
            "#8B4513",
            "#228B22",
            "#90EE90",
            "#D3D3D3",
        ]  # brown, green, light green, gray
        cmap = LinearSegmentedColormap.from_list("forest", colors, N=4)

        im = ax.imshow(forest_type, cmap=cmap, vmin=0, vmax=3)

        # Create legend
        labels = [
            model.get("name", f"Type {i}")
            for i, model in enumerate(biomass_models.values())
        ]
        patches = [
            mpatches.Patch(color=colors[i], label=labels[i]) for i in range(len(labels))
        ]
        ax.legend(handles=patches, loc="upper right", fontsize=11)

        ax.set_title("Forest Type Classification", fontsize=14, fontweight="bold")
        ax.set_xlabel("Column")
        ax.set_ylabel("Row")

        plt.tight_layout()

        output_path = self.output_dir / "forest_type_map.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info(f"Saved forest type map: {output_path}")
        return output_path

    def create_carbon_breakdown_chart(self, breakdown: Dict) -> Path:
        """
        Create bar chart showing carbon by forest type

        Args:
            breakdown: Dictionary with carbon breakdown by type

        Returns:
            Path to saved visualization
        """
        logger.info("Creating carbon breakdown chart...")

        if not breakdown:
            logger.warning("No breakdown data available")
            return None

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

        types = list(breakdown.keys())
        areas = [breakdown[t]["area_ha"] for t in types]
        co2e = [breakdown[t]["total_co2e"] for t in types]

        colors = ["#228B22", "#90EE90", "#D3D3D3", "#8B4513"][: len(types)]

        # Area breakdown
        ax1.bar(types, areas, color=colors, edgecolor="black", linewidth=1.5)
        ax1.set_ylabel("Area (hectares)", fontsize=12)
        ax1.set_title("Area by Forest Type", fontsize=14, fontweight="bold")
        ax1.tick_params(axis="x", rotation=45)
        ax1.grid(axis="y", alpha=0.3)

        # Carbon breakdown
        ax2.bar(types, co2e, color=colors, edgecolor="black", linewidth=1.5)
        ax2.set_ylabel("CO2e (tonnes)", fontsize=12)
        ax2.set_title("Carbon Credits by Forest Type", fontsize=14, fontweight="bold")
        ax2.tick_params(axis="x", rotation=45)
        ax2.grid(axis="y", alpha=0.3)

        plt.tight_layout()

        output_path = self.output_dir / "carbon_breakdown.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info(f"Saved carbon breakdown: {output_path}")
        return output_path


def generate_text_report(results: Dict, output_path: str = None) -> str:
    """
    Generate comprehensive text report

    Args:
        results: Dictionary with all results
        output_path: Optional path to save report

    Returns:
        Report text
    """
    lines = [
        "",
        "=" * 80,
        "CARBON CREDIT ASSESSMENT REPORT",
        "=" * 80,
        f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",
        "",
        "-" * 80,
        "PROJECT INFORMATION",
        "-" * 80,
    ]

    # Project info
    project_info = results.get("project", {})
    lines.append(f"Project Name: {project_info.get('name', 'N/A')}")
    lines.append(f"AOI File: {project_info.get('aoi_file', 'N/A')}")
    lines.append(f"Time Period: {project_info.get('time_period', 'N/A')}")
    lines.append("")

    # Data quality
    lines.extend(
        [
            "-" * 80,
            "DATA QUALITY",
            "-" * 80,
        ]
    )

    quality = results.get("quality", {})
    for key, value in quality.items():
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for k, v in value.items():
                lines.append(f"  {k}: {v}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("")

    # Vegetation indices
    lines.extend(
        [
            "-" * 80,
            "VEGETATION INDICES",
            "-" * 80,
        ]
    )

    ndvi_stats = results.get("ndvi_stats", {})
    ndwi_stats = results.get("ndwi_stats", {})

    lines.append("NDVI Statistics:")
    for key, value in ndvi_stats.items():
        lines.append(f"  {key}: {value:.4f}")
    lines.append("")

    lines.append("NDWI Statistics:")
    for key, value in ndwi_stats.items():
        lines.append(f"  {key}: {value:.4f}")
    lines.append("")

    # Carbon calculation
    lines.extend(
        [
            "-" * 80,
            "CARBON CALCULATION",
            "-" * 80,
        ]
    )

    carbon = results.get("carbon", {})
    lines.append(f"Total Area: {carbon.get('total_area_ha', 0):.2f} hectares")
    lines.append(f"Total CO2e: {carbon.get('total_co2e', 0):.2f} tonnes")
    lines.append(f"CO2e per hectare: {carbon.get('co2e_per_ha', 0):.2f} tonnes/ha")
    lines.append(f"Credits Issued: {carbon.get('credits_issued', 0)}")
    lines.append("")

    uncertainty = carbon.get("uncertainty", {})
    if uncertainty:
        lines.append("Uncertainty Bounds:")
        lines.append(f"  Lower: {uncertainty.get('lower_bound', 0):.2f} tonnes CO2e")
        lines.append(f"  Upper: {uncertainty.get('upper_bound', 0):.2f} tonnes CO2e")
        lines.append(f"  Confidence: {uncertainty.get('confidence_interval', 'N/A')}")
        lines.append("")

    # Breakdown by forest type
    breakdown = carbon.get("breakdown", {})
    if breakdown:
        lines.extend(
            [
                "-" * 80,
                "BREAKDOWN BY FOREST TYPE",
                "-" * 80,
            ]
        )

        for forest_type, data in breakdown.items():
            lines.append(f"\n{forest_type}:")
            lines.append(f"  Area: {data.get('area_ha', 0):.2f} ha")
            lines.append(f"  Mean NDVI: {data.get('mean_ndvi', 0):.4f}")
            lines.append(f"  Mean AGB: {data.get('mean_agb_per_ha', 0):.2f} tonnes/ha")
            lines.append(f"  Total CO2e: {data.get('total_co2e', 0):.2f} tonnes")
        lines.append("")

    # Eligibility
    lines.extend(
        [
            "-" * 80,
            "ELIGIBILITY ASSESSMENT",
            "-" * 80,
        ]
    )

    eligibility = results.get("eligibility", {})
    lines.append(f"Status: {eligibility.get('status', 'UNKNOWN')}")
    lines.append("")

    criteria = eligibility.get("criteria", {})
    for criterion_name, criterion in criteria.items():
        status = "✓ PASS" if criterion.get("passed") else "✗ FAIL"
        lines.append(f"{criterion.get('name')}: {status}")
        lines.append(f"  {criterion.get('message')}")
        lines.append("")

    lines.extend(["=" * 80, ""])

    report_text = "\n".join(lines)

    # Save if path provided
    if output_path:
        with open(output_path, "w") as f:
            f.write(report_text)
        logger.info(f"Text report saved: {output_path}")

    return report_text
