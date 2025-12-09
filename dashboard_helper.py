
import boto3
import json
import logging

logging.basicConfig(level=logging.INFO)
cloudWatchClient = boto3.client("cloudwatch")

def get_dashboard_data(dashboard_name, cw_client=None):
    """Get dashboard data using the provided client or default global client."""
    client = cw_client if cw_client is not None else cloudWatchClient
    response = client.get_dashboard(DashboardName=dashboard_name)
    return json.loads(response["DashboardBody"])

