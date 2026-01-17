import logging
import boto3
import os
from datetime import datetime
import json

from csv_helper import save_metrics_group_to_csv, OUTPUT_ROOT
from log_helper import collect_error_logs
from config import SERVICES_METADATA, SERVICES_METADATA_PERF, PERIOD


logging.basicConfig(level=logging.INFO)

def get_metric_types(service_name):
    """Generate metric type definitions for a given service (SRA or SRM)."""
    return {
        "internalErrors": {"name": f"{service_name} MS Errors", "type": "Error"},
        "externalErrors": {"name": "External APis Errors", "type": "Error"},
        "internalPerformance": {"name": f"{service_name} performance in MS", "type": "Performance"},
        "externalPerformance": {"name": "External APIs performance in MS", "type": "Performance"},
        "cpuUsage": {"name": "Max CPU and Memory", "type": "gauge"},
    }

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
    """Extract full metric definitions from a dashboard widget by title.

    Returns a list of metric definitions, where each definition is the full metric array
    from the dashboard (e.g., ["AWS/ECS", "CPUUtilization", "ServiceName", "...", ...])
    """
    for widget in dashboard_body["widgets"]:
        if widget["properties"].get("title") == title:
            return widget["properties"].get("metrics", [])
    return []


def get_metric_query(metric_def, statType):
    """Build a CloudWatch metric query from a dashboard metric definition.

    Args:
        metric_def: Full metric array from dashboard, e.g.:
            ["AWS/ECS", "CPUUtilization", "ServiceName", "wfm-...", "ClusterName", "..."]
            or ["namespace", "MetricName", "DimKey", "DimValue", ...]
        statType: The statistic type (e.g., "Maximum", "Sum", "Average")

    Returns:
        A CloudWatch MetricDataQuery dict
    """
    # Parse the metric definition array
    namespace = metric_def[0]
    metric_name = metric_def[1]

    # Build dimensions from the remaining key-value pairs
    dimensions = []
    i = 2
    while i < len(metric_def) - 1:
        dim_key = metric_def[i]
        dim_value = metric_def[i + 1]
        # Skip placeholder values like "."
        if dim_key != "." and dim_value != ".":
            dimensions.append({"Name": dim_key, "Value": dim_value})
        i += 2

    # Generate a unique ID for this metric
    metric_id = "".join(metric_name.split()).lower().replace(".", "_").replace("-", "_")

    return {
        "Id": metric_id,
        "MetricStat": {
            "Metric": {
                "Namespace": namespace,
                "MetricName": metric_name,
                "Dimensions": dimensions
            },
            "Period": PERIOD,
            "Stat": statType,
        },
        "ReturnData": True
    }


def process_metric_type(cw_client, dashboard_body, metric_type_key, metric_type_meta, start_time, end_time):
    """Process a single metric type for a region and return collected data."""
    # Determine threshold and stat type based on metric name
    metric_name = metric_type_meta["name"]
    if "Error" in metric_name:
        threshold = 0
        statType = "Sum"
    elif "CPU" in metric_name or "Memory" in metric_name:
        # For CPU and Memory, threshold is 70%
        threshold = 70
        statType = "Maximum"
    else:
        # For Performance metrics, threshold is 500ms
        threshold = 500
        statType = "Average"

    group_data = []
    for metric_def in getMetricsList(dashboard_body, metric_type_meta["name"]):
        # Extract the metric name for labeling (it's the second element)
        metric_name = metric_def[1]

        # Build query with the full metric definition
        query = get_metric_query(metric_def, statType)
        _count, errorsDict = get_metrics_with_threshold(cw_client, threshold, query, start_time, end_time)
        for timestamp, value in errorsDict.items():
            group_data.append({"metric": metric_name, "timestamp": timestamp, "value": value})
    return group_data


def collect_metrics_data_for_region(region_code, dashboard_name, region_name, log_group, start_time, end_time, service_name, metric_types, is_perf: bool = False):
    """Collect metrics & logs for a single region and save in service-specific region subfolder.

    Data will be written under `output/prod/<service>/<region>/` or `output/perf/<service>/<region>/`.
    """
    top_dir = "perf" if is_perf else "prod"
    region_rel_folder = os.path.join(top_dir, service_name, region_code)
    region_folder = os.path.join(OUTPUT_ROOT, region_rel_folder)
    os.makedirs(region_folder, exist_ok=True)

    print(f"Collecting {service_name} for region {region_code} (dashboard={dashboard_name}, aws_region={region_name}) into {region_folder}")
    dashboard_body = get_dashboard(dashboard_name, region_name)
    cw_client = make_cloudwatch_client(region_name)
    for metric_type_key, meta in metric_types.items():
        group_data = process_metric_type(cw_client, dashboard_body, metric_type_key, meta, start_time, end_time)
        save_metrics_group_to_csv(meta['name'], group_data, region=region_rel_folder)
    # Collect logs
    collect_error_logs(log_group, start_time, end_time, region_rel_folder, region=region_name, max_entries=10000, max_iterations=100)


def getAllMetricDetails(start_time: datetime | None = None, end_time: datetime | None = None, regions: list | None = None, services: list | None = None, is_perf: bool = False):
    """Collect metrics & logs for all (or selected) services and regions.

    Args:
        start_time: Start time for metric & log collection.
        end_time: End time.
        regions: Optional list of region codes to restrict collection.
        services: Optional list of service names (SRA, SRM) to restrict collection.
        is_perf: If True, use the PERf-specific metadata and write under `perf/` top-level folder.
    """
    if start_time is None or end_time is None:
        raise ValueError("start_time and end_time must be provided (configured in main.py)")

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
