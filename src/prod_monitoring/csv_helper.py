import csv
import os
import re
from typing import List, Dict, Optional
from collections import Counter, defaultdict

# Base output directory: repo_root/output
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
OUTPUT_ROOT = os.path.join(REPO_ROOT, "output")


def _region_csv_dir(region: Optional[str]):
    """Return path to a csv_data directory.

    Expected usage:
    - If `region` is a full region folder path (e.g., 'prod/SRA/NA1' or 'perf/SRM/NA1'),
      CSVs are written to: <repo_root>/output/<region>/csv_data
    - If `region` is None, write to: <repo_root>/output/csv_data (legacy fallback)
    """
    if not region:
        csv_dir = os.path.join(OUTPUT_ROOT, "csv_data")
        os.makedirs(csv_dir, exist_ok=True)
        return csv_dir

    csv_dir = os.path.join(OUTPUT_ROOT, region, "csv_data")
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
    """Extract error signature from log message.

    Note: We add context for ServiceCallException-like cases where the exception
    message is empty/generic, otherwise many different failures collapse into one bucket.
    """
    import re

    if not log_message or not log_message.strip():
        return ("Unknown", "Unknown", "Empty log message")

    def _normalize_first_error_line(text: str) -> str:
        """Generic normalization for the first ERROR-line message.

        Goal: keep the core action/summary, drop dynamic/huge payloads.
        Avoid service-specific hardcoding.
        """
        if not text:
            return ""

        # Collapse very large structured payloads common in these logs.
        # Examples: BaseSCRRequest{...}, RequestedChanges{...}, ActivityChange{...}
        text = re.sub(r'\b\w+\{[^\n\r]{0,2000}\}', lambda m: (m.group(0).split('{', 1)[0] + '{...}'), text)

        # Remove long bracket blocks (often contain dynamic context)
        text = re.sub(r'\[[^\]]{40,}\]', '[...]', text)

        # Remove URLs
        text = re.sub(r'https?://\S+', '[URL]', text)

        # Remove key=value segments where value is long/dynamic (UUIDs, timestamps, ids)
        text = re.sub(r"\b\w+=[^,\s]{12,}", "key=[...]", text)

        # Drop quoted payloads (keeps the fact there was a value)
        text = re.sub(r"'[^']{12,}'", "'[...']", text)
        text = re.sub(r'"[^"]{12,}"', '"..."', text)

        # Normalize spaces/punctuation
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    # Capture the first log line's logger (the class after ERROR)
    first_logger = ""
    m_logger = re.search(r'\bERROR\s+(\S+)', log_message)
    if m_logger:
        first_logger = m_logger.group(1).split('.')[-1]

    # Extract exception type
    exception_pattern = r'(java\.lang\.\w+Exception|com\.nice\.saas\.wfo\.\S+Exception|\w+Exception):\s*(.+?)(?:\n|$)'
    exception_match = re.search(exception_pattern, log_message)

    if exception_match:
        exception_type = exception_match.group(1).split('.')[-1]
        exception_message = exception_match.group(2).strip()
        normalized_message = _normalize_error_message(exception_message)
        location = _extract_error_location(log_message)

        # Treat stack-trace-only or empty exception messages as "generic".
        is_generic = (
            not normalized_message
            or normalized_message in {"", "{}", "unknown", "n/a"}
            or normalized_message.startswith("at com.")
            or normalized_message.startswith("at org.")
        )

        if is_generic:
            # First ERROR line message (after the trailing ] block)
            first_error_line = ""
            m_msg = re.search(r'\bERROR\b[^\n]*?\]\s+(.+?)(?:\n|$)', log_message)
            if m_msg:
                first_error_line = m_msg.group(1).strip()

            first_error_line_norm = _normalize_error_message(_normalize_first_error_line(first_error_line))

            parts = [exception_type]
            if first_logger:
                parts.append(first_logger)
            if first_error_line_norm:
                parts.append(first_error_line_norm)

            signature = " | ".join(parts)
        else:
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
