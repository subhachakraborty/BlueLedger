"""
Raster processing utilities for geospatial operations
"""

import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.mask import mask
from pyproj import CRS as PyCRS
import logging

logger = logging.getLogger(__name__)


class RasterProcessor:
    """Handle raster file operations"""

    @staticmethod
    def save_geotiff(
        path: str,
        array: np.ndarray,
        crs: CRS,
        transform: rasterio.Affine,
        nodata: float = np.nan,
    ):
        """
        Save array as GeoTIFF

        Args:
            path: Output file path
            array: Data array
            crs: Coordinate reference system
            transform: Affine transformation
            nodata: NoData value
        """
        logger.info(f"Saving GeoTIFF: {path}")

        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=array.shape[0],
            width=array.shape[1],
            count=1,
            dtype=array.dtype,
            crs=crs,
            transform=transform,
            nodata=nodata,
            compress="lzw",  # Compression for smaller files
        ) as dst:
            dst.write(array, 1)

        logger.info(f"Saved: {path} ({array.shape[1]}x{array.shape[0]})")

    @staticmethod
    def reproject_raster(
        src_path: str,
        dst_path: str,
        dst_crs: PyCRS,
        resampling: Resampling = Resampling.nearest,
    ):
        """
        Reproject raster to different CRS

        Args:
            src_path: Source raster path
            dst_path: Destination raster path
            dst_crs: Target coordinate reference system
            resampling: Resampling method
        """
        logger.info(f"Reprojecting {src_path} to {dst_crs}")

        with rasterio.open(src_path) as src:
            # Calculate optimal transform and dimensions
            transform, width, height = calculate_default_transform(
                src.crs, dst_crs, src.width, src.height, *src.bounds
            )

            # Update metadata
            meta = src.meta.copy()
            meta.update(
                {
                    "crs": dst_crs,
                    "transform": transform,
                    "width": width,
                    "height": height,
                    "compress": "lzw",
                }
            )

            # Perform reprojection
            with rasterio.open(dst_path, "w", **meta) as dst:
                reproject(
                    source=rasterio.band(src, 1),
                    destination=rasterio.band(dst, 1),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    resampling=resampling,
                )

        logger.info(f"Reprojected: {dst_path}")

    @staticmethod
    def calculate_zonal_statistics(
        raster_path: str, polygon, stats: list = None
    ) -> dict:
        """
        Calculate statistics within a polygon

        Args:
            raster_path: Path to raster file
            polygon: Shapely polygon
            stats: List of statistics to calculate

        Returns:
            Dictionary with statistics
        """
        if stats is None:
            stats = ["mean", "min", "max", "std", "median", "count"]

        logger.info(f"Calculating zonal statistics for {raster_path}")

        with rasterio.open(raster_path) as src:
            # Mask raster with polygon
            out_image, out_transform = mask(src, [polygon], crop=True)
            data = out_image[0]

            # Remove NoData values
            valid_data = data[~np.isnan(data)]

            if len(valid_data) == 0:
                logger.warning("No valid data found in polygon")
                return {stat: np.nan for stat in stats}

            # Calculate statistics
            results = {}

            if "count" in stats:
                results["count"] = int(len(valid_data))
            if "mean" in stats:
                results["mean"] = float(np.mean(valid_data))
            if "std" in stats:
                results["std"] = float(np.std(valid_data))
            if "min" in stats:
                results["min"] = float(np.min(valid_data))
            if "max" in stats:
                results["max"] = float(np.max(valid_data))
            if "median" in stats:
                results["median"] = float(np.median(valid_data))
            if "sum" in stats:
                results["sum"] = float(np.sum(valid_data))
            if "q25" in stats:
                results["q25"] = float(np.percentile(valid_data, 25))
            if "q75" in stats:
                results["q75"] = float(np.percentile(valid_data, 75))

            logger.info(f"Zonal stats: mean={results.get('mean', 'N/A'):.4f}")

            return results

    @staticmethod
    def determine_utm_crs(polygon) -> PyCRS:
        """
        Determine appropriate UTM CRS for a polygon

        Args:
            polygon: Shapely polygon in WGS84

        Returns:
            PyProj CRS object for UTM zone
        """
        centroid = polygon.centroid

        # Calculate UTM zone from longitude
        utm_zone = int((centroid.x + 180) / 6) + 1

        # Determine hemisphere and construct EPSG code
        if centroid.y >= 0:
            epsg_code = 32600 + utm_zone  # Northern hemisphere
        else:
            epsg_code = 32700 + utm_zone  # Southern hemisphere

        utm_crs = PyCRS.from_epsg(epsg_code)

        logger.info(
            f"Determined UTM zone: {utm_zone} "
            f"({'North' if centroid.y >= 0 else 'South'}), "
            f"EPSG:{epsg_code}"
        )

        return utm_crs

    @staticmethod
    def calculate_area(polygon, crs=None) -> float:
        """
        Calculate polygon area in hectares

        Args:
            polygon: Shapely polygon
            crs: Coordinate reference system (if None, assumes meters)

        Returns:
            Area in hectares
        """
        area_m2 = polygon.area
        area_ha = area_m2 / 10000

        logger.info(f"Calculated area: {area_ha:.2f} hectares")

        return area_ha
