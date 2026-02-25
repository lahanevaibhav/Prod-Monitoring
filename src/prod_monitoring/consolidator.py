"""
Consolidator Module - Creates unified monitoring report
Consolidates all AWS data and AI analysis into a single comprehensive file
"""

import os
import json
import csv
import shutil
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Base output directory
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
OUTPUT_ROOT = os.path.join(REPO_ROOT, "output")


class MonitoringConsolidator:
    """Consolidates all monitoring data into a single comprehensive report"""

    def __init__(self, environment: str = "prod"):
        """
        Initialize consolidator

        Args:
            environment: Environment name ('prod' or 'perf')
        """
        self.environment = environment
        self.env_path = os.path.join(OUTPUT_ROOT, environment)
        self.consolidated_data: Dict[str, Any] = {
            "metadata": {
                "environment": environment,
                "generated_at": datetime.now().isoformat(),
                "report_version": "2.0"
            },
            "services": {}
        }

    def collect_all_data(self) -> Dict:
        """
        Collect all monitoring data from the environment directory

        Returns:
            Dictionary containing all consolidated data
        """
        if not os.path.exists(self.env_path):
            print(f"⚠️  Environment path not found: {self.env_path}")
            return self.consolidated_data

        # Process each service (SRA, SRM, RDS)
        for service_name in os.listdir(self.env_path):
            service_path = os.path.join(self.env_path, service_name)

            if not os.path.isdir(service_path):
                continue

            if service_name in ["SRA", "SRM"]:
                self._collect_service_data(service_name, service_path)
            elif service_name == "RDS":
                self._collect_rds_data(service_path)

        return self.consolidated_data

    def _collect_service_data(self, service_name: str, service_path: str):
        """Collect data for SRA/SRM service across all regions"""
        if service_name not in self.consolidated_data["services"]:
            self.consolidated_data["services"][service_name] = {
                "regions": {}
            }

        # Process each region
        for region_name in os.listdir(service_path):
            region_path = os.path.join(service_path, region_name)

            if not os.path.isdir(region_path):
                continue

            print(f"  📂 Collecting {service_name}/{region_name}...")

            region_data = {
                "csv_data": {},
                "ai_analysis": None,
                "screenshots": [],
                "metrics_summary": {}
            }

            # Collect CSV data
            csv_dir = os.path.join(region_path, "csv_data")
            if os.path.exists(csv_dir):
                region_data["csv_data"] = self._collect_csv_data(csv_dir)

                # Collect AI analysis
                region_data["ai_analysis"] = self._collect_ai_analysis(csv_dir)

            # Collect screenshots
            screenshots_dir = os.path.join(region_path, "screenshots")
            if os.path.exists(screenshots_dir):
                region_data["screenshots"] = self._list_screenshots(screenshots_dir)

            # Generate metrics summary
            region_data["metrics_summary"] = self._generate_metrics_summary(region_data["csv_data"])

            self.consolidated_data["services"][service_name]["regions"][region_name] = region_data


    def _collect_csv_data(self, csv_dir: str) -> Dict[str, List[Dict]]:
        """Collect all CSV files from a directory"""
        csv_data = {}

        if not os.path.exists(csv_dir):
            return csv_data

        for filename in os.listdir(csv_dir):
            if filename.endswith('.csv'):
                filepath = os.path.join(csv_dir, filename)
                csv_name = os.path.splitext(filename)[0]

                try:
                    with open(filepath, 'r', encoding='utf-8', newline='') as f:
                        reader = csv.DictReader(f)
                        csv_data[csv_name] = list(reader)
                except Exception as e:
                    print(f"    ⚠️  Error reading {filename}: {e}")
                    csv_data[csv_name] = []

        return csv_data

    def _collect_ai_analysis(self, csv_dir: str) -> Optional[Dict]:
        """Collect AI analysis from JSON file"""
        ai_json_path = os.path.join(csv_dir, "ai_analysis.json")

        if os.path.exists(ai_json_path):
            try:
                with open(ai_json_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"    ⚠️  Error reading AI analysis: {e}")
                return None

        return None

    def _list_screenshots(self, screenshots_dir: str) -> List[str]:
        """List all screenshot files"""
        screenshots = []

        if not os.path.exists(screenshots_dir):
            return screenshots

        for filename in os.listdir(screenshots_dir):
            if filename.endswith('.png'):
                screenshots.append(filename)

        return sorted(screenshots)

    def _generate_metrics_summary(self, csv_data: Dict[str, List[Dict]]) -> Dict:
        """Generate summary statistics from CSV data"""
        summary = {
            "total_errors": 0,
            "unique_error_patterns": 0,
            "metrics_collected": len(csv_data),
            "high_cpu_count": 0,
            "high_memory_count": 0,
            "performance_issues": 0
        }

        # Count errors from classified_errors
        if "classified_errors" in csv_data:
            summary["unique_error_patterns"] = len(csv_data["classified_errors"])
            for error in csv_data["classified_errors"]:
                count = error.get("Occurrence Count", 0)
                try:
                    summary["total_errors"] += int(count)
                except (ValueError, TypeError):
                    pass

        # Count performance issues from metrics
        for metric_name, metric_data in csv_data.items():
            if "cpu" in metric_name.lower():
                for row in metric_data:
                    try:
                        value = float(row.get("value", 0))
                        if value > 80:  # CPU > 80%
                            summary["high_cpu_count"] += 1
                    except (ValueError, TypeError):
                        pass

            if "memory" in metric_name.lower():
                for row in metric_data:
                    try:
                        value = float(row.get("value", 0))
                        if value > 80:  # Memory > 80%
                            summary["high_memory_count"] += 1
                    except (ValueError, TypeError):
                        pass

            if any(perf_word in metric_name.lower() for perf_word in ["latency", "duration", "response"]):
                summary["performance_issues"] += len(metric_data)

        return summary

    def save_consolidated_json(self, output_filename: str = None) -> str:
        """
        Save consolidated data as JSON

        Args:
            output_filename: Custom filename (optional)

        Returns:
            Path to saved file
        """
        if output_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"consolidated_monitoring_{self.environment}_{timestamp}.json"

        output_path = os.path.join(self.env_path, output_filename)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.consolidated_data, f, indent=2)

        print(f"✅ Consolidated JSON saved: {output_path}")
        return output_path

    def save_consolidated_markdown(self, output_filename: str = None) -> str:
        """
        Save consolidated data as Markdown report

        Args:
            output_filename: Custom filename (optional)

        Returns:
            Path to saved file
        """
        if output_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"consolidated_monitoring_{self.environment}_{timestamp}.md"

        output_path = os.path.join(self.env_path, output_filename)

        with open(output_path, 'w', encoding='utf-8') as f:
            self._write_markdown_report(f)

        print(f"✅ Consolidated Markdown saved: {output_path}")
        return output_path

    def _write_markdown_report(self, f):
        """Write consolidated report in Markdown format"""
        metadata = self.consolidated_data["metadata"]

        # Header
        f.write("# AWS Production Monitoring - Consolidated Report\n\n")
        f.write(f"**Environment:** {metadata['environment'].upper()}\n")
        f.write(f"**Generated:** {metadata['generated_at']}\n")
        f.write(f"**Report Version:** {metadata['report_version']}\n\n")
        f.write("---\n\n")

        # Data Collection Summary
        f.write("## 📋 Data Collection Summary\n\n")
        self._write_data_summary(f)
        f.write("\n---\n\n")

        # Executive Summary
        f.write("## 📊 Executive Summary\n\n")
        self._write_executive_summary(f)
        f.write("\n---\n\n")

        # Service Details
        services = self.consolidated_data.get("services", {})

        for service_name in ["SRA", "SRM", "RDS"]:
            if service_name not in services:
                continue

            f.write(f"## 🔧 {service_name} Service\n\n")

            if service_name in ["SRA", "SRM"]:
                self._write_service_details(f, service_name, services[service_name])
            elif service_name == "RDS":
                self._write_rds_details(f, services[service_name])

            f.write("\n---\n\n")

    def _write_data_summary(self, f):
        """Write data collection summary section"""
        services = self.consolidated_data.get("services", {})

        total_screenshots = 0
        total_csv_files = 0
        regions_count = 0
        services_list = []

        for svc_name, svc_data in services.items():
            if svc_name in ["SRA", "SRM"]:
                services_list.append(svc_name)
                regions = svc_data.get("regions", {})
                regions_count += len(regions)

                for region_data in regions.values():
                    screenshots = region_data.get("screenshots", [])
                    total_screenshots += len(screenshots)

                    csv_data = region_data.get("csv_data", {})
                    total_csv_files += len(csv_data)

        f.write(f"- **Services Monitored:** {', '.join(services_list) if services_list else 'None'}\n")
        f.write(f"- **Total Regions:** {regions_count}\n")
        f.write(f"- **Screenshots Collected:** {total_screenshots}\n")
        f.write(f"- **CSV Files Processed:** {total_csv_files}\n")
        f.write(f"- **Time Period:** Last 24 hours\n")

    def _write_executive_summary(self, f):
        """Write executive summary section"""
        services = self.consolidated_data.get("services", {})

        total_errors = 0
        total_unique_patterns = 0
        total_regions = 0
        critical_issues = []

        for service_name, service_data in services.items():
            if service_name in ["SRA", "SRM"]:
                regions = service_data.get("regions", {})
                total_regions += len(regions)

                for region_name, region_data in regions.items():
                    summary = region_data.get("metrics_summary", {})
                    total_errors += summary.get("total_errors", 0)
                    total_unique_patterns += summary.get("unique_error_patterns", 0)

                    # Check for critical issues
                    if summary.get("total_errors", 0) > 100:
                        critical_issues.append(f"{service_name}/{region_name}: {summary['total_errors']} errors")

                    if summary.get("high_cpu_count", 0) > 10:
                        critical_issues.append(f"{service_name}/{region_name}: High CPU detected")

        f.write(f"- **Total Regions Monitored:** {total_regions}\n")
        f.write(f"- **Total Errors:** {total_errors:,}\n")
        f.write(f"- **Unique Error Patterns:** {total_unique_patterns}\n")

        if critical_issues:
            f.write(f"\n### ⚠️ Critical Issues\n\n")
            for issue in critical_issues:
                f.write(f"- {issue}\n")
        else:
            f.write(f"\n✅ **No critical issues detected**\n")

    def _write_service_details(self, f, service_name: str, service_data: Dict):
        """Write service details for SRA/SRM"""
        regions = service_data.get("regions", {})

        if not regions:
            f.write(f"*No data collected for {service_name}*\n\n")
            return

        for region_name, region_data in sorted(regions.items()):
            f.write(f"### 🌍 Region: {region_name}\n\n")

            # Metrics Summary
            summary = region_data.get("metrics_summary", {})
            f.write("#### Metrics Overview\n\n")
            f.write(f"- **Total Errors:** {summary.get('total_errors', 0):,}\n")
            f.write(f"- **Unique Patterns:** {summary.get('unique_error_patterns', 0)}\n")
            f.write(f"- **High CPU Events:** {summary.get('high_cpu_count', 0)}\n")
            f.write(f"- **High Memory Events:** {summary.get('high_memory_count', 0)}\n")
            f.write(f"- **Metrics Collected:** {summary.get('metrics_collected', 0)}\n\n")

            # AI Analysis
            ai_analysis = region_data.get("ai_analysis")
            if ai_analysis and ai_analysis.get("status") == "success":
                f.write("#### 🤖 AI Analysis\n\n")
                analysis_text = ai_analysis.get("analysis", "No analysis available")
                f.write(f"{analysis_text}\n\n")
            elif ai_analysis and ai_analysis.get("status") == "error":
                f.write("#### ⚠️ AI Analysis\n\n")
                f.write(f"*AI analysis failed: {ai_analysis.get('message', 'Unknown error')}*\n\n")

            # Top Errors
            csv_data = region_data.get("csv_data", {})
            if "classified_errors" in csv_data:
                classified = csv_data["classified_errors"]
                if classified:
                    f.write("#### 🔴 Top Errors\n\n")
                    f.write("| Count | Error | Location |\n")
                    f.write("|-------|-------|----------|\n")

                    for error in classified[:10]:  # Top 10
                        count = error.get("Occurrence Count", 0)
                        signature = error.get("Error Signature", "Unknown")[:80]
                        location = error.get("Location", "N/A")[:40]
                        f.write(f"| {count} | {signature} | {location} |\n")

                    f.write("\n")

            # Screenshots - List ALL screenshots
            screenshots = region_data.get("screenshots", [])
            if screenshots:
                f.write(f"#### 📸 Screenshots ({len(screenshots)})\n\n")
                for screenshot in sorted(screenshots):
                    f.write(f"- {screenshot}\n")
                f.write("\n")

    def _write_rds_details(self, f, rds_data: Dict):
        """Write RDS instance details"""
        instances = rds_data.get("instances", {})

        if not instances:
            f.write("*No RDS data collected*\n\n")
            return

        for instance_name, instance_data in sorted(instances.items()):
            f.write(f"### 💾 Instance: {instance_name}\n\n")

            summary = instance_data.get("metrics_summary", {})
            f.write(f"- **Metrics Collected:** {summary.get('metrics_collected', 0)}\n")
            f.write(f"- **High CPU Events:** {summary.get('high_cpu_count', 0)}\n")
            f.write(f"- **High Memory Events:** {summary.get('high_memory_count', 0)}\n\n")


    def save_consolidated_pdf(self, output_filename: str = None) -> Optional[str]:
        """
        Save consolidated data as PDF

        Args:
            output_filename: Custom filename (optional)

        Returns:
            Path to saved file or None if PDF generation failed
        """
        try:
            from .pdf_generator import generate_pdf_report

            if output_filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"monitoring_report_{self.environment}_{timestamp}.pdf"

            output_path = os.path.join(self.env_path, output_filename)

            result = generate_pdf_report(
                self.consolidated_data,
                output_path,
                title=f"AWS Monitoring Report - {self.environment.upper()}"
            )

            if result:
                print(f"✅ PDF report saved: {output_path}")
                return output_path
            else:
                print(f"⚠️  PDF generation failed (reportlab may not be installed)")
                return None

        except ImportError:
            print(f"⚠️  PDF generation skipped (install reportlab: pip install reportlab)")
            return None
        except Exception as e:
            print(f"⚠️  PDF generation failed: {e}")
            logger.error(f"PDF generation error: {e}")
            return None

    def cleanup_individual_files(self):
        """Remove individual CSV files if configured to keep consolidated only"""
        try:
            # Import config
            KEEP_INDIVIDUAL_CSVS = True  # Default
            try:
                from .unified_config import KEEP_INDIVIDUAL_CSVS
            except:
                pass  # Use default

            if KEEP_INDIVIDUAL_CSVS:
                return

            print("\n🧹 Cleaning up individual CSV files (keeping consolidated data only)...")

            # Remove service folders but keep screenshots
            for service in ['SRA', 'SRM']:
                service_path = os.path.join(self.env_path, service)
                if os.path.exists(service_path):
                    for region_dir in os.listdir(service_path):
                        region_path = os.path.join(service_path, region_dir)
                        if os.path.isdir(region_path):
                            csv_data_path = os.path.join(region_path, 'csv_data')
                            if os.path.exists(csv_data_path):
                                shutil.rmtree(csv_data_path)
                                print(f"  Removed: {service}/{region_dir}/csv_data")

            print("✅ Cleanup complete")

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")


def consolidate_monitoring_data(environment: str = "prod", save_json: bool = True,
                                save_markdown: bool = True, save_pdf: bool = True,
                                cleanup: bool = False):
    """
    Consolidate all monitoring data into unified reports

    Args:
        environment: Environment to consolidate ('prod' or 'perf')
        save_json: Whether to save JSON output
        save_markdown: Whether to save Markdown output
        save_pdf: Whether to save PDF output
        cleanup: Whether to remove individual CSV files after consolidation

    Returns:
        Tuple of (json_path, markdown_path, pdf_path)
    """
    print("=" * 80)
    print(f"📦 Consolidating Monitoring Data - {environment.upper()}")
    print("=" * 80)

    consolidator = MonitoringConsolidator(environment)

    print("\n🔍 Collecting data from all services and regions...")
    consolidator.collect_all_data()

    json_path = None
    markdown_path = None
    pdf_path = None

    if save_json:
        print("\n💾 Saving consolidated JSON...")
        json_path = consolidator.save_consolidated_json()

    if save_markdown:
        print("\n📝 Saving consolidated Markdown report...")
        markdown_path = consolidator.save_consolidated_markdown()

    if save_pdf:
        print("\n📄 Generating PDF report...")
        pdf_path = consolidator.save_consolidated_pdf()

    if cleanup:
        consolidator.cleanup_individual_files()

    print("\n" + "=" * 80)
    print("✅ Consolidation Complete!")
    print("=" * 80)

    if json_path:
        print(f"📄 JSON Report: {json_path}")
    if markdown_path:
        print(f"📄 Markdown Report: {markdown_path}")
    if pdf_path:
        print(f"📄 PDF Report: {pdf_path}")

    print("=" * 80)

    return json_path, markdown_path, pdf_path

