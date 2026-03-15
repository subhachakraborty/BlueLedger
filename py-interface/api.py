"""
Flask API for BlueLedger Carbon Credit Pipeline.

Endpoints:
  GET  /health  - Health check
  POST /run     - Submit GeoJSON, run pipeline, return results
"""

import json
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from flask import Flask, jsonify, request

# Paths
BASE_DIR = Path(__file__).resolve().parent
AOI_PATH = BASE_DIR / "aoi.geojson"
LOGS_DIR = BASE_DIR / "logs"
OUTPUTS_DIR = BASE_DIR / "outputs"

app = Flask(__name__)


@app.get("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


@app.post("/run")
def run_pipeline():
    """
    Accept UUID and geometry, run the carbon credit pipeline, and return results in new format.
    """
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Received /run request")
    
    # 1. Validate new input format
    try:
        data = request.get_json(force=True)
        uuid = data.get("UUID", "unknown")
        name = data.get("name", "unknown")
        geometry = data.get("geometry")
        
        if not geometry:
            print("ERROR: Missing 'geometry' field in request")
            return jsonify({"error": "Missing 'geometry' field"}), 400
            
    except Exception as e:
        print(f"ERROR: JSON parsing failed: {e}")
        return jsonify({"error": f"Invalid JSON: {str(e)}"}), 400

    # Save the geometry portion as aoi.geojson for the pipeline
    AOI_PATH.write_text(json.dumps(geometry, indent=2), encoding="utf-8")
    print(f"Saved AOI geometry to {AOI_PATH} for UUID: {uuid}")

    # 2. Create directories and run main.py
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    run_start = datetime.now()
    timestamp = run_start.strftime("%Y%m%d_%H%M%S")
    log_file = LOGS_DIR / f"api_run_{timestamp}.log"

    print(f"Starting pipeline execution for UUID {uuid}...")
    proc = subprocess.run(
        [sys.executable, "main.py"],
        cwd=str(BASE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    print(f"Pipeline finished with exit code {proc.returncode}")

    # Save log
    log_file.write_text(proc.stdout or "", encoding="utf-8")

    # 3. Build summary JSON from results
    summary = _extract_summary(run_start)
    
    # Determine STATUS_CODE string ("True" if ELIGIBLE, "False" otherwise)
    status_str = str(summary.get("STATUS", "FAILED"))
    status_code = "True" if status_str.startswith("ELIGIBLE") else "False"

    # 4. Return new response format
    return jsonify({
        "UUID": uuid,
        "name": name,
        "STATUS_CODE": status_code,
        "summary": {
            "NDVI_MEAN": summary.get("NDVI_MEAN"),
            "NDWI_MEAN": summary.get("NDWI_MEAN"),
            "STATUS": status_str,
            "TOTAL_AREA": summary.get("TOTAL_AREA"),
            "TOTAL_CREDITS": summary.get("TOTAL_CREDITS")
        }
    })


def _extract_summary(run_start: datetime):
    """Extract summary data from pipeline results produced by this run.

    Args:
        run_start: Datetime captured immediately before subprocess.run so that
                   only files written during (or after) this run are considered.
                   This prevents returning stale results from a previous run.
    """
    run_start_ts = run_start.timestamp()

    # Try to read from a results JSON written during this run
    results_files = [
        p for p in LOGS_DIR.glob("results_*.json")
        if p.stat().st_mtime >= run_start_ts
    ]
    if results_files:
        latest = max(results_files, key=lambda p: p.stat().st_mtime)
        try:
            data = json.loads(latest.read_text(encoding="utf-8"))
            results = data.get("results", {})
            return {
                "NDVI_MEAN": results.get("ndvi_stats", {}).get("mean"),
                "NDWI_MEAN": results.get("ndwi_stats", {}).get("mean"),
                "TOTAL_AREA": results.get("carbon", {}).get("total_area_ha"),
                "TOTAL_CREDITS": results.get("carbon", {}).get("credits_issued"),
                "STATUS": results.get("eligibility", {}).get("status"),
                "TIME_PERIOD": results.get("project", {}).get("time_period"),
            }
        except Exception:
            pass

    # Fallback: parse the text report only if it was written during this run
    report_path = OUTPUTS_DIR / "carbon_credit_report.txt"
    if report_path.exists() and report_path.stat().st_mtime >= run_start_ts:
        return _parse_report(report_path.read_text(encoding="utf-8"))

    # Default failed response — nothing from this run was found
    return {
        "NDVI_MEAN": None,
        "NDWI_MEAN": None,
        "TOTAL_AREA": None,
        "TOTAL_CREDITS": None,
        "STATUS": "FAILED",
        "TIME_PERIOD": None,
    }


def _parse_report(text):
    """Parse carbon credit report text to extract summary values."""
    summary = {
        "NDVI_MEAN": None,
        "NDWI_MEAN": None,
        "TOTAL_AREA": None,
        "TOTAL_CREDITS": None,
        "STATUS": None,
        "TIME_PERIOD": None,
    }

    lines = [ln.strip() for ln in text.splitlines()]
    for i, line in enumerate(lines):
        # Look for mean values after NDVI/NDWI Statistics headers
        if line == "NDVI Statistics:" and i + 1 < len(lines):
            for j in range(i + 1, min(i + 10, len(lines))):
                if lines[j].startswith("mean:"):
                    try:
                        summary["NDVI_MEAN"] = float(lines[j].split("mean:")[1].strip())
                    except ValueError:
                        pass
                    break

        if line == "NDWI Statistics:" and i + 1 < len(lines):
            for j in range(i + 1, min(i + 10, len(lines))):
                if lines[j].startswith("mean:"):
                    try:
                        summary["NDWI_MEAN"] = float(lines[j].split("mean:")[1].strip())
                    except ValueError:
                        pass
                    break

        if line.startswith("Total Area:"):
            try:
                summary["TOTAL_AREA"] = float(line.split(":")[1].split("hectares")[0].strip())
            except ValueError:
                pass

        if line.startswith("Credits Issued:"):
            try:
                summary["TOTAL_CREDITS"] = int(line.split(":")[1].strip())
            except ValueError:
                pass

        if line.startswith("Status:"):
            summary["STATUS"] = line.split(":")[1].strip()

        if line.startswith("Time Period:"):
            summary["TIME_PERIOD"] = line.split(":")[1].strip()

    return summary


if __name__ == "__main__":
    print("Starting BlueLedger API on http://0.0.0.0:8000")
    print("Endpoints:")
    print("  GET  /health - Health check")
    print("  POST /run    - Submit GeoJSON and run pipeline")
    app.run(host="0.0.0.0", port=8000, debug=False)
