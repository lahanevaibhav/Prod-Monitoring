
import logging
import boto3
from datetime import datetime
from dashboard_helper import get_dashboard_data

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
START_TIME = datetime(2025, 8, 24)
END_TIME = datetime(2025, 8, 26)

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
    print(f"\n{query['Id']}")
    print(f"Errors Count: {errorCount}")
    print(f"Errors Dictionary: {errorsDict}")
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
    for metric_type, info in METRIC_TYPES.items():
        print(f"Metrics for {info['name']}")
        threshold = 0 if info["type"] == "Error" else 500
        statType = "Sum" if info["type"] == "Error" else "Average"
        for metricName in getMetricsList(info["name"]):
            query = get_metric_query(metricName, statType)
            get_metrics_with_threshold(threshold, query)
        print()
