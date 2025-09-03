from metrics_helper import *
from dashboard_helper import *

DASHBOARD_NAME = "test-SRM-Dashboard"

def main():
    # dashboard_data = get_dashboard_data(DASHBOARD_NAME)
    # print("Dashboard Data:", dashboard_data)

    errors_dict = getAllMetricDetails()

    # Save metric widget images for each metric
    from screenshot_helper import save_metric_widget_image
    dashboard_data = get_dashboard_data(DASHBOARD_NAME)
    from metrics_helper import METRIC_TYPES, START_TIME, END_TIME
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