import os
import boto3
import json
from typing import Dict, Iterable

from metrics_helper import SERVICES_METADATA, SERVICES_METADATA_PERF
from dashboard_helper import get_dashboard_data
from csv_helper import OUTPUT_ROOT

ROOT_DIR = os.path.dirname(__file__)
GLOBAL_SCREENSHOTS_DIR = os.path.join(ROOT_DIR, 'screenshots')  # legacy root screenshots (kept for backwards comp.)
os.makedirs(GLOBAL_SCREENSHOTS_DIR, exist_ok=True)
cloudwatch_client = boto3.client("cloudwatch")  # default client (may be reused for NA1 aggregate if desired)


def save_metric_widget_image(widget, metric_name, start_time, end_time, target_dir: str):
    """
    Saves a CloudWatch metric widget image for the given metric and time range into target_dir.
    """
    statType = "Sum" if "Error" in metric_name else "Average"
    metric_widget_json = json.dumps({
        "metrics": widget["properties"]["metrics"],
        "view": "timeSeries",
        "stacked": False,
        "stat": statType,
        "period": 300,
        "region": cloudwatch_client.meta.region_name,
        "title": metric_name,
        "width": 1200,
        "height": 800,
        "start": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
        "end": end_time.strftime("%Y-%m-%dT%H:%M:%S")
    })
    response = cloudwatch_client.get_metric_widget_image(MetricWidget=metric_widget_json)
    os.makedirs(target_dir, exist_ok=True)
    filename = f"{metric_name}.png"
    filepath = os.path.join(target_dir, filename)
    with open(filepath, "wb") as f:
        f.write(response["MetricWidgetImage"])
    print(f"Saved widget image: {filepath}")
    return filepath


def save_all_widgets_for_region(region_code: str, service_name: str = "SRA", start_time=None, end_time=None, is_perf: bool = False):
    """Fetch dashboard for region and service, save screenshots for every widget into service-specific region folder.

    When is_perf=True screenshots are saved under <ROOT>/perf/<service>/<region>/screenshots
    Otherwise under <ROOT>/prod/<service>/<region>/screenshots
    """
    if start_time is None or end_time is None:
        raise ValueError("start_time and end_time must be provided (configured in main.py)")

    # Choose metadata map based on perf/prod
    metadata_map = SERVICES_METADATA_PERF if is_perf else SERVICES_METADATA
    if service_name not in metadata_map:
        print(f"Service {service_name} not configured in metadata_map")
        return []

    metadata = metadata_map[service_name]
    if region_code not in metadata:
        print(f"Region {region_code} not configured for service {service_name}")
        return []

    top_dir = "perf" if is_perf else "prod"
    region_rel_folder = os.path.join(top_dir, service_name, region_code)
    region_folder = os.path.join(OUTPUT_ROOT, region_rel_folder)
    screenshots_dir = os.path.join(region_folder, 'screenshots')

    dashboard_name, aws_region, _log_group = metadata[region_code]
    cw_client = boto3.client("cloudwatch", region_name=aws_region)
    # override global client region for widget generation
    global cloudwatch_client
    cloudwatch_client = cw_client
    dashboard = get_dashboard_data(dashboard_name, cw_client)
    saved = []
    for widget in dashboard.get("widgets", []):
        metric_name = widget["properties"].get("title", "unknown_metric")
        try:
            path = save_metric_widget_image(widget, metric_name, start_time, end_time, target_dir=screenshots_dir)
            saved.append(path)
        except Exception as e:
            print(f"Failed to save widget {metric_name} for service {service_name} region {region_code}: {e}")
    return saved


def save_all_widgets_for_all_regions(start_time=None, end_time=None, regions: Iterable[str] | None = None, services: Iterable[str] | None = None, is_perf: bool = False):
    """Iterate through all configured services and regions and save screenshots.

    When is_perf=True it uses the perf metadata map and saves under perf/<service>/<region>/screenshots
    """
    if start_time is None or end_time is None:
        raise ValueError("start_time and end_time must be provided (configured in main.py)")

    metadata_map = SERVICES_METADATA_PERF if is_perf else SERVICES_METADATA
    selected_services = services if services else metadata_map.keys()
    results: Dict[str, Dict[str, list[str]]] = {}

    for service_name in selected_services:
        if service_name not in metadata_map:
            print(f"Service {service_name} not configured; skipping")
            continue

        metadata = metadata_map[service_name]
        targets = regions if regions else metadata.keys()
        results[service_name] = {}

        for code in targets:
            if code not in metadata:
                print(f"Region {code} not configured for service {service_name}; skipping")
                continue
            results[service_name][code] = save_all_widgets_for_region(code, service_name, start_time, end_time, is_perf=is_perf)

    return results
