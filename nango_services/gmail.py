"""
Gmail message normalization helpers
Handles conversion of Nango Gmail records to internal schema
"""
import logging
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)


def normalize_gmail_message(
    gmail_record: Dict[str, Any],
    tenant_id: str
) -> Dict[str, Any]:
    """
    Normalize a Gmail record from Nango into our schema.

    Nango GmailEmail model structure:
    {
        "id": "message_id",
        "sender": "sender@example.com",
        "recipients": ["recipient@example.com"],
        "date": "2024-01-01T00:00:00Z",
        "subject": "Subject line",
        "body": "Email body content",
        "attachments": [...],
        ...
    }

    Args:
        gmail_record: Raw Gmail record from Nango
        tenant_id: Tenant identifier

    Returns:
        Normalized message dictionary
    """
    # Extract sender information
    sender_raw = gmail_record.get("sender", "")
    # Gmail sender can be "Name <email@example.com>" or just "email@example.com"
    if "<" in sender_raw and ">" in sender_raw:
        # Parse "Name <email@example.com>"
        sender_name = sender_raw.split("<")[0].strip()
        sender_address = sender_raw.split("<")[1].split(">")[0].strip()
    else:
        sender_name = ""
        sender_address = sender_raw.strip()

    # Extract recipient addresses
    recipients = gmail_record.get("recipients", [])
    # Ensure recipients is always a list (Nango might send string)
    if isinstance(recipients, str):
        recipients = [recipients]
    elif not isinstance(recipients, list):
        recipients = []

    to_addresses = []
    for recipient in recipients:
        if isinstance(recipient, str):
            # Extract email from "Name <email>" format if present
            if "<" in recipient and ">" in recipient:
                email = recipient.split("<")[1].split(">")[0].strip()
            else:
                email = recipient.strip()
            to_addresses.append(email)

    # Parse date
    date_str = gmail_record.get("date")
    if date_str:
        try:
            received_datetime = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            received_datetime = None
    else:
        received_datetime = None

    # For Gmail, we'll use the sender's email as the user_id and user_principal_name
    # since Gmail doesn't have the same tenant/user structure as Outlook
    user_email = sender_address or "unknown@gmail.com"

    # Get full body (Nango provides full email body in 'body' field)
    full_body = gmail_record.get("body", "")

    return {
        "tenant_id": tenant_id,
        "user_id": user_email,  # Use email as user ID for Gmail
        "user_principal_name": user_email,
        "message_id": gmail_record.get("id"),
        "source": "gmail",
        "subject": gmail_record.get("subject", ""),
        "sender_name": sender_name,
        "sender_address": sender_address,
        "to_addresses": to_addresses,
        "received_datetime": received_datetime.isoformat() if received_datetime else None,
        "web_link": "",  # Gmail records from Nango may not include web link
        "full_body": full_body,  # Full email body content
        "change_key": ""  # Gmail doesn't use change keys
    }
