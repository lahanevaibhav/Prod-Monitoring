import logging
import boto3
from datetime import datetime
from dashboard_helper import get_dashboard_data
from csv_helper import save_metrics_group_to_csv


METRIC_TYPES = {
    "internalErrors": {"name": "SRA MS Errors", "type": "Error"},
    "externalErrors": {"name": "External APis Errors", "type": "Error"},
    "internalPerformance": {"name": "SRA performance in MS", "type": "Performance"},
    "externalPerformance": {"name": "External APIs performance in MS", "type": "Performance"}
}

logging.basicConfig(level=logging.INFO)
cloudWatchClient = boto3.client("cloudwatch")
sraDashboardResponse = get_dashboard_data("test-SRA-Dashboard")

NAMESPACE = "test.service.metrics"
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

def getAllMetricDetails():
    from csv_helper import save_metrics_group_to_csv, save_error_logs
    period_label = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Save metrics as before
    for metric_type, info in METRIC_TYPES.items():
        print(f"Metrics for {info['name']}")
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
        save_metrics_group_to_csv(info['name'], group_data)

    # Fetch all error logs for a time window (e.g., last 24 hours)
    logs_client = boto3.client("logs")
    log_group = "test-schedule-rules-automation"  # TODO: set correct log group
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now().timestamp() - 24*60*60) * 1000)  # last 24 hours
    error_log_rows = []
    try:
        response = logs_client.filter_log_events(
            logGroupName=log_group,
            startTime=start_time,
            endTime=end_time,
            filterPattern='ERROR ?Exception -METRICS_AGG',
            limit=1000
        )
        for event in response.get("events", []):
            error_log_rows.append({
                "timestamp": datetime.fromtimestamp(event["timestamp"] / 1000).isoformat(),
                "log_message": event["message"]
            })
    except Exception as e:
        error_log_rows.append({
            "timestamp": datetime.now().isoformat(),
            "log_message": f"Log fetch error: {e}"
        })
    save_error_logs(error_log_rows, period_label)
    print()
