from metrics_helper import *
from dashboard_helper import *

DASHBOARD_NAME = "test-SRM-Dashboard"

def main():
    # dashboard_data = get_dashboard_data(DASHBOARD_NAME)
    # print("Dashboard Data:", dashboard_data)

    errors_dict = getAllMetricDetails()

if __name__ == "__main__":
    main()