# BlueLedger API Documentation

Flask-based REST API for the Carbon Credit Pipeline.

**Base URL:** `http://localhost:8000`

---

## Endpoints

### 1. Health Check

**`GET /health`**

Returns the API status.

**Response:**
```json
{"status": "ok"}
```

---

### 2. Run Pipeline

**`POST /run`**

Submit an area of interest with metadata and execute the carbon credit analysis pipeline.

#### Request

**Headers:**
```
Content-Type: application/json
```

**Body:** JSON object containing UUID, name, and GeoJSON geometry.

| Field | Type | Description |
|-------|------|-------------|
| `UUID` | string | Unique identifier for the request |
| `name` | string | Descriptive name for the area |
| `geometry` | object | Valid GeoJSON geometry object (e.g., Polygon) |

**Example:**
```json
{
  "UUID": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Amazon Basin Area A",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[88.3, 22.5], [88.4, 22.5], [88.4, 22.6], [88.3, 22.6], [88.3, 22.5]]]
  }
}
```

#### Response

| Field | Type | Description |
|-------|------|-------------|
| `UUID` | string | The UUID provided in the request |
| `name` | string | The name provided in the request |
| `STATUS_CODE` | string | "True" if ELIGIBLE, "False" otherwise |
| `summary` | object | Extracted metrics |

**Summary Object:**

| Field | Type | Description |
|-------|------|-------------|
| `NDVI_MEAN` | float | Normalized Difference Vegetation Index mean |
| `NDWI_MEAN` | float | Normalized Difference Water Index mean |
| `STATUS` | string | Eligibility status (e.g., "ELIGIBLE", "NOT_ELIGIBLE", "FAILED") |
| `TOTAL_AREA` | float | Area in hectares |
| `TOTAL_CREDITS` | integer | Carbon credits issued |

**Example Response:**
```json
{
  "UUID": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Amazon Basin Area A",
  "STATUS_CODE": "True",
  "summary": {
    "NDVI_MEAN": 0.306,
    "NDWI_MEAN": -0.345,
    "STATUS": "ELIGIBLE",
    "TOTAL_AREA": 3003.95,
    "TOTAL_CREDITS": 4576
  }
}
```

#### Error Responses

**400 Bad Request** - Missing Geometry:
```json
{"error": "Missing 'geometry' field"}
```

**400 Bad Request** - Invalid JSON:
```json
{"error": "Invalid JSON: <error details>"}
```

---

## Quick Start

**Start the server:**
```bash
python3 api.py
```

**Test health:**
```bash
curl http://localhost:8000/health
```

**Run pipeline:**
```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "UUID": "test-uuid",
    "name": "Test Area",
    "geometry": {
      "type": "Polygon",
      "coordinates": [[[88.3, 22.5], [88.4, 22.5], [88.4, 22.6], [88.3, 22.6], [88.3, 22.5]]]
    }
  }'
```

---

## Output Files

| File | Location | Description |
|------|----------|-------------|
| `api_run_*.log` | `logs/` | API-level execution logs |
| `carbon_calc_*.log` | `logs/` | Detailed pipeline execution logs |
| `results_*.json` | `logs/` | Detailed pipeline results in JSON |
| `carbon_credit_report.txt` | `outputs/` | Full analysis report |
| `*_wgs84.tif`, `*_utm.tif` | `outputs/` | Generated NDVI/NDWI rasters |
