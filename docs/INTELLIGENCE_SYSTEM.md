# Multi-Tiered Organizational Intelligence System

## Overview

The Intelligence System adds time-aggregated insights to CORTEX, providing daily, weekly, and monthly summaries of organizational activity. Think of it as adding a **memory layer** to your business data that improves search relevance and provides strategic context.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ RAW DATA (Source of Truth)                                  │
│ documents table - All emails, invoices, files               │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ NIGHTLY AGGREGATION (Background Jobs)                       │
│ ├─ Daily Intelligence (midnight)                            │
│ ├─ Weekly Intelligence (Monday 1am)                         │
│ └─ Monthly Intelligence (1st of month 2am)                  │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ INTELLIGENCE TABLES (Pre-computed Summaries)                │
│ ├─ daily_intelligence: 24-hour activity snapshots           │
│ ├─ weekly_intelligence: 7-day trend analysis                │
│ └─ monthly_intelligence: 30-day strategic insights          │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ API ENDPOINTS (Fast Retrieval)                              │
│ GET /api/v1/intelligence/daily?date=YYYY-MM-DD              │
│ GET /api/v1/intelligence/weekly?week_start=YYYY-MM-DD       │
│ GET /api/v1/intelligence/monthly?month=YYYY-MM-01           │
└─────────────────────────────────────────────────────────────┘
```

## What Gets Computed

### Daily Intelligence (24-hour snapshots)
Generated nightly at midnight for yesterday's data.

**Metrics:**
- Document counts by type (email, invoice, bill, payment, pdf)
- QuickBooks financial totals (revenue, expenses, payments)
- Entity activity (top 10 people, companies mentioned)
- Email communication patterns (top senders, recipients)
- Key topics/themes from content
- AI-generated natural language summary

**Example Response:**
```json
{
  "date": "2025-11-05",
  "metrics": {
    "total_documents": 47,
    "document_counts": {"email": 35, "invoice": 12},
    "invoice_total_amount": 50000.00
  },
  "entities": {
    "most_active_people": [
      {"name": "Alex Thompson", "mentions": 15},
      {"name": "Sarah Chen", "mentions": 8}
    ]
  },
  "ai_summary": "Yesterday saw high activity with 47 documents..."
}
```

### Weekly Intelligence (7-day trends)
Generated every Monday at 1am for the previous week.

**Metrics:**
- Week-over-week activity changes
- Trending entities (increasing mentions)
- New relationships discovered
- Business momentum indicators (deals advancing/stalling)
- Weekly financial summary
- AI-generated weekly insights

**Example Response:**
```json
{
  "week_start": "2025-11-04",
  "week_end": "2025-11-10",
  "metrics": {
    "total_documents": 234,
    "wow_change_percent": 15.3
  },
  "trends": {
    "trending_people": [
      {"name": "Alex Thompson", "mentions": 45, "trend": "up"}
    ]
  },
  "weekly_summary": "This week showed strong momentum with..."
}
```

### Monthly Intelligence (30-day insights)
Generated on the 1st of each month at 2am for the previous month.

**Metrics:**
- Monthly activity summary (documents, emails, invoices)
- Financial performance (revenue, expenses, net income)
- Top customers and revenue breakdown
- Entity evolution (new entities, expertise development)
- Month-over-month trends
- Strategic alignment indicators
- AI-generated executive summary

**Example Response:**
```json
{
  "month": "2025-11-01",
  "month_name": "November 2025",
  "financial_summary": {
    "total_revenue": 250000.00,
    "net_income": 85000.00,
    "revenue_by_customer": [
      {"customer": "Acme Corp", "revenue": 75000.00}
    ]
  },
  "executive_summary": "November showed strong growth with..."
}
```

## Database Schema

### Tables Created

**`daily_intelligence`**
- Primary key: `(tenant_id, date)`
- Stores 24-hour activity snapshots
- JSONB columns for flexible metrics
- AI summary text field

**`weekly_intelligence`**
- Primary key: `(tenant_id, week_start)`
- Stores 7-day trend analysis
- Week-over-week comparison metrics
- Trending entity tracking

**`monthly_intelligence`**
- Primary key: `(tenant_id, month)`
- Stores 30-day strategic insights
- Financial performance metrics
- Executive summary field

### Indexes
- Multi-column indexes on `(tenant_id, date)` for fast retrieval
- Descending date indexes for "latest" queries

## API Endpoints

### Daily Intelligence

#### Get Specific Date
```http
GET /api/v1/intelligence/daily?date=2025-11-05
Authorization: Bearer <token>
```

#### Get Latest
```http
GET /api/v1/intelligence/daily/latest
Authorization: Bearer <token>
```

### Weekly Intelligence

#### Get Specific Week
```http
GET /api/v1/intelligence/weekly?week_start=2025-11-04
Authorization: Bearer <token>
```

#### Get Latest
```http
GET /api/v1/intelligence/weekly/latest
Authorization: Bearer <token>
```

### Monthly Intelligence

#### Get Specific Month
```http
GET /api/v1/intelligence/monthly?month=2025-11-01
Authorization: Bearer <token>
```

#### Get Latest
```http
GET /api/v1/intelligence/monthly/latest
Authorization: Bearer <token>
```

### Trend Analysis

#### Daily Trends (Time Series)
```http
GET /api/v1/intelligence/trends/daily?days=30
Authorization: Bearer <token>
```

Returns time series data for charting.

#### Weekly Trends
```http
GET /api/v1/intelligence/trends/weekly?weeks=12
Authorization: Bearer <token>
```

#### Monthly Trends
```http
GET /api/v1/intelligence/trends/monthly?months=12
Authorization: Bearer <token>
```

### Health Check
```http
GET /api/v1/intelligence/health
Authorization: Bearer <token>
```

Returns data availability status.

## Background Jobs

### Cron Schedule

**Daily Intelligence**
- Schedule: `0 0 * * *` (midnight daily)
- Runtime: ~30 seconds per tenant
- Generates: Previous day's summary

**Weekly Intelligence**
- Schedule: `0 1 * * 1` (Monday 1am)
- Runtime: ~1-2 minutes per tenant
- Generates: Previous week's trends

**Monthly Intelligence**
- Schedule: `0 2 1 * *` (1st of month 2am)
- Runtime: ~2-3 minutes per tenant
- Generates: Previous month's insights

### Manual Triggering

To manually generate intelligence for a specific tenant:

```python
from app.services.jobs.intelligence_tasks import (
    generate_daily_intelligence_task,
    generate_weekly_intelligence_task,
    generate_monthly_intelligence_task
)

# Generate yesterday's daily intelligence
generate_daily_intelligence_task.send("user-123", "2025-11-05")

# Generate last week's intelligence (Monday date)
generate_weekly_intelligence_task.send("user-123", "2025-11-04")

# Generate last month's intelligence (1st of month)
generate_monthly_intelligence_task.send("user-123", "2025-11-01")
```

## Implementation Details

### Data Flow

1. **Raw Documents** → Stored in `documents` table during sync
2. **Background Job** → Runs nightly, queries documents by date range
3. **Aggregation** → Calculates metrics, queries Neo4j for entity activity
4. **AI Summary** → Generates natural language summary with OpenAI
5. **Storage** → Upserts into intelligence table
6. **API** → Fast retrieval of pre-computed data

### Multi-Tenant Isolation

All intelligence tables include `tenant_id` column:
- Each tenant's data is completely isolated
- Queries always filter by `tenant_id`
- Background jobs process all tenants sequentially

### Performance Characteristics

**Generation Time:**
- Daily: ~30 seconds (queries 50-100 documents)
- Weekly: ~1-2 minutes (aggregates 7 daily records)
- Monthly: ~2-3 minutes (aggregates 4 weekly records)

**API Response Time:**
- All endpoints: <100ms (pre-computed data)
- No expensive calculations at query time
- Simple SELECT queries with indexes

### AI Summary Generation

Uses GPT-4o-mini for cost-effective summaries:
- Daily: 2-3 sentence summary
- Weekly: 3-4 sentence trend analysis
- Monthly: 4-5 sentence executive summary

**Prompt Engineering:**
- Context includes key metrics
- Focuses on insights, not just numbers
- Executive-friendly language

## Migration & Setup

### 1. Run Database Migration

```bash
# Apply schema to Supabase
psql $DATABASE_URL < migrations/create_intelligence_tables.sql
```

### 2. Initialize Supabase Client

The system uses the global `supabase_client` initialized at startup.

### 3. Deploy Cron Jobs

Cron jobs are defined in `render.yaml` and automatically deployed with Render.

### 4. Test Manually

```python
# Test daily intelligence generation
python -m app.services.jobs.run_daily_intelligence
```

## Monitoring & Debugging

### Check Job Status

```bash
# Render dashboard → Cron Jobs → View logs
```

### Query Intelligence Data Directly

```sql
-- Check if daily intelligence exists
SELECT date, total_documents, ai_summary
FROM daily_intelligence
WHERE tenant_id = 'user-123'
ORDER BY date DESC
LIMIT 10;

-- Check computation performance
SELECT date, computation_duration_ms
FROM daily_intelligence
WHERE tenant_id = 'user-123'
ORDER BY date DESC;
```

### Common Issues

**No data generated:**
- Check if documents exist for the date range
- Verify cron job ran successfully in Render logs
- Ensure Supabase client is initialized

**Slow generation:**
- Check Neo4j query performance
- Verify indexes exist on `documents.source_created_at`
- Monitor OpenAI API latency

**Missing AI summaries:**
- Check OpenAI API key is configured
- Verify OpenAI API quota
- Review error logs for LLM failures

## Future Enhancements

### Near-term (1-2 weeks)
- [ ] Real-time dashboard widgets
- [ ] Historical comparison charts
- [ ] Export to PDF/PowerPoint
- [ ] Email digest notifications

### Medium-term (1-2 months)
- [ ] Anomaly detection alerts
- [ ] Custom metric definitions per tenant
- [ ] Sentiment analysis integration
- [ ] Predictive trends (ML-based)

### Long-term (3-6 months)
- [ ] Natural language queries ("How did we do last quarter?")
- [ ] Automated insights recommendations
- [ ] Goal tracking and alignment scoring
- [ ] Executive briefing generation

## Integration with Search

### Current State
Intelligence data is stored separately and retrieved via dedicated endpoints.

### Future Integration
- Search queries could reference intelligence summaries
- "What happened last week?" → Fetches weekly intelligence
- "How's revenue trending?" → Shows monthly financial trends
- Context-aware answers using time-aggregated data

## Cost Analysis

### Storage
- ~1KB per daily record → ~365KB per year per tenant
- ~5KB per weekly record → ~260KB per year per tenant
- ~10KB per monthly record → ~120KB per year per tenant
- **Total: <1MB per tenant per year**

### Compute
- Daily job: ~30 seconds × 365 days = ~3 hours/year per tenant
- Weekly job: ~1 minute × 52 weeks = ~1 hour/year per tenant
- Monthly job: ~2 minutes × 12 months = ~24 minutes/year per tenant
- **Total: ~5 hours/year per tenant**

### OpenAI API
- ~300 tokens per summary × 3 periods/day × 365 days = ~330K tokens/year
- At $0.15/1M tokens (GPT-4o-mini input) = **$0.05/year per tenant**

## Security Considerations

- All endpoints require authentication (`get_current_user_id`)
- Tenant isolation enforced at database query level
- No cross-tenant data leakage possible
- JSONB columns sanitized before storage
- Rate limiting inherited from FastAPI middleware

## Conclusion

The Intelligence System transforms CORTEX from a search tool into a **strategic intelligence platform**. By pre-computing time-aggregated summaries, it provides:

✅ **Fast retrieval** - Sub-100ms API responses
✅ **Strategic context** - Understand trends and patterns
✅ **Executive insights** - AI-generated summaries
✅ **Historical analysis** - Track changes over time
✅ **Scalable architecture** - Low storage and compute costs

The system is production-ready and designed to run autonomously with minimal maintenance.
