
from metrics_helper import getAllMetricDetails, METRIC_TYPES, START_TIME, END_TIME
from dashboard_helper import get_dashboard_data
from screenshot_helper import save_metric_widget_image

DASHBOARD_NAME = "test-SRM-Dashboard"

def main():
    getAllMetricDetails()
    dashboard_data = get_dashboard_data(DASHBOARD_NAME)
    for widget in dashboard_data.get("widgets", []):
        metric_name = widget["properties"].get("title", "unknown_metric")
        save_metric_widget_image(
            widget,
            metric_name,
            START_TIME,
            END_TIME
        )

if __name__ == "__main__":
    main()