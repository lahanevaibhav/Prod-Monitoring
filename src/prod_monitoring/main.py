from datetime import datetime, timedelta

from metrics_helper import getAllMetricDetails
from screenshot_helper import save_all_widgets_for_all_regions
from rds_helper import collect_all_rds_metrics
from config import METRICS_METADATA_RDS, METRICS_METADATA_RDS_PERF

# Hardcoded configuration: set to True to collect 'perf' metadata and write under perf/ directories
IS_PERF = False

# # Use this for manual testing with fixed dates
# START_TIME = datetime(2025, 12, 7, 0, 0, 0)
# END_TIME = datetime(2025, 12, 8, 0, 0, 0)

_now = datetime.now()
_today_start = _now.replace(hour=0, minute=0, second=0, microsecond=0)
START_TIME = _today_start - timedelta(days=2)
END_TIME = _today_start - timedelta(seconds=1)

def main(is_perf: bool = IS_PERF):
    # Collect metrics + logs for both SRA and SRM services across all regions
    print(f"Starting data collection for SRA and SRM services... (is_perf={is_perf})")
    getAllMetricDetails(start_time=START_TIME, end_time=END_TIME, is_perf=is_perf)

    # Capture screenshots for every service and region dashboard into service-specific folders
    print("Starting screenshot collection for SRA and SRM services...")
    save_all_widgets_for_all_regions(start_time=START_TIME, end_time=END_TIME, is_perf=is_perf)

    # Collect RDS metrics for all configured regions
    rds_metadata = METRICS_METADATA_RDS_PERF if is_perf else METRICS_METADATA_RDS
    if rds_metadata:
        print("Starting RDS metrics collection...")
        collect_all_rds_metrics(start_time=START_TIME, end_time=END_TIME,
                               rds_metadata=rds_metadata, is_perf=is_perf)
    else:
        print("Skipping RDS metrics collection (no RDS instances configured)")
        print("  To enable: Run 'python discover_rds_instances.py' to find your RDS instances")
        print("  Then update config.py with your RDS instance identifiers")

    print("Data collection complete for all services (SRA, SRM, and RDS)!")

if __name__ == "__main__":
    main()