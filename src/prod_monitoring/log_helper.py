import logging
from datetime import datetime

from .csv_helper import save_error_logs
from .anonymizer import anonymize_log_message
from .aws_profile_manager import get_profile_manager, AWSProfileManager

# Import configuration settings
try:
    from .unified_config import MAX_LOG_ENTRIES
except ImportError:
    # Fallback defaults if unified_config is not available
    MAX_LOG_ENTRIES = 10000

# Additional settings
ANONYMIZE_LOGS = True
LOG_FILTER_PATTERN = 'ERROR -METRICS_AGG'
MAX_LOG_ITERATIONS = 100

# Configure logging
logging.basicConfig(level=logging.INFO)

# Get the profile manager instance
profile_manager = get_profile_manager()


def should_exclude_log(message):
    """Check if entire log entry should be excluded based on useless patterns."""
    if not message or not message.strip():
        return True

    # Patterns that indicate the entire log entry is useless
    exclude_patterns = (
        'NotificationDispatcherImpl',
    )

    # If message contains any exclude pattern, skip entire log entry
    return any(pattern in message for pattern in exclude_patterns)

def clean_log_message(message):
    """Clean log message to prevent CSV formatting issues and filter out framework noise."""
    if not message or not message.strip():
        return ""
    
    # Define noise patterns to filter out from individual lines
    noise_patterns = ('shared.restclient', 'platform.shared', 'platform.boot', 'java.base',
                      'org.springframework', 'org.apache', 'jakarta.servlet', 'jdk.internal', 'fasterxml.jackson')
    
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
    """Process log events and convert to required format, excluding useless entries."""
    log_rows = []
    for event in events:
        # Skip entire log entry if it contains useless patterns
        if should_exclude_log(event['message']):
            continue

        cleaned_message = clean_log_message(event['message'])
        # Only add if there's actual content after cleaning
        if cleaned_message:
            # Apply anonymization if enabled (for LLM consumption)
            if ANONYMIZE_LOGS:
                cleaned_message = anonymize_log_message(cleaned_message)
            
            log_rows.append({
                "timestamp": datetime.fromtimestamp(event['timestamp'] / 1000).isoformat(),
                "log_message": cleaned_message
            })
    return log_rows

def collect_error_logs(log_group, start_time, end_time, region_code, region,
                      filter_pattern=None, max_entries=None, max_iterations=None):
    """
    Collect and save error logs from CloudWatch Logs.
    
    Args:
        log_group (str): CloudWatch log group name
        start_time (datetime): Start time for log collection
        end_time (datetime): End time for log collection
        filter_pattern (str): CloudWatch filter pattern for logs (uses config default if None)
        max_entries (int): Maximum number of log entries to collect (uses config default if None)
        max_iterations (int): Maximum number of pagination iterations (uses config default if None)

    Returns:
        int: Number of log entries collected
    """
    # Use config defaults if not specified
    if filter_pattern is None:
        filter_pattern = LOG_FILTER_PATTERN
    if max_entries is None:
        max_entries = MAX_LOG_ENTRIES
    if max_iterations is None:
        max_iterations = MAX_LOG_ITERATIONS

    logs_client = profile_manager.create_client("logs", region_name=region,
                                               purpose=AWSProfileManager.DATA_PROFILE)
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
    save_error_logs(error_log_rows, region_code)
    return len(error_log_rows)
