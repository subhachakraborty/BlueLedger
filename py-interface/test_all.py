import numpy as np
import geopandas as gpd
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.mask import mask
from pyproj import CRS as PyCRS

from sentinelhub import (
    SHConfig,
    SentinelHubRequest,
    DataCollection,
    MimeType,
    Geometry
)


CLIENT_ID = "216572c1-2472-41d5-ad4e-77b36a1a4ca7"
CLIENT_SECRET = "hDozpdGWtOVGkO7Kue5v3zRgfU1Alcoj"

GEOJSON_FILE = "aoi2.geojson"

NDVI_WGS84 = "ndvi_wgs84.tif"
NDWI_WGS84 = "ndwi_wgs84.tif"
NDVI_UTM = "ndvi_utm.tif"
NDWI_UTM = "ndwi_utm.tif"

TIME_INTERVAL = ("2026-01-01", "2026-01-31")
OUTPUT_SIZE = (512, 512)

# SENTINEL HUB CONFIG

config = SHConfig()
config.sh_client_id = CLIENT_ID
config.sh_client_secret = CLIENT_SECRET

if not CLIENT_ID or not CLIENT_SECRET:
    raise ValueError("Sentinel Hub credentials not set")

# LOAD AOI

gdf = gpd.read_file(GEOJSON_FILE)
if gdf.empty:
    raise ValueError("GeoJSON contains no features")

gdf = gdf.to_crs(epsg=4326)
geometry = Geometry(gdf.geometry.iloc[0], crs="EPSG:4326")
aoi_polygon = gdf.geometry.iloc[0]


# DETERMINE UTM CRS

centroid = aoi_polygon.centroid
utm_zone = int((centroid.x + 180) / 6) + 1
epsg_code = 32600 + utm_zone if centroid.y >= 0 else 32700 + utm_zone
utm_crs = PyCRS.from_epsg(epsg_code)

aoi_utm = gdf.to_crs(utm_crs).geometry.iloc[0]


# EVALSCRIPT (NDVI + NDWI + CLOUD MASK)

evalscript = """
//VERSION=3
function setup() {
  return {
    input: ["B03", "B04", "B08", "SCL"],
    output: { bands: 2, sampleType: "FLOAT32" }
  };
}

function evaluatePixel(sample) {
  if (sample.SCL == 3 || sample.SCL == 8 || sample.SCL == 9 || sample.SCL == 10) {
    return [NaN, NaN];
  }

  let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
  let ndwi = (sample.B03 - sample.B08) / (sample.B03 + sample.B08);

  return [ndvi, ndwi];
}
"""

# SENTINEL HUB REQUEST

request = SentinelHubRequest(
    evalscript=evalscript,
    input_data=[
        SentinelHubRequest.input_data(
            data_collection=DataCollection.SENTINEL2_L2A,
            time_interval=TIME_INTERVAL,
            mosaicking_order="leastCC"
        )
    ],
    responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
    geometry=geometry,
    size=OUTPUT_SIZE,
    config=config
)

print("Requesting Sentinel-2 data...")
data = request.get_data()[0]

ndvi = data[:, :, 0]
ndwi = data[:, :, 1]

# SAVE WGS84 GEOTIFFS

bounds = geometry.geometry.bounds
height, width = ndvi.shape
transform = from_bounds(*bounds, width, height)

def save_tiff(path, array, crs, transform):
    with rasterio.open(
        path, "w",
        driver="GTiff",
        height=array.shape[0],
        width=array.shape[1],
        count=1,
        dtype="float32",
        crs=crs,
        transform=transform
    ) as dst:
        dst.write(array, 1)

save_tiff(NDVI_WGS84, ndvi, CRS.from_epsg(4326), transform)
save_tiff(NDWI_WGS84, ndwi, CRS.from_epsg(4326), transform)

# REPROJECT TO UTM

def reproject_to_utm(src_path, dst_path, dst_crs):
    with rasterio.open(src_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds
        )

        meta = src.meta.copy()
        meta.update({
            "crs": dst_crs,
            "transform": transform,
            "width": width,
            "height": height
        })

        with rasterio.open(dst_path, "w", **meta) as dst:
            reproject(
                source=rasterio.band(src, 1),
                destination=rasterio.band(dst, 1),
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs=dst_crs,
                resampling=Resampling.nearest
            )

reproject_to_utm(NDVI_WGS84, NDVI_UTM, utm_crs)
reproject_to_utm(NDWI_WGS84, NDWI_UTM, utm_crs)

# ZONAL STATISTICS

def zonal_stats(raster_path, polygon):
    with rasterio.open(raster_path) as src:
        out_image, _ = mask(src, [polygon], crop=True)
        data = out_image[0]
        data = data[~np.isnan(data)]

        return {
            "mean": float(np.mean(data)),
            "min": float(np.min(data)),
            "max": float(np.max(data))
        }

ndvi_stats = zonal_stats(NDVI_UTM, aoi_utm)
ndwi_stats = zonal_stats(NDWI_UTM, aoi_utm)

# CARBON CREDIT CALCULATION (NDWI-VALIDATED)

CARBON_FRACTION = 0.48
CO2_TO_C_RATIO = 3.67
AGB_A = 120.3
AGB_B = -35.4
NDWI_THRESHOLD = -0.4

def ndvi_to_agb(ndvi):
    return max(0.0, AGB_A * ndvi + AGB_B)

def agb_to_carbon(agb):
    return agb * CARBON_FRACTION

def carbon_to_co2e(carbon):
    return carbon * CO2_TO_C_RATIO

area_ha = aoi_utm.area / 10_000
ndvi_mean = ndvi_stats["mean"]
ndwi_mean = ndwi_stats["mean"]

if ndwi_mean < NDWI_THRESHOLD:
    eligibility_status = "INELIGIBLE (Hydrological condition failed)"
    total_co2e = 0.0
    credits_issued = 0
else:
    agb_per_ha = ndvi_to_agb(ndvi_mean)
    carbon_per_ha = agb_to_carbon(agb_per_ha)
    co2e_per_ha = carbon_to_co2e(carbon_per_ha)
    total_co2e = co2e_per_ha * area_ha
    credits_issued = int(np.floor(total_co2e))
    eligibility_status = "ELIGIBLE"


print("\n===== FINAL CARBON CREDIT RESULTS =====")
print("Eligibility Status:", eligibility_status)
print("UTM CRS:", utm_crs)
print("NDVI stats:", ndvi_stats)
print("NDWI stats:", ndwi_stats)
print("Project Area (ha):", area_ha)
print("Total CO2e (t):", total_co2e)
print("Credits Issued:", credits_issued)
print("\nOutputs:")
print(f" - {NDVI_UTM}")
print(f" - {NDWI_UTM}")
