"""
Unified Configuration Loader
Loads ALL configuration from config.ini
"""

import os
import configparser
import logging
from typing import Dict, Tuple, List

logger = logging.getLogger(__name__)

# Find config file
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "config.ini")

# Load configuration
config = configparser.ConfigParser()
if os.path.exists(CONFIG_FILE):
    config.read(CONFIG_FILE)
    logger.info(f"Loaded configuration from {CONFIG_FILE}")
else:
    logger.warning(f"Config file not found: {CONFIG_FILE}")
    config = None


def get_config(key: str, default=None, section="DEFAULT"):
    """Get configuration value"""
    if config and config.has_option(section, key):
        return config.get(section, key)
    return os.getenv(key, default)


def get_bool(key: str, default=False, section="DEFAULT"):
    """Get boolean configuration value"""
    if config and config.has_option(section, key):
        return config.getboolean(section, key)
    return os.getenv(key, str(default)).lower() in ('true', '1', 'yes', 'on')


def get_int(key: str, default=0, section="DEFAULT"):
    """Get integer configuration value"""
    if config and config.has_option(section, key):
        return config.getint(section, key)
    try:
        return int(os.getenv(key, default))
    except:
        return default


# ============================================================================
# AWS AUTHENTICATION
# ============================================================================
# Using default AWS profile (credentials stored via PowerShell script)
AWS_REGION = get_config("AWS_REGION", "us-west-2")

# ============================================================================
# AI ANALYSIS
# ============================================================================
ENABLE_AI_ANALYSIS = get_bool("ENABLE_AI_ANALYSIS", True)
LAMBDA_FUNCTION_NAME = get_config("LAMBDA_FUNCTION_NAME")  # Deprecated - use API Gateway instead
LAMBDA_API_ENDPOINT = get_config("LAMBDA_API_ENDPOINT")
LAMBDA_API_KEY = get_config("LAMBDA_API_KEY")
LAMBDA_TIMEOUT = get_int("LAMBDA_TIMEOUT", 60)
APPLICATION_CONTEXT_FILE = get_config("APPLICATION_CONTEXT_FILE", "application_context.txt")
MIN_ERRORS_FOR_AI_ANALYSIS = get_int("MIN_ERRORS_FOR_AI_ANALYSIS", 1)

# ============================================================================
# DATA COLLECTION
# ============================================================================
IS_PERFORMANCE_MODE = get_bool("IS_PERFORMANCE_MODE", False)
START_DAYS_BACK = get_int("START_DAYS_BACK", 2)
END_DAYS_BACK = get_int("END_DAYS_BACK", 1)
MAX_LOG_ENTRIES = get_int("MAX_LOG_ENTRIES", 10000)
METRIC_PERIOD = get_int("METRIC_PERIOD", 300)

# ============================================================================
# SERVICE ENABLEMENT
# ============================================================================
ENABLE_SRA = get_bool("ENABLE_SRA", True)
ENABLE_SRM = get_bool("ENABLE_SRM", True)
ENABLE_SCREENSHOTS = get_bool("ENABLE_SCREENSHOTS", True)

# ============================================================================
# OUTPUT SETTINGS
# ============================================================================
GENERATE_PDF_REPORT = get_bool("GENERATE_PDF_REPORT", True)
OUTPUT_DIR = get_config("OUTPUT_DIR", "output")
KEEP_INDIVIDUAL_CSVS = get_bool("KEEP_INDIVIDUAL_CSVS", False)
SCREENSHOT_FORMAT = get_config("SCREENSHOT_FORMAT", "png")

# ============================================================================
# ADVANCED SETTINGS
# ============================================================================
MAX_RETRIES = get_int("MAX_RETRIES", 3)
RETRY_DELAY_SECONDS = get_int("RETRY_DELAY_SECONDS", 2)
MAX_PARALLEL_REGIONS = get_int("MAX_PARALLEL_REGIONS", 5)
LOG_LEVEL = get_config("LOG_LEVEL", "INFO")

# ============================================================================
# PDF SETTINGS
# ============================================================================
PDF_TITLE = get_config("PDF_TITLE", "AWS Production Monitoring Report")
PDF_INCLUDE_SCREENSHOTS = get_bool("PDF_INCLUDE_SCREENSHOTS", True)
PDF_INCLUDE_AI_ANALYSIS = get_bool("PDF_INCLUDE_AI_ANALYSIS", True)
PDF_PAGE_SIZE = get_config("PDF_PAGE_SIZE", "A4")
PDF_FONT_SIZE = get_int("PDF_FONT_SIZE", 10)

# ============================================================================
# SERVICE METADATA PARSING
# ============================================================================

def parse_service_metadata(prefix: str) -> Dict[str, Tuple[str, str, str]]:
    """
    Parse service metadata from config

    Args:
        prefix: Config key prefix (e.g., 'SRA_PROD', 'SRM_PERF')

    Returns:
        Dict mapping region code to (dashboard_name, aws_region, log_group)
    """
    metadata = {}

    if not config:
        return metadata

    for key in config.defaults():
        if key.startswith(prefix.lower() + "_"):
            # Extract region code (e.g., SRA_PROD_AU -> AU)
            region_code = key[len(prefix)+1:].upper()

            # Parse value: dashboard_name,aws_region,log_group
            value = config.get("DEFAULT", key)
            parts = [p.strip() for p in value.split(",")]

            if len(parts) == 3:
                metadata[region_code] = tuple(parts)
            else:
                logger.warning(f"Invalid metadata format for {key}: {value}")

    return metadata


# ============================================================================
# LOAD SERVICE METADATA
# ============================================================================

# SRA Production
METADATA_SRA_PROD = parse_service_metadata("SRA_PROD")

# SRM Production
METADATA_SRM_PROD = parse_service_metadata("SRM_PROD")

# SRA Performance
METADATA_SRA_PERF = parse_service_metadata("SRA_PERF")

# SRM Performance
METADATA_SRM_PERF = parse_service_metadata("SRM_PERF")

# ============================================================================
# SERVICE MAPPINGS
# ============================================================================

SERVICES_METADATA = {
    "SRA": METADATA_SRA_PROD,
    "SRM": METADATA_SRM_PROD
}

SERVICES_METADATA_PERF = {
    "SRA": METADATA_SRA_PERF,
    "SRM": METADATA_SRM_PERF
}


# Metric period for CloudWatch (for backward compatibility)
PERIOD = METRIC_PERIOD

# ============================================================================
# VALIDATION
# ============================================================================

def validate_config():
    """Validate critical configuration"""
    issues = []

    if ENABLE_AI_ANALYSIS and not LAMBDA_API_ENDPOINT:
        issues.append("AI_ANALYSIS enabled but LAMBDA_API_ENDPOINT not set")

    if ENABLE_SRA and not METADATA_SRA_PROD and not METADATA_SRA_PERF:
        issues.append("SRA enabled but no regions configured")

    if ENABLE_SRM and not METADATA_SRM_PROD and not METADATA_SRM_PERF:
        issues.append("SRM enabled but no regions configured")

    if issues:
        logger.warning("Configuration issues found:")
        for issue in issues:
            logger.warning(f"  - {issue}")

    return len(issues) == 0


# Validate on import
validate_config()

