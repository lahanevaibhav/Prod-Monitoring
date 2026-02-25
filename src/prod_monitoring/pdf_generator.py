"""
PDF Report Generator
Creates comprehensive PDF reports with all monitoring data and AI analysis
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

# Import OUTPUT_ROOT
try:
    from .csv_helper import OUTPUT_ROOT
except ImportError:
    from csv_helper import OUTPUT_ROOT

# Try to import PDF libraries
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph,
        Spacer, PageBreak, Image, KeepTogether
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("ReportLab not installed. Install with: pip install reportlab")


class PDFReportGenerator:
    """Generate comprehensive PDF monitoring reports"""

    def __init__(self, output_path: str, title: str = "AWS Monitoring Report",
                 author: str = "", page_size="A4"):
        """
        Initialize PDF generator

        Args:
            output_path: Path to save PDF file
            title: Report title
            author: Report author (optional)
            page_size: Page size (A4 or letter)
        """
        if not PDF_AVAILABLE:
            raise ImportError("ReportLab library required for PDF generation")

        self.output_path = output_path
        self.title = title
        self.author = author
        self.page_size = A4 if page_size.upper() == "A4" else letter

        # Create document
        self.doc = SimpleDocTemplate(
            output_path,
            pagesize=self.page_size,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )

        # Styles
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

        # Story elements
        self.story = []

    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))

        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=12,
            spaceBefore=12
        ))

        self.styles.add(ParagraphStyle(
            name='SubSection',
            parent=self.styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#34495e'),
            spaceAfter=6
        ))

        self.styles.add(ParagraphStyle(
            name='HealthyStatus',
            parent=self.styles['Normal'],
            textColor=colors.green,
            fontSize=14,
            fontName='Helvetica-Bold'
        ))

        self.styles.add(ParagraphStyle(
            name='WarningStatus',
            parent=self.styles['Normal'],
            textColor=colors.orange,
            fontSize=14,
            fontName='Helvetica-Bold'
        ))

        self.styles.add(ParagraphStyle(
            name='ErrorStatus',
            parent=self.styles['Normal'],
            textColor=colors.red,
            fontSize=14,
            fontName='Helvetica-Bold'
        ))

    def add_cover_page(self, environment: str, generated_at: str, data_summary: Dict = None):
        """Add cover page with data collection summary"""
        # Title
        self.story.append(Spacer(1, 1.5*inch))
        self.story.append(Paragraph(self.title, self.styles['CustomTitle']))
        self.story.append(Spacer(1, 0.3*inch))

        # Environment
        env_text = f"<b>Environment:</b> {environment.upper()}"
        self.story.append(Paragraph(env_text, self.styles['Normal']))
        self.story.append(Spacer(1, 0.15*inch))

        # Generated date
        date_text = f"<b>Generated:</b> {generated_at}"
        self.story.append(Paragraph(date_text, self.styles['Normal']))
        self.story.append(Spacer(1, 0.4*inch))

        # Data Collection Summary
        if data_summary:
            self.story.append(Paragraph("<b>Data Collection Summary</b>", self.styles['SubSection']))
            self.story.append(Spacer(1, 0.1*inch))

            summary_items = [
                f"• Services Monitored: {data_summary.get('services_count', 0)}",
                f"• Regions Analyzed: {data_summary.get('regions_count', 0)}",
                f"• Total Screenshots: {data_summary.get('screenshots_count', 0)}",
                f"• CSV Files Collected: {data_summary.get('csv_files_count', 0)}",
                f"• Time Period: {data_summary.get('time_period', 'Last 24 hours')}",
            ]

            for item in summary_items:
                self.story.append(Paragraph(item, self.styles['Normal']))
                self.story.append(Spacer(1, 0.05*inch))

        self.story.append(PageBreak())

    def add_executive_summary(self, summary_data: Dict):
        """Add executive summary section"""
        self.story.append(Paragraph("Executive Summary", self.styles['SectionHeader']))
        self.story.append(Spacer(1, 0.15*inch))

        # Summary table
        data = [
            ["Metric", "Value"],
            ["Total Regions Monitored", str(summary_data.get('total_regions', 0))],
            ["Total Errors", f"{summary_data.get('total_errors', 0):,}"],
            ["Unique Error Patterns", str(summary_data.get('unique_patterns', 0))],
            ["Services Analyzed", summary_data.get('services', 'N/A')],
        ]

        table = Table(data, colWidths=[3*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        self.story.append(table)
        self.story.append(Spacer(1, 0.2*inch))

        # Critical issues
        critical_issues = summary_data.get('critical_issues', [])
        if critical_issues:
            self.story.append(Paragraph("Critical Issues", self.styles['SubSection']))
            for issue in critical_issues[:5]:  # Top 5
                self.story.append(Paragraph(f"• {issue}", self.styles['Normal']))
            self.story.append(Spacer(1, 0.15*inch))
        else:
            self.story.append(Paragraph("✅ No critical issues detected",
                                      self.styles['HealthyStatus']))
            self.story.append(Spacer(1, 0.15*inch))

        self.story.append(PageBreak())

    def add_service_section(self, service_name: str, service_data: Dict):
        """Add service details section"""
        self.story.append(Paragraph(f"{service_name} Service", self.styles['SectionHeader']))
        self.story.append(Spacer(1, 0.15*inch))

        regions = service_data.get('regions', {})

        if not regions:
            self.story.append(Paragraph(f"No data collected for {service_name}",
                                      self.styles['Normal']))
            self.story.append(Spacer(1, 0.3*inch))
            return

        for region_name, region_data in sorted(regions.items()):
            self._add_region_details(service_name, region_name, region_data)

    def _add_region_details(self, service_name: str, region_name: str, region_data: Dict):
        """Add region details"""
        # Region header
        self.story.append(Paragraph(f"Region: {region_name}", self.styles['SubSection']))

        # Metrics summary
        summary = region_data.get('metrics_summary', {})
        total_errors = summary.get('total_errors', 0)

        # Status indicator
        if total_errors == 0:
            status_text = f"<font color='green'>✅ HEALTHY</font> - No errors detected"
        elif total_errors < 10:
            status_text = f"<font color='orange'>⚠️ MINOR ISSUES</font> - {total_errors} errors"
        else:
            status_text = f"<font color='red'>🔴 ATTENTION NEEDED</font> - {total_errors} errors"

        self.story.append(Paragraph(status_text, self.styles['Normal']))
        self.story.append(Spacer(1, 0.08*inch))

        # Metrics table
        metrics_data = [
            ["Metric", "Value"],
            ["Total Errors", f"{summary.get('total_errors', 0):,}"],
            ["Unique Patterns", str(summary.get('unique_error_patterns', 0))],
            ["High CPU Events", str(summary.get('high_cpu_count', 0))],
            ["High Memory Events", str(summary.get('high_memory_count', 0))],
        ]

        table = Table(metrics_data, colWidths=[2.5*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))

        self.story.append(table)
        self.story.append(Spacer(1, 0.15*inch))

        # AI Analysis
        ai_analysis = region_data.get('ai_analysis')
        if ai_analysis and ai_analysis.get('status') == 'success':
            self.story.append(Paragraph("AI Analysis", self.styles['SubSection']))
            analysis_text = ai_analysis.get('analysis', 'No analysis available')

            # Parse and format the AI analysis text properly
            lines = analysis_text.split('\n')
            i = 0
            while i < len(lines):
                line = lines[i].strip()

                if not line:
                    i += 1
                    continue

                # Handle section headers (numbered items like "1. Root Cause Analysis:")
                if line and line[0].isdigit() and '. ' in line[:5]:
                    # This is a main section header
                    clean_line = line.replace('**', '').replace('##', '').replace('###', '').replace('#', '')
                    self.story.append(Paragraph(f"<b>{clean_line}</b>", self.styles['Normal']))
                    self.story.append(Spacer(1, 0.05*inch))

                # Handle bullet points with proper indentation
                elif line.startswith('- '):
                    clean_line = line[2:].replace('**', '<b>').replace('##', '').replace('###', '').replace('#', '')
                    if '<b>' in clean_line and '</b>' not in clean_line:
                        # Close bold tag if not closed
                        if ':' in clean_line:
                            clean_line = clean_line.replace(':', ':</b>', 1)
                        else:
                            clean_line += '</b>'

                    # Add bullet with indentation
                    try:
                        self.story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;• {clean_line}", self.styles['Normal']))
                    except:
                        # Fallback for problematic text
                        safe_line = clean_line.replace('<', '&lt;').replace('>', '&gt;')
                        self.story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;• {safe_line}", self.styles['Normal']))

                # Handle regular text
                else:
                    clean_line = line.replace('**', '<b>').replace('##', '').replace('###', '').replace('#', '')
                    if '<b>' in clean_line and '</b>' not in clean_line:
                        clean_line += '</b>'

                    try:
                        if clean_line:
                            self.story.append(Paragraph(clean_line, self.styles['Normal']))
                    except:
                        # Fallback for problematic text
                        safe_line = clean_line.replace('<', '&lt;').replace('>', '&gt;')
                        self.story.append(Paragraph(safe_line, self.styles['Normal']))

                i += 1

            self.story.append(Spacer(1, 0.15*inch))

        # Top Errors
        csv_data = region_data.get('csv_data', {})
        if 'classified_errors' in csv_data and csv_data['classified_errors']:
            self.story.append(Paragraph("Top Errors", self.styles['SubSection']))

            # Create table data with Paragraph objects for text wrapping
            error_table_data = [["Count", "Error", "Location"]]

            # Define a style for table cells with smaller font
            cell_style = ParagraphStyle(
                'CellStyle',
                parent=self.styles['Normal'],
                fontSize=8,
                leading=10,
                wordWrap='CJK'
            )

            for error in csv_data['classified_errors'][:10]:  # Top 10
                count = error.get('Occurrence Count', 0)
                signature = str(error.get('Error Signature', 'Unknown'))
                location = str(error.get('Location', 'N/A'))

                # Use Paragraph objects for wrapping long text
                error_table_data.append([
                    Paragraph(str(count), cell_style),
                    Paragraph(signature, cell_style),
                    Paragraph(location, cell_style)
                ])

            # Adjust column widths: Count (narrow), Error (wide), Location (medium)
            # Total width: ~6.5 inches (fits within page margins)
            error_table = Table(error_table_data, colWidths=[0.5*inch, 4*inch, 2*inch])
            error_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),  # Center count column
                ('ALIGN', (1, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4)
            ]))

            self.story.append(error_table)

        self.story.append(Spacer(1, 0.2*inch))

        # Add screenshots
        screenshots = region_data.get('screenshots', [])
        if screenshots:
            self._add_screenshots_section(service_name, region_name, screenshots)

    def _add_screenshots_section(self, service_name: str, region_name: str, screenshots: List[str]):
        """Add all screenshots to the PDF report with titles kept together"""
        import os
        from pathlib import Path

        # Get the environment path
        env_name = "perf" if "perf" in self.output_path.lower() else "prod"
        screenshots_dir = os.path.join(OUTPUT_ROOT, env_name, service_name, region_name, "screenshots")

        if not os.path.exists(screenshots_dir):
            logger.warning(f"Screenshots directory not found: {screenshots_dir}")
            return

        self.story.append(Paragraph(f"Dashboard Screenshots ({len(screenshots)})", self.styles['SubSection']))
        self.story.append(Spacer(1, 0.08*inch))

        # Add each screenshot with title kept together
        for screenshot_file in sorted(screenshots):
            screenshot_path = os.path.join(screenshots_dir, screenshot_file)

            if not os.path.exists(screenshot_path):
                logger.warning(f"Screenshot not found: {screenshot_path}")
                continue

            try:
                # Create elements to keep together
                elements_to_keep = []

                # Add screenshot title
                title = screenshot_file.replace('.png', '').replace('_', ' ').title()
                elements_to_keep.append(Paragraph(title, self.styles['Normal']))
                elements_to_keep.append(Spacer(1, 0.05*inch))

                # Add image - resize to fit page width
                img = Image(screenshot_path)

                # Calculate size to fit within page margins
                available_width = self.page_size[0] - 1.5*inch  # Account for margins
                available_height = 3.5*inch  # Max height for screenshots (reduced from 4)

                # Get original size
                img_width = img.imageWidth
                img_height = img.imageHeight

                # Calculate scaling
                width_ratio = available_width / img_width
                height_ratio = available_height / img_height
                scale = min(width_ratio, height_ratio, 1.0)  # Don't upscale

                # Set final size
                img.drawWidth = img_width * scale
                img.drawHeight = img_height * scale

                elements_to_keep.append(img)

                # Use KeepTogether to prevent title from being separated from screenshot
                self.story.append(KeepTogether(elements_to_keep))
                self.story.append(Spacer(1, 0.12*inch))

            except Exception as e:
                logger.error(f"Failed to add screenshot {screenshot_file}: {e}")
                self.story.append(Paragraph(f"Error loading screenshot: {screenshot_file}",
                                          self.styles['Normal']))
                self.story.append(Spacer(1, 0.08*inch))

    def generate(self, consolidated_data: Dict):
        """
        Generate PDF from consolidated data

        Args:
            consolidated_data: Dictionary with all monitoring data
        """
        metadata = consolidated_data.get('metadata', {})
        services = consolidated_data.get('services', {})

        # Build data collection summary
        data_summary = self._build_data_summary(services)

        # Cover page with data summary
        self.add_cover_page(
            environment=metadata.get('environment', 'Unknown'),
            generated_at=metadata.get('generated_at', datetime.now().isoformat()),
            data_summary=data_summary
        )

        # Executive summary
        summary_data = self._build_summary(services)
        self.add_executive_summary(summary_data)

        # Services
        for service_name in ['SRA', 'SRM']:
            if service_name in services:
                self.add_service_section(service_name, services[service_name])
                self.story.append(PageBreak())

        # RDS
        if 'RDS' in services:
            self.add_rds_section(services['RDS'])

        # Build PDF
        self.doc.build(self.story)
        logger.info(f"PDF report generated: {self.output_path}")

    def _build_data_summary(self, services: Dict) -> Dict:
        """Build data collection summary for cover page"""
        total_screenshots = 0
        total_csv_files = 0
        regions_count = 0
        services_list = []

        for svc_name, svc_data in services.items():
            if svc_name in ['SRA', 'SRM']:
                services_list.append(svc_name)
                regions = svc_data.get('regions', {})
                regions_count += len(regions)

                for region_data in regions.values():
                    screenshots = region_data.get('screenshots', [])
                    total_screenshots += len(screenshots)

                    csv_data = region_data.get('csv_data', {})
                    total_csv_files += len(csv_data)

        return {
            'services_count': len(services_list),
            'regions_count': regions_count,
            'screenshots_count': total_screenshots,
            'csv_files_count': total_csv_files,
            'time_period': 'Last 24 hours'
        }

    def _build_summary(self, services: Dict) -> Dict:
        """Build executive summary data"""
        total_errors = 0
        total_unique = 0
        total_regions = 0
        critical_issues = []
        service_names = []

        for svc_name, svc_data in services.items():
            if svc_name in ['SRA', 'SRM']:
                service_names.append(svc_name)
                regions = svc_data.get('regions', {})
                total_regions += len(regions)

                for region, region_data in regions.items():
                    summary = region_data.get('metrics_summary', {})
                    errors = summary.get('total_errors', 0)
                    total_errors += errors
                    total_unique += summary.get('unique_error_patterns', 0)

                    if errors > 100:
                        critical_issues.append(f"{svc_name}/{region}: {errors} errors")
                    if summary.get('high_cpu_count', 0) > 10:
                        critical_issues.append(f"{svc_name}/{region}: High CPU detected")

        return {
            'total_regions': total_regions,
            'total_errors': total_errors,
            'unique_patterns': total_unique,
            'services': ', '.join(service_names),
            'critical_issues': critical_issues
        }


def generate_pdf_report(consolidated_data: Dict, output_path: str,
                       title: str = "AWS Monitoring Report",
                       author: str = "DevOps Team") -> str:
    """
    Generate PDF report from consolidated data

    Args:
        consolidated_data: Dictionary with all monitoring data
        output_path: Path to save PDF
        title: Report title
        author: Report author

    Returns:
        Path to generated PDF
    """
    if not PDF_AVAILABLE:
        logger.error("ReportLab not installed. Install with: pip install reportlab")
        return None

    try:
        generator = PDFReportGenerator(output_path, title=title, author=author)
        generator.generate(consolidated_data)
        return output_path
    except Exception as e:
        logger.error(f"Failed to generate PDF: {e}")
        import traceback
        traceback.print_exc()
        return None

