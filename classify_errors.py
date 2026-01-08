"""
Error Log Classifier - Analyzes error logs and creates classified_errors.csv with error counts
"""

import csv
import re
import os
from collections import Counter, defaultdict
from typing import Dict, List, Tuple
from datetime import datetime

def extract_error_signature(log_message: str) -> Tuple[str, str, str]:
    """
    Extract error signature by identifying the core error pattern.
    Returns: (error_type, error_location, error_signature)
    """
    if not log_message or not log_message.strip():
        return ("Unknown", "Unknown", "Empty log message")

    # Extract exception type
    exception_pattern = r'(java\.lang\.\w+Exception|com\.nice\.saas\.\S+Exception|\w+Exception):\s*(.+?)(?:\n|$)'
    exception_match = re.search(exception_pattern, log_message)

    if exception_match:
        exception_type = exception_match.group(1).split('.')[-1]  # Get just the exception name
        exception_message = exception_match.group(2).strip()

        # Normalize the exception message by removing dynamic data
        normalized_message = normalize_error_message(exception_message)

        # Extract the method/class where error occurred
        location = extract_error_location(log_message)

        # Create signature
        signature = f"{exception_type}: {normalized_message}"

        return (exception_type, location, signature)

    # If no exception pattern found, look for ERROR keyword
    error_pattern = r'ERROR\s+(\S+)\s+.*?\]\s+(.+?)(?:\n|$)'
    error_match = re.search(error_pattern, log_message)

    if error_match:
        class_name = error_match.group(1).split('.')[-1]
        error_msg = error_match.group(2).strip()
        normalized_msg = normalize_error_message(error_msg)

        return ("ERROR", class_name, f"ERROR in {class_name}: {normalized_msg}")

    # Fallback: use first meaningful line
    first_line = log_message.split('\n')[0][:200]
    normalized = normalize_error_message(first_line)
    return ("Unknown", "Unknown", normalized)

def normalize_error_message(message: str) -> str:
    """
    Normalize error message by removing dynamic data (UUIDs, timestamps, user IDs, etc.)
    """
    # Remove UUIDs (format: 11ef8709-70d4-4670-b102-0242ac110002)
    message = re.sub(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', '[UUID]', message, flags=re.IGNORECASE)

    # Remove hex IDs (format: 22f8ddccbde6b48f)
    message = re.sub(r'\b[0-9a-f]{16}\b', '[HEX-ID]', message)
    message = re.sub(r'\b[0-9a-f]{12,}\b', '[HEX-ID]', message)

    # Remove timestamps (ISO format)
    message = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?', '[TIMESTAMP]', message)

    # Remove time patterns (HH:MM:SS.mmm)
    message = re.sub(r'\d{2}:\d{2}:\d{2}\.\d+', '[TIME]', message)

    # Remove numeric IDs
    message = re.sub(r"'[0-9]+'" , "'[ID]'", message)

    # Remove tenant/customer names in brackets (e.g., [legal_answer_edge_llc26123588])
    message = re.sub(r'\[\w+_\w+_\w+_\w+\d+\]', '[TENANT]', message)

    # Remove BaseSCRRequest content (too specific)
    message = re.sub(r'BaseSCRRequest\{[^}]+\}', 'BaseSCRRequest{...}', message)

    # Remove RequestedChanges content
    message = re.sub(r'RequestedChanges\{[^}]+\}', 'RequestedChanges{...}', message)

    # Remove ActivityChange content
    message = re.sub(r'ActivityChange\{[^}]+\}', 'ActivityChange{...}', message)

    # Remove array contents
    message = re.sub(r'\[[^\]]{50,}\]', '[...]', message)

    # Remove specific numeric values
    message = re.sub(r'\b\d{3,}\b', '[NUM]', message)

    # Normalize whitespace
    message = ' '.join(message.split())

    return message

def extract_error_location(log_message: str) -> str:
    """
    Extract the primary location (class.method) where error occurred
    """
    # Look for "at com.nice.saas..." pattern
    at_pattern = r'at (com\.nice\.saas\.wfo\.\w+\.[\w\.]+)\.(\w+)\('
    at_match = re.search(at_pattern, log_message)

    if at_match:
        class_path = at_match.group(1)
        method = at_match.group(2)
        # Get just the class name (last part)
        class_name = class_path.split('.')[-1]
        return f"{class_name}.{method}"

    # Look for ERROR keyword with class
    error_pattern = r'ERROR\s+(com\.nice\.saas\.wfo\.\S+)'
    error_match = re.search(error_pattern, log_message)

    if error_match:
        class_path = error_match.group(1)
        class_name = class_path.split('.')[-1]
        return class_name

    return "Unknown"

def classify_error_logs(error_log_path: str, output_path: str) -> Dict:
    """
    Classify error logs and create classified_errors.csv

    Args:
        error_log_path: Path to error_logs.csv
        output_path: Path to save classified_errors.csv

    Returns:
        Dictionary with classification statistics
    """
    print(f"Reading error logs from: {error_log_path}")

    if not os.path.exists(error_log_path):
        print(f"Error: File not found: {error_log_path}")
        return {}

    # Data structures for classification
    error_signatures = Counter()  # signature -> count
    error_examples = {}  # signature -> first example
    error_timestamps = defaultdict(list)  # signature -> list of timestamps
    error_details = defaultdict(lambda: {"type": "", "location": "", "count": 0})

    # Read and classify errors
    with open(error_log_path, 'r', encoding='utf-8', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        total_errors = 0

        for row in reader:
            total_errors += 1
            timestamp = row.get('timestamp', '')
            log_message = row.get('log_message', '')

            if not log_message:
                continue

            # Extract error signature
            error_type, location, signature = extract_error_signature(log_message)

            # Count this error
            error_signatures[signature] += 1

            # Store details
            if signature not in error_examples:
                error_examples[signature] = log_message  # Store full log message

            error_timestamps[signature].append(timestamp)

            error_details[signature]["type"] = error_type
            error_details[signature]["location"] = location
            error_details[signature]["count"] = error_signatures[signature]

    print(f"Total error log entries processed: {total_errors}")
    print(f"Unique error patterns found: {len(error_signatures)}")

    # Write classified errors to CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            "Error Signature",
            "Occurrence Count",
            "Location",
            "Sample Error Message"
        ])

        # Sort by count (descending)
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

    print(f"Classified errors saved to: {output_path}")

    # Return statistics
    stats = {
        "total_errors": total_errors,
        "unique_patterns": len(error_signatures),
        "top_errors": sorted_errors[:10]
    }

    return stats

def classify_all_regions_and_services(base_dir: str = "C:\\Prod Monitoring"):
    """
    Classify error logs for all services and regions
    """
    print("=" * 80)
    print("Error Log Classification - Processing All Services and Regions")
    print("=" * 80 + "\n")

    services = ["SRA", "SRM"]
    regions = ["NA1", "AU", "CA", "JP", "DE", "UK"]

    total_stats = {
        "services_processed": 0,
        "total_errors": 0,
        "total_unique_patterns": 0
    }

    for service in services:
        for region in regions:
            error_log_path = os.path.join(base_dir, service, region, "csv_data", "error_logs.csv")
            classified_path = os.path.join(base_dir, service, region, "csv_data", "classified_errors.csv")

            if not os.path.exists(error_log_path):
                print(f"⚠️  Skipping {service}/{region} - error_logs.csv not found")
                continue

            print(f"\n📊 Processing {service}/{region}...")
            print("-" * 80)

            try:
                stats = classify_error_logs(error_log_path, classified_path)

                if stats:
                    print(f"✅ {service}/{region} completed:")
                    print(f"   - Total errors: {stats['total_errors']}")
                    print(f"   - Unique patterns: {stats['unique_patterns']}")
                    print(f"   - Top 3 errors:")
                    for i, (sig, count) in enumerate(stats['top_errors'][:3], 1):
                        print(f"     {i}. {sig[:80]}... (Count: {count})")

                    total_stats["services_processed"] += 1
                    total_stats["total_errors"] += stats['total_errors']
                    total_stats["total_unique_patterns"] += stats['unique_patterns']

            except Exception as e:
                print(f"❌ Error processing {service}/{region}: {e}")

    print("\n" + "=" * 80)
    print("Classification Complete - Summary")
    print("=" * 80)
    print(f"Services/Regions processed: {total_stats['services_processed']}")
    print(f"Total errors classified: {total_stats['total_errors']}")
    print(f"Total unique error patterns: {total_stats['total_unique_patterns']}")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    # Process all services and regions
    classify_all_regions_and_services()

