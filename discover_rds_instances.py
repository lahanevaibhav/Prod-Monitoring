"""
RDS Instance Discovery Tool

This script helps you find your RDS instances across different AWS regions
so you can configure them in config.py for metrics collection.
"""

import boto3
from typing import Dict, List

# Common AWS regions
REGIONS = [
    'us-west-2',      # NA1 (Oregon)
    'us-east-1',      # NA1 (Virginia)
    'ap-southeast-2', # AU (Sydney)
    'ca-central-1',   # CA (Canada)
    'ap-northeast-1', # JP (Tokyo)
    'eu-central-1',   # DE (Frankfurt)
    'eu-west-2',      # UK (London)
]


def discover_rds_instances_in_region(region_name: str) -> List[Dict]:
    """
    Discover RDS instances in a specific region.

    Returns:
        List of RDS instance information
    """
    try:
        rds_client = boto3.client('rds', region_name=region_name)
        response = rds_client.describe_db_instances()

        instances = []
        for db in response.get('DBInstances', []):
            instances.append({
                'identifier': db['DBInstanceIdentifier'],
                'engine': db['Engine'],
                'engine_version': db['EngineVersion'],
                'instance_class': db['DBInstanceClass'],
                'status': db['DBInstanceStatus'],
                'multi_az': db.get('MultiAZ', False),
                'performance_insights': db.get('PerformanceInsightsEnabled', False),
                'endpoint': db.get('Endpoint', {}).get('Address', 'N/A'),
            })

        return instances
    except Exception as e:
        print(f"  Error accessing region {region_name}: {e}")
        return []


def discover_all_rds_instances():
    """
    Discover RDS instances across all configured regions.
    """
    print("="*80)
    print("RDS Instance Discovery Tool")
    print("="*80)
    print("\nScanning AWS regions for RDS instances...\n")

    all_instances = {}
    total_instances = 0

    for region in REGIONS:
        print(f"Checking {region}...", end=" ")
        instances = discover_rds_instances_in_region(region)

        if instances:
            all_instances[region] = instances
            total_instances += len(instances)
            print(f"✓ Found {len(instances)} instance(s)")
        else:
            print("No instances")

    print(f"\n{'='*80}")
    print(f"Total RDS Instances Found: {total_instances}")
    print(f"{'='*80}\n")

    if total_instances == 0:
        print("⚠️  No RDS instances found in any region.")
        print("\nPossible reasons:")
        print("  1. No RDS instances exist in your AWS account")
        print("  2. AWS credentials are not configured correctly")
        print("  3. IAM permissions don't allow RDS describe operations")
        print("\nTo verify AWS credentials:")
        print("  aws sts get-caller-identity")
        print("\nTo check RDS permissions:")
        print("  aws rds describe-db-instances --region us-west-2")
        return

    # Display detailed information
    for region, instances in all_instances.items():
        print(f"\n{'─'*80}")
        print(f"Region: {region}")
        print(f"{'─'*80}")

        for idx, instance in enumerate(instances, 1):
            print(f"\n  Instance {idx}:")
            print(f"    Identifier:          {instance['identifier']}")
            print(f"    Engine:              {instance['engine']} {instance['engine_version']}")
            print(f"    Instance Class:      {instance['instance_class']}")
            print(f"    Status:              {instance['status']}")
            print(f"    Multi-AZ:            {instance['multi_az']}")
            print(f"    Performance Insights: {instance['performance_insights']}")
            print(f"    Endpoint:            {instance['endpoint']}")

    # Generate config.py snippet
    print(f"\n{'='*80}")
    print("Configuration Snippet for config.py")
    print(f"{'='*80}\n")

    print("# Copy this to your config.py file:\n")
    print("METRICS_METADATA_RDS = {")

    region_codes = {
        'us-west-2': 'NA1',
        'us-east-1': 'NA1_EAST',
        'ap-southeast-2': 'AU',
        'ca-central-1': 'CA',
        'ap-northeast-1': 'JP',
        'eu-central-1': 'DE',
        'eu-west-2': 'UK',
    }

    for region, instances in all_instances.items():
        region_code = region_codes.get(region, region.upper().replace('-', '_'))

        for instance in instances:
            identifier = instance['identifier']
            pi_status = "✓ PI enabled" if instance['performance_insights'] else "✗ PI disabled"
            print(f'    "{region_code}": ("{region}", "{identifier}"),  # {instance["engine"]} - {pi_status}')

    print("}\n")

    # Performance Insights summary
    pi_enabled = sum(1 for instances in all_instances.values()
                     for instance in instances if instance['performance_insights'])

    if pi_enabled > 0:
        print(f"✓ {pi_enabled} instance(s) have Performance Insights enabled")
        print("  (Top queries and slow queries will be collected)")

    if total_instances - pi_enabled > 0:
        print(f"\n⚠️  {total_instances - pi_enabled} instance(s) do not have Performance Insights enabled")
        print("  (Top queries and slow queries will be skipped)")
        print("\nTo enable Performance Insights:")
        print("  AWS Console → RDS → Modify Instance → Enable Performance Insights")


def main():
    """Main entry point."""
    try:
        # Test AWS credentials first
        print("Testing AWS credentials...", end=" ")
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print(f"✓ Connected as: {identity['Arn']}\n")

        # Discover instances
        discover_all_rds_instances()

    except Exception as e:
        print(f"\n✗ Error: {e}\n")
        print("Please ensure:")
        print("  1. AWS credentials are configured (run: aws configure)")
        print("  2. You have permissions to describe RDS instances")
        print("  3. You're connected to the internet")


if __name__ == "__main__":
    main()

