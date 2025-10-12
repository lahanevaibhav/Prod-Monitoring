import os
import boto3
import json
from datetime import datetime
from typing import Dict, Any, Iterable

from metrics_helper import METRICS_METADATA_SRA, START_TIME, END_TIME
from dashboard_helper import get_dashboard_data

ROOT_DIR = os.path.dirname(__file__)
GLOBAL_SCREENSHOTS_DIR = os.path.join(ROOT_DIR, 'screenshots')  # legacy root screenshots (kept for backwards comp.)
os.makedirs(GLOBAL_SCREENSHOTS_DIR, exist_ok=True)
cloudwatch_client = boto3.client("cloudwatch")  # default client (may be reused for NA1 aggregate if desired)

def save_metric_widget_image(widget, metric_name, start_time, end_time, region_code: str | None = None):
    """
    Saves a CloudWatch metric widget image for the given metric and time range.
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
        "width": 900,
        "height": 600,
        "start": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end": end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    })
    response = cloudwatch_client.get_metric_widget_image(MetricWidget=metric_widget_json)
    # Region specific folder (screenshots/<region_code>) if provided
    if region_code:
        region_root = os.path.join(ROOT_DIR, region_code)
        target_dir = os.path.join(region_root, 'screenshots')
        os.makedirs(target_dir, exist_ok=True)
    else:
        target_dir = GLOBAL_SCREENSHOTS_DIR
    filename = f"{metric_name}.png"
    filepath = os.path.join(target_dir, filename)
    with open(filepath, "wb") as f:
        f.write(response["MetricWidgetImage"])
    print(f"Saved widget image: {filepath}")
    return filepath

def save_all_widgets_for_region(region_code: str, start_time=START_TIME, end_time=END_TIME):
    """Fetch dashboard for region and save screenshots for every widget into region folder."""
    if region_code not in METRICS_METADATA_SRA:
        print(f"Region {region_code} not configured in METRICS_METADATA_SRA")
        return []
    dashboard_name, aws_region, _log_group = METRICS_METADATA_SRA[region_code]
    cw_client = boto3.client("cloudwatch", region_name=aws_region)
    # override global client region for widget generation; simpler than changing function signature widely
    global cloudwatch_client
    cloudwatch_client = cw_client
    dashboard = get_dashboard_data(dashboard_name)
    saved = []
    for widget in dashboard.get("widgets", []):
        metric_name = widget["properties"].get("title", "unknown_metric")
        try:
            path = save_metric_widget_image(widget, metric_name, start_time, end_time, region_code=region_code)
            saved.append(path)
        except Exception as e:
            print(f"Failed to save widget {metric_name} for region {region_code}: {e}")
    return saved

def save_all_widgets_for_all_regions(start_time=START_TIME, end_time=END_TIME, regions: Iterable[str] | None = None):
    """Iterate through all configured regions and save screenshots."""
    targets = regions if regions else METRICS_METADATA_SRA.keys()
    results: Dict[str, list[str]] = {}
    for code in targets:
        results[code] = save_all_widgets_for_region(code, start_time, end_time)
    return results
