"""
Gmail Preprocessor for Hybrid RAG Pipeline
Transforms Nango Gmail JSON into format expected by HybridRAGPipeline
"""
from datetime import datetime
from typing import Dict, Any, Optional
import re
from bs4 import BeautifulSoup
from flanker.addresslib import address


class GmailPreprocessor:
    """
    Preprocesses Gmail data from Nango API for ingestion into Hybrid RAG Pipeline

    What LlamaIndex/Graphiti Handle:
    - LlamaIndex: Text chunking, embedding generation, Qdrant storage
    - Graphiti: Entity extraction, relationship identification, knowledge graph construction

    What This Preprocessor Handles:
    - Parsing Nango's Gmail JSON structure
    - Converting HTML body to plain text
    - Extracting sender/recipient information
    - Formatting email content as readable text
    - Building metadata dict for downstream processing
    """

    @staticmethod
    def clean_html(html_content: str) -> str:
        """
        Convert HTML email body to plain text
        Removes HTML tags, decodes entities, cleans up whitespace
        """
        if not html_content:
            return ""

        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Get text
        text = soup.get_text()

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)

        return text

    @staticmethod
    def parse_email_address(email_field: str) -> tuple[str, str]:
        """
        Parse email field using Flanker (production-grade, RFC-compliant parser by Mailgun)

        Examples:
        - "Nicolas Codet <nick@thunderbird-labs.com>" -> ("Nicolas Codet", "nick@thunderbird-labs.com")
        - "nick@thunderbird-labs.com" -> ("", "nick@thunderbird-labs.com")
        - "support@seated.com" -> ("", "support@seated.com")
        - "\"AI Automation Society (Skool)\" <noreply@skool.com>" -> ("AI Automation Society (Skool)", "noreply@skool.com")

        Flanker handles:
        - RFC 5322 compliant parsing
        - Edge cases (quoted names, special characters, etc.)
        - 20x faster than Python's stdlib email parser
        """
        if not email_field:
            return ("", "")

        # Use Flanker's battle-tested parser
        parsed = address.parse(email_field.strip())

        if parsed:
            return (parsed.display_name or "", parsed.address)

        # Fallback if parsing fails (rare)
        return ("", email_field.strip())

    @staticmethod
    def parse_recipients(recipients_field: str) -> list[str]:
        """
        Parse recipients field (may be comma-separated or single email)

        Examples:
        - "nick@thunderbird-labs.com" -> ["nick@thunderbird-labs.com"]
        - "Alexander Kashkarian <alex@thunderbird-labs.com>" -> ["alex@thunderbird-labs.com"]
        """
        if not recipients_field:
            return []

        # Split by comma if multiple recipients
        recipient_list = [r.strip() for r in recipients_field.split(',')]

        # Extract email addresses
        emails = []
        for recipient in recipient_list:
            _, email = GmailPreprocessor.parse_email_address(recipient)
            if email:
                emails.append(email)

        return emails

    @staticmethod
    def format_email_content(nango_email: Dict[str, Any]) -> str:
        """
        Format email content as readable text for ingestion

        Creates a simple, readable format:
        From: Name <email>
        To: recipient1@domain.com, recipient2@domain.com
        Date: October 20, 2025
        Subject: Email Subject

        Email body content here...
        """
        sender = nango_email.get("sender", "")
        recipients = nango_email.get("recipients", "")
        date_str = nango_email.get("date", "")
        subject = nango_email.get("subject", "")
        body = nango_email.get("body", "")

        # Parse date
        try:
            date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            formatted_date = date_obj.strftime("%B %d, %Y at %I:%M %p")
        except:
            formatted_date = date_str

        # Clean HTML from body
        clean_body = GmailPreprocessor.clean_html(body)

        # Build formatted content
        content = f"""From: {sender}
To: {recipients}
Date: {formatted_date}
Subject: {subject}

{clean_body}
"""

        return content

    @staticmethod
    def transform_for_pipeline(nango_email: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
        """
        Transform Nango Gmail JSON into format expected by HybridRAGPipeline.ingest_document()

        Input (Nango Format):
        {
            "id": "199c07124b9fd56f",
            "sender": "Nicolas Codet <nick@thunderbird-labs.com>",
            "recipients": "Alexander Kashkarian <alex@thunderbird-labs.com>",
            "date": "2025-10-03T19:51:02.000Z",
            "subject": "Re: Fixed Duplicates",
            "body": "<html>Full email HTML content here...</html>",
            "attachments": [...],
            "threadId": "199441c0814b4196"
        }

        Output (Pipeline Format):
        {
            "content": "From: ...\nTo: ...\n\nEmail body...",
            "document_name": "Email Subject",
            "source": "gmail",
            "document_type": "email",
            "reference_time": datetime(2025, 10, 3, 19, 51, 2),
            "metadata": {
                "tenant_id": "uuid",
                "message_id": "199c07124b9fd56f",
                "thread_id": "199441c0814b4196",
                "from_name": "Nicolas Codet",
                "from_address": "nick@thunderbird-labs.com",
                "to_addresses": ["alex@thunderbird-labs.com"],
                "subject": "Re: Fixed Duplicates",
                "has_attachments": True,
                "attachment_count": 5
            }
        }
        """
        # Format content as readable text
        content = GmailPreprocessor.format_email_content(nango_email)

        # Parse sender
        sender_name, sender_address = GmailPreprocessor.parse_email_address(
            nango_email.get("sender", "")
        )

        # Parse recipients
        to_addresses = GmailPreprocessor.parse_recipients(
            nango_email.get("recipients", "")
        )

        # Parse date
        date_str = nango_email.get("date", "")
        try:
            reference_time = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            reference_time = datetime.now()

        # Build metadata
        attachments = nango_email.get("attachments", [])
        metadata = {
            "tenant_id": tenant_id,
            "message_id": nango_email.get("id", ""),
            "thread_id": nango_email.get("threadId", ""),
            "from_name": sender_name,
            "from_address": sender_address,
            "to_addresses": to_addresses,
            "subject": nango_email.get("subject", ""),
            "has_attachments": len(attachments) > 0,
            "attachment_count": len(attachments)
        }

        # Return pipeline-ready format
        return {
            "content": content,
            "document_name": nango_email.get("subject", "Untitled Email"),
            "source": "gmail",
            "document_type": "email",
            "reference_time": reference_time,
            "metadata": metadata
        }


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

async def example_usage():
    """
    Example: How to use GmailPreprocessor with HybridRAGPipeline
    """
    from hybrid_rag_pipeline import HybridRAGPipeline

    # Sample Nango email (from your logs)
    nango_email = {
        "id": "199c07124b9fd56f",
        "sender": "Nicolas Codet <nick@thunderbird-labs.com>",
        "recipients": "Alexander Kashkarian <alex@thunderbird-labs.com>",
        "date": "2025-10-03T19:51:02.000Z",
        "subject": "Re: Fixed Duplicates",
        "body": "just sent a text for the code\r\n\r\nOn Fri, Oct 3, 2025 at 12:38\u202fPM Jevon Perra <jevon@jcap.net> wrote:\r\n\r\n> Great.\r\n> here's my personal google pass Niccanopen1\r\n",
        "attachments": [],
        "threadId": "199441c0814b4196"
    }

    # Transform to pipeline format
    preprocessor = GmailPreprocessor()
    pipeline_input = preprocessor.transform_for_pipeline(
        nango_email,
        tenant_id="cc06fb97-a78a-40c3-94f8-98efa7df3208"
    )

    # Ingest into pipeline
    pipeline = HybridRAGPipeline()

    try:
        result = await pipeline.ingest_document(
            content=pipeline_input["content"],
            document_name=pipeline_input["document_name"],
            source=pipeline_input["source"],
            document_type=pipeline_input["document_type"],
            reference_time=pipeline_input["reference_time"],
            metadata=pipeline_input["metadata"]
        )

        print(f"✅ Ingested email: {result['document_name']}")
        print(f"   Episode ID: {result['episode_id']}")
        print(f"   Chunks: {result['num_chunks']}")

    finally:
        await pipeline.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
