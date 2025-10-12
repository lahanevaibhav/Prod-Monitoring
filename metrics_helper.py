import logging
import boto3
from datetime import datetime
from dashboard_helper import get_dashboard_data
import json
from csv_helper import save_metrics_group_to_csv
from log_helper import collect_error_logs


METRIC_TYPES = {
    "internalErrors": {"name": "SRA MS Errors", "type": "Error"},
    "externalErrors": {"name": "External APis Errors", "type": "Error"},
    "internalPerformance": {"name": "SRA performance in MS", "type": "Performance"},
    "externalPerformance": {"name": "External APIs performance in MS", "type": "Performance"}
}

logging.basicConfig(level=logging.INFO)

# Region metadata: region_code -> (dashboard_name, aws_region, log_group)
METRICS_METADATA_SRA = {
    "NA1": ("production-SRA-Dashboard", "us-west-2", "production-schedule-rules-automation"),
    "AU": ("production-au-SRA-Dashboard", "ap-southeast-2", "production-au-schedule-rules-automation"),
    "CA": ("production-ca-SRA-Dashboard", "ca-central-1", "production-ca-schedule-rules-automation"),
    "JP": ("production-jp-SRA-Dashboard", "ap-northeast-1", "production-jp-schedule-rules-automation"),
    "DE": ("production-de-SRA-Dashboard", "eu-central-1", "production-de-schedule-rules-automation"),
    "UK": ("production-uk-SRA-Dashboard", "eu-west-2", "production-uk-schedule-rules-automation")
}

# Default time range; can be overridden per call
START_TIME = datetime(2025, 10, 10)
END_TIME = datetime(2025, 10, 11)

PERIOD = 60

def make_cloudwatch_client(region_name: str):
    return boto3.client("cloudwatch", region_name=region_name)

def get_dashboard(region_dashboard: str, region_name: str):
    cw = make_cloudwatch_client(region_name)
    response = cw.get_dashboard(DashboardName=region_dashboard)
    return json.loads(response["DashboardBody"])

def get_metrics_data(cw_client, metric_query, start_time, end_time):
    response = cw_client.get_metric_data(
        MetricDataQueries=[metric_query],
        StartTime=start_time,
        EndTime=end_time,
        ScanBy="TimestampAscending",
        LabelOptions={"Timezone": "+0530"}
    )
    return response['MetricDataResults']

def get_metrics_with_threshold(cw_client, threshold, query, start_time, end_time):
    metricsData = get_metrics_data(cw_client, query, start_time, end_time)
    errorsDict = {}
    errorCount = 0
    for idx, value in enumerate(metricsData[0]["Values"]):
        if value > threshold:
            errorCount += value
            errorsDict[metricsData[0]["Timestamps"][idx].isoformat()] = value
    # CSV saving removed; handled in getAllMetricDetails
    return errorCount, errorsDict

def getMetricsList(dashboard_body, title):
    for widget in dashboard_body["widgets"]:
        if widget["properties"].get("title") == title:
            return [metric[1] for metric in widget["properties"].get("metrics", [])]
    return []

def get_metric_query(metricName, statType, namespace):
    return {
        "Id": "".join(metricName.split()).lower().replace(".", "_").replace("-", "_"),
        "MetricStat": {
            "Metric": {
                "Namespace": namespace,
                "MetricName": metricName,
                "Dimensions": [{"Name": "type", "Value": "gauge"}]
            },
            "Period": PERIOD,
            "Stat": statType,
        },
        "ReturnData": True
    }

def process_metric_type(cw_client, dashboard_body, metric_type_key, metric_type_meta, namespace, start_time, end_time):
    """Process a single metric type for a region and return collected data."""
    threshold = 0 if metric_type_meta["type"] == "Error" else 500
    statType = "Sum" if metric_type_meta["type"] == "Error" else "Average"
    group_data = []
    for metricName in getMetricsList(dashboard_body, metric_type_meta["name"]):
        query = get_metric_query(metricName, statType, namespace)
        _count, errorsDict = get_metrics_with_threshold(cw_client, threshold, query, start_time, end_time)
        for timestamp, value in errorsDict.items():
            group_data.append({"metric": metricName, "timestamp": timestamp, "value": value})
    return group_data

def collect_metrics_data_for_region(region_code, dashboard_name, region_name, log_group, start_time, end_time):
    """Collect metrics & logs for a single region and save in region subfolder."""
    print(f"Collecting region {region_code} (dashboard={dashboard_name}, aws_region={region_name})")
    dashboard_body = get_dashboard(dashboard_name, region_name)
    cw_client = make_cloudwatch_client(region_name)
    namespace = f"production-{region_code.lower()}.service.metrics"  # Could vary per region if needed
    if region_code == "NA1":
        namespace = "production.service.metrics"
    for metric_type_key, meta in METRIC_TYPES.items():
        group_data = process_metric_type(cw_client, dashboard_body, metric_type_key, meta, namespace, start_time, end_time)
        save_metrics_group_to_csv(meta['name'], group_data, region=region_code)
    # Collect logs
    collect_error_logs(log_group, start_time, end_time, region_code,region=region_name, max_entries=10000, max_iterations=100)

def getAllMetricDetails(start_time: datetime = START_TIME, end_time: datetime = END_TIME, regions: list | None = None):
    """Collect metrics & logs for all (or selected) regions defined in METRICS_METADATA_SRA.

    Args:
        start_time: Start time for metric & log collection.
        end_time: End time.
        regions: Optional list of region codes to restrict collection.
    """
    selected = regions if regions else METRICS_METADATA_SRA.keys()
    for region_code in selected:
        if region_code not in METRICS_METADATA_SRA:
            logging.warning(f"Region code {region_code} not defined in METRICS_METADATA_SRA; skipping")
            continue
        dashboard_name, aws_region, log_group = METRICS_METADATA_SRA[region_code]
        collect_metrics_data_for_region(region_code, dashboard_name, aws_region, log_group, start_time, end_time)
