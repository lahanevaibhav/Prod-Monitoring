from dashboard_helper import get_dashboard_data
import boto3
import json
from datetime import datetime, timedelta
import logging

METRIC_TYPES = {
    "internalErrors": {"name": "SRA MS Errors", "type": "Error"},
    "externalErrors": {"name": "External APis Errors", "type": "Error"},
    "internalPerformance": {"name": "SRA performance in MS", "type": "Performance"},
    "externalPerformance": {"name": "External APIs performance in MS", "type": "Performance"}
}

logging.basicConfig(level=logging.INFO)

cloudWatchClient = boto3.client("cloudwatch")

sraDashboardResponse = get_dashboard_data("test-SRA-Dashboard")


def get_metrics_data(metric_query):
    response = cloudWatchClient.get_metric_data(
        MetricDataQueries=[metric_query],
        StartTime=START_TIME,
        EndTime=END_TIME,
        ScanBy="TimestampAscending",
        LabelOptions={
        "Timezone": "+0530"
        }
    )
    return response['MetricDataResults']

def get_metrics_with_threshold(threshold, query):
    """
        This function returns the metrics which crosses threshold
        :threshold - 0 for errors and 500 for performance
    """

    metricsData = get_metrics_data(query)
    errorsDict = dict()
    errorCount = 0

    for index in range(len(metricsData[0]["Values"])):
        if metricsData[0]["Values"][index] > threshold:
            errorCount += metricsData[0]["Values"][index]
            errorsDict[metricsData[0]["Timestamps"][index].isoformat()] = metricsData[0]["Values"][index]
    
    # if(errorCount > threshold):
    print("\n")
    print(query["Id"])
    print("Errors Count:", errorCount)
    print("Errors Dictionary:", errorsDict)
    return errorCount, errorsDict


def getMetricsList(title):
    metricsList = []
    for widget in sraDashboardResponse["widgets"]:
        if widget["properties"]["title"] != title:
            continue

        metrics = widget["properties"]["metrics"]

        metricsList = list(metric[1] for metric in metrics)
            
    return metricsList


NAMESPACE = "test.service.metrics"
REGION = "us-west-2"
PERIOD = 60
START_TIME = datetime(2025, 8, 24)
END_TIME = datetime(2025, 8, 26)


def get_metric_query(metricName, statType):
    return {
        "Id": "".join(metricName.split()).lower().replace(".", "_").replace("-", "_"),
        "MetricStat": {
            "Metric": {
                "Namespace": NAMESPACE,
                "MetricName": metricName,
                "Dimensions": [
                    {
                        "Name": "type",
                        "Value": "gauge"
                    },
                ]
            },
            "Period": PERIOD,
            "Stat": statType,
        },
        "ReturnData": True
    }

def getAllMetricDetails():
    for metric_type in METRIC_TYPES.keys():
        print(f"Metrics for {METRIC_TYPES[metric_type]["name"]}")

        if METRIC_TYPES[metric_type]["type"] == "Error":
            threshold = 0
            statType = "Sum"
        else:
            threshold = 500
            statType = "Average"

        for metricName in getMetricsList(METRIC_TYPES[metric_type]["name"]):
            query = get_metric_query(metricName, statType)
            get_metrics_with_threshold(threshold, query)

        print("\n")
