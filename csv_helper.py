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
    return filepath
