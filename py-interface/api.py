"""
Simple Flask API for BlueLedger Carbon Credit Pipeline.

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
    Accept GeoJSON input, run the carbon credit pipeline, and return results.

    Returns:
        - log_file: Path to API execution log
        - carbon_credit_report: Path to the generated report
        - summary: JSON with NDVI_MEAN, NDWI_MEAN, TOTAL_AREA, TOTAL_CREDITS, STATUS, TIME_PERIOD
    """
    # 1. Validate and save GeoJSON input
    try:
        geojson = request.get_json(force=True)
        if not isinstance(geojson, dict) or "type" not in geojson:
            return jsonify({"error": "Invalid GeoJSON: must have 'type' field"}), 400
    except Exception as e:
        return jsonify({"error": f"Invalid JSON: {str(e)}"}), 400

    # Save as aoi.geojson
    AOI_PATH.write_text(json.dumps(geojson, indent=2), encoding="utf-8")

    # 2. Create directories and run main.py
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOGS_DIR / f"api_run_{timestamp}.log"

    proc = subprocess.run(
        [sys.executable, "main.py"],
        cwd=str(BASE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )

    # Save log
    log_file.write_text(proc.stdout or "", encoding="utf-8")

    # 3. Build summary JSON from results
    summary = _extract_summary()

    # Save summary.json
    summary_path = OUTPUTS_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # 4. Return response
    report_path = OUTPUTS_DIR / "carbon_credit_report.txt"

    return jsonify(
        {
            "success": proc.returncode == 0,
            "exit_code": proc.returncode,
            "files": {
                "log_file": str(log_file),
                "carbon_credit_report": (
                    str(report_path) if report_path.exists() else None
                ),
                "summary_json": str(summary_path),
            },
            "summary": summary,
        }
    )


def _extract_summary():
    """Extract summary data from pipeline results."""
    # Try to read from results JSON first
    results_files = list(LOGS_DIR.glob("results_*.json"))
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

    # Fallback: parse the text report
    report_path = OUTPUTS_DIR / "carbon_credit_report.txt"
    if report_path.exists():
        return _parse_report(report_path.read_text(encoding="utf-8"))

    # Default failed response
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
                summary["TOTAL_AREA"] = float(
                    line.split(":")[1].split("hectares")[0].strip()
                )
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
