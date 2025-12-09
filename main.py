
from metrics_helper import getAllMetricDetails, START_TIME, END_TIME
from screenshot_helper import save_all_widgets_for_all_regions

def main():
    # Collect metrics + logs for both SRA and SRM services across all regions
    print("Starting data collection for SRA and SRM services...")
    getAllMetricDetails()

    # Capture screenshots for every service and region dashboard into service-specific folders
    print("Starting screenshot collection for SRA and SRM services...")
    save_all_widgets_for_all_regions(start_time=START_TIME, end_time=END_TIME)

    print("Data collection complete for both services!")

if __name__ == "__main__":
    main()