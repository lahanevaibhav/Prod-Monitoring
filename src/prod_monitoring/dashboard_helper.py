
import boto3
import json
import logging
from .aws_profile_manager import get_profile_manager, AWSProfileManager

logging.basicConfig(level=logging.INFO)

# Get the profile manager instance
profile_manager = get_profile_manager()
cloudWatchClient = profile_manager.create_client("cloudwatch",
                                                purpose=AWSProfileManager.DATA_PROFILE)

def get_dashboard_data(dashboard_name, cw_client=None):
    """Get dashboard data using the provided client or default global client."""
    client = cw_client if cw_client is not None else cloudWatchClient
    response = client.get_dashboard(DashboardName=dashboard_name)
    return json.loads(response["DashboardBody"])


