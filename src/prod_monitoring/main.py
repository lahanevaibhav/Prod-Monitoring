from datetime import datetime, timedelta

from src.prod_monitoring import consolidate_monitoring_data
from src.prod_monitoring.unified_config import (
    GENERATE_PDF_REPORT,
    KEEP_INDIVIDUAL_CSVS,
    IS_PERFORMANCE_MODE,
    START_DAYS_BACK,
    END_DAYS_BACK,
    ENABLE_SRA,
    ENABLE_SRM,
    ENABLE_SCREENSHOTS
)
from .metrics_helper import getAllMetricDetails
from .screenshot_helper import save_all_widgets_for_all_regions

# Calculate time range based on configuration
_now = datetime.now()
_today_start = _now.replace(hour=0, minute=0, second=0, microsecond=0)
START_TIME = _today_start - timedelta(days=START_DAYS_BACK)
END_TIME = _today_start - timedelta(days=END_DAYS_BACK, seconds=-1)

def main(is_perf: bool = None):
    """
    Main entry point for production monitoring data collection.

    Args:
        is_perf: Override performance mode setting from config (optional)
    """
    # Use config setting if not explicitly provided
    if is_perf is None:
        is_perf = IS_PERFORMANCE_MODE

    env_name = "Performance" if is_perf else "Production"

    print("=" * 80)
    print(f">> Starting {env_name} Monitoring Data Collection")
    print("=" * 80)
    print(f"Time Range: {START_TIME} to {END_TIME}")
    print(f"Services: SRA={ENABLE_SRA}, SRM={ENABLE_SRM}")
    print(f"Screenshots: {ENABLE_SCREENSHOTS}")
    print("=" * 80 + "\n")

    # Validate AWS credentials before starting
    print(">> Validating AWS credentials...")
    from .aws_profile_manager import get_profile_manager

    profile_mgr = get_profile_manager()

    # Validate data access credentials
    if not profile_mgr.validate_credentials(profile_mgr.DATA_PROFILE):
        print("\n" + "=" * 80)
        print("ERROR: AWS CREDENTIALS ERROR")
        print("=" * 80)
        print("\nYour AWS credentials have expired or are invalid.")
        print("\nTo fix this issue:")
        print("\n1. Refresh credentials using PowerShell script")
        print("\n2. Or manually configure:")
        print("   aws configure")
        print("\n3. Verify credentials with:")
        print("   aws sts get-caller-identity")
        print("=" * 80)
        return

    print("SUCCESS: AWS credentials validated successfully\n")

    # Collect metrics + logs for both SRA and SRM services across all regions
    services_to_collect = []
    if ENABLE_SRA:
        services_to_collect.append("SRA")
    if ENABLE_SRM:
        services_to_collect.append("SRM")

    if services_to_collect:
        print(f">> Collecting metrics and logs for: {', '.join(services_to_collect)}")
        getAllMetricDetails(
            start_time=START_TIME,
            end_time=END_TIME,
            is_perf=is_perf,
            services=services_to_collect
        )
    else:
        print("WARNING: No services enabled for collection")

    # Capture screenshots for every service and region dashboard
    if ENABLE_SCREENSHOTS and services_to_collect:
        print(f"\n>> Capturing dashboard screenshots for: {', '.join(services_to_collect)}")
        save_all_widgets_for_all_regions(
            start_time=START_TIME,
            end_time=END_TIME,
            is_perf=is_perf
        )
    elif not ENABLE_SCREENSHOTS:
        print("\nINFO: Screenshots disabled in config.ini")

    # Generate consolidated report
    print("\n" + "=" * 80)
    print(f"SUCCESS: {env_name} monitoring data collection complete!")
    print("=" * 80)

    env = "perf" if is_perf else "prod"
    print(f"\n>> Generating consolidated report for {env.upper()} environment...")

    # Initialize variables
    json_path = None
    md_path = None
    pdf_path = None

    try:
        json_path, md_path, pdf_path = consolidate_monitoring_data(
            environment=env,
            save_json=True,
            save_markdown=True,
            save_pdf=GENERATE_PDF_REPORT,
            cleanup=not KEEP_INDIVIDUAL_CSVS
        )
    except Exception as e:
        print(f"WARNING: Failed to generate consolidated report: {e}")
        print("   Individual service reports are still available.")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print(">> Output Summary")
    print("=" * 80)
    print(f">> Output location: output/{env}/")
    print("\nWhat you have:")

    if pdf_path:
        print(f"   [+] MAIN REPORT (PDF): monitoring_report_{env}_*.pdf")
        print(f"       >> Open this file first for complete overview")

    if md_path:
        print(f"   [+] Markdown Report: consolidated_monitoring_{env}_*.md")

    if json_path:
        print(f"   [+] JSON Data: consolidated_monitoring_{env}_*.json")

    if KEEP_INDIVIDUAL_CSVS:
        print(f"   [+] Individual service folders (SRA, SRM, RDS) with CSV data")
        print(f"   [+] Screenshots in each region's screenshots/ folder")
    else:
        print(f"   [i] Individual CSV files removed (consolidated data only)")
        print(f"   [+] Screenshots preserved in screenshots/ folders")

    print("\nQuick Start:")
    if pdf_path:
        print(f"   1. Open the PDF report for complete analysis")
        print(f"   2. Review AI analysis sections for insights")
        print(f"   3. Check executive summary for critical issues")
    else:
        print(f"   1. Open the Markdown report for quick overview")
        print(f"   2. Read AI analysis sections for insights")
        print(f"   3. Check the JSON file for programmatic access")
    print("=" * 80)

if __name__ == "__main__":
    main()