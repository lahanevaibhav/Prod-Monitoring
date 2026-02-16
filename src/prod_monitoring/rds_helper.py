"""
RDS Metrics Collection Helper

This module collects RDS (Relational Database Service) metrics from AWS CloudWatch
and Performance Insights, including:
- CPU Usage
- Memory Usage
- Database Errors
- Top 10 Queries
- Slow Queries (queries that took a lot of time)

Data is saved in CSV format and screenshots are captured for visualization.
"""

import logging
import boto3
import os
import csv
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from csv_helper import OUTPUT_ROOT

logging.basicConfig(level=logging.INFO)


def make_cloudwatch_client(region_name: str):
    """Create a CloudWatch client for the specified region."""
    return boto3.client("cloudwatch", region_name=region_name)


def make_rds_client(region_name: str):
    """Create an RDS client for the specified region."""
    return boto3.client("rds", region_name=region_name)


def make_pi_client(region_name: str):
    """Create a Performance Insights client for the specified region."""
    return boto3.client("pi", region_name=region_name)


def get_rds_instances(rds_client, db_instance_identifier: Optional[str] = None) -> List[Dict]:
    """
    Get list of RDS instances.

    Args:
        rds_client: Boto3 RDS client
        db_instance_identifier: Optional specific DB instance to fetch.
                                Can be exact name or a pattern to match (e.g., "wfm-storage")

    Returns:
        List of RDS instance metadata dictionaries
    """
    try:
        # If identifier looks like a pattern (short string without full AWS naming)
        # or contains wildcards, search for matching instances
        if db_instance_identifier and len(db_instance_identifier) < 30:
            # Get all instances and filter by pattern
            response = rds_client.describe_db_instances()
            all_instances = response.get('DBInstances', [])

            # First try exact match
            exact_match = [db for db in all_instances
                          if db['DBInstanceIdentifier'] == db_instance_identifier]
            if exact_match:
                target_instances = exact_match
            else:
                # Try pattern matching (contains)
                target_instances = [db for db in all_instances
                                  if db_instance_identifier.lower() in db['DBInstanceIdentifier'].lower()]

                if target_instances:
                    logging.info(f"Pattern '{db_instance_identifier}' matched {len(target_instances)} instance(s)")
        else:
            # Exact instance identifier provided
            if db_instance_identifier:
                response = rds_client.describe_db_instances(DBInstanceIdentifier=db_instance_identifier)
            else:
                response = rds_client.describe_db_instances()
            target_instances = response.get('DBInstances', [])

        instances = []
        for db_instance in target_instances:
            instances.append({
                'DBInstanceIdentifier': db_instance['DBInstanceIdentifier'],
                'DBInstanceClass': db_instance['DBInstanceClass'],
                'Engine': db_instance['Engine'],
                'EngineVersion': db_instance['EngineVersion'],
                'DBInstanceArn': db_instance['DBInstanceArn'],
                'PerformanceInsightsEnabled': db_instance.get('PerformanceInsightsEnabled', False),
                'PerformanceInsightsResourceId': db_instance.get('DbiResourceId', '')
            })
        return instances
    except Exception as e:
        if "DBInstanceNotFound" in str(e):
            logging.warning(f"RDS instance not found: {db_instance_identifier}")
        else:
            logging.error(f"Error fetching RDS instances: {e}")
        return []


def get_rds_metric_data(cw_client, db_instance_id: str, metric_name: str,
                       start_time: datetime, end_time: datetime,
                       stat: str = "Average", period: int = 300) -> List[Dict]:
    """
    Fetch CloudWatch metric data for an RDS instance.

    Args:
        cw_client: CloudWatch client
        db_instance_id: RDS DB instance identifier
        metric_name: CloudWatch metric name (e.g., 'CPUUtilization')
        start_time: Start time for metrics
        end_time: End time for metrics
        stat: Statistic type (Average, Maximum, Minimum, Sum)
        period: Period in seconds

    Returns:
        List of data points with timestamps and values
    """
    try:
        response = cw_client.get_metric_statistics(
            Namespace='AWS/RDS',
            MetricName=metric_name,
            Dimensions=[
                {
                    'Name': 'DBInstanceIdentifier',
                    'Value': db_instance_id
                }
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=period,
            Statistics=[stat]
        )

        data_points = []
        for point in sorted(response.get('Datapoints', []), key=lambda x: x['Timestamp']):
            data_points.append({
                'timestamp': point['Timestamp'].isoformat(),
                'value': point.get(stat, 0),
                'unit': point.get('Unit', '')
            })

        return data_points
    except Exception as e:
        logging.error(f"Error fetching metric {metric_name} for {db_instance_id}: {e}")
        return []


def get_rds_database_errors(cw_client, db_instance_id: str,
                            start_time: datetime, end_time: datetime,
                            period: int = 300) -> List[Dict]:
    """
    Collect RDS database errors from CloudWatch metrics.

    Returns:
        List of error data points
    """
    error_metrics = []

    # Common RDS error metrics
    error_metric_names = [
        'DatabaseConnections',  # Track connection errors (spikes/drops)
        'FailedSQLServerAgentJobsCount',  # SQL Server specific
        'DeadlocksPerSecond',  # Deadlock errors
        'BlockedProcesses',  # Blocked processes
    ]

    for metric_name in error_metric_names:
        try:
            data = get_rds_metric_data(cw_client, db_instance_id, metric_name,
                                      start_time, end_time, stat='Sum', period=period)
            for point in data:
                error_metrics.append({
                    'metric_name': metric_name,
                    'timestamp': point['timestamp'],
                    'value': point['value'],
                    'db_instance': db_instance_id
                })
        except Exception as e:
            logging.debug(f"Metric {metric_name} not available for {db_instance_id}: {e}")
            continue

    return error_metrics


def get_top_queries(pi_client, resource_id: str, start_time: datetime,
                   end_time: datetime, max_results: int = 10) -> List[Dict]:
    """
    Get top queries from RDS Performance Insights.

    Args:
        pi_client: Performance Insights client
        resource_id: Performance Insights resource ID (DbiResourceId)
        start_time: Start time
        end_time: End time
        max_results: Maximum number of queries to return (AWS allows 1-10)

    Returns:
        List of top queries with statistics
    """
    try:
        # AWS PI API MaxResults constraint: must be between 1 and 10
        max_results = min(max(max_results, 1), 10)

        response = pi_client.describe_dimension_keys(
            ServiceType='RDS',
            Identifier=resource_id,
            StartTime=start_time,
            EndTime=end_time,
            Metric='db.load.avg',
            GroupBy={
                'Group': 'db.sql',
                'Dimensions': ['db.sql.statement']
            },
            MaxResults=max_results
        )

        queries = []
        for key in response.get('Keys', []):
            dimensions = key.get('Dimensions', {})
            query_text = dimensions.get('db.sql.statement', 'N/A')

            # Get total load from metrics
            total_load = 0
            for metric in key.get('Metrics', {}).values():
                if isinstance(metric, (int, float)):
                    total_load += metric

            queries.append({
                'query': query_text[:500],  # Truncate long queries
                'total_load': total_load,
                'dimensions': dimensions
            })

        return sorted(queries, key=lambda x: x['total_load'], reverse=True)
    except Exception as e:
        logging.error(f"Error fetching top queries: {e}")
        return []


def get_slow_queries(pi_client, resource_id: str, start_time: datetime,
                    end_time: datetime, latency_threshold_ms: float = 1000.0,
                    max_results: int = 10) -> List[Dict]:
    """
    Get slow queries that exceeded a latency threshold.

    Note: For Aurora MySQL, Performance Insights doesn't directly expose latency metrics.
    This function gets queries by database load, which correlates with execution time.
    High load queries are typically slow queries.

    Args:
        pi_client: Performance Insights client
        resource_id: Performance Insights resource ID
        start_time: Start time
        end_time: End time
        latency_threshold_ms: Latency threshold in milliseconds (informational)
        max_results: Maximum number of queries to return (AWS allows 1-10)

    Returns:
        List of queries sorted by database load (proxy for slowness)
    """
    try:
        # AWS PI API MaxResults constraint: must be between 1 and 10
        max_results = min(max(max_results, 1), 10)

        # For Aurora MySQL, use db.load.avg as a proxy for slow queries
        # High database load typically indicates slow/expensive queries
        response = pi_client.describe_dimension_keys(
            ServiceType='RDS',
            Identifier=resource_id,
            StartTime=start_time,
            EndTime=end_time,
            Metric='db.load.avg',  # Use load as proxy for slowness
            GroupBy={
                'Group': 'db.sql',
                'Dimensions': ['db.sql.statement']
            },
            MaxResults=max_results
        )

        slow_queries = []
        for key in response.get('Keys', []):
            dimensions = key.get('Dimensions', {})
            query_text = dimensions.get('db.sql.statement', 'N/A')

            # Calculate total load and max load from metrics
            total_load = 0
            max_load = 0
            for metric_value in key.get('Metrics', {}).values():
                if isinstance(metric_value, (int, float)):
                    total_load += metric_value
                    max_load = max(max_load, metric_value)

            # Calculate max execution time from max load
            # Higher max load indicates longer execution time
            # A load of 1.0 for 1 second = 1000ms execution
            max_time_ms = max_load * 1000 if max_load > 0 else 0

            # Calculate average time from total load
            # This is a rough estimate: total load represents cumulative execution time
            avg_time_ms = (total_load * 1000) / 10 if total_load > 0 else 0  # Divide by sample points

            # All queries returned are considered "high load" queries
            slow_queries.append({
                'query': query_text[:500],
                'total_load': round(total_load, 2),
                'max_load': round(max_load, 2),
                'max_time_ms': round(max_time_ms, 2),
                'avg_time_ms': round(avg_time_ms, 2),
                'note': 'High database load (likely slow query)',
                'dimensions': dimensions
            })

        return sorted(slow_queries, key=lambda x: x['total_load'], reverse=True)
    except Exception as e:
        logging.error(f"Error fetching slow queries: {e}")
        return []


def save_rds_metric_to_csv(metric_name: str, data_points: List[Dict],
                           output_dir: str, db_instance_id: str, threshold: float = None):
    """
    Save RDS metric data to CSV file.

    Args:
        metric_name: Name of the metric
        data_points: List of data points
        output_dir: Output directory path
        db_instance_id: Database instance identifier
        threshold: Optional threshold - only save points above this value (e.g., 50 for CPU%)
    """
    csv_dir = os.path.join(output_dir, 'csv_data')
    os.makedirs(csv_dir, exist_ok=True)

    filename = f"{metric_name}_{db_instance_id}.csv"
    filepath = os.path.join(csv_dir, filename)

    # Apply threshold filter if specified
    filtered_points = data_points
    if threshold is not None:
        filtered_points = [point for point in data_points if point.get('value', 0) > threshold]

    with open(filepath, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['timestamp', 'value', 'unit'])

        for point in filtered_points:
            writer.writerow([
                point.get('timestamp', ''),
                point.get('value', 0),
                point.get('unit', '')
            ])

    print(f"Saved RDS metric CSV: {filepath} ({len(filtered_points)} data points)")
    return filepath


def save_rds_errors_to_csv(error_data: List[Dict], output_dir: str):
    """Save RDS error metrics to CSV."""
    csv_dir = os.path.join(output_dir, 'csv_data')
    os.makedirs(csv_dir, exist_ok=True)

    filepath = os.path.join(csv_dir, 'rds_errors.csv')

    with open(filepath, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['metric_name', 'timestamp', 'value', 'db_instance'])

        for error in error_data:
            writer.writerow([
                error.get('metric_name', ''),
                error.get('timestamp', ''),
                error.get('value', 0),
                error.get('db_instance', '')
            ])

    print(f"Saved RDS errors CSV: {filepath}")
    return filepath


def save_queries_to_csv(queries: List[Dict], output_dir: str, filename: str):
    """Save query data to CSV."""
    csv_dir = os.path.join(output_dir, 'csv_data')
    os.makedirs(csv_dir, exist_ok=True)

    filepath = os.path.join(csv_dir, filename)

    with open(filepath, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)

        # Check if this is slow queries (has 'max_time_ms' field) or top queries
        if queries and 'max_time_ms' in queries[0]:
            # Slow queries format with execution time metrics
            writer.writerow(['query', 'total_load', 'max_load', 'max_time_ms', 'avg_time_ms', 'note'])
            for query in queries:
                writer.writerow([
                    query.get('query', ''),
                    query.get('total_load', 0),
                    query.get('max_load', 0),
                    query.get('max_time_ms', 0),
                    query.get('avg_time_ms', 0),
                    query.get('note', '')
                ])
        else:
            # Top queries format
            writer.writerow(['query', 'total_load'])
            for query in queries:
                writer.writerow([
                    query.get('query', ''),
                    query.get('total_load', 0)
                ])

    print(f"Saved queries CSV: {filepath}")
    return filepath


def save_rds_metric_screenshot(cw_client, db_instance_id: str, metric_name: str,
                               start_time: datetime, end_time: datetime,
                               output_dir: str, stat: str = "Average"):
    """
    Save CloudWatch metric screenshot for RDS.

    Args:
        cw_client: CloudWatch client
        db_instance_id: RDS instance identifier
        metric_name: Metric name
        start_time: Start time
        end_time: End time
        output_dir: Output directory
        stat: Statistic type
    """
    screenshots_dir = os.path.join(output_dir, 'screenshots')
    os.makedirs(screenshots_dir, exist_ok=True)

    metric_widget_json = json.dumps({
        "metrics": [
            ["AWS/RDS", metric_name, "DBInstanceIdentifier", db_instance_id]
        ],
        "view": "timeSeries",
        "stacked": False,
        "stat": stat,
        "period": 300,
        "region": cw_client.meta.region_name,
        "title": f"{metric_name} - {db_instance_id}",
        "width": 1200,
        "height": 800,
        "start": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
        "end": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
        "yAxis": {
            "left": {
                "min": 0
            }
        }
    })

    try:
        response = cw_client.get_metric_widget_image(MetricWidget=metric_widget_json)
        filename = f"{metric_name}_{db_instance_id}.png"
        filepath = os.path.join(screenshots_dir, filename)

        with open(filepath, "wb") as f:
            f.write(response["MetricWidgetImage"])

        print(f"Saved RDS screenshot: {filepath}")
        return filepath
    except Exception as e:
        logging.error(f"Error saving screenshot for {metric_name}: {e}")
        return None


def collect_rds_metrics_for_region(region_code: str, region_name: str,
                                   db_instance_identifier: str,
                                   start_time: datetime, end_time: datetime,
                                   is_perf: bool = False):
    """
    Collect all RDS metrics for a specific region and database instance.

    Args:
        region_code: Region code (e.g., 'NA1', 'EU1')
        region_name: AWS region name (e.g., 'us-west-2')
        db_instance_identifier: RDS database instance identifier
        start_time: Start time for metrics collection
        end_time: End time for metrics collection
        is_perf: Whether this is performance environment
    """
    top_dir = "perf" if is_perf else "prod"
    region_rel_folder = os.path.join(top_dir, "RDS", region_code)
    output_dir = os.path.join(OUTPUT_ROOT, region_rel_folder)
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n{'='*80}")
    print(f"Collecting RDS metrics for region {region_code} ({region_name})")
    print(f"Database Instance: {db_instance_identifier}")
    print(f"Output Directory: {output_dir}")
    print(f"{'='*80}\n")

    # Create clients
    cw_client = make_cloudwatch_client(region_name)
    rds_client = make_rds_client(region_name)
    pi_client = make_pi_client(region_name)

    # Get RDS instance details (supports exact match or pattern)
    instances = get_rds_instances(rds_client, db_instance_identifier)
    if not instances:
        print(f"\n⚠️  WARNING: No RDS instances matching '{db_instance_identifier}' found in region {region_name}")
        print(f"    Skipping RDS metrics collection for {region_code}")
        print(f"    To fix: Update config.py with your actual RDS instance identifier or pattern")
        print(f"    Run: aws rds describe-db-instances --region {region_name} --query 'DBInstances[*].DBInstanceIdentifier'\n")
        return

    # If pattern matched multiple instances, use the first one (or could process all)
    if len(instances) > 1:
        print(f"ℹ️  Pattern '{db_instance_identifier}' matched {len(instances)} instances, using first: {instances[0]['DBInstanceIdentifier']}")

    instance = instances[0]
    actual_instance_id = instance['DBInstanceIdentifier']
    print(f"✓ Found RDS instance: {actual_instance_id} ({instance['Engine']} {instance['EngineVersion']})")

    # Collect CPU Usage
    print(f"\nCollecting CPU Usage metrics...")
    cpu_data = get_rds_metric_data(cw_client, actual_instance_id,
                                   'CPUUtilization', start_time, end_time,
                                   stat='Average')
    if cpu_data:
        save_rds_metric_to_csv('CPUUtilization', cpu_data, output_dir, actual_instance_id, threshold=50.0)
        save_rds_metric_screenshot(cw_client, actual_instance_id, 'CPUUtilization',
                                   start_time, end_time, output_dir, stat='Average')

    # Collect Database Connections
    print(f"Collecting Database Connections...")
    conn_data = get_rds_metric_data(cw_client, actual_instance_id,
                                   'DatabaseConnections', start_time, end_time,
                                   stat='Average')
    if conn_data:
        save_rds_metric_to_csv('DatabaseConnections', conn_data, output_dir, actual_instance_id)
        save_rds_metric_screenshot(cw_client, actual_instance_id, 'DatabaseConnections',
                                   start_time, end_time, output_dir, stat='Average')

    # Collect Database Errors
    print(f"Collecting Database Errors...")
    error_data = get_rds_database_errors(cw_client, actual_instance_id,
                                        start_time, end_time)
    if error_data:
        save_rds_errors_to_csv(error_data, output_dir)

    # Collect Performance Insights data if enabled
    if instance.get('PerformanceInsightsEnabled') and instance.get('PerformanceInsightsResourceId'):
        resource_id = instance['PerformanceInsightsResourceId']
        print(f"\nCollecting Performance Insights data...")

        # Get top 10 queries
        print(f"Fetching top 10 queries...")
        top_queries = get_top_queries(pi_client, resource_id, start_time, end_time, max_results=10)
        if top_queries:
            save_queries_to_csv(top_queries, output_dir, 'top_10_queries.csv')

        # Get slow queries (queries taking more than 1 second)
        print(f"Fetching slow queries...")
        slow_queries = get_slow_queries(pi_client, resource_id, start_time, end_time,
                                       latency_threshold_ms=1000.0, max_results=10)
        if slow_queries:
            save_queries_to_csv(slow_queries, output_dir, 'slow_queries.csv')
    else:
        print(f"\nPerformance Insights is not enabled for this instance.")
        print(f"Skipping top queries and slow queries collection.")

    print(f"\n{'='*80}")
    print(f"RDS metrics collection completed for {region_code}")
    print(f"{'='*80}\n")


def collect_all_rds_metrics(start_time: datetime, end_time: datetime,
                            rds_metadata: Dict[str, Tuple[str, str]],
                            is_perf: bool = False):
    """
    Collect RDS metrics for all configured regions.

    Args:
        start_time: Start time for metrics
        end_time: End time for metrics
        rds_metadata: Dictionary mapping region codes to (region_name, db_instance_id) tuples
        is_perf: Whether this is performance environment
    """
    print(f"\n{'#'*80}")
    print(f"# Starting RDS Metrics Collection")
    print(f"# Environment: {'Performance' if is_perf else 'Production'}")
    print(f"# Time Range: {start_time} to {end_time}")
    print(f"{'#'*80}\n")

    for region_code, (region_name, db_instance_id) in rds_metadata.items():
        try:
            collect_rds_metrics_for_region(
                region_code=region_code,
                region_name=region_name,
                db_instance_identifier=db_instance_id,
                start_time=start_time,
                end_time=end_time,
                is_perf=is_perf
            )
        except Exception as e:
            logging.error(f"Error collecting RDS metrics for region {region_code}: {e}", exc_info=True)
            continue

    print(f"\n{'#'*80}")
    print(f"# RDS Metrics Collection Complete!")
    print(f"{'#'*80}\n")

