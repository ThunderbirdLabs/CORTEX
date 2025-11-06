# Intelligence & Identity Resolution System - Complete Guide

## Overview

CORTEX's Intelligence and Identity Resolution systems work together to provide **Claude-style personalized business intelligence summaries** that are deeply contextual and actionable.

**The Problem We Solve:**
- Same person shows up as multiple identities across platforms
- Daily activity gets lost in noise - hard to track who's doing what
- Generic summaries that don't tell you anything useful
- No way to track trends, blockers, or strategic progress

**The Solution:**
1. **Identity Resolution** - Unify people across platforms into canonical identities
2. **Intelligence Aggregation** - Pre-compute detailed summaries with actual context
3. **AI Summaries** - Claude-style personalized briefings

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ INCOMING DATA (Gmail, Outlook, QuickBooks, Drive, Slack)       │
│ ramiro@socalplastics.com sends email about "URGENT Waterless"  │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ IDENTITY RESOLUTION (Real-time during sync)                     │
│                                                                  │
│ 1. Check: Have we seen ramiro@socalplastics.com before?        │
│    - YES → Return existing canonical_id                         │
│    - NO  → Fuzzy match by email domain + name similarity        │
│           → Create new canonical identity if no match           │
│                                                                  │
│ 2. Result:                                                      │
│    canonical_identity_id: "550e8400-..."                       │
│    canonical_name: "Ramiro"                                    │
│    confidence: 1.0                                              │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ DOCUMENT STORAGE (Supabase documents table)                    │
│                                                                  │
│ {                                                               │
│   "title": "Re: URGENT Delivery and response Waterless",      │
│   "content": "Full email body...",                             │
│   "source": "gmail",                                            │
│   "document_type": "email",                                     │
│   "ingested_at": "2025-11-05T14:23:00Z",                       │
│   "metadata": {                                                 │
│     "sender_address": "ramiro@socalplastics.com",             │
│     "sender_name": "Ramiro",                                   │
│     "canonical_identity_id": "550e8400-...",  // ← IDENTITY!   │
│     "canonical_name": "Ramiro"                // ← IDENTITY!   │
│   }                                                             │
│ }                                                               │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
         [Documents accumulate throughout the day...]
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ MIDNIGHT: DAILY INTELLIGENCE AGGREGATION                        │
│                                                                  │
│ 1. Query all documents from yesterday (by ingested_at)         │
│ 2. Group by canonical_name (not email!)                        │
│    - Ramiro: 41 documents                                      │
│    - Lydia: 12 documents                                       │
│    - Solomon: 8 documents                                      │
│ 3. Extract sample email subjects per person                    │
│    - Ramiro: ["URGENT Waterless", "Safran Meeting Notes"]     │
│ 4. Query Neo4j for company mentions                            │
│    - So Cal Plastics: 45 mentions                             │
│    - Safran Group: 23 mentions                                 │
│ 5. Calculate QuickBooks metrics                                │
│ 6. Build rich context with all this data                       │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ AI SUMMARY GENERATION (OpenAI GPT-4o-mini)                     │
│                                                                  │
│ Prompt includes:                                                │
│ - Per-person activity with email subjects                      │
│ - Company relationships and themes                             │
│ - Financial data                                                │
│ - Specific PO numbers, project names                           │
│                                                                  │
│ Style: Claude's "Here's what I remember" - conversational,     │
│        specific, deeply contextual                              │
│                                                                  │
│ Output: 6-10 detailed paragraphs covering:                     │
│ - People Activity (person-by-person breakdowns)                │
│ - Company Overview (relationship dynamics)                      │
│ - Urgent Items (blockers, time-sensitive issues)               │
│ - Financial Activity                                            │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ STORAGE (Supabase daily_intelligence table)                    │
│                                                                  │
│ {                                                               │
│   "tenant_id": "23e4af88-...",                                 │
│   "date": "2025-11-05",                                        │
│   "total_documents": 348,                                      │
│   "document_counts": {"email": 175, "attachment": 173},       │
│   "most_active_people": [                                      │
│     {                                                           │
│       "name": "Ramiro",                                        │
│       "count": 41,                                             │
│       "sample_subjects": ["URGENT Waterless", "Safran..."]    │
│     }                                                           │
│   ],                                                            │
│   "most_active_companies": [...],                             │
│   "ai_summary": "**Ramiro at So Cal Plastics**: Ramiro has..." │
│ }                                                               │
│                                                                  │
│ → Ready for dashboards, email reports, API queries!            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 1: Identity Resolution System

### The Problem

Without identity resolution:
```
Documents from ramiro@socalplastics.com → Counted as "ramiro@socalplastics.com"
Documents from ramiro@gmail.com        → Counted as "ramiro@gmail.com"
QuickBooks customer "Ramiro Rodriguez"  → Counted as "Ramiro Rodriguez"
```

❌ **Result:** Same person counted as 3 separate people!

### The Solution

With identity resolution:
```
ramiro@socalplastics.com  ─┐
ramiro@gmail.com          ─┼─→ canonical_id: 550e8400-...
QuickBooks "Ramiro"       ─┘   canonical_name: "Ramiro"
```

✅ **Result:** One unified identity across all platforms!

### How It Works

**When an email arrives:**

```python
# In app/services/sync/persistence.py (line 116)

# 1. Email normalized from Gmail/Outlook
email = {
    "sender_address": "ramiro@socalplastics.com",
    "sender_name": "Ramiro",
    "subject": "Re: URGENT Waterless delivery"
}

# 2. Resolve identity
from app.services.identity import resolve_identity

identity = await resolve_identity(
    supabase=supabase,
    tenant_id="user-123",
    platform="gmail",
    email="ramiro@socalplastics.com",
    platform_user_id="ramiro@socalplastics.com",
    display_name="Ramiro"
)

# 3. Returns:
{
    "canonical_identity_id": "550e8400-e29b-41d4-a716-446655440000",
    "canonical_name": "Ramiro",
    "canonical_email": "ramiro@socalplastics.com",
    "is_new": False,  # Found existing identity
    "confidence": 1.0,
    "match_reason": "Exact email match"
}

# 4. Document metadata gets tagged
metadata = {
    "sender_address": "ramiro@socalplastics.com",
    "sender_name": "Ramiro",
    "canonical_identity_id": "550e8400-...",  # ← Added!
    "canonical_name": "Ramiro"                 # ← Added!
}
```

### Matching Algorithm

**Tier 1: Exact Match (Confidence 1.0)**
- Email address already exists → instant match
- Same `platform` + `platform_user_id` → instant match

**Tier 2: High Confidence Fuzzy (≥0.9)**
- Same email domain + high name similarity
- Example: `r.rodriguez@socalplastics.com` + "R. Rodriguez" matches `ramiro@socalplastics.com` + "Ramiro" (same domain, initials match)
- **Action:** Auto-merge

**Tier 3: Medium Confidence (0.75-0.89)**
- Same domain + moderate name similarity
- **Action:** Add to admin review queue

**Tier 4: Low Confidence (<0.75)**
- Name similarity only, no email match
- **Action:** Create new identity (assume different person)

### Database Schema

**canonical_identities** - One record per unique person
```sql
CREATE TABLE canonical_identities (
    id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    canonical_name TEXT NOT NULL,     -- "Ramiro"
    canonical_email TEXT,              -- ramiro@socalplastics.com
    is_team_member BOOLEAN,
    metadata JSONB
);
```

**platform_identities** - Links platform IDs to canonical identity
```sql
CREATE TABLE platform_identities (
    canonical_identity_id UUID REFERENCES canonical_identities(id),
    platform TEXT NOT NULL,            -- 'gmail', 'outlook', 'quickbooks'
    platform_user_id TEXT NOT NULL,    -- ramiro@socalplastics.com
    display_name TEXT,                 -- How name appears on platform
    confidence FLOAT                   -- 0.0-1.0
);
```

**email_aliases** - All emails for a person
```sql
CREATE TABLE email_aliases (
    canonical_identity_id UUID REFERENCES canonical_identities(id),
    email_address TEXT NOT NULL,       -- Normalized (lowercase)
    is_primary BOOLEAN,
    source_platform TEXT,
    usage_count INT
);
```

### Example Data Flow

```
1. First email from ramiro@socalplastics.com
   → Create canonical identity: "Ramiro" (550e8400-...)
   → Add platform_identity: gmail, ramiro@socalplastics.com
   → Add email_alias: ramiro@socalplastics.com

2. Email from ramiro@gmail.com (same person, different email)
   → Fuzzy match: Same domain? NO. Name match? YES (Ramiro).
   → Confidence < 0.75 (different domain)
   → Create NEW canonical identity OR add to review queue

3. Email from ramiro@socalplastics.com again
   → Exact match! canonical_id: 550e8400-...
   → Document tagged with existing identity
```

---

## Part 2: Intelligence Aggregation System

### Daily Intelligence (Runs at Midnight UTC)

**What It Does:**
Analyzes all documents from the previous day and generates a detailed, personalized summary.

**Data Collected:**

```python
# From app/services/intelligence/aggregator.py

metrics = {
    "total_documents": 348,
    "document_counts": {
        "email": 175,
        "attachment": 173,
        "invoice": 0
    },
    "most_active_people": [
        {
            "name": "Ramiro",                    # ← Uses canonical_name!
            "count": 41,
            "sample_subjects": [
                "Re: URGENT Delivery and response Waterless",
                "Safran WWS Meeting Notes",
                "Re: PO #19632-03 Status"
            ]
        },
        {
            "name": "Lydia",
            "count": 12,
            "sample_subjects": [
                "Fw: TE:PO2733337311-NAmerica Purcha-482799",
                "Supplier Quality Certification Expiration"
            ]
        }
    ],
    "most_active_companies": [
        {"name": "So Cal Plastics", "count": 45},
        {"name": "Safran Group", "count": 23}
    ],
    "quickbooks_metrics": {
        "invoice_total": 12450.00,
        "invoice_outstanding": 4250.00
    },
    "sample_subjects": [
        "URGENT Waterless delivery",
        "PO #19632-03 follow-up",
        "Supplier certification renewal",
        ...  // 20 total for AI context
    ]
}
```

**AI Prompt Structure:**

```
You are creating a personalized daily business intelligence summary.

# Daily Activity Report - 2025-11-05

## Overview
Total: 348 documents
- Emails: 175
- Attachments: 173

## People Activity
- Ramiro: 41 documents
  → "Re: URGENT Delivery and response Waterless"
  → "Safran WWS Meeting Notes"
  → "Re: PO #19632-03 Status"
- Lydia: 12 documents
  → "Fw: TE:PO2733337311-NAmerica Purcha-482799"
  → "Supplier Quality Certification Expiration"

## Company Activity
- So Cal Plastics: 45 mentions
- Safran Group: 23 mentions

## Sample Email Subjects
- URGENT Waterless delivery
- PO #19632-03 follow-up
- Supplier certification renewal
...

Instructions:
- Summarize each person's activity using their actual email subjects
- Highlight urgent issues, blockers, or major accomplishments
- Note specific PO numbers, project names, deliverables
- Group activity by company
- Call out urgent items requiring attention

Style: Write like Claude's "Here's what I remember" summaries
Length: 6-10 detailed paragraphs
```

**AI Output Example:**

```markdown
## People Activity

**Ramiro at So Cal Plastics**: Ramiro has been particularly active today,
engaging in 41 documents. A significant point of focus appears to be the
urgent delivery issue related to the "Waterless" project, as evidenced by
multiple email threads titled "Re: URGENT Delivery and response Waterless."
This suggests that there may be time-sensitive concerns regarding a product
or service delivery that could impact client satisfaction or operational
timelines. Additionally, he is involved in discussions surrounding the meeting
notes from a recent collaboration with Safran, indicating ongoing projects
that require meticulous follow-up and possibly a strategic alignment on
deliverables.

**Lydia at Superior Mold**: With 12 documents, Lydia's activity revolves
around purchase orders and supplier quality certifications. The emails titled
"Fw: TE:PO2733337311-NAmerica Purcha-482799" and "Fw: TE Connectivity -
Supplier Quality Certification Expiration Notice" highlight her role in
ensuring compliance and timely procurement...

## Company Overview

The activity today highlights a significant collaboration between So Cal
Plastics and Safran Group, emphasizing the importance of timely communication
and project management in their partnership. Ramiro's urgent delivery issues
could potentially impact their ongoing projects together...

## Urgent Items

The most pressing matter today is Ramiro's urgent delivery issue concerning
"Waterless." This could have cascading effects on client satisfaction and
operational timelines if not addressed promptly. Additionally, Solomon's
repeated references to P.O #19632-03 signal that there may be unresolved
issues that require immediate clarification...
```

**Stored in Database:**

```sql
INSERT INTO daily_intelligence (
    tenant_id,
    date,
    total_documents,
    document_counts,
    most_active_people,
    most_active_companies,
    ai_summary
) VALUES (
    '23e4af88-...',
    '2025-11-05',
    348,
    '{"email": 175, "attachment": 173}',
    '[{"name": "Ramiro", "count": 41, ...}]',
    '[{"name": "So Cal Plastics", "count": 45}]',
    'The detailed AI summary above...'
);
```

### Weekly Intelligence (Runs Monday 1am UTC)

**Focus:** Company-wide strategic overview, not person-by-person

**Sections:**
- **Week in Review** - What shipped, what got completed
- **Goals vs Reality** - What we tried vs what happened
- **Trends & Patterns** - Activity changes, new companies
- **Blockers & Risks** - What's stuck, needs attention
- **Looking Ahead** - Priorities for next week

**Example Output:**

```markdown
## Week in Review

This week, the team completed critical deliverables on the Safran WWS project,
with So Cal Plastics handling urgent waterless system components. Superior
Mold finalized supplier certifications for TE Connectivity, ensuring compliance
before the Q1 deadline. Pacific Metal Stampings resolved the long-standing
PO #19632-03 discrepancy after three rounds of clarification.

## Trends & Patterns

Communication volume with Safran Group increased 48% week-over-week, indicating
ramping project activity. So Cal Plastics emerged as the most active partner
with 167 total exchanges, suggesting they're handling critical path items. New
company LivaNova appeared in 6 documents, potentially signaling a new
partnership in early stages...
```

### Monthly Intelligence (Runs 1st of Month 2am UTC)

**Focus:** Executive-level strategic summary

**Sections:**
- **Executive Summary** - Major wins/challenges
- **Business Performance** - Revenue, pipeline, customers
- **Strategic Initiatives** - Project progress
- **Organizational Health** - Team productivity patterns
- **Risks & Opportunities**
- **Recommendations** - Focus areas for next month

---

## How Canonical IDs Power Intelligence

### Without Canonical IDs

```python
# Counting by email address (BAD)
person_counts = {}
for doc in documents:
    sender = doc['metadata']['sender_address']
    person_counts[sender] = person_counts.get(sender, 0) + 1

# Result:
{
    "ramiro@socalplastics.com": 35,
    "ramiro@gmail.com": 6,           # Same person!
    "r.rodriguez@socalplastics.com": 3  # Same person!
}
```

❌ Ramiro appears 3 times, split across emails!

### With Canonical IDs

```python
# Counting by canonical_name (GOOD)
person_counts = {}
for doc in documents:
    canonical_name = doc['metadata'].get('canonical_name')
    if canonical_name:
        person_counts[canonical_name] = person_counts.get(canonical_name, 0) + 1

# Result:
{
    "Ramiro": 44  # All emails unified!
}
```

✅ Ramiro counted once, accurately!

### The Magic

```sql
-- Query documents by canonical identity
SELECT
    metadata->>'canonical_name' as person,
    metadata->>'canonical_identity_id' as identity_id,
    COUNT(*) as doc_count,
    ARRAY_AGG(title) as subjects
FROM documents
WHERE tenant_id = 'user-123'
  AND ingested_at >= '2025-11-05T00:00:00Z'
  AND ingested_at < '2025-11-06T00:00:00Z'
GROUP BY metadata->>'canonical_name', metadata->>'canonical_identity_id'
ORDER BY doc_count DESC;

-- Returns:
-- person     | identity_id    | doc_count | subjects
-- Ramiro     | 550e8400-...   | 44        | {URGENT Waterless, Safran Meeting, ...}
-- Lydia      | abc-123-...    | 12        | {PO 2733337311, Supplier Cert, ...}
```

This is how the intelligence system knows:
- **WHO** is most active (Ramiro)
- **WHAT** they're working on (Waterless project, Safran)
- **WHY** it matters (urgent delivery issue)

---

## Cron Schedule

```yaml
# render.yaml

# Daily Intelligence - Midnight UTC
- type: cron
  name: daily-intelligence
  schedule: "0 0 * * *"
  startCommand: python -m app.services.jobs.run_daily_intelligence

# Weekly Intelligence - Monday 1am UTC
- type: cron
  name: weekly-intelligence
  schedule: "0 1 * * 1"
  startCommand: python -m app.services.jobs.run_weekly_intelligence

# Monthly Intelligence - 1st of month 2am UTC
- type: cron
  name: monthly-intelligence
  schedule: "0 2 1 * *"
  startCommand: python -m app.services.jobs.run_monthly_intelligence
```

**Timezone Note:**
- Midnight UTC = 4pm PST (previous day) = 7pm EST (previous day)
- So "daily" intelligence for Nov 5th runs at 4pm PST on Nov 5th

---

## API Usage

### Query Daily Intelligence

```python
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Get yesterday's summary
result = supabase.table("daily_intelligence")\
    .select("*")\
    .eq("tenant_id", "user-123")\
    .eq("date", "2025-11-05")\
    .single()\
    .execute()

daily = result.data
print(daily['ai_summary'])  # Claude-style summary
print(daily['most_active_people'])  # [{name, count, subjects}, ...]
```

### Get Weekly Trends

```python
# Get last 30 days of daily summaries
result = supabase.table("daily_intelligence")\
    .select("date, total_documents, most_active_people")\
    .eq("tenant_id", "user-123")\
    .gte("date", "2025-10-06")\
    .order("date", desc=True)\
    .execute()

for day in result.data:
    print(f"{day['date']}: {day['total_documents']} docs")
```

### Find Person Activity Over Time

```python
# Track Ramiro's activity across multiple days
result = supabase.table("daily_intelligence")\
    .select("date, most_active_people")\
    .eq("tenant_id", "user-123")\
    .gte("date", "2025-11-01")\
    .execute()

for day in result.data:
    for person in day['most_active_people']:
        if person['name'] == 'Ramiro':
            print(f"{day['date']}: {person['count']} docs")
            print(f"  Topics: {person['sample_subjects']}")
```

---

## Cost Analysis

### Daily Intelligence

**Per Tenant Per Day:**
- Query documents: ~0.001s (indexed)
- Query Neo4j: ~0.01s
- AI summary (GPT-4o-mini): ~1500 tokens
  - Input: ~800 tokens (context)
  - Output: ~700 tokens (summary)
  - Cost: ~$0.0015

**Monthly Cost:**
- Daily: $0.0015 × 30 = **$0.045/month**
- Weekly: $0.001 × 4 = **$0.004/month**
- Monthly: $0.002 × 1 = **$0.002/month**
- **Total: ~$0.05 per tenant per month**

For 100 tenants: **$5/month**
For 1,000 tenants: **$50/month**

Super cheap because we use GPT-4o-mini!

---

## Migration Commands

```bash
# Run on Supabase
psql $DATABASE_URL < migrations/create_identity_resolution_tables.sql
psql $DATABASE_URL < migrations/create_intelligence_tables.sql
```

Creates:
- `canonical_identities`
- `platform_identities`
- `email_aliases`
- `identity_merge_suggestions`
- `daily_intelligence`
- `weekly_intelligence`
- `monthly_intelligence`

---

## Future Enhancements

### Identity Resolution
- [ ] Phone number matching
- [ ] LinkedIn profile linking
- [ ] Admin UI for merge review queue
- [ ] Bulk merge operations
- [ ] Team member auto-detection

### Intelligence
- [ ] Real-time intelligence (not just daily)
- [ ] Custom goals tracking ("Did we hit our target?")
- [ ] Sentiment analysis per person/company
- [ ] Anomaly detection (unusual activity patterns)
- [ ] Dashboard widgets for CEO briefings
- [ ] Email digests (daily summary sent to inbox)

---

## Troubleshooting

### Intelligence shows "0 people"

**Cause:** Your existing documents don't have `canonical_name` in metadata yet.

**Solution:** Identity resolution only runs on NEW emails going forward. Historical emails need backfill.

**Workaround:** The intelligence system falls back to `sender_address` if no `canonical_name` exists.

### Intelligence using wrong date

**Cause:** Documents don't have `source_created_at` set.

**Solution:** We use `ingested_at` as fallback (when doc was added to DB).

### Summary is too generic

**Check:**
1. Are sample subjects being collected? Look at `sample_subjects` in metrics
2. Are people grouped correctly? Check `most_active_people`
3. Is Neo4j returning companies? Check `most_active_companies`

If all empty → Your docs might not have proper metadata.

---

## Summary

**Identity Resolution:**
- Real-time during email sync
- Unifies people across platforms
- Adds `canonical_identity_id` + `canonical_name` to metadata
- Powers accurate person tracking

**Intelligence System:**
- Runs on schedule (daily/weekly/monthly)
- Groups by canonical identity (not email!)
- Extracts actual email subjects for context
- Generates Claude-style personalized summaries
- Stores in Supabase for instant queries

**Result:**
Instead of generic "348 documents processed" you get:
"Ramiro at So Cal Plastics (41 docs) urgently addressing Waterless delivery issue with Safran. Lydia managing PO #2733337311 supplier certifications. Solomon tracking PO #19632-03 - potential delay requiring attention..."

**Perfect for:** CEO daily briefings, executive dashboards, weekly standups, monthly board reports.

All powered by canonical identities ensuring accurate, unified tracking! 🚀
