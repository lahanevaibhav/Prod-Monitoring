# AWS Production Monitoring
**Automated AWS CloudWatch monitoring with AI-powered analysis and comprehensive reports.**
## Quick Start
```bash
# 1. Install dependencies
pip install -r requirements.txt
# 2. Configure AWS credentials
aws configure --profile wfoprod
aws configure --profile dev
# 3. Edit config.ini with your settings
# (Uncomment regions you want to monitor)
# 4. Run monitoring
python run.py
# 5. View results
# Open: output/prod/consolidated_monitoring_prod_*.pdf (if PDF enabled)
# Or: output/prod/consolidated_monitoring_prod_*.md
```
See **[QUICK_SETUP.md](QUICK_SETUP.md)** for detailed setup instructions.
---
## Features
- **Multi-Region Support** - Monitor services across all AWS regions
- **AI-Powered Analysis** - Intelligent error analysis and recommendations
- **Automated Reports** - PDF and Markdown reports with all metrics
- **CloudWatch Integration** - Metrics, logs, and dashboard screenshots
- **Simple Configuration** - Single config.ini file for all settings
- **Multi-Profile Support** - Separate AWS profiles for data and Lambda access
---
## Configuration
All configuration is in **config.ini** - the only file you need to edit.
### Required Settings
```ini
# AWS Profiles
AWS_PROFILE_DATA=wfoprod      # Profile for CloudWatch/Logs access
AWS_PROFILE_LAMBDA=dev         # Profile for AI Lambda endpoint
# Lambda Endpoint (get from DevOps team)
LAMBDA_ENDPOINT=https://your-api-id.execute-api.us-west-2.amazonaws.com/default/...
```
### Service Configuration
Uncomment the regions you want to monitor:
```ini
# SRA Production
SRA_PROD_AU=production-au-SRA-Dashboard,ap-southeast-2,production-au-schedule-rules-automation
# SRM Production
SRM_PROD_AU=production-au-SRM-Dashboard,ap-southeast-2,production-au-schedule-requests-manager
```
### Optional Settings
```ini
# Enable/disable features
ENABLE_AI_ANALYSIS=true
GENERATE_PDF_REPORT=true
ENABLE_SCREENSHOTS=true
# Time range (days back from today at midnight)
START_DAYS_BACK=2
END_DAYS_BACK=1
# Environment mode
IS_PERFORMANCE_MODE=false
```
---
## What You Get
After running, you will find:
```
output/prod/
├── consolidated_monitoring_prod_YYYYMMDD_HHMMSS.json    # All data in JSON
├── consolidated_monitoring_prod_YYYYMMDD_HHMMSS.md      # Markdown report
├── consolidated_monitoring_prod_YYYYMMDD_HHMMSS.pdf     # PDF report (optional)
└── SRA/
    └── AU/
        ├── csv_data/              # Metrics in CSV format
        └── screenshots/           # Dashboard screenshots
```
**Reports Include:**
- Executive Summary
- Metrics for all configured services and regions
- Error logs with AI analysis
- Performance metrics and trends
- Dashboard screenshots
---
## Usage
### Daily Monitoring
```bash
python run.py
```
### Test Your Setup
```bash
python test_multi_profile.py
```
### Regenerate Reports
```bash
python consolidate_data.py
```
### Performance Environment
```ini
# In config.ini
IS_PERFORMANCE_MODE=true
```
---
## Troubleshooting
### AWS Credentials
```bash
# For SSO users
aws sso login --profile wfoprod
aws sso login --profile dev
# Verify credentials
aws sts get-caller-identity --profile wfoprod
aws sts get-caller-identity --profile dev
```
### Test Your Setup
```bash
python test_multi_profile.py
```
### Common Issues
**No regions configured**
- Edit config.ini and uncomment the regions you want to monitor
**LAMBDA_ENDPOINT not set**
- Get the Lambda endpoint URL from your DevOps team and add it to config.ini
**AWS credentials expired**
- Run: aws sso login --profile wfoprod
---
## Requirements
- Python 3.x
- AWS CLI configured
- AWS credentials with permissions for CloudWatch and Lambda
Install dependencies:
```bash
pip install -r requirements.txt
```
---
## Project Structure
```
Prod-Monitoring/
├── config.ini                    # ← EDIT THIS (only config file)
├── run.py                        # ← RUN THIS (main entry point)
├── test_multi_profile.py         # Test AWS setup
├── consolidate_data.py           # Regenerate reports
├── requirements.txt              # Python dependencies
├── README.md                     # This file
├── QUICK_SETUP.md                # Detailed setup guide
├── application_context.txt       # AI context (optional)
├── src/
│   └── prod_monitoring/          # Source code
└── output/                       # Generated reports
```
---
## License
Internal use only.