"""
Anonymization utilities for removing sensitive information from logs and data.
Redacts: usernames, emails, names, UUIDs, tenant IDs, timestamps, and other PII.
"""

import re


def _redact_tenant_like_values(text: str) -> str:
    if not text:
        return text

    # Bracketed tenant tokens seen in these logs, e.g.:
    # [legal_answer_edge_llc26123588] or [some-tenant_12345] or [tenant_name]
    text = re.sub(r"\[[A-Za-z0-9][A-Za-z0-9._]*\d{3,}\]", "[TENANT_REDACTED]", text)
    text = re.sub(r"\[(tenant|customer|org|organization|account)[:=]\s*[^\]]+\]", "[TENANT_REDACTED]", text, flags=re.IGNORECASE)

    # Key/value forms commonly appearing in structured log payloads
    # tenantId=..., tenant=..., customer=..., organizationName=..., tenantName=...
    text = re.sub(
        r"\b(tenantId|tenantID|tenant|tenantName|customer|customerName|organization|organizationName|org|account|accountName)\b\s*[:=]\s*('([^']+)'|\"([^\"]+)\"|([^,\s\]}]+))",
        lambda m: f"{m.group(1)}=[TENANT_REDACTED]",
        text,
        flags=re.IGNORECASE,
    )

    # URL path/query occurrences
    text = re.sub(r"(/tenants/)([^/?\s]+)", r"\1[TENANT_REDACTED]", text, flags=re.IGNORECASE)
    text = re.sub(r"(tenant(?:Id|ID|Name)?=)([^&\s]+)", r"\1[TENANT_REDACTED]", text, flags=re.IGNORECASE)

    return text


def anonymize_log_message(message: str) -> str:
    """
    Remove or redact sensitive information from log messages.
    
    Args:
        message: Raw log message that may contain PII
        
    Returns:
        Anonymized log message safe for LLM processing
    """
    if not message or not message.strip():
        return message
    
    # Apply all anonymization patterns
    anonymized = message

    # Tenant/org masking (run early to avoid leaking names inside other structures)
    anonymized = _redact_tenant_like_values(anonymized)

    # 1. Email addresses (e.g., john.doe@example.com)
    anonymized = re.sub(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        '[EMAIL_REDACTED]',
        anonymized
    )
    
    # 2. userName field in log structures (e.g., userName='John Doe')
    anonymized = re.sub(
        r"userName='([^']+)'",
        "userName='[USER_NAME_REDACTED]'",
        anonymized
    )
    
    # 3. User names in JSON-like structures with quotes
    anonymized = re.sub(
        r'"userName"\s*:\s*"([^"]+)"',
        '"userName":"[USER_NAME_REDACTED]"',
        anonymized
    )
    
    # 4. Common name patterns in error messages (First Last format)
    # This catches patterns like "user: John Smith" or "User 'Jane Doe'"
    # Be conservative - only match clear First+Last name patterns
    anonymized = re.sub(
        r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b(?=[\s,\'\"])',
        '[NAME_REDACTED]',
        anonymized
    )
    
    # 5. statusUpdaterName field
    anonymized = re.sub(
        r"statusUpdaterName='([^']+)'",
        "statusUpdaterName='[NAME_REDACTED]'",
        anonymized
    )
    
    # 6. userComment field (may contain user-entered text)
    anonymized = re.sub(
        r"userComment='([^']+)'",
        "userComment='[COMMENT_REDACTED]'",
        anonymized
    )
    
    # 7. User display names in brackets or parentheses
    anonymized = re.sub(
        r'\[user:\s*([^\]]+)\]',
        '[user:[USER_REDACTED]]',
        anonymized,
        flags=re.IGNORECASE
    )
    
    # 8. Phone numbers (various formats)
    anonymized = re.sub(
        r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',
        '[PHONE_REDACTED]',
        anonymized
    )

    # Run tenant masking again after other substitutions (covers values introduced by normalization)
    anonymized = _redact_tenant_like_values(anonymized)

    return anonymized


def anonymize_csv_file(input_path: str, output_path: str = None) -> str:
    """
    Anonymize an existing CSV file containing logs.
    
    Args:
        input_path: Path to CSV file with potentially sensitive data
        output_path: Path to save anonymized CSV (defaults to input_path with '_anonymized' suffix)
        
    Returns:
        Path to anonymized file
    """
    import csv
    import os
    
    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_anonymized{ext}"
    
    with open(input_path, 'r', encoding='utf-8', newline='') as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        
        with open(output_path, 'w', encoding='utf-8', newline='') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for row in reader:
                # Anonymize the log_message field
                if 'log_message' in row:
                    row['log_message'] = anonymize_log_message(row['log_message'])
                writer.writerow(row)
    
    print(f"Anonymized CSV saved to: {output_path}")
    return output_path
