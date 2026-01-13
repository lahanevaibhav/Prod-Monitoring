from datetime import datetime, timedelta

from metrics_helper import getAllMetricDetails
from screenshot_helper import save_all_widgets_for_all_regions

# Hardcoded configuration: set to True to collect 'perf' metadata and write under perf/ directories
IS_PERF = False

# # Use this for manual testing with fixed dates
# START_TIME = datetime(2025, 12, 7, 0, 0, 0)
# END_TIME = datetime(2025, 12, 8, 0, 0, 0)

_now = datetime.now()
_today_start = _now.replace(hour=0, minute=0, second=0, microsecond=0)
START_TIME = _today_start - timedelta(days=3)
END_TIME = _today_start - timedelta(seconds=1)

def main(is_perf: bool = IS_PERF):
    # Collect metrics + logs for both SRA and SRM services across all regions
    print(f"Starting data collection for SRA and SRM services... (is_perf={is_perf})")
    getAllMetricDetails(start_time=START_TIME, end_time=END_TIME, is_perf=is_perf)

    # Capture screenshots for every service and region dashboard into service-specific folders
    print("Starting screenshot collection for SRA and SRM services...")
    save_all_widgets_for_all_regions(start_time=START_TIME, end_time=END_TIME, is_perf=is_perf)

    print("Data collection complete for both services!")

if __name__ == "__main__":
    main()