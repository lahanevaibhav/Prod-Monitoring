"""
Consolidate existing monitoring data into a single unified report.
Run this script to generate consolidated reports from previously collected data.
"""

import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from prod_monitoring.consolidator import consolidate_monitoring_data


def main():
    """Main entry point for consolidation script"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Consolidate AWS monitoring data into unified reports'
    )
    parser.add_argument(
        '--environment', '-e',
        choices=['prod', 'perf'],
        default='prod',
        help='Environment to consolidate (default: prod)'
    )
    parser.add_argument(
        '--json-only',
        action='store_true',
        help='Generate only JSON report (skip Markdown)'
    )
    parser.add_argument(
        '--markdown-only',
        action='store_true',
        help='Generate only Markdown report (skip JSON)'
    )

    args = parser.parse_args()

    # Determine output formats
    save_json = not args.markdown_only
    save_markdown = not args.json_only

    # Run consolidation
    consolidate_monitoring_data(
        environment=args.environment,
        save_json=save_json,
        save_markdown=save_markdown
    )


if __name__ == "__main__":
    main()

