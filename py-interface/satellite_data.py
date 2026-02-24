"""
Satellite data acquisition from Sentinel Hub with caching
"""

import numpy as np
import hashlib
import time
from pathlib import Path
from typing import List, Tuple, Optional
import logging

from sentinelhub import SHConfig, SentinelHubRequest, DataCollection, MimeType, Geometry

logger = logging.getLogger(__name__)


class SatelliteDataAcquisition:
    """Handle satellite data requests with caching and retry logic"""

    def __init__(self, config: dict):
        """
        Initialize satellite data acquisition

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.cache_dir = Path(config.get("cache_dir", "cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.enable_cache = config.get("enable_cache", True)
        self.max_retries = config.get("max_retries", 3)
        self.retry_delay = config.get("retry_delay_seconds", 5)

        # Setup Sentinel Hub configuration
        self.sh_config = SHConfig()
        self.sh_config.sh_client_id = config.get("client_id")
        self.sh_config.sh_client_secret = config.get("client_secret")

        if not self.sh_config.sh_client_id or not self.sh_config.sh_client_secret:
            raise ValueError(
                "Sentinel Hub credentials not set. "
                "Please set SENTINEL_HUB_CLIENT_ID and SENTINEL_HUB_CLIENT_SECRET "
                "environment variables."
            )

        logger.info("Sentinel Hub configuration initialized")

    def _get_cache_key(
        self, geometry_bounds: tuple, time_interval: tuple, output_size: tuple
    ) -> str:
        """
        Generate unique cache key for a request

        Args:
            geometry_bounds: Bounding box tuple
            time_interval: Time interval tuple
            output_size: Output size tuple

        Returns:
            MD5 hash string
        """
        key_string = f"{geometry_bounds}{time_interval}{output_size}"
        return hashlib.md5(key_string.encode()).hexdigest()

    def _load_from_cache(
        self, cache_key: str
    ) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """
        Load data from cache if available

        Args:
            cache_key: Cache key

        Returns:
            Tuple of (ndvi, ndwi) arrays or None if not cached
        """
        cache_file = self.cache_dir / f"{cache_key}.npz"

        if cache_file.exists():
            logger.info(f"Loading from cache: {cache_key[:8]}...")
            try:
                cached = np.load(cache_file)
                return cached["ndvi"], cached["ndwi"]
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
                return None

        return None

    def _save_to_cache(self, cache_key: str, ndvi: np.ndarray, ndwi: np.ndarray):
        """
        Save data to cache

        Args:
            cache_key: Cache key
            ndvi: NDVI array
            ndwi: NDWI array
        """
        cache_file = self.cache_dir / f"{cache_key}.npz"

        try:
            np.savez_compressed(cache_file, ndvi=ndvi, ndwi=ndwi)
            logger.info(f"Saved to cache: {cache_key[:8]}...")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def get_evalscript(self) -> str:
        """
        Get the evaluation script for Sentinel Hub

        Returns:
            Evalscript string
        """
        return """
        //VERSION=3
        function setup() {
          return {
            input: ["B03", "B04", "B08", "SCL"],
            output: { bands: 2, sampleType: "FLOAT32" }
          };
        }

        function evaluatePixel(sample) {
          // Cloud masking: exclude cloud shadow, cloud medium/high probability, thin cirrus
          if (sample.SCL == 3 || sample.SCL == 8 || sample.SCL == 9 || sample.SCL == 10) {
            return [NaN, NaN];
          }

          // Calculate NDVI: (NIR - Red) / (NIR + Red)
          let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
          
          // Calculate NDWI: (Green - NIR) / (Green + NIR)
          let ndwi = (sample.B03 - sample.B08) / (sample.B03 + sample.B08);

          return [ndvi, ndwi];
        }
        """

    def request_data(
        self, geometry: Geometry, time_interval: tuple, output_size: tuple
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Request satellite data with retry logic

        Args:
            geometry: Sentinel Hub Geometry object
            time_interval: Tuple of (start_date, end_date)
            output_size: Tuple of (width, height)

        Returns:
            Tuple of (ndvi, ndwi) arrays

        Raises:
            Exception: If all retry attempts fail
        """
        for attempt in range(self.max_retries):
            try:
                logger.info(
                    f"Requesting data (attempt {attempt + 1}/{self.max_retries}): "
                    f"{time_interval[0]} to {time_interval[1]}"
                )

                request = SentinelHubRequest(
                    evalscript=self.get_evalscript(),
                    input_data=[
                        SentinelHubRequest.input_data(
                            data_collection=DataCollection.SENTINEL2_L2A,
                            time_interval=time_interval,
                            mosaicking_order="leastCC",
                        )
                    ],
                    responses=[
                        SentinelHubRequest.output_response("default", MimeType.TIFF)
                    ],
                    geometry=geometry,
                    size=output_size,
                    config=self.sh_config,
                )

                data = request.get_data()[0]

                ndvi = data[:, :, 0]
                ndwi = data[:, :, 1]

                logger.info(
                    f"Successfully retrieved data: {data.shape}, "
                    f"valid pixels: {np.count_nonzero(~np.isnan(ndvi)):,}"
                )

                return ndvi, ndwi

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")

                if attempt < self.max_retries - 1:
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    logger.error("All retry attempts exhausted")
                    raise

    def get_data(
        self,
        geometry: Geometry,
        time_intervals: List[tuple],
        output_size: tuple,
        composite_method: str = "median",
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get satellite data with temporal compositing

        Args:
            geometry: Sentinel Hub Geometry object
            time_intervals: List of time interval tuples
            output_size: Tuple of (width, height)
            composite_method: Method for temporal compositing

        Returns:
            Tuple of (ndvi, ndwi) composite arrays
        """
        geometry_bounds = geometry.geometry.bounds

        # Generate cache key for the composite
        cache_key = self._get_cache_key(
            geometry_bounds, tuple(time_intervals), output_size
        )

        # Try to load from cache
        if self.enable_cache:
            cached_data = self._load_from_cache(cache_key)
            if cached_data is not None:
                return cached_data

        # Download data for each time interval
        ndvi_list = []
        ndwi_list = []

        for interval in time_intervals:
            try:
                ndvi, ndwi = self.request_data(geometry, interval, output_size)
                ndvi_list.append(ndvi)
                ndwi_list.append(ndwi)
            except Exception as e:
                logger.warning(f"Failed to get data for interval {interval}: {e}")
                continue

        if not ndvi_list:
            raise ValueError("No data successfully retrieved for any time interval")

        # Create temporal composite
        if len(ndvi_list) == 1:
            ndvi_composite = ndvi_list[0]
            ndwi_composite = ndwi_list[0]
        else:
            logger.info(
                f"Creating {composite_method} composite from {len(ndvi_list)} images"
            )

            ndvi_stack = np.stack(ndvi_list, axis=0)
            ndwi_stack = np.stack(ndwi_list, axis=0)

            if composite_method == "median":
                ndvi_composite = np.nanmedian(ndvi_stack, axis=0)
                ndwi_composite = np.nanmedian(ndwi_stack, axis=0)
            elif composite_method == "mean":
                ndvi_composite = np.nanmean(ndvi_stack, axis=0)
                ndwi_composite = np.nanmean(ndwi_stack, axis=0)
            elif composite_method == "max":
                ndvi_composite = np.nanmax(ndvi_stack, axis=0)
                ndwi_composite = np.nanmax(ndwi_stack, axis=0)
            else:
                raise ValueError(f"Unknown composite method: {composite_method}")

        # Save to cache
        if self.enable_cache:
            self._save_to_cache(cache_key, ndvi_composite, ndwi_composite)

        return ndvi_composite, ndwi_composite
