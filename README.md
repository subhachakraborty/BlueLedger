# Architecute

### First Draft
![Architecture](./assets/images/architecture.svg)

### Second Draft
![Architecture_second_draft](./assets/images/architecture_update.svg)

---

## Python Interface

This is a *satellite-based carbon credit assessment pipeline* that uses Sentinel-2 satellite imagery to estimate how much CO₂ a forested area sequesters, and then issues carbon credits accordingly. Here's how it all fits together:

---

### The Big Picture

The system takes a geographic area of interest (a polygon defined in a GeoJSON file), downloads satellite imagery for it, analyzes the vegetation, and produces a verified carbon credit estimate. The entire flow is orchestrated by carbon_credit_pipeline.py, with main.py as the command-line entry point.

---

### Step-by-Step Flow

*1. Configuration (config.yaml + config_loader.py)*
Everything is driven by a YAML config file. It holds Sentinel Hub API credentials (loaded from environment variables for security), time intervals for imagery acquisition, forest biomass model parameters, and eligibility thresholds. The Config class resolves ${ENV_VAR} placeholders at runtime and masks sensitive values in logs.

*2. Satellite Data Acquisition (satellite_data.py)*
The system connects to *Sentinel Hub* and downloads Sentinel-2 imagery for the area. It calculates two spectral indices per pixel using a custom JavaScript evalscript run server-side:
- *NDVI* (Normalized Difference Vegetation Index) — measures vegetation density/health
- *NDWI* (Normalized Difference Water Index) — measures moisture/water content

Cloud-contaminated pixels are masked out (using Sentinel-2's Scene Classification Layer). If multiple time intervals are configured, images are composited (median by default) for better cloud-free coverage. Results are cached locally as .npz files to avoid redundant API calls.

*3. Data Quality Assessment (data_quality.py)*
Before any analysis, the pipeline checks that enough valid (non-NaN, non-cloud) pixels exist — at least 80% coverage by default. It also checks *temporal stability*: if NDVI varies too much across time periods, the area is likely cropland rather than forest (forests are stable year-round, crops are not).

*4. Forest Type Classification & Carbon Calculation (carbon_calculator.py)*
This is the scientific core. Each pixel is classified into one of four forest types based on NDVI and NDWI thresholds, using a *priority system* to prevent overlap:

| Forest Type | NDVI Range | Priority |
|---|---|---|
| Dense Forest | 0.6 – 1.0 | Highest (2) |
| Moderate Forest | 0.4 – 0.6 | 1 |
| Sparse Vegetation | 0.2 – 0.4 | 0 |
| Non-Forest | < 0.2 | Lowest (-1) |

For each pixel, the carbon pipeline runs a chain of conversions:

NDVI → AGB (Above Ground Biomass, tonnes/ha)
     → Carbon Mass (× 0.48 carbon fraction)
     → CO₂ equivalent (× 3.67 molecular weight ratio)
     × pixel area (hectares)
= tonnes CO₂e

The biomass conversion uses simple linear models (AGB = a × NDVI + b) with different coefficients per forest type. A *±15% uncertainty band* is also calculated on the final number.

*5. Eligibility Assessment (eligibility.py)*
The project must pass five checks to be eligible for carbon credits:
- *Hydrology*: Mean NDWI must be above −0.4 (not too dry)
- *Minimum Biomass*: Mean NDVI must exceed 0.3
- *Minimum Area*: At least 1 hectare
- *Data Quality*: ≥80% valid pixel coverage
- *Temporal Stability*: Low coefficient of variation (CV ≤ 0.3), proving it's forest not cropland

*6. Change Detection / Additionality (change_detection.py)*
A key concept in carbon markets is *additionality* — proving the forest wouldn't have been preserved anyway. The system compares current NDVI against a historical baseline (12 months prior) to detect improvement trends. If >60% of pixels show improvement, it's flagged as "SIGNIFICANT_IMPROVEMENT", strengthening the credit claim.

*7. Visualization & Reporting (visualization.py, raster_processing.py)*
The pipeline outputs:
- GeoTIFF rasters of NDVI and NDWI (in UTM projection for accurate area calculations)
- Maps showing forest type classification
- Distribution histograms of index values
- Bar charts of carbon credits by forest type
- A full text report summarizing all results

---

### Key Design Choices

- *Projected CRS requirement*: Pixel area is only calculated in UTM (meters), never in degrees, avoiding the distortion that would occur if lat/lon coordinates were used directly.
- *Priority-based classification*: Forest types are assigned highest-priority first, so a pixel that qualifies for both "dense" and "moderate" always gets classified as "dense" — no ambiguity.
- *Caching*: Satellite data downloads are expensive (API calls, time), so results are cached by an MD5 hash of the request parameters.
- *Separation of concerns*: Each module has a single responsibility, making it straightforward to swap out, for example, the biomass model or the satellite data provider independently.

---


## References
- [Usage of multer](https://betterstack.com/community/guides/scaling-nodejs/multer-in-nodejs/)
- [Multer - Stack Overflow](https://stackoverflow.com/questions/15772394/how-to-upload-display-and-save-images-using-node-js-and-express)
- [Multer S3](https://www.npmjs.com/package/multer-s3/v/2.9.1)
- [Amazon S3](https://docs.aws.amazon.com/sdk-for-javascript/v3/developer-guide/javascript_s3_code_examples.html)
- [AWS sdk v3 GitHub](https://github.com/aws/aws-sdk-js-v3)
