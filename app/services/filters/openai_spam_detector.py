"""
OpenAI-powered spam/newsletter detection for email filtering
Uses gpt-4o-mini for cheap, accurate classification
"""
import logging
from typing import List, Dict, Any
import openai
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize OpenAI client
openai.api_key = settings.openai_api_key


def truncate_email_content(subject: str, body: str, max_words: int = 200, max_chars: int = 1000) -> str:
    """
    Truncate email to subject + first N words/characters of body to reduce token costs.
    
    Args:
        subject: Email subject line
        body: Full email body
        max_words: Maximum words to include from body
        max_chars: Maximum characters for entire content (subject + body)
        
    Returns:
        Truncated email content for classification
    """
    # Truncate subject if too long
    subject_truncated = subject[:200] if len(subject) > 200 else subject
    
    # Clean up body (remove excessive whitespace, HTML-like content)
    body_clean = body.replace('\r\n', ' ').replace('\n', ' ').replace('\t', ' ').strip()
    
    # Remove multiple spaces
    import re
    body_clean = re.sub(r'\s+', ' ', body_clean)
    
    # Truncate by words first
    body_words = body_clean.split()[:max_words]
    truncated_body = ' '.join(body_words)
    
    # Then truncate by total character count
    content = f"Subject: {subject_truncated}\nBody: {truncated_body}"
    
    if len(content) > max_chars:
        # Calculate how much body we can keep
        subject_part = f"Subject: {subject_truncated}\nBody: "
        available_chars = max_chars - len(subject_part) - 10  # Leave some buffer
        
        if available_chars > 50:  # Only truncate if we have meaningful content left
            truncated_body = truncated_body[:available_chars] + "..."
            content = f"Subject: {subject_truncated}\nBody: {truncated_body}"
    
    return content


def classify_email_batch(emails: List[Dict[str, Any]], batch_size: int = 10) -> List[str]:
    """
    Classify multiple emails as BUSINESS or SPAM using OpenAI gpt-4o-mini.
    
    Processes emails in batches to optimize API usage and reduce costs.
    
    Args:
        emails: List of email dicts with 'subject', 'body', and 'sender' keys
        batch_size: Number of emails to process per API call (max 10 recommended)
        
    Returns:
        List of classifications: "BUSINESS" or "SPAM" for each email
    """
    if not settings.openai_api_key:
        logger.warning("OpenAI API key not found, skipping spam filtering")
        return ["BUSINESS"] * len(emails)  # Default to business if no key
    
    all_classifications = []
    
    for i in range(0, len(emails), batch_size):
        batch = emails[i:i + batch_size]
        
        try:
            # Load email classifier prompt from Supabase (falls back to hardcoded if unavailable)
            from app.services.company_context import get_prompt_template

            classifier_template = get_prompt_template("email_classifier")
            if not classifier_template:
                logger.warning("⚠️  Could not load email_classifier prompt from Supabase, using hardcoded fallback")
                classifier_template = """You are filtering emails for Unit Industries Group, Inc., a plastic injection molding manufacturer in Santa Ana, CA.

COMPANY CONTEXT:
- Specializes in: injection molding, connectors, high-temp thermoplastics, printed circuitry, wire harnessing, electro/mechanical assembly
- Industries served: Communications, Medical, Defense/Aerospace, Industrial/Semiconductor, Multimedia, Automotive, Clean Technology
- Has Class 100,000 Clean Room for medical molding
- Key vendors: SCP (Southern California Plastics), SMC (materials), shipping carriers, machinery vendors
- Key clients: Medical device companies, aerospace contractors, automotive suppliers, communications equipment manufacturers

BUSINESS emails include:
- Purchase orders, quotes, RFQs, invoices from clients/vendors
- Technical specifications, CAD files, engineering drawings
- Quality control documents (CoC, FOD, ISO 9001 audits)
- Production schedules, shipping notifications, material deliveries
- Employee communications, internal operations
- Industry-specific content (molding, thermoplastics, quality standards)

SPAM emails include:
- Generic newsletters, marketing campaigns, promotions
- Automated notifications unrelated to manufacturing
- Mass-sent emails not specific to injection molding/manufacturing

Classify each email as BUSINESS or SPAM. Respond with only the classifications, one per line:"""
            else:
                logger.info("✅ Using email_classifier prompt from Supabase")

            # Build prompt with multiple emails
            prompt_parts = [
                classifier_template,
                ""
            ]
            
            for j, email in enumerate(batch, 1):
                truncated = truncate_email_content(
                    email.get('subject', ''), 
                    email.get('body', ''), 
                    max_words=100,   # Keep it short
                    max_chars=800    # Hard limit - prevent massive emails from costing $$
                )
                sender = email.get('sender', 'unknown')
                prompt_parts.append(f"{j}. From: {sender}")
                prompt_parts.append(f"   {truncated}")
                prompt_parts.append("")
            
            prompt = "\n".join(prompt_parts)
            
            # Call OpenAI API with cheapest model
            response = openai.chat.completions.create(
                model="gpt-4o-mini",  # Cheapest model
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert email classifier. Reply only with BUSINESS or SPAM, one per line."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=50,  # Very small response needed
                temperature=0   # Deterministic results
            )
            
            # Parse response
            classifications = response.choices[0].message.content.strip().split('\n')
            classifications = [c.strip().upper() for c in classifications if c.strip()]
            
            # Ensure we have the right number of classifications
            while len(classifications) < len(batch):
                classifications.append("BUSINESS")  # Default to business if parsing fails
            
            all_classifications.extend(classifications[:len(batch)])
            
            logger.info(f"Classified batch of {len(batch)} emails: {classifications[:len(batch)]}")
            
        except Exception as e:
            logger.error(f"Error classifying email batch: {e}")
            # Default to BUSINESS if OpenAI fails
            all_classifications.extend(["BUSINESS"] * len(batch))
    
    return all_classifications


def should_filter_email(email: Dict[str, Any]) -> bool:
    """
    Determine if an email should be filtered out (not ingested).
    
    Args:
        email: Email dict with subject, body, sender
        
    Returns:
        True if email should be filtered (is spam/newsletter), False if should keep
    """
    # Quick bypass for obviously business emails
    sender = email.get('sender', '').lower()
    subject = email.get('subject', '').lower()
    
    # Always keep emails from company domains or with business keywords
    business_indicators = [
        '@unitindustriesgroup.com',
        'invoice', 'quote', 'proposal', 'contract', 'order',
        'meeting', 'project', 'delivery', 'shipment'
    ]
    
    if any(indicator in sender or indicator in subject for indicator in business_indicators):
        return False  # Don't filter - definitely business
    
    # Use OpenAI for everything else
    try:
        classification = classify_email_batch([email])[0]
        should_filter = classification == "SPAM"
        
        if should_filter:
            logger.info(f"🚫 Filtered spam email: '{email.get('subject', 'No Subject')}' from {email.get('sender', 'Unknown')}")
        else:
            logger.debug(f"✅ Keeping business email: '{email.get('subject', 'No Subject')}'")
            
        return should_filter
        
    except Exception as e:
        logger.error(f"Error in spam filtering, keeping email: {e}")
        return False  # When in doubt, keep the email
