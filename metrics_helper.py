import logging
import boto3
from datetime import datetime
from dashboard_helper import get_dashboard_data
from csv_helper import save_metrics_group_to_csv
from log_helper import collect_error_logs


METRIC_TYPES = {
    "internalErrors": {"name": "SRA MS Errors", "type": "Error"},
    "externalErrors": {"name": "External APis Errors", "type": "Error"},
    "internalPerformance": {"name": "SRA performance in MS", "type": "Performance"},
    "externalPerformance": {"name": "External APIs performance in MS", "type": "Performance"}
}

logging.basicConfig(level=logging.INFO)
cloudWatchClient = boto3.client("cloudwatch")
sraDashboardResponse = get_dashboard_data("production-SRA-Dashboard")

NAMESPACE = "production.service.metrics"
REGION = "us-west-2"
PERIOD = 60
START_TIME = datetime(2025, 9, 10)
END_TIME = datetime(2025, 9, 11)

def get_metrics_data(metric_query):
    response = cloudWatchClient.get_metric_data(
        MetricDataQueries=[metric_query],
        StartTime=START_TIME,
        EndTime=END_TIME,
        ScanBy="TimestampAscending",
        LabelOptions={"Timezone": "+0530"}
    )
    return response['MetricDataResults']

def get_metrics_with_threshold(threshold, query):
    metricsData = get_metrics_data(query)
    errorsDict = {}
    errorCount = 0
    for idx, value in enumerate(metricsData[0]["Values"]):
        if value > threshold:
            errorCount += value
            errorsDict[metricsData[0]["Timestamps"][idx].isoformat()] = value
    # CSV saving removed; handled in getAllMetricDetails
    return errorCount, errorsDict

def getMetricsList(title):
    for widget in sraDashboardResponse["widgets"]:
        if widget["properties"]["title"] == title:
            return [metric[1] for metric in widget["properties"]["metrics"]]
    return []

def get_metric_query(metricName, statType):
    return {
        "Id": "".join(metricName.split()).lower().replace(".", "_").replace("-", "_"),
        "MetricStat": {
            "Metric": {
                "Namespace": NAMESPACE,
                "MetricName": metricName,
                "Dimensions": [{"Name": "type", "Value": "gauge"}]
            },
            "Period": PERIOD,
            "Stat": statType,
        },
        "ReturnData": True
    }

def process_metric_type(metric_type, info):
    """Process a single metric type and return the collected data."""
    threshold = 0 if info["type"] == "Error" else 500
    statType = "Sum" if info["type"] == "Error" else "Average"
    group_data = []
    
    for metricName in getMetricsList(info["name"]):
        query = get_metric_query(metricName, statType)
        errorCount, errorsDict = get_metrics_with_threshold(threshold, query)
        for timestamp, value in errorsDict.items():
            group_data.append({
                "metric": metricName,
                "timestamp": timestamp,
                "value": value
            })
    
    return group_data

def collect_metrics_data():
    """Collect and save metrics data for all metric types."""
    for metric_type, info in METRIC_TYPES.items():
        group_data = process_metric_type(metric_type, info)
        save_metrics_group_to_csv(info['name'], group_data)

def getAllMetricDetails():
    """Main function to collect all metrics and error logs."""
    collect_metrics_data()
    
    # Collect error logs using the log helper
    log_group = "production-schedule-rules-automation"  # TODO: set correct log group
    collect_error_logs(log_group, START_TIME, END_TIME)
