import csv
import os
from typing import List, Dict

CSV_DIR = os.path.join(os.path.dirname(__file__), 'csv_data')
os.makedirs(CSV_DIR, exist_ok=True)


def save_metrics_group_to_csv(group_name: str, group_data: List[Dict]):
    """
    Save grouped metric data to a CSV file. Each row: metric, timestamp, value
    """
    filename = f"{group_name}.csv"
    filepath = os.path.join(CSV_DIR, filename)
    with open(filepath, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["metric", "timestamp", "value"])
        for row in group_data:
            # Extract last part after last dot or underscore
            metric_short = row["metric"].split('.')[-1]
            writer.writerow([metric_short, row["timestamp"], row["value"]])
    print(f"Saved grouped CSV: {filepath}")
    return filepath
