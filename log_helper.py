import logging
import boto3
from datetime import datetime
from csv_helper import save_error_logs

# Configure logging
logging.basicConfig(level=logging.INFO)

def clean_log_message(message):
    """Clean log message to prevent CSV formatting issues and filter out framework noise."""
    if not message or not message.strip():
        return ""
    
    # Define noise patterns to filter out
    noise_patterns = ('java.base', 'org.springframework', 'org.apache', 'jakarta.servlet', 'jdk.internal')
    
    # Process and filter lines in a single pass
    cleaned_lines = []
    for line in message.split('\n'):
        stripped = line.strip()
        if stripped and not any(pattern in line for pattern in noise_patterns):
            # Normalize whitespace efficiently
            normalized = ' '.join(line.replace('\r', ' ').replace('\t', ' ').split())
            if normalized:
                cleaned_lines.append(normalized)
    
    # Keep actual newlines for better readability - CSV will automatically quote the field
    # This preserves line structure while being CSV-safe
    return '\n'.join(cleaned_lines)

def get_time_range_for_logs(start_time, end_time):
    """Get the time range for log collection in milliseconds."""
    start_ms = int(start_time.timestamp() * 1000)
    end_ms = int(end_time.timestamp() * 1000)
    print(f"Log collection time range: {start_time} to {end_time}")
    print(f"Timestamp range: {start_ms} - {end_ms}")
    return start_ms, end_ms

def fetch_log_events(logs_client, log_group, start_time, end_time, filter_pattern=None, next_token=None, limit=1000):
    """Fetch log events from CloudWatch Logs with pagination support."""
    params = {
        'logGroupName': log_group,
        'startTime': start_time,
        'endTime': end_time,
        'limit': limit
    }
    
    # Add filter pattern if provided
    if filter_pattern:
        params['filterPattern'] = filter_pattern
    
    # Add pagination token if provided
    if next_token:
        params['nextToken'] = next_token
    
    return logs_client.filter_log_events(**params)

def process_log_events(events):
    """Process log events and convert to required format."""
    log_rows = []
    for event in events:
        log_rows.append({
            "timestamp": datetime.fromtimestamp(event['timestamp'] / 1000).isoformat(),
            "log_message": clean_log_message(event['message'])
        })
    return log_rows

def collect_error_logs(log_group, start_time, end_time, filter_pattern='ERROR -METRICS_AGG -nginxinternal', max_entries=10000, max_iterations=100):
    """
    Collect and save error logs from CloudWatch Logs.
    
    Args:
        log_group (str): CloudWatch log group name
        start_time (datetime): Start time for log collection
        end_time (datetime): End time for log collection
        filter_pattern (str): CloudWatch filter pattern for logs
        max_entries (int): Maximum number of log entries to collect
        max_iterations (int): Maximum number of pagination iterations
    
    Returns:
        int: Number of log entries collected
    """
    logs_client = boto3.client("logs")
    start_ms, end_ms = get_time_range_for_logs(start_time, end_time)
    error_log_rows = []
    iteration_count = 0
    
    try:
        # Initial request
        response = fetch_log_events(logs_client, log_group, start_ms, end_ms, filter_pattern)
        error_log_rows.extend(process_log_events(response.get('events', [])))
        next_token = response.get('nextToken')
        iteration_count += 1
        
        # Continue pagination if needed
        while (next_token and 
               len(error_log_rows) < max_entries and 
               iteration_count < max_iterations):
            
            response = fetch_log_events(logs_client, log_group, start_ms, end_ms, filter_pattern, next_token)
            error_log_rows.extend(process_log_events(response.get('events', [])))
            next_token = response.get('nextToken')
            iteration_count += 1
            
            # Log progress every 10 iterations
            if iteration_count % 10 == 0:
                print(f"Processed {iteration_count} iterations, collected {len(error_log_rows)} log entries")
        
        print(f"Fetched {len(error_log_rows)} error log entries in {iteration_count} iterations.")
        
    except Exception as e:
        logging.error(f"Error fetching logs from {log_group}: {e}")
        error_log_rows.append({
            "timestamp": datetime.now().isoformat(),
            "log_message": f"Log fetch error from {log_group}: {e}"
        })
    
    # Save logs to CSV
    save_error_logs(error_log_rows)
    return len(error_log_rows)

def collect_logs_from_multiple_groups(log_groups, start_time, end_time, filter_pattern='ERROR -METRICS_AGG -nginxinternal'):
    """
    Collect error logs from multiple CloudWatch log groups.
    
    Args:
        log_groups (list): List of CloudWatch log group names
        start_time (datetime): Start time for log collection
        end_time (datetime): End time for log collection
        filter_pattern (str): CloudWatch filter pattern for logs
    
    Returns:
        dict: Dictionary with log group names as keys and entry counts as values
    """
    results = {}
    
    for log_group in log_groups:
        print(f"Collecting logs from: {log_group}")
        try:
            count = collect_error_logs(log_group, start_time, end_time, filter_pattern)
            results[log_group] = count
        except Exception as e:
            logging.error(f"Failed to collect logs from {log_group}: {e}")
            results[log_group] = 0
    
    return results

def get_log_group_info(log_group_name):
    """Get information about a CloudWatch log group."""
    logs_client = boto3.client("logs")
    
    try:
        response = logs_client.describe_log_groups(logGroupNamePrefix=log_group_name)
        log_groups = response.get('logGroups', [])
        
        for group in log_groups:
            if group['logGroupName'] == log_group_name:
                return {
                    'name': group['logGroupName'],
                    'creation_time': datetime.fromtimestamp(group['creationTime'] / 1000),
                    'retention_days': group.get('retentionInDays', 'Never expires'),
                    'stored_bytes': group.get('storedBytes', 0),
                    'metric_filter_count': group.get('metricFilterCount', 0)
                }
        
        return None
        
    except Exception as e:
        logging.error(f"Error getting log group info for {log_group_name}: {e}")
        return None

def list_available_log_groups(prefix=None, limit=50):
    """List available CloudWatch log groups."""
    logs_client = boto3.client("logs")
    
    try:
        params = {'limit': limit}
        if prefix:
            params['logGroupNamePrefix'] = prefix
            
        response = logs_client.describe_log_groups(**params)
        log_groups = response.get('logGroups', [])
        
        return [group['logGroupName'] for group in log_groups]
        
    except Exception as e:
        logging.error(f"Error listing log groups: {e}")
        return []