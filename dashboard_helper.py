
import boto3
import json
import logging

logging.basicConfig(level=logging.INFO)
cloudWatchClient = boto3.client("cloudwatch")

def get_dashboard_data(dashboard_name):
    response = cloudWatchClient.get_dashboard(DashboardName=dashboard_name)
    return json.loads(response["DashboardBody"])

