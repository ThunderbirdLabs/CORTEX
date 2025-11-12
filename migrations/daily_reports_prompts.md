# Daily Reports - Prompts to Add to Supabase

Add these to `company_prompts` table in MASTER Supabase with your `company_id`.

---

## 1. daily_report_client_relationships

**prompt_name:** Client Relationships Daily Report Synthesis
**prompt_description:** Synthesizes query answers into daily client relationships report

**prompt_template:**
```
You are creating the daily Client Relationships report for {company_name}.

REPORT DATE: {report_date}

You have answers from multiple focused searches about yesterday's client communications.

{previous_context}

SEARCH RESULTS:
{query_answers}

Create a structured report with these sections:
{sections_config}

For each section:
- Use information from the search results
- Include specific names, companies, PO numbers, quotes
- Cite sources with document links when available
- If this relates to something from previous day, add evolution note

Format in markdown with emojis, bold text, and clear structure.
Focus on actionable insights and connections.
```

---

## 2. daily_report_operations

**prompt_name:** Operations Daily Report Synthesis
**prompt_description:** Synthesizes query answers into daily operations report

**prompt_template:**
```
You are creating the daily Operations report for {company_name}.

REPORT DATE: {report_date}

You have answers from multiple focused searches about yesterday's operational activity.

{previous_context}

SEARCH RESULTS:
{query_answers}

Create a structured report with these sections:
{sections_config}

For each section:
- Focus on POs, production status, quality issues, shipments
- Include tracking numbers, quantities, dates
- Mention specific people responsible
- Note blockers or delays
- If continuing from previous day, note evolution

Format in markdown. Be specific and data-driven.
```

---

## 3. daily_report_summary_generator

**prompt_name:** Daily Report Summary Generator
**prompt_description:** Creates 2-3 paragraph summary for next day's context

**prompt_template:**
```
You are creating a concise summary of today's {report_type} report for tomorrow's context.

FULL REPORT:
{full_report}

Create a 2-3 paragraph summary that captures:
- Most important findings
- Key items that need follow-up
- Ongoing situations
- Notable changes from recent days

This summary will be used tomorrow to provide context. Focus on continuity and open items.

Write in past tense, be specific with names/numbers, keep it under 500 words.
```

---

## 4. daily_report_dynamic_questions

**prompt_name:** Dynamic Question Generator
**prompt_description:** Generates follow-up questions from previous day's key items

**prompt_template:**
```
You are generating follow-up questions for today's daily report based on yesterday's findings.

YESTERDAY'S SUMMARY:
{previous_summary}

KEY ITEMS TO FOLLOW UP ON:
{key_items_json}

PREVIOUS REPORT DATE: {previous_date}

Generate {max_questions} specific follow-up questions that check on:
- Issues that were unresolved
- Shipments that were scheduled
- Approvals that were pending
- Commitments that were made
- Problems that were identified

Make questions specific (mention company names, PO numbers, etc.).
Do NOT include dates (time filtering handled separately).

Output one question per line, no numbering.
```

---

## 5. daily_report_key_items_extractor

**prompt_name:** Key Items Extractor
**prompt_description:** Extracts structured data from report for dynamic questions

**prompt_template:**
```
Extract key items from this report that should be followed up on tomorrow.

REPORT:
{full_report}

Extract and structure as JSON:
{{
  "client_issues": [
    {{"company": "ACME Corp", "issue": "late shipment", "urgency": "high", "po": "123"}}
  ],
  "pending_approvals": ["7020-9036", "7020-9037"],
  "scheduled_shipments": [
    {{"company": "TTI Inc", "expected_date": "2025-11-13", "tracking": "885403557633"}}
  ],
  "open_questions": ["Need to confirm MOOG red-line approval"],
  "commitments_made": [
    {{"who": "Hayden", "what": "ship by Wednesday", "to_whom": "Debbie at AEMT"}}
  ]
}}

Only include items that genuinely need follow-up. Return valid JSON only.
```

---

## Instructions

1. Go to MASTER Supabase → `company_prompts` table
2. Insert 5 new rows with your `company_id`
3. Copy each prompt_template above
4. Set `is_active = true`
5. Test by running: `get_prompt_template('daily_report_client_relationships')`
