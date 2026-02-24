#!/usr/bin/env python3
"""
Main entry point for Carbon Credit Calculation System
"""

import argparse
import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from carbon_credit_pipeline import CarbonCreditPipeline


def check_environment():
    required_vars = ["SENTINEL_HUB_CLIENT_ID", "SENTINEL_HUB_CLIENT_SECRET"]
    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        print("ERROR: Missing required environment variables:")
        for var in missing:
            print(f"  - {var}")
        print("\nPlease set them before running:")
        print("  export SENTINEL_HUB_CLIENT_ID='your-client-id'")
        print("  export SENTINEL_HUB_CLIENT_SECRET='your-client-secret'")
        print()
        return False

    return True


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Calculate carbon credits from satellite imagery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default config.yaml
  python main.py

  # Run with custom config
  python main.py --config my_config.yaml
        """,
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)",
    )

    parser.add_argument(
        "--skip-env-check",
        action="store_true",
        help="Skip environment variable check (use with caution)",
    )

    args = parser.parse_args()

    # Check environment
    if not args.skip_env_check:
        if not check_environment():
            sys.exit(1)

    # Check if config exists
    if not Path(args.config).exists():
        print(f"ERROR: Configuration file not found: {args.config}")
        sys.exit(1)

    # Run pipeline
    try:
        print("Initializing Carbon Credit Calculation Pipeline...")
        print(f"Using configuration: {args.config}\n")

        pipeline = CarbonCreditPipeline(config_path=args.config)
        results = pipeline.run()

        print("\n" + "=" * 80)
        print("SUCCESS!")
        print("=" * 80)
        print("\nFinal Results:")
        print(f"  Status: {results['eligibility']['status']}")
        print(f"  Total Area: {results['carbon']['total_area_ha']:.2f} hectares")
        print(f"  Total CO2e: {results['carbon']['total_co2e']:.2f} tonnes")
        print(f"  Credits Issued: {results['carbon']['credits_issued']}")
        print(f"\nOutputs saved to: {Path(args.config).parent / 'outputs'}")
        print(f"Logs saved to: {Path(args.config).parent / 'logs'}")
        print()

        return 0

    except KeyboardInterrupt:
        print("\n\nPipeline interrupted by user")
        return 130

    except Exception as e:
        print(f"\n\nERROR: Pipeline failed: {str(e)}")
        print("\nCheck the log files for detailed error information.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
