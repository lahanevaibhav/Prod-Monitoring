
from metrics_helper import getAllMetricDetails, START_TIME, END_TIME, METRICS_METADATA_SRA
from screenshot_helper import save_all_widgets_for_all_regions

def main():
    # Collect metrics + logs per region
    getAllMetricDetails()
    # Now capture screenshots for every region dashboard into per-region folders
    save_all_widgets_for_all_regions(start_time=START_TIME, end_time=END_TIME)

if __name__ == "__main__":
    main()