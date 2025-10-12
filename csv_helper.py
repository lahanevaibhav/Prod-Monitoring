import csv
import os
from typing import List, Dict, Optional

CSV_DIR = os.path.join(os.path.dirname(__file__), 'csv_data')
os.makedirs(CSV_DIR, exist_ok=True)

def _region_dir(region: Optional[str]):
    if not region:
        return CSV_DIR
    path = os.path.join(CSV_DIR, region)
    os.makedirs(path, exist_ok=True)
    return path

def save_metrics_group_to_csv(group_name: str, group_data: List[Dict], region: Optional[str] = None):
    """Save grouped metric data to a CSV file.

    If region is supplied, write to csv_data/<region>/<group_name>.csv else root csv_data.
    Each row: metric, timestamp, value
    """
    filename = f"{group_name}.csv"
    dir_path = _region_dir(region)
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
    """Save error logs to region-specific folder if provided (csv_data/<region>/error_logs.csv)."""
    filename = "error_logs.csv"
    dir_path = _region_dir(region)
    filepath = os.path.join(dir_path, filename)
    with open(filepath, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["timestamp", "log_message"])
        for row in error_log_rows:
            writer.writerow([row["timestamp"], row["log_message"]])
    print(f"Saved error logs: {filepath}")
    return filepath
