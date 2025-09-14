import logging
import boto3
from datetime import datetime
from dashboard_helper import get_dashboard_data
from csv_helper import save_metrics_group_to_csv, save_error_logs


METRIC_TYPES = {
    "internalErrors": {"name": "SRA MS Errors", "type": "Error"},
    "externalErrors": {"name": "External APis Errors", "type": "Error"},
    "internalPerformance": {"name": "SRA performance in MS", "type": "Performance"},
    "externalPerformance": {"name": "External APIs performance in MS", "type": "Performance"}
}

logging.basicConfig(level=logging.INFO)
cloudWatchClient = boto3.client("cloudwatch")
sraDashboardResponse = get_dashboard_data("production-SRA-Dashboard")

NAMESPACE = "production.service.metrics"
REGION = "us-west-2"
PERIOD = 60
START_TIME = datetime(2025, 9, 10)
END_TIME = datetime(2025, 9, 11)

def get_metrics_data(metric_query):
    response = cloudWatchClient.get_metric_data(
        MetricDataQueries=[metric_query],
        StartTime=START_TIME,
        EndTime=END_TIME,
        ScanBy="TimestampAscending",
        LabelOptions={"Timezone": "+0530"}
    )
    return response['MetricDataResults']

def get_metrics_with_threshold(threshold, query):
    metricsData = get_metrics_data(query)
    errorsDict = {}
    errorCount = 0
    for idx, value in enumerate(metricsData[0]["Values"]):
        if value > threshold:
            errorCount += value
            errorsDict[metricsData[0]["Timestamps"][idx].isoformat()] = value
    # CSV saving removed; handled in getAllMetricDetails
    return errorCount, errorsDict

def getMetricsList(title):
    for widget in sraDashboardResponse["widgets"]:
        if widget["properties"]["title"] == title:
            return [metric[1] for metric in widget["properties"]["metrics"]]
    return []

def get_metric_query(metricName, statType):
    return {
        "Id": "".join(metricName.split()).lower().replace(".", "_").replace("-", "_"),
        "MetricStat": {
            "Metric": {
                "Namespace": NAMESPACE,
                "MetricName": metricName,
                "Dimensions": [{"Name": "type", "Value": "gauge"}]
            },
            "Period": PERIOD,
            "Stat": statType,
        },
        "ReturnData": True
    }

def process_metric_type(metric_type, info):
    """Process a single metric type and return the collected data."""
    threshold = 0 if info["type"] == "Error" else 500
    statType = "Sum" if info["type"] == "Error" else "Average"
    group_data = []
    
    for metricName in getMetricsList(info["name"]):
        query = get_metric_query(metricName, statType)
        errorCount, errorsDict = get_metrics_with_threshold(threshold, query)
        for timestamp, value in errorsDict.items():
            group_data.append({
                "metric": metricName,
                "timestamp": timestamp,
                "value": value
            })
    
    return group_data

def collect_metrics_data():
    """Collect and save metrics data for all metric types."""
    for metric_type, info in METRIC_TYPES.items():
        group_data = process_metric_type(metric_type, info)
        save_metrics_group_to_csv(info['name'], group_data)

def get_time_range_for_logs():
    """Get the time range for log collection (last 24 hours)."""
    end_time = int(END_TIME.timestamp() * 1000)
    start_time = int(START_TIME.timestamp() * 1000)
    print(START_TIME, END_TIME)
    print(f"Log collection time range: {start_time} - {end_time}")
    return start_time, end_time

def fetch_log_events(logs_client, log_group, start_time, end_time, next_token=None):
    """Fetch log events from CloudWatch Logs with pagination support."""
    params = {
        'logGroupName': log_group,
        'startTime': start_time,
        'endTime': end_time,
        'filterPattern': 'ERROR -METRICS_AGG -nginxinternal',
        'limit': 1000
    }

    if next_token:
        params['nextToken'] = next_token
    
    return logs_client.filter_log_events(**params)

def clean_log_message(message):
    """Clean log message to prevent CSV formatting issues."""
    # Remove or replace problematic characters
    cleaned = message.replace('\n', ' ')  # Replace newlines with spaces
    cleaned = cleaned.replace('\r', ' ')  # Replace carriage returns with spaces
    cleaned = cleaned.replace('\t', ' ')  # Replace tabs with spaces
    
    # Remove excessive whitespace
    cleaned = ' '.join(cleaned.split())
    
    return cleaned

def process_log_events(events):
    """Process log events and convert to required format."""
    log_rows = []
    for event in events:
        log_rows.append({
            "timestamp": datetime.fromtimestamp(event['timestamp'] / 1000).isoformat(),
            "log_message": clean_log_message(event['message'])
        })
    return log_rows

def collect_error_logs():
    """Collect and save error logs from CloudWatch Logs."""
    logs_client = boto3.client("logs")
    log_group = "production-schedule-rules-automation"  # TODO: set correct log group
    start_time, end_time = get_time_range_for_logs()
    error_log_rows = []
    
    try:
        # Initial request
        response = fetch_log_events(logs_client, log_group, start_time, end_time)
        error_log_rows.extend(process_log_events(response.get('events', [])))
        next_token = response.get('nextToken')
        while next_token and len(error_log_rows) < 10000:  # Limit to prevent excessive data
            response = fetch_log_events(logs_client, log_group, start_time, end_time, next_token)
            error_log_rows.extend(process_log_events(response.get('events', [])))
            next_token = response.get('nextToken')
        print(f"Fetched {len(error_log_rows)} error log entries.")
    except Exception as e:
        error_log_rows.append({
            "timestamp": datetime.now().isoformat(),
            "log_message": f"Log fetch error: {e}"
        })
    
    save_error_logs(error_log_rows)

def getAllMetricDetails():
    """Main function to collect all metrics and error logs."""
    collect_metrics_data()
    collect_error_logs()
