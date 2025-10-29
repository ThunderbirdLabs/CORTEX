"""
Company Context Loader - Dynamic Company Information & Prompts from Master Supabase

Loads company-specific information (description, team, industries, location, etc.)
AND prompt templates from the master Supabase database.

This makes EVERYTHING dynamic:
- Company context (name, description, team, industries)
- Prompt templates (CEO assistant, email classifier, vision OCR, etc.)

Each company can customize both their data AND their prompts!
"""
import logging
from typing import Dict, List, Optional
from app.core.config_master import master_config
from app.core.dependencies import master_supabase_client

logger = logging.getLogger(__name__)

# Global cache for company context (loaded once at startup)
_company_context_cache: Optional[Dict] = None

# Global cache for prompt templates (loaded once at startup)
_prompt_templates_cache: Optional[Dict[str, str]] = None


def load_company_context() -> Dict:
    """
    Load company information from master Supabase.

    Returns dict with:
        - name: Company name
        - slug: Company slug
        - description: Company description
        - location: Company location
        - industries: List of industries served
        - capabilities: List of key capabilities
        - team: List of team members with name, title, role_description, reports_to
        - contact_name: Primary contact name
        - contact_email: Primary contact email

    If not in multi-tenant mode, returns default/empty context.
    """
    global _company_context_cache

    # Return cached context if already loaded
    if _company_context_cache is not None:
        return _company_context_cache

    # Check if multi-tenant mode is enabled
    if not master_config.is_multi_tenant:
        logger.info("📋 Single-tenant mode - no dynamic company context")
        _company_context_cache = {
            "name": "Your Company",
            "slug": "default",
            "description": "A business",
            "location": "Unknown",
            "industries": [],
            "capabilities": [],
            "team": [],
            "contact_name": "",
            "contact_email": ""
        }
        return _company_context_cache

    try:
        # Load company info from master Supabase
        logger.info(f"🔍 Loading company context for company_id: {master_config.company_id}")

        company_result = master_supabase_client.table("companies")\
            .select("*")\
            .eq("id", master_config.company_id)\
            .single()\
            .execute()

        if not company_result.data:
            logger.error(f"❌ Company not found in master Supabase: {master_config.company_id}")
            _company_context_cache = _get_default_context()
            return _company_context_cache

        company = company_result.data

        # Load team members from master Supabase
        team_result = master_supabase_client.table("company_team_members")\
            .select("*")\
            .eq("company_id", master_config.company_id)\
            .eq("is_active", True)\
            .execute()

        team = team_result.data or []

        # Build context
        _company_context_cache = {
            "name": company.get("name", "Your Company"),
            "slug": company.get("slug", "default"),
            "description": company.get("company_description", ""),
            "location": company.get("company_location", ""),
            "industries": company.get("industries_served", []),
            "capabilities": company.get("key_capabilities", []),
            "team": team,
            "contact_name": company.get("primary_contact_name", ""),
            "contact_email": company.get("primary_contact_email", "")
        }

        logger.info(f"✅ Loaded company context for: {_company_context_cache['name']}")
        logger.info(f"   📍 Location: {_company_context_cache['location']}")
        logger.info(f"   👥 Team members: {len(_company_context_cache['team'])}")
        logger.info(f"   🏭 Industries: {len(_company_context_cache['industries'])}")

        return _company_context_cache

    except Exception as e:
        logger.error(f"❌ Failed to load company context: {e}")
        _company_context_cache = _get_default_context()
        return _company_context_cache


def _get_default_context() -> Dict:
    """Return default context when loading fails."""
    return {
        "name": "Your Company",
        "slug": "default",
        "description": "A business",
        "location": "Unknown",
        "industries": [],
        "capabilities": [],
        "team": [],
        "contact_name": "",
        "contact_email": ""
    }


def get_company_context() -> Dict:
    """
    Get cached company context (loads if not already loaded).

    Use this function in all services that need company information.
    """
    return load_company_context()


def load_prompt_templates() -> Dict[str, str]:
    """
    Load all prompt templates from master Supabase.

    Returns dict mapping prompt_key → prompt_template text.
    Loads once and caches in memory.
    """
    global _prompt_templates_cache

    # Return cached prompts if already loaded
    if _prompt_templates_cache is not None:
        return _prompt_templates_cache

    # Check if multi-tenant mode is enabled
    if not master_config.is_multi_tenant:
        logger.info("📋 Single-tenant mode - using default prompts (not from database)")
        _prompt_templates_cache = {}
        return _prompt_templates_cache

    try:
        logger.info(f"🔍 Loading prompt templates for company_id: {master_config.company_id}")

        result = master_supabase_client.table("company_prompts")\
            .select("prompt_key, prompt_template")\
            .eq("company_id", master_config.company_id)\
            .eq("is_active", True)\
            .execute()

        prompts = {row["prompt_key"]: row["prompt_template"] for row in result.data}

        _prompt_templates_cache = prompts

        logger.info(f"✅ Loaded {len(prompts)} prompt templates: {list(prompts.keys())}")

        return _prompt_templates_cache

    except Exception as e:
        logger.error(f"❌ Failed to load prompt templates: {e}")
        _prompt_templates_cache = {}
        return _prompt_templates_cache


def get_prompt_template(prompt_key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get a specific prompt template by key.

    Args:
        prompt_key: Prompt identifier (e.g., "ceo_assistant", "email_classifier")
        default: Default template if not found

    Returns:
        Prompt template string, or None if not found
    """
    prompts = load_prompt_templates()
    return prompts.get(prompt_key, default)


def render_prompt_template(prompt_key: str, variables: Dict[str, str]) -> str:
    """
    Render a prompt template with variable substitution.

    Args:
        prompt_key: Prompt identifier
        variables: Dict of variable_name → value for {{variable_name}} placeholders

    Returns:
        Rendered prompt string with variables replaced

    Example:
        render_prompt_template("ceo_assistant", {
            "company_name": "Acme Corp",
            "context_str": "...",
            "query_str": "What materials do we use?"
        })
    """
    template = get_prompt_template(prompt_key)

    if not template:
        logger.warning(f"⚠️  Prompt template '{prompt_key}' not found")
        return ""

    # Simple variable substitution (replace {{var}} with value)
    rendered = template
    for var_name, var_value in variables.items():
        placeholder = f"{{{{{var_name}}}}}"  # {{var_name}}
        rendered = rendered.replace(placeholder, str(var_value))

    return rendered


def build_ceo_prompt_template() -> str:
    """
    Build CEO Assistant prompt template with dynamic company context.

    NOW LOADS FROM SUPABASE! Falls back to building from context if no template found.

    Used by query_engine.py for response synthesis.
    """
    context = get_company_context()

    # Try to load template from Supabase first
    template = get_prompt_template("ceo_assistant")

    if template:
        # Template exists in database - render it with company context variables
        logger.info("✅ Using CEO prompt template from master Supabase")

        # Build team list
        team_lines = []
        for member in context["team"]:
            name = member.get("name", "Unknown")
            title = member.get("title", "")
            role_desc = member.get("role_description", "")

            if title and role_desc:
                team_lines.append(f"- {name} - {title}: {role_desc}")
            elif title:
                team_lines.append(f"- {name} - {title}")
            else:
                team_lines.append(f"- {name}")

        team_section = "\n".join(team_lines) if team_lines else "- Team information not available"

        # Build industries list
        industries_str = ", ".join(context["industries"]) if context["industries"] else "Various industries"

        # Build company profile section
        profile_parts = [f"{context['name']} - {context['location']}"]

        if context["description"]:
            profile_parts.append(context["description"])

        if context["industries"]:
            profile_parts.append(f"Industries: {industries_str}")

        if context["capabilities"]:
            capabilities_str = ", ".join(context["capabilities"])
            profile_parts.append(f"Key capabilities: {capabilities_str}")

        company_profile = "\n".join(profile_parts)

        # Render template with variables
        return render_prompt_template("ceo_assistant", {
            "company_name": context["name"],
            "company_description": context["description"][:100] if context["description"] else "a business",
            "company_profile": company_profile,
            "team_section": team_section
        })

    else:
        # Fallback: build prompt from context (for single-tenant or if template missing)
        logger.warning("⚠️  CEO prompt template not found in database, using fallback")

        # Build team list
        team_lines = []
        for member in context["team"]:
            name = member.get("name", "Unknown")
            title = member.get("title", "")
            role_desc = member.get("role_description", "")

            if title and role_desc:
                team_lines.append(f"- {name} - {title}: {role_desc}")
            elif title:
                team_lines.append(f"- {name} - {title}")
            else:
                team_lines.append(f"- {name}")

        team_section = "\n".join(team_lines) if team_lines else "- Team information not available"

        # Build industries list
        industries_str = ", ".join(context["industries"]) if context["industries"] else "Various industries"

        # Build capabilities list
        capabilities_str = ", ".join(context["capabilities"]) if context["capabilities"] else ""

        # Build company profile section
        profile_parts = [f"{context['name']} - {context['location']}"]

        if context["description"]:
            profile_parts.append(context["description"])

        if context["industries"]:
            profile_parts.append(f"Industries: {industries_str}")

        if context["capabilities"]:
            profile_parts.append(f"Key capabilities: {capabilities_str}")

        company_profile = "\n".join(f"- {part}" if i > 0 else part for i, part in enumerate(profile_parts))

        # Build full prompt template (fallback version)
        prompt = f"""You are the CEO of {context['name']}, {context['description'][:100] if context['description'] else 'a business'}.

COMPANY PROFILE:
{company_profile}

YOUR TEAM:
{team_section}

Below are answers from sub-questions (not raw documents):
---------------------
{{{{context_str}}}}
---------------------

Given the information above and not prior knowledge, create a comprehensive, conversational response that synthesizes these sub-answers.

QUOTING POLICY:
- Use direct quotes when they add value: specific numbers, impactful statements, unique insights
- Keep quotes to 1-2 full sentences maximum
- Don't quote mundane facts or simple status updates
- The sub-answers already contain quotes - use them when relevant

SOURCING:
- The sub-answers may contain markdown links like "[Document Title](url)" - PRESERVE THESE EXACTLY
- If sub-answers don't have markdown links, cite sources naturally: "The ISO checklist shows..." or "According to the QC report..."
- Never break or modify existing markdown links from sub-answers
- Never use technical IDs like "document_id: 180"
- When combining information from multiple sources, cross-reference naturally

HANDLING GAPS:
- If sub-answers don't fully address the question, acknowledge what's missing
- Don't make up information not present in the context
- If sub-answers conflict, present both perspectives

STYLE:
- Conversational and direct - skip formal report language
- Make connections between different pieces of information
- Provide insights and suggestions
- Skip greetings and sign-offs

FORMATTING (markdown):
- Emoji section headers (📦 🚨 📊 🚛 💰 ⚡ 🎯) to organize
- **Bold** for important numbers, names, key points
- Bullet points and numbered lists for structure
- Tables for data comparisons
- ✅/❌ for status
- Code blocks for metrics/dates/technical details

Question: {{{{query_str}}}}
Answer: """

        return prompt


def build_email_classification_context() -> str:
    """
    Build company context for email spam detection.

    NOW LOADS FROM SUPABASE! Falls back to building from context if no template found.

    Used by openai_spam_detector.py for filtering emails.
    """
    context = get_company_context()

    # Try to load template from Supabase first
    template = get_prompt_template("email_classifier")

    if template:
        logger.info("✅ Using email classifier prompt from master Supabase")

        # Build company context section
        context_lines = []

        if context["description"]:
            context_lines.append(f"- Company: {context['description']}")

        if context["capabilities"]:
            context_lines.append(f"- Specializes in: {', '.join(context['capabilities'])}")

        if context["industries"]:
            context_lines.append(f"- Industries served: {', '.join(context['industries'])}")

        company_context = "\n".join(context_lines)

        # Return the header portion (without batch_emails placeholder)
        # The actual email batch will be added by openai_spam_detector.py
        return render_prompt_template("email_classifier", {
            "company_name": context["name"],
            "company_location": context["location"],
            "company_context": company_context,
            "batch_emails": ""  # Will be filled in by openai_spam_detector
        }).rsplit("{{batch_emails}}", 1)[0]  # Remove empty batch_emails placeholder

    else:
        # Fallback: build context from scratch
        logger.warning("⚠️  Email classifier prompt not found in database, using fallback")

        lines = [
            f"You are filtering emails for {context['name']}, located in {context['location']}.",
            "",
            "COMPANY CONTEXT:"
        ]

        if context["description"]:
            lines.append(f"- Company: {context['description']}")

        if context["capabilities"]:
            lines.append(f"- Specializes in: {', '.join(context['capabilities'])}")

        if context["industries"]:
            lines.append(f"- Industries served: {', '.join(context['industries'])}")

        return "\n".join(lines)


def build_vision_ocr_context() -> str:
    """
    Build company context for GPT-4o Vision OCR (file parsing).

    NOW LOADS FROM SUPABASE! Falls back to building from context if no template found.

    Used by file_parser.py for business relevance checks.
    """
    context = get_company_context()

    # Build short description for vision prompts
    if context["description"]:
        desc = context["description"][:150]  # Keep it short for prompts
    else:
        desc = context["name"]

    if context["capabilities"]:
        desc += f" - {', '.join(context['capabilities'][:3])}"  # Top 3 capabilities

    return f"{context['name']} ({desc})"


def get_vision_ocr_business_check_prompt() -> str:
    """
    Get the full GPT-4o Vision business relevance check prompt.

    Returns the template with company context filled in.
    """
    template = get_prompt_template("vision_ocr_business_check")

    if template:
        company_short_desc = build_vision_ocr_context()
        return render_prompt_template("vision_ocr_business_check", {
            "company_short_desc": company_short_desc
        })
    else:
        # Fallback - return empty string, let file_parser use its hardcoded prompt
        return ""


def get_vision_ocr_extract_prompt() -> str:
    """
    Get the full GPT-4o Vision text extraction prompt.

    Returns the template from database (no variables needed).
    """
    return get_prompt_template("vision_ocr_extract", default="")


def get_company_name() -> str:
    """Get company name only."""
    return get_company_context()["name"]


def get_company_description() -> str:
    """Get company description only."""
    return get_company_context()["description"]


def get_company_location() -> str:
    """Get company location only."""
    return get_company_context()["location"]


def get_team_members() -> List[Dict]:
    """Get team members list only."""
    return get_company_context()["team"]
