from metrics_helper import getAllMetricDetails, START_TIME, END_TIME
from screenshot_helper import save_all_widgets_for_all_regions

# Hardcoded configuration: set to True to collect 'perf' metadata and write under perf/ directories
IS_PERF = False

# Optional: hardcoded services/regions can be added here if needed in future
# SERVICES = ["SRA", "SRM"]

def main(is_perf: bool = IS_PERF):
    # Collect metrics + logs for both SRA and SRM services across all regions
    print(f"Starting data collection for SRA and SRM services... (is_perf={is_perf})")
    getAllMetricDetails(is_perf=is_perf)

    # Capture screenshots for every service and region dashboard into service-specific folders
    print("Starting screenshot collection for SRA and SRM services...")
    save_all_widgets_for_all_regions(start_time=START_TIME, end_time=END_TIME, is_perf=is_perf)

    print("Data collection complete for both services!")

if __name__ == "__main__":
    main()