# Prod Monitoring (CloudWatch Dashboard Evidence)

This project collects **CloudWatch dashboard metrics evidence** (screenshots/images) and **error logs** for multiple services and regions. It outputs per-region artifacts (PNGs + CSVs) and can generate a simple HTML report.

## Features

- Captures **dashboard metric images** (screenshots) for multiple metric types, including:
  - **Errors**
  - **Performance / latency**
  - **Counts / throughput**
  - (and any other widgets present in the configured CloudWatch dashboards)
- Pulls **error logs** and produces CSVs such as:
  - error log extracts
  - error counts / grouped summaries
  - classified error categories (where applicable)
- Organizes output by **service** and **region** under `SRA/<REGION>/...` and `SRM/<REGION>/...`.
- Generates an **HTML report** from the collected evidence.

## Prerequisites

- Python **3.x**
- AWS credentials available in your environment (for example via `aws configure` / environment variables / SSO), with permissions to:
  - read CloudWatch dashboards and metrics
  - read relevant log groups / streams (if log collection is enabled)

## How to run

1. Install Python 3.x.
2. Install dependencies:

   - `pip install boto3`

3. Run the **AWS v1 script** with the **prod account**:

   - Edit the script and set the **prod account number** in the `target account` value.
   - Run the script.

4. Run the main collector:

   - `python main.py`

This will populate folders like:

- `SRA/<REGION>/screenshots/` (PNG images)
- `SRA/<REGION>/csv_data/` (CSV outputs)
- `SRM/<REGION>/screenshots/` (PNG images)
- `SRM/<REGION>/csv_data/` (CSV outputs)

## Generate report (after collection)

After the run is complete, generate the report:

- Performance report:
  - `python generate_region_report.py --is-perf`

## Notes

- Dashboard/region selection is driven by metadata in the code (for example in `metrics_helper.py`).
- If you add or rename widgets in CloudWatch dashboards, the produced images/CSVs will change accordingly.

