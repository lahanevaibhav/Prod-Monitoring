import csv
import os
from typing import List, Dict, Optional

ROOT_DIR = os.path.dirname(__file__)
LEGACY_CSV_ROOT = os.path.join(ROOT_DIR, 'csv_data')  # kept for backwards compatibility
os.makedirs(LEGACY_CSV_ROOT, exist_ok=True)

def _region_csv_dir(region: Optional[str]):
    """Return path to region-specific csv_data directory.

    New structure: <root>/<SERVICE>/<REGION>/csv_data
    Fallback (no region): <root>/csv_data (legacy)
    """
    if not region:
        return LEGACY_CSV_ROOT
    region_root = os.path.join(ROOT_DIR, region)
    csv_dir = os.path.join(region_root, 'csv_data')
    os.makedirs(csv_dir, exist_ok=True)
    return csv_dir

def save_metrics_group_to_csv(group_name: str, group_data: List[Dict], region: Optional[str] = None):
    """Save grouped metric data to a CSV file.

    If region is supplied, write to csv_data/<region>/<group_name>.csv else root csv_data.
    Each row: metric, timestamp, value
    """
    filename = f"{group_name}.csv"
    dir_path = _region_csv_dir(region)
    filepath = os.path.join(dir_path, filename)
    with open(filepath, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["metric", "timestamp", "value"])
        for row in group_data:
            metric_short = row["metric"].split('.')[-1]
            writer.writerow([metric_short, row["timestamp"], row["value"]])
    print(f"Saved grouped CSV: {filepath}")
    return filepath

def save_error_logs(error_log_rows: list, region: Optional[str] = None):
    """Save error logs to region-specific folder if provided (<region>/csv_data/error_logs.csv)."""
    filename = "error_logs.csv"
    dir_path = _region_csv_dir(region)
    filepath = os.path.join(dir_path, filename)
    with open(filepath, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["timestamp", "log_message"])
        for row in error_log_rows:
            writer.writerow([row["timestamp"], row["log_message"]])
    print(f"Saved error logs: {filepath}")

    # Automatically classify errors after saving
    try:
        classify_and_save_errors(filepath, dir_path)
    except Exception as e:
        print(f"Warning: Error classification failed: {e}")

    return filepath

def classify_and_save_errors(error_log_path: str, dir_path: str):
    """Classify errors and save to classified_errors.csv"""
    import re
    from collections import Counter, defaultdict

    classified_path = os.path.join(dir_path, "classified_errors.csv")

    # Read and classify errors
    error_signatures = Counter()
    error_examples = {}
    error_timestamps = defaultdict(list)
    error_details = defaultdict(lambda: {"type": "", "location": "", "count": 0})

    with open(error_log_path, 'r', encoding='utf-8', newline='') as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            timestamp = row.get('timestamp', '')
            log_message = row.get('log_message', '')

            if not log_message:
                continue

            # Extract error signature
            error_type, location, signature = _extract_error_signature(log_message)

            # Count this error
            error_signatures[signature] += 1

            # Store details
            if signature not in error_examples:
                error_examples[signature] = log_message  # Store full log message

            error_timestamps[signature].append(timestamp)
            error_details[signature]["type"] = error_type
            error_details[signature]["location"] = location
            error_details[signature]["count"] = error_signatures[signature]

    # Write classified errors
    with open(classified_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            "Error Signature",
            "Occurrence Count",
            "Location",
            "Sample Error Message"
        ])

        sorted_errors = sorted(error_signatures.items(), key=lambda x: x[1], reverse=True)

        for signature, count in sorted_errors:
            location = error_details[signature]["location"]
            sample = error_examples.get(signature, "")  # Full log, no truncation

            writer.writerow([
                signature,
                count,
                location,
                sample
            ])

    print(f"Saved classified errors: {classified_path} ({len(error_signatures)} unique patterns)")

def _extract_error_signature(log_message: str):
    """Extract error signature from log message"""
    import re

    if not log_message or not log_message.strip():
        return ("Unknown", "Unknown", "Empty log message")

    # Extract exception type
    exception_pattern = r'(java\.lang\.\w+Exception|com\.nice\.saas\.\S+Exception|\w+Exception):\s*(.+?)(?:\n|$)'
    exception_match = re.search(exception_pattern, log_message)

    if exception_match:
        exception_type = exception_match.group(1).split('.')[-1]
        exception_message = exception_match.group(2).strip()
        normalized_message = _normalize_error_message(exception_message)
        location = _extract_error_location(log_message)
        signature = f"{exception_type}: {normalized_message}"
        return (exception_type, location, signature)

    # Fallback to ERROR pattern
    error_pattern = r'ERROR\s+(\S+)\s+.*?\]\s+(.+?)(?:\n|$)'
    error_match = re.search(error_pattern, log_message)

    if error_match:
        class_name = error_match.group(1).split('.')[-1]
        error_msg = error_match.group(2).strip()
        normalized_msg = _normalize_error_message(error_msg)
        return ("ERROR", class_name, f"ERROR in {class_name}: {normalized_msg}")

    first_line = log_message.split('\n')[0][:200]
    normalized = _normalize_error_message(first_line)
    return ("Unknown", "Unknown", normalized)

def _normalize_error_message(message: str) -> str:
    """Normalize error message by removing dynamic data"""
    import re

    message = re.sub(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', '[UUID]', message, flags=re.IGNORECASE)
    message = re.sub(r'\b[0-9a-f]{16}\b', '[HEX-ID]', message)
    message = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?', '[TIMESTAMP]', message)
    message = re.sub(r'\d{2}:\d{2}:\d{2}\.\d+', '[TIME]', message)
    message = re.sub(r"'[0-9]+'" , "'[ID]'", message)
    message = re.sub(r'\[\w+_\w+_\w+_\w+\d+\]', '[TENANT]', message)
    message = re.sub(r'BaseSCRRequest\{[^}]+\}', 'BaseSCRRequest{...}', message)
    message = re.sub(r'RequestedChanges\{[^}]+\}', 'RequestedChanges{...}', message)
    message = re.sub(r'ActivityChange\{[^}]+\}', 'ActivityChange{...}', message)
    message = re.sub(r'\[[^\]]{50,}\]', '[...]', message)
    message = re.sub(r'\b\d{3,}\b', '[NUM]', message)
    message = ' '.join(message.split())
    return message

def _extract_error_location(log_message: str) -> str:
    """Extract error location from log message"""
    import re

    at_pattern = r'at (com\.nice\.saas\.wfo\.\w+\.[\w\.]+)\.(\w+)\('
    at_match = re.search(at_pattern, log_message)

    if at_match:
        class_path = at_match.group(1)
        method = at_match.group(2)
        class_name = class_path.split('.')[-1]
        return f"{class_name}.{method}"

    error_pattern = r'ERROR\s+(com\.nice\.saas\.wfo\.\S+)'
    error_match = re.search(error_pattern, log_message)

    if error_match:
        class_path = error_match.group(1)
        class_name = class_path.split('.')[-1]
        return class_name

    return "Unknown"

