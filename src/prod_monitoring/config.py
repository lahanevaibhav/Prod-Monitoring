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

