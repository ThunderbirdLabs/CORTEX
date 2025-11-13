# HighForce CORTEX: Complete System Architecture & User Flow

## Table of Contents
1. [System Overview](#system-overview)
2. [All Applications Explained](#all-applications-explained)
3. [Authentication & Authorization](#authentication--authorization)
4. [Data Flow & Security](#data-flow--security)
5. [User Journey: Standard Build](#user-journey-standard-build)
6. [Enterprise Build Path](#enterprise-build-path)
7. [Admin Operations](#admin-operations)
8. [Data Ownership & Exports](#data-ownership--exports)

---

## System Overview

### What CORTEX Is
**"Turn your scattered business data into an AI that answers questions"**

CORTEX is a multi-tenant RAG (Retrieval-Augmented Generation) platform that:
- Ingests emails, documents, files from various sources
- Builds a knowledge graph of entities (people, companies, deals)
- Enables natural language search across all company data
- Provides secure, isolated intelligence per company

### The "Own Your Intelligence" Model
- **Standard Build**: Managed multi-tenant SaaS ($2500 setup + $899/mo)
- **Enterprise Build**: Self-hosted dedicated infrastructure (Custom pricing)

---

## All Applications Explained

### 1. **CORTEX Backend** (Main Application)
**Location:** `/Users/nicolascodet/Desktop/CORTEX OFFICAL/CORTEX`
**Tech:** FastAPI + Python
**Purpose:** Company operational backend (one per company in multi-tenant, or dedicated instance for enterprise)

**What It Does:**
- OAuth connector management (Nango integration)
- Data ingestion pipelines (emails, documents, files)
- RAG search API (hybrid vector + keyword search)
- Chat API with context-aware responses
- Entity extraction and knowledge graph building
- Spam filtering and document classification

**Database:** Company Supabase (per-company isolated data)
- `documents` - All ingested content
- `chunks` - Vector embeddings for search
- `chats` - User chat history (private per user)
- `connections` - OAuth connection metadata
- `sync_jobs` - Background job tracking
- `entities` - Extracted people/companies/deals

**Infrastructure:**
- Supabase (PostgreSQL + Auth)
- Qdrant (Vector database for embeddings)
- Redis (Job queue for background tasks)
- OpenAI API (Embeddings + LLM)

**Environment Variables:**
- `COMPANY_ID` - Unique company identifier
- `SUPABASE_URL` - Company's Supabase URL
- `QDRANT_URL` - Company's Qdrant cluster
- `REDIS_URL` - Company's Redis instance
- `MASTER_SUPABASE_URL` - Master control plane (multi-tenant mode)

---

### 2. **ConnectorFrontend** (User Dashboard)
**Location:** `/Users/nicolascodet/Desktop/CORTEX OFFICAL/CORTEX/connectorfrontend`
**Tech:** Next.js + React + TypeScript
**Purpose:** End-user interface for CEO/employees

**Pages:**
- `/` - Dashboard (metrics, recent activity)
- `/search` - Natural language search + chat interface
- `/reports` - Saved reports and analytics
- `/team` - User management (invite/remove users)
- `/connections` - OAuth connector management
- `/settings` - User preferences

**Key Features:**
- Natural language search with source citations
- Chat interface with context retention
- Document preview and filtering
- Connection status for Gmail/Outlook/Drive/QuickBooks
- Team member invitation with domain validation
- Export data functionality

**Authentication:** Supabase Auth (JWT tokens)
- Company Supabase for user sessions
- Multi-tenant: User gets `company_id` in JWT metadata

---

### 3. **Master Backend** (Control Plane)
**Location:** `/Users/nicolascodet/Desktop/CORTEX OFFICAL/MASTERBACKEND`
**Tech:** FastAPI + Python
**Purpose:** HighForce admin control plane for managing all companies

**What It Does:**
- Company provisioning (create new tenants)
- Deployment credential management
- Admin authentication and audit logging
- Sync permission overrides
- Company status management (provisioning → active)
- Billing and subscription management (future)

**Database:** Master Supabase (centralized control)
- `companies` - All customer companies
- `company_deployments` - Infrastructure credentials per company
- `nango_original_connections` - OAuth connection tracking
- `sync_permissions` - Admin overrides for sync locks
- `admins` - HighForce admin users
- `audit_log_global` - All admin actions logged

**Admin Endpoints:**
- `POST /companies` - Create new company + auto-create deployment placeholder
- `PATCH /deployments/{company_id}` - Update infrastructure credentials
- `PATCH /companies/{company_id}/sync-permissions` - Enable/disable sync override
- `GET /admin/sync-monitoring` - View all companies' sync states

---

### 4. **Master Frontend** (Admin Dashboard)
**Location:** `/Users/nicolascodet/Desktop/CORTEX OFFICAL/MASTERFRONTEND`
**Tech:** Next.js + React + TypeScript
**Purpose:** HighForce admin interface

**Pages:**
- `/dashboard` - Overview of all companies
- `/companies` - List and manage companies
- `/companies/[id]` - Company details and settings
- `/companies/[id]/deployments` - Edit infrastructure credentials
- `/companies/[id]/sync-permissions` - Override sync locks
- `/admin/sync-monitoring` - Monitor syncs across all companies
- `/admin/users` - Manage HighForce admin users

**Authentication:** Separate admin auth (not customer-facing)
- Admin Supabase with strict RLS policies
- IP whitelisting (optional)
- Session-based auth with audit logging

---

### 5. **Nango** (OAuth Integration Layer)
**Platform:** Nango.dev (3rd party)
**Purpose:** Unified OAuth for all connectors

**Supported Integrations:**
- Gmail (domain-wide delegation)
- Outlook 365 (admin consent)
- Google Drive
- QuickBooks
- Dropbox, OneDrive, Salesforce, HubSpot (future)

**How It Works:**
1. CORTEX calls Nango API to generate OAuth session
2. User completes OAuth in Nango-hosted popup
3. Nango calls webhook: `POST /nango/oauth/callback`
4. CORTEX saves connection_id to database
5. CORTEX fetches data via Nango unified API

**Configuration:** `nango-integrations/nango.yaml`
- 1-year initial backfill for all syncs
- Incremental syncs after first run (hourly/daily)
- Auto-start: false (manual trigger only)

---

## Authentication & Authorization

### Multi-Layer Security Model

#### **Layer 1: JWT Authentication** (Supabase Auth)
```
User → ConnectorFrontend → Login → Supabase Auth
                                    ↓
                              JWT Token with:
                              - user_id (for private data)
                              - company_id (for shared data)
                              ↓
                         All API requests use this token
```

**Token Validation:**
- CORTEX backend validates JWT signature
- Checks `company_id` in metadata matches `COMPANY_ID` env var
- Verifies user exists in `company_users` table (multi-tenant)

#### **Layer 2: Row-Level Security** (RLS)
**In Company Supabase:**
- Chats: Filtered by `user_email` (private per user)
- Documents: Filtered by `company_id` (shared across company)
- Entities: Filtered by `company_id`
- Connections: Filtered by `tenant_id` (user-level)

**In Master Supabase:**
- Companies: Admin-only access
- Deployments: Admin-only access
- Sync permissions: Admin-only access

#### **Layer 3: Company Isolation** (Environment-Based)
```
Company A:
  COMPANY_ID=company-a-uuid
  SUPABASE_URL=company-a.supabase.co
  QDRANT_COLLECTION_NAME=company_a_docs

Company B:
  COMPANY_ID=company-b-uuid
  SUPABASE_URL=company-b.supabase.co
  QDRANT_COLLECTION_NAME=company_b_docs

→ Complete infrastructure isolation
```

#### **Layer 4: Admin Access** (Separate Auth)
- Admin users in separate Master Supabase
- Different auth domain (admin.highforce.com vs app.highforce.com)
- Admin actions logged to `audit_log_global`
- IP whitelisting (optional)

---

## Data Flow & Security

### Ingestion Pipeline

```
Data Sources (Gmail, Drive, etc.)
  ↓
Nango API (OAuth + Sync)
  ↓
CORTEX Backend /sync/initial/{provider}
  ↓
Background Worker (Dramatiq + Redis)
  ↓
Normalization Layer
  ├→ Spam filter (OpenAI classifier)
  ├→ Entity extraction (NER)
  └→ Document chunking
  ↓
Storage Layer (Parallel)
  ├→ Supabase (metadata + full text)
  ├→ Qdrant (vector embeddings)
  └→ Knowledge Graph (entities + relationships)
  ↓
Ready for Search/Chat
```

### Search Flow

```
User Query: "What quality issues did we have with steel suppliers?"
  ↓
ConnectorFrontend /search
  ↓
CORTEX Backend /api/v1/search
  ↓
Hybrid Search Engine
  ├→ Vector search (Qdrant) - semantic similarity
  ├→ Keyword search (Supabase FTS) - exact matches
  └→ Entity graph search - relationships
  ↓
Reranking + Deduplication
  ↓
LLM Response Generation (OpenAI + context)
  ↓
Response with Sources
```

### Chat Flow

```
User: "Tell me more about that issue"
  ↓
ConnectorFrontend /chat
  ↓
CORTEX Backend /api/v1/chat
  ↓
Context Retrieval
  ├→ Previous chat history (Supabase)
  ├→ Referenced documents (from prev answer)
  └→ Related entities (knowledge graph)
  ↓
Augmented Prompt → OpenAI API
  ↓
Streamed Response
```

---

## User Journey: Standard Build

### Phase 1: Sales & Setup ($2500 setup fee)

**1. Inbound Lead**
- Customer fills out form on highforce.com
- Sales call to qualify (budget, use case, data volume)
- Proposal: $2500 setup + $899/mo

**2. Contract Signed**
- Customer pays $2500 setup fee
- Locks in onboarding slot (2-week process)

---

### Phase 2: HighForce Admin Provisions Infrastructure

**Admin Actions (Master Dashboard):**

1. **Create Company Record**
```
Admin → Master Frontend → /companies/new
  Company Name: "Acme Manufacturing"
  Slug: "acme-mfg"
  Owner Email: "ceo@acme.com"
  Plan: "standard"

→ Master Backend: POST /companies
→ Creates company in Master Supabase
→ Auto-creates deployment placeholder (NULL credentials)
→ Status: "provisioning"
```

2. **Provision Infrastructure** (Manual - will automate Phase 2)
```
Admin manually creates:
  ✓ Supabase project (acme-mfg)
  ✓ Qdrant cluster (acme-mfg-cluster)
  ✓ Redis instance (acme-mfg-redis)
  ✓ Render web service (cortex-acme)

Admin → Master Frontend → /companies/{id}/deployments
  Fills in:
  - Supabase URL
  - Supabase keys (anon + service)
  - Qdrant URL + API key
  - Redis URL
  - OpenAI API key

→ Master Backend: PATCH /deployments/{company_id}
→ When Supabase creds present: status → "active"
```

3. **Deploy CORTEX Instance**
```
Admin deploys to Render:
  Service name: cortex-acme
  Repo: CORTEX
  Environment:
    COMPANY_ID=<company_uuid>
    MASTER_SUPABASE_URL=<master_url>
    MASTER_SUPABASE_SERVICE_KEY=<master_key>

  (All other creds loaded from master Supabase automatically)

→ CORTEX starts, loads credentials from deployment record
→ Ready for data ingestion
```

---

### Phase 3: White-Glove Onboarding (2 weeks)

**Week 1: Data Connections**

**HighForce Team Actions:**

1. **Setup OAuth Connectors**
```
Call with CEO:
  Admin: "Let's connect your Gmail and Google Drive"
  CEO: Logs into app.acme-cortex.highforce.com
  CEO: /connections → Clicks "Connect Gmail"

  OAuth Flow:
    → Nango popup opens
    → CEO signs in with Google
    → Grants domain-wide access
    → Webhook: POST /nango/oauth/callback
    → Connection saved in both:
      - Company Supabase (connections table)
      - Master Supabase (nango_original_connections table)
```

2. **Trigger Initial Historical Sync**
```
Still on call:
  Admin (watching): "Now click 'Sync Now' for Gmail"
  CEO: Clicks button

  Modal appears:
    "⚠️ About to sync 1 year of Gmail data
     ⏱ Will take 4-8 hours
     📧 You'll get email when complete
     🔒 This is ONE-TIME, button will disappear
     📞 Need more? Contact sales"

  CEO: Clicks "Start Historical Sync"

  Backend:
    POST /sync/initial/gmail
    → Sets can_manual_sync = FALSE (LOCKED)
    → Creates sync_job (backfill_days: 365)
    → Enqueues background task
    → Returns job_id

  CEO sees: "⏳ Historical sync in progress..."
  Button disappears forever
```

3. **Background Sync Runs** (4-8 hours)
```
Dramatiq Worker:
  → Fetches 365 days of Gmail via Nango API
  → Filters spam/newsletters (OpenAI classifier)
  → Extracts entities (people, companies, deals)
  → Chunks documents (1000 tokens each)
  → Generates embeddings (OpenAI ada-002)
  → Stores in Supabase + Qdrant
  → Builds knowledge graph relationships

  On completion:
    → Sets initial_sync_completed = TRUE
    → Sends email: "Your Gmail sync is complete!"
    → Enables auto-sync (hourly incremental)
```

**Repeat for Outlook, Drive, QuickBooks, etc.**

**Week 2: Training & Optimization**

4. **Custom Prompt Engineering**
```
HighForce team:
  → Analyzes customer's data (industry, terminology)
  → Tunes search prompts for their domain
  → Configures entity types (suppliers, materials, etc.)
  → Sets up custom reports/dashboards
```

5. **Team Onboarding**
```
CEO invites team members:
  /team → "Invite User"

  Modal:
    Email: "manager@acme.com"
    Role: [Admin | User | Viewer]

  Backend validates:
    → Same domain as CEO? (acme.com ✓)
    → Different domain? Show warning

  Manager gets email:
    → Magic link to set password
    → Signs in, data already synced and ready
```

6. **Go-Live Training**
```
HighForce runs training session:
  → How to search (natural language examples)
  → How to chat (asking follow-ups)
  → How to export data
  → How to invite more users

Customer is now live!
```

---

### Phase 4: Production ($899/mo)

**Ongoing Operations:**

**Automatic Syncs:**
```
Nango runs hourly incremental syncs:
  Gmail → New/modified emails since last sync
  Drive → New/modified files since last sync

CORTEX background workers:
  → Fetch new data from Nango API
  → Process and ingest
  → Update knowledge graph
  → Data always up-to-date
```

**User Activity:**
```
CEO searches: "What did John say about the Q3 forecast?"
  → CORTEX retrieves relevant emails/docs
  → LLM generates answer with sources
  → CEO clicks source to view original email

Manager chats: "Summarize our supplier issues this year"
  → Multi-turn conversation
  → Context retained across messages
  → Can ask follow-ups: "Which supplier had most issues?"
```

**Admin Monitoring:**
```
HighForce admin dashboard:
  → Sync status for all companies
  → Error alerts if sync fails
  → Usage metrics (searches, chats, data volume)
  → Billing status
```

**Data Exports:**
```
CEO requests export:
  /settings → "Export My Data"

  Backend generates:
    ├→ documents.jsonl (all documents + metadata)
    ├→ entities.jsonl (knowledge graph)
    ├→ chats.jsonl (chat history)
    └→ embeddings.parquet (vector data)

  Zips and uploads to S3
  Sends download link via email

  → Customer owns their intelligence forever
```

---

## Enterprise Build Path

### When Standard → Enterprise

**Trigger Events:**
1. Customer needs >1 year retention
2. Regulatory compliance (HIPAA, FedRAMP, etc.)
3. Data sovereignty requirements (on-prem)
4. Integration with enterprise systems (SAP, Oracle)
5. Custom SLA requirements

**Pricing Model:**
- Setup: $10-20k (infrastructure + migration)
- Monthly: $2500-5000+ (dedicated infrastructure)
- Contracts: 1-3 year commitments

---

### Enterprise Architecture

**Option A: Dedicated Cloud (Isolated Multi-Tenant)**
```
Customer: "Acme Manufacturing Enterprise"

Infrastructure:
  ✓ Dedicated Supabase project (no sharing)
  ✓ Dedicated Qdrant cluster (larger instances)
  ✓ Dedicated Redis instance
  ✓ Dedicated Render web service (or AWS ECS)
  ✓ Custom domain (cortex.acme.com)

Security:
  ✓ VPN/Private Link to customer network
  ✓ Custom compliance (SOC 2, ISO 27001, etc.)
  ✓ Audit logging + retention
  ✓ SSO integration (SAML, Okta)

Customization:
  ✓ Unlimited historical retention (5+ years)
  ✓ Custom entity types for their industry
  ✓ Custom integrations (SAP, Oracle, etc.)
  ✓ Dedicated CSM
```

**Option B: Self-Hosted (Air-Gapped)**
```
Customer runs CORTEX in their own infrastructure

Deployment:
  ├→ Docker Compose (single-node)
  └→ Kubernetes (multi-node)

Customer provides:
  ✓ Postgres database
  ✓ Redis instance
  ✓ Qdrant cluster (or we host)
  ✓ OpenAI API key (or local LLM)

HighForce provides:
  ✓ Docker images
  ✓ Deployment scripts
  ✓ Update packages
  ✓ Support + training

Customer controls:
  ✓ All infrastructure
  ✓ All data (never leaves their network)
  ✓ All access controls

HighForce still gets:
  ✓ Telemetry (anonymized usage metrics)
  ✓ Support contract revenue
  ✓ Update subscription revenue
```

---

### Enterprise Migration Process

**Phase 1: Planning (Week 1-2)**
```
HighForce team:
  → Audit current data volume
  → Map compliance requirements
  → Design infrastructure architecture
  → Plan migration timeline
```

**Phase 2: Infrastructure Setup (Week 3-4)**
```
Automated provisioning (future):
  → Terraform scripts create infrastructure
  → Kubernetes manifests deploy CORTEX
  → Migration tools prepare data export

Manual (current):
  → HighForce provisions dedicated resources
  → Configures VPN/Private Link
  → Sets up monitoring + alerting
```

**Phase 3: Data Migration (Week 5-6)**
```
Export from standard build:
  → Full database dump (documents, entities, embeddings)
  → S3 transfer to enterprise infrastructure

Import to enterprise:
  → Restore database
  → Rebuild vector indexes
  → Verify data integrity

Zero downtime:
  → Keep standard build running
  → Switch DNS when migration complete
```

**Phase 4: Go-Live (Week 7)**
```
Cutover:
  → DNS points to new enterprise instance
  → OAuth reconnection (if needed for new domain)
  → User acceptance testing
  → Decommission standard build
```

---

### Future: Automated Cluster Creation

**The Vision:**
```
Admin clicks "Upgrade to Enterprise" in Master Dashboard
  ↓
Terraform automation:
  → Creates dedicated Supabase project
  → Creates dedicated Qdrant cluster
  → Creates dedicated Redis instance
  → Creates dedicated Render service (or ECS)
  → Configures networking (VPC, firewall, etc.)
  ↓
Migration automation:
  → Exports data from standard build
  → Imports to enterprise infrastructure
  → Switches DNS
  ↓
Customer upgraded in 1 hour (vs 6 weeks manual)
```

**Tech Stack:**
- Terraform (infrastructure as code)
- Ansible (configuration management)
- GitHub Actions (CI/CD for deployments)
- Pulumi (alternative to Terraform)

---

## Admin Operations

### What HighForce Admins Manage

#### **1. Company Lifecycle**
```
Create → Provision → Onboard → Active → (Optional) Upgrade → (Optional) Churn
```

**Admin Actions:**
- Create new company (POST /companies)
- Update deployment credentials (PATCH /deployments/{id})
- Monitor sync status (GET /admin/sync-monitoring)
- Override sync locks if customer needs re-sync
- Manage billing/subscriptions (future)
- Handle support tickets

#### **2. Sync Management**

**Normal Flow:**
```
CEO connects → Syncs once → Locked forever
```

**Override Flow (Troubleshooting):**
```
Customer: "We're missing emails from last month"
  ↓
Admin investigates:
  → Checks sync_jobs table for errors
  → Finds sync failed mid-way
  ↓
Admin enables override:
  Master Supabase:
    INSERT INTO sync_permissions (company_id, can_manual_sync_override)
    VALUES ('<company_id>', TRUE);
  ↓
Customer re-syncs:
  → Button reappears
  → CEO clicks "Sync Now"
  → Sync runs again
  ↓
Override auto-removed after sync
```

#### **3. Infrastructure Monitoring**

**Admin Dashboard Shows:**
- Company status (active, provisioning, suspended)
- Sync health (last sync time, errors)
- Data volume (documents, embeddings, storage)
- Usage metrics (searches, chats, API calls)
- Cost allocation (Supabase, Qdrant, OpenAI usage)

**Alerts:**
- Sync failed for >24 hours
- Storage approaching limit
- Unusual API usage spike
- Customer requested support

#### **4. Security & Compliance**

**Admin Responsibilities:**
- Audit log review (`audit_log_global`)
- Customer data export requests
- GDPR deletion requests
- Security incident response
- Compliance reporting (SOC 2 audits)

---

## Data Ownership & Exports

### The "Own Your Intelligence" Promise

**Customer Rights:**
1. **Full data export** anytime, for any reason
2. **No vendor lock-in** - we help them migrate
3. **Permanent retention** - even after cancellation
4. **Portable format** - standard JSON/Parquet

---

### Export Formats

**In-App Export (User-Initiated):**
```
/settings → "Export My Data"

Generates ZIP with:
├── documents/
│   ├── documents.jsonl (metadata + content)
│   ├── emails.jsonl (emails only)
│   └── files.jsonl (files only)
├── entities/
│   ├── people.jsonl
│   ├── companies.jsonl
│   └── relationships.jsonl
├── chats/
│   └── chat_history.jsonl
├── embeddings/
│   └── vectors.parquet (OpenAI embeddings)
└── README.md (how to use this data)
```

**Admin-Initiated Export (Support/Migration):**
```
Master Backend:
  POST /admin/companies/{company_id}/export

Full database dump:
  ├→ Supabase backup (pg_dump)
  ├→ Qdrant snapshot (collection export)
  ├→ Redis backup (RDB file)
  └→ All credentials/config

Upload to S3:
  → Secure bucket with time-limited presigned URL
  → Encrypted at rest (AES-256)
  → Expires after 7 days

Send to customer:
  → Email with download link
  → Instructions for restoration
  → Offer migration support
```

---

### Migration Support

**If Customer Leaves:**
```
Customer: "We're moving to Glean/building in-house"

HighForce response:
  1. Full data export (above)
  2. Migration guide:
     - How to import into competitor
     - How to rebuild vector indexes
     - How to migrate users
  3. Transition support:
     - 30-day overlap period
     - Help with data validation
     - Answer technical questions

Why we do this:
  → Removes buying fear
  → Demonstrates confidence in product
  → Creates goodwill (they may come back)
  → Differentiates from competitors
```

---

### Export Automation (Growing Data = Growing Value)

**The Strategy:**
```
Customer accumulates data over time:
  Year 1: 100K documents
  Year 2: 250K documents
  Year 3: 500K documents

Export value grows:
  → More emails/docs = richer intelligence
  → More entities = better knowledge graph
  → More context = better answers

Switching cost increases:
  → "We have 500K documents in here"
  → "Our entire institutional knowledge is in CORTEX"
  → "Can't afford to lose this intelligence"

Result: High retention, low churn
```

**Automatic Backup Schedule:**
```
Weekly snapshots:
  → Full database backup
  → Stored in customer's S3 bucket (optional)
  → Customer owns backups forever

Monthly archives:
  → Compressed long-term storage
  → Cheap S3 Glacier storage
  → Customer can retrieve anytime
```

---

## Summary: The Complete Flow

### Standard Build
```
Sales → $2500 Setup Fee → Admin Provisions (Manual) → White-Glove Onboarding
  ↓                                                         ↓
Customer pays                                    OAuth + Historical Sync
  ↓                                                         ↓
$899/mo                                          Data ingested, locked forever
  ↓                                                         ↓
Production use                                    Auto-sync keeps data current
  ↓                                                         ↓
Data export anytime                              Intelligence grows
```

### Enterprise Build
```
Customer outgrows Standard → Sales Call → $10-20k Setup → Dedicated Infrastructure
  ↓                                                                ↓
Migrate data                                              Custom compliance + integrations
  ↓                                                                ↓
$2500-5000/mo                                             Dedicated CSM + support
  ↓                                                                ↓
Long-term contract                                        Customer owns infrastructure option
```

### Who Manages What

| **Resource** | **Standard Build** | **Enterprise Build** | **Who Manages** |
|--------------|-------------------|---------------------|-----------------|
| Supabase | Shared/Isolated project | Dedicated project | HighForce (standard) / Customer option (enterprise) |
| Qdrant | Shared cluster | Dedicated cluster | HighForce (standard) / Customer option (enterprise) |
| Redis | Shared instance | Dedicated instance | HighForce (standard) / Customer option (enterprise) |
| CORTEX Backend | Shared Render service | Dedicated service/self-hosted | HighForce (standard) / Customer option (enterprise) |
| OAuth Tokens | Nango (shared) | Nango (dedicated) / Customer IDP | Nango / Customer option (enterprise) |
| Data | Customer-owned, HighForce-managed | Customer-owned, customer-managed (optional) | Customer owns, HighForce manages (standard) |
| Backups | HighForce S3 | Customer S3 / On-prem | HighForce (standard) / Customer (enterprise) |
| Auth | Supabase Auth | Supabase Auth / SSO | HighForce (standard) / Customer IDP (enterprise) |

---

## Next Steps

### Immediate (Current State)
- ✅ Multi-tenant auth working
- ✅ One-time sync with admin override
- ✅ User invitation system
- ✅ Team management
- ✅ Chat privacy per user
- ⏳ Frontend modal for sync confirmation

### Phase 2 (Next 2-4 weeks)
- [ ] Automate infrastructure provisioning (Terraform)
- [ ] Admin dashboard for sync monitoring
- [ ] In-app data export functionality
- [ ] Automatic weekly backups
- [ ] Billing integration (Stripe)

### Phase 3 (Enterprise Ready)
- [ ] Self-hosted deployment packages
- [ ] SSO integration (SAML, Okta)
- [ ] Custom compliance reports
- [ ] Enterprise migration automation
- [ ] Dedicated CSM portal

---

**The Bottom Line:**

You're selling **business transformation disguised as SaaS**. The $2500 setup fee + white-glove onboarding ensures success. The data ownership guarantee removes buying fear. The export functionality builds trust and growing data creates switching costs.

This is how you compete with Glean/Notion AI - not on features, but on **ownership, control, and permanent value**.
