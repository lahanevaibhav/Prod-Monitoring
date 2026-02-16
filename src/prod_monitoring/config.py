"""
Configuration file for production monitoring metrics metadata.

This file contains the region metadata mappings for different services (SRA, SRM)
and environments (production, performance).

Each region entry is a tuple of: (dashboard_name, aws_region, log_group)
"""

# Production metadata for SRA
METRICS_METADATA_SRA = {
    # "NA1": ("test-SRA-Dashboard", "us-west-2", "test-schedule-rules-automation"),
    # "AU": ("production-au-SRA-Dashboard", "ap-southeast-2", "production-au-schedule-rules-automation"),
    # "CA": ("production-ca-SRA-Dashboard", "ca-central-1", "production-ca-schedule-rules-automation"),
    # "JP": ("production-jp-SRA-Dashboard", "ap-northeast-1", "production-jp-schedule-rules-automation"),
    # "DE": ("production-de-SRA-Dashboard", "eu-central-1", "production-de-schedule-rules-automation"),
    # "UK": ("production-uk-SRA-Dashboard", "eu-west-2", "production-uk-schedule-rules-automation")
}

# Production metadata for SRM
METRICS_METADATA_SRM = {
    "NA1": ("test-SRM-Dashboard", "us-west-2", "test-schedule-requests-manager"),
    # "AU": ("production-au-SRM-Dashboard", "ap-southeast-2", "production-au-schedule-requests-manager"),
    # "CA": ("production-ca-SRM-Dashboard", "ca-central-1", "production-ca-schedule-requests-manager"),
    # "JP": ("production-jp-SRM-Dashboard", "ap-northeast-1", "production-jp-schedule-requests-manager"),
    # "DE": ("production-de-SRM-Dashboard", "eu-central-1", "production-de-schedule-requests-manager"),
    # "UK": ("production-uk-SRM-Dashboard", "eu-west-2", "production-uk-schedule-requests-manager")
}

# Performance environment metadata for SRA (for now only NA1 is present)
METRICS_METADATA_SRA_PERF = {
    "NA1": ("perf-wcx-SRA-Dashboard", "us-west-2", "perf-wcx-schedule-rules-automation")
}

# Performance environment metadata for SRM (for now only NA1 is present)
METRICS_METADATA_SRM_PERF = {
    "NA1": ("perf-wcx-SRM-Dashboard", "us-west-2", "perf-wcx-schedule-requests-manager")
}

# Service metadata mapping for production environment
SERVICES_METADATA = {
    "SRA": METRICS_METADATA_SRA,
    "SRM": METRICS_METADATA_SRM
}

# Service metadata mapping for performance environment
SERVICES_METADATA_PERF = {
    "SRA": METRICS_METADATA_SRA_PERF,
    "SRM": METRICS_METADATA_SRM_PERF
}

# CloudWatch metric period in seconds
PERIOD = 300

# ============================================================================
# RDS CONFIGURATION
# ============================================================================
# To enable RDS metrics collection:
# 1. Find your RDS instance identifiers:
#    aws rds describe-db-instances --region us-west-2 --query 'DBInstances[*].DBInstanceIdentifier'
# 2. Update the dictionaries below with your actual instance names
# 3. Comment out or remove regions you don't want to collect
#
# Format: "REGION_CODE": ("aws_region", "db_instance_identifier")
# ============================================================================

# RDS metadata for production environment
# WFM Test instances with Performance Insights enabled
METRICS_METADATA_RDS = {
    # WFM Test instances (both have Performance Insights - queries will be collected!)
    "NA1_WFM_1": ("us-west-2", "test-wfm-storage-wfmaurora57instance1-7ynzsbxgvvab"),
    "NA1_WFM_2": ("us-west-2", "test-wfm-storage-wfmaurora57instance2-nqqtzm9ousss"),

    # Additional options (uncomment to enable):
    # Development WFM instances
    # "NA1_DEV_WFM_1": ("us-west-2", "dev-wfm-storage-wfmaurora57instance1-ljzijyljuarm"),
    # "NA1_DEV_WFM_2": ("us-west-2", "dev-wfm-storage-wfmaurora57instance2-xb028zp22hnx"),

    # Test Platform Storage
    # "NA1_PLATFORM_1": ("us-west-2", "test-platform-storage-rds-aurorainstance4-ygr4nstbk5h2"),
    # "NA1_PLATFORM_2": ("us-west-2", "test-platform-storage-rds-aurorainstance5-vy4oabrxqzfl"),
}

# RDS metadata for performance environment
METRICS_METADATA_RDS_PERF = {
    # Uncomment and update with your actual RDS instance:
    # "NA1": ("us-west-2", "perf-wcx-rds-instance")
}

