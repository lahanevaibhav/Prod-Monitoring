import logging
import boto3
import os
from datetime import datetime
import json
from csv_helper import save_metrics_group_to_csv
from log_helper import collect_error_logs


logging.basicConfig(level=logging.INFO)

def get_metric_types(service_name):
    """Generate metric type definitions for a given service (SRA or SRM)."""
    return {
        "internalErrors": {"name": f"{service_name} MS Errors", "type": "Error"},
        "externalErrors": {"name": "External APis Errors", "type": "Error"},
        "internalPerformance": {"name": f"{service_name} performance in MS", "type": "Performance"},
        "externalPerformance": {"name": "External APIs performance in MS", "type": "Performance"}
    }

# Region metadata: region_code -> (dashboard_name, aws_region, log_group)
METRICS_METADATA_SRA = {
    "NA1": ("production-SRA-Dashboard", "us-west-2", "production-schedule-rules-automation"),
    "AU": ("production-au-SRA-Dashboard", "ap-southeast-2", "production-au-schedule-rules-automation"),
    "CA": ("production-ca-SRA-Dashboard", "ca-central-1", "production-ca-schedule-rules-automation"),
    "JP": ("production-jp-SRA-Dashboard", "ap-northeast-1", "production-jp-schedule-rules-automation"),
    "DE": ("production-de-SRA-Dashboard", "eu-central-1", "production-de-schedule-rules-automation"),
    "UK": ("production-uk-SRA-Dashboard", "eu-west-2", "production-uk-schedule-rules-automation")
}

METRICS_METADATA_SRM = {
    "NA1": ("production-SRM-Dashboard", "us-west-2", "production-schedule-requests-manager"),
    "AU": ("production-au-SRM-Dashboard", "ap-southeast-2", "production-au-schedule-requests-manager"),
    "CA": ("production-ca-SRM-Dashboard", "ca-central-1", "production-ca-schedule-requests-manager"),
    "JP": ("production-jp-SRM-Dashboard", "ap-northeast-1", "production-jp-schedule-requests-manager"),
    "DE": ("production-de-SRM-Dashboard", "eu-central-1", "production-de-schedule-requests-manager"),
    "UK": ("production-uk-SRM-Dashboard", "eu-west-2", "production-uk-schedule-requests-manager")
}

# New perf-only metadata for SRA and SRM (for now only NA1 is present)
METRICS_METADATA_SRA_PERF = {
    "NA1": ("perf-wcx-SRA-Dashboard", "us-west-2", "perf-wcx-schedule-rules-automation")
}

METRICS_METADATA_SRM_PERF = {
    "NA1": ("perf-wcx-SRM-Dashboard", "us-west-2", "perf-wcx-schedule-requests-manager")
}

# Service metadata mapping (prod)
SERVICES_METADATA = {
    "SRA": METRICS_METADATA_SRA,
    "SRM": METRICS_METADATA_SRM
}

SERVICES_METADATA_PERF = {
    "SRA": METRICS_METADATA_SRA_PERF,
    "SRM": METRICS_METADATA_SRM_PERF
}

# Default time range; can be overridden per call
START_TIME = datetime(2025, 12, 7, 0, 0, 0)
END_TIME = datetime(2025, 12, 8, 0, 0, 0)

PERIOD = 300


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
        ScanBy="TimestampAscending"
        # No LabelOptions - uses local timezone by default
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


def collect_metrics_data_for_region(region_code, dashboard_name, region_name, log_group, start_time, end_time, service_name, metric_types, is_perf: bool = False):
    """Collect metrics & logs for a single region and save in service-specific region subfolder.

    Data will be written under either `prod/<service>/<region>/` or `perf/<service>/<region>/` depending on `is_perf`.
    """
    top_dir = "perf" if is_perf else "prod"
    region_folder = os.path.join(top_dir, service_name, region_code)
    os.makedirs(region_folder, exist_ok=True)

    print(f"Collecting {service_name} for region {region_code} (dashboard={dashboard_name}, aws_region={region_name}) into {region_folder}")
    dashboard_body = get_dashboard(dashboard_name, region_name)
    cw_client = make_cloudwatch_client(region_name)
    namespace = f"production-{region_code.lower()}.service.metrics"  # Could vary per region if needed
    if region_code == "NA1":
        namespace = "production.service.metrics"
    for metric_type_key, meta in metric_types.items():
        group_data = process_metric_type(cw_client, dashboard_body, metric_type_key, meta, namespace, start_time, end_time)
        save_metrics_group_to_csv(meta['name'], group_data, region=region_folder)
    # Collect logs
    collect_error_logs(log_group, start_time, end_time, region_folder, region=region_name, max_entries=10000, max_iterations=100)


def getAllMetricDetails(start_time: datetime = START_TIME, end_time: datetime = END_TIME, regions: list | None = None, services: list | None = None, is_perf: bool = False):
    """Collect metrics & logs for all (or selected) services and regions.

    Args:
        start_time: Start time for metric & log collection.
        end_time: End time.
        regions: Optional list of region codes to restrict collection.
        services: Optional list of service names (SRA, SRM) to restrict collection.
        is_perf: If True, use the PERf-specific metadata and write under `perf/` top-level folder.
    """
    # Decide default services based on whether this is a perf run or prod run
    if services:
        selected_services = services
    else:
        selected_services = SERVICES_METADATA_PERF.keys() if is_perf else SERVICES_METADATA.keys()

    for service_name in selected_services:
        # Use the appropriate metadata mapping for validation and lookup
        metadata_map = SERVICES_METADATA_PERF if is_perf else SERVICES_METADATA
        if service_name not in metadata_map:
            logging.warning(f"Service {service_name} not defined in {'SERVICES_METADATA_PERF' if is_perf else 'SERVICES_METADATA'}; skipping")
            continue

        # Choose metadata for the selected service from the appropriate map
        metadata = metadata_map[service_name]

        metric_types = get_metric_types(service_name)
        selected_regions = regions if regions else metadata.keys()

        for region_code in selected_regions:
            if region_code not in metadata:
                logging.warning(f"Region code {region_code} not defined for service {service_name}; skipping")
                continue
            dashboard_name, aws_region, log_group = metadata[region_code]
            collect_metrics_data_for_region(region_code, dashboard_name, aws_region, log_group, start_time, end_time, service_name, metric_types, is_perf=is_perf)
