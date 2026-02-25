"""
Anonymization utilities for removing sensitive information from logs and data.
Redacts: usernames, emails, names, UUIDs, tenant IDs, timestamps, and other PII.
"""

from __future__ import annotations

import os
import re
from typing import Callable

# Pre-compiled regex patterns (kept in the same effective order as before)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_USERNAME_SQ_RE = re.compile(r"userName='([^']+)'")
_USERNAME_JSON_RE = re.compile(r'"userName"\s*:\s*"([^"]+)"')
_NAME_RE = re.compile(r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b(?=[\s,\'\"])" )
_STATUS_UPDATER_RE = re.compile(r"statusUpdaterName='([^']+)'")
_USER_COMMENT_RE = re.compile(r"userComment='([^']+)'")
_USER_BRACKET_RE = re.compile(r"\[user:\s*([^]]+)]", flags=re.IGNORECASE)
_PHONE_RE = re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")

# Tenant/org related patterns
_TENANT_BRACKETED_ID_RE = re.compile(r"\[[A-Za-z0-9][A-Za-z0-9._-]*\d{3,}]")
_TENANT_BRACKETED_KV_RE = re.compile(r"\[(tenant|customer|org|organization|account)[:=]\s*[^]]+]", flags=re.IGNORECASE)
_TENANT_KV_RE = re.compile(
    r"\b(tenantId|tenantID|tenant|tenantName|customer|customerName|organization|organizationName|org|account|accountName)\b\s*[:=]\s*(?:'[^']+'|\"[^\"]+\"|[^,\s\]}]+)",
    flags=re.IGNORECASE,
)
_TENANT_PATH_RE = re.compile(r"(/tenants/)([^/?\s]+)", flags=re.IGNORECASE)
_TENANT_QUERY_RE = re.compile(r"(tenant(?:Id|ID|Name)?=)([^&\s]+)", flags=re.IGNORECASE)


def _sub(text: str, pattern: re.Pattern[str], repl: str | Callable[[re.Match[str]], str]) -> str:
    return pattern.sub(repl, text)


def _redact_tenant_like_values(text: str) -> str:
    """Redact tenant/org identifiers in common log formats."""
    if not text:
        return text

    text = _sub(text, _TENANT_BRACKETED_ID_RE, "[TENANT_REDACTED]")
    text = _sub(text, _TENANT_BRACKETED_KV_RE, "[TENANT_REDACTED]")

    def _tenant_kv_repl(m: re.Match[str]) -> str:
        # Preserve original key spelling/casing from the log
        key = m.group(1)
        return f"{key}=[TENANT_REDACTED]"

    # Replace whole key/value token with key=[TENANT_REDACTED]
    text = _TENANT_KV_RE.sub(_tenant_kv_repl, text)

    # URL path/query occurrences
    text = _TENANT_PATH_RE.sub(r"\1[TENANT_REDACTED]", text)
    text = _TENANT_QUERY_RE.sub(r"\1[TENANT_REDACTED]", text)

    return text


def anonymize_log_message(message: str) -> str:
    """Remove or redact sensitive information from log messages."""
    if not message or not message.strip():
        return message

    anonymized = message

    # Tenant/org masking (run early to avoid leaking names inside other structures)
    anonymized = _redact_tenant_like_values(anonymized)

    anonymized = _sub(anonymized, _EMAIL_RE, "[EMAIL_REDACTED]")
    anonymized = _sub(anonymized, _USERNAME_SQ_RE, "userName='[USER_NAME_REDACTED]'")
    anonymized = _sub(anonymized, _USERNAME_JSON_RE, '"userName":"[USER_NAME_REDACTED]"')

    # Keep same conservative matching approach
    anonymized = _sub(anonymized, _NAME_RE, "[NAME_REDACTED]")

    anonymized = _sub(anonymized, _STATUS_UPDATER_RE, "statusUpdaterName='[NAME_REDACTED]'")
    anonymized = _sub(anonymized, _USER_COMMENT_RE, "userComment='[COMMENT_REDACTED]'")
    anonymized = _sub(anonymized, _USER_BRACKET_RE, "[user:[USER_REDACTED]]")
    anonymized = _sub(anonymized, _PHONE_RE, "[PHONE_REDACTED]")

    # Run tenant masking again after other substitutions
    anonymized = _redact_tenant_like_values(anonymized)

    return anonymized


# Alias for general text anonymization
def anonymize_text(text: str) -> str:
    """Anonymize any text - alias for anonymize_log_message"""
    return anonymize_log_message(text)


def anonymize_csv_file(input_path: str, output_path: str | None = None) -> str:
    """Anonymize an existing CSV file containing logs."""
    import csv

    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_anonymized{ext}"

    with open(input_path, "r", encoding="utf-8", newline="") as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames

        with open(output_path, "w", encoding="utf-8", newline="") as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()

            for row in reader:
                if "log_message" in row:
                    row["log_message"] = anonymize_log_message(row["log_message"])
                writer.writerow(row)

    print(f"Anonymized CSV saved to: {output_path}")
    return output_path
