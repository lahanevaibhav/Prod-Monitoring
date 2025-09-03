
import os
import boto3
import json
from datetime import datetime

SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), 'screenshots')
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
cloudwatch_client = boto3.client("cloudwatch")

def save_metric_widget_image(widget, metric_name, start_time, end_time):
	"""
	Saves a CloudWatch metric widget image for the given metric and time range.
	"""
	metric_widget_json = json.dumps({
		"metrics": widget["properties"]["metrics"],
		"view": "timeSeries",
		"stacked": False,
		"region": cloudwatch_client.meta.region_name,
		"title": metric_name,
		"width": 600,
		"height": 395,
		"start": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
		"end": end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
	})
	response = cloudwatch_client.get_metric_widget_image(MetricWidget=metric_widget_json)
	filename = f"{metric_name}.png"
	filepath = os.path.join(SCREENSHOTS_DIR, filename)
	with open(filepath, "wb") as f:
		f.write(response["MetricWidgetImage"])
	print(f"Saved widget image: {filepath}")
	return filepath
