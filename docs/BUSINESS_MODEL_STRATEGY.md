# Unit Industries - Business Model & Roadmap

## Current Phase: Custom Dedicated Deployments (NOW)

### How It Works Today

**Customer Setup:**
- Customer creates their own infrastructure accounts:
  - Neo4j Aura (they own the account)
  - Qdrant Cloud (they own the account)
  - Supabase/PostgreSQL (they own the account)
  - DigitalOcean (optional, for self-hosting)

**We Provide:**
- Render backend deployment (our infrastructure)
- Frontend deployment (Vercel, white-labeled)
- Connection to THEIR databases via environment variables
- Background processing and ingestion pipelines
- Ongoing management and monitoring

**Customer Value Proposition:**
- **"You Own Your Data"** - Literally. We connect to YOUR databases.
- **No Vendor Lock-In** - If you leave, you keep all your data in your accounts
- **Full Control** - You can audit, backup, export anytime
- **Compliance-Ready** - Your data stays in your infrastructure

**Pricing:**
- Software & Management: $5,000 - $10,000/month
- Their Infrastructure Costs: ~$100-200/month (paid by them)
- Our Infrastructure Costs: $25-50/month (Render backend)

**Onboarding Time:** 2-4 hours (manual setup)

---

## Future Phase: True SaaS with Data Ownership (2-3 Months)

### What We're Building

**Auto-Provisioned Dedicated Infrastructure:**

When a customer signs up, we automatically:
1. Create a dedicated Neo4j database in our Neo4j cluster (or provision Aura instance via API)
2. Create a dedicated Qdrant collection in our Qdrant cluster
3. Create a dedicated PostgreSQL schema/database in our Supabase project
4. Store their connection details in our customer database
5. Initialize their knowledge graph with proper schema
6. Send them credentials and access

**Technical Implementation:**

```
Customer Signs Up
    ↓
Provisioning Script Runs:
    - CREATE DATABASE customer_abc123 (Neo4j)
    - CREATE COLLECTION customer_abc123 (Qdrant)  
    - CREATE SCHEMA customer_abc123 (PostgreSQL)
    ↓
Store Configuration:
    customer_infrastructure table with their DB URIs/credentials
    ↓
Dynamic Routing:
    Every API call routes to customer's dedicated databases
    ↓
Customer Starts Using:
    Connect Gmail/Drive → Data syncs to THEIR databases
```

**Key Technical Features:**
- Dynamic database routing based on user_id
- Physical isolation (separate databases/collections per customer)
- One backend serves all customers (cost-efficient)
- Self-service signup and provisioning
- Automated backups per customer

**Customer Still "Owns" Their Data:**

Even though we provision and manage it, customers get:
- **Full Export Capabilities:**
  - One-click export to their own Neo4j instance
  - One-click export to their own Qdrant instance
  - PostgreSQL dump available anytime
  - Standard formats (JSON, CSV, Cypher scripts)

- **Data Portability:**
  - Export knowledge graph as Cypher script
  - Export vectors as JSONL with embeddings
  - Export all documents and metadata
  - Can spin up their own instance and import

- **Migration Path:**
  - If they want to self-host, we provide migration tools
  - Export → Spin up their own Neo4j/Qdrant → Import → Done
  - They can continue using our software pointed at their infrastructure
  - Or take the data and leave entirely

**Pricing Tiers:**

**Professional ($2,500/month):**
- Shared backend, dedicated databases
- Up to 50,000 documents
- Standard support
- Monthly exports

**Business ($5,000/month):**
- Dedicated databases in premium tier
- Up to 250,000 documents
- Priority support
- Daily backups
- Real-time export API

**Enterprise ($15,000/month):**
- Fully dedicated Render instance
- Unlimited documents
- 24/7 support
- Continuous sync to customer's infrastructure
- Air-gapped deployment options

**Why This Works:**
- ✅ Easy signup (self-service)
- ✅ Physical isolation (separate databases)
- ✅ Customer owns their data (export anytime)
- ✅ No vendor lock-in (migration tools)
- ✅ Scales to 100+ customers
- ✅ Lower per-customer costs for us

**Development Timeline:** 2-3 months
- Week 1-2: Dynamic database routing
- Week 3-4: Auto-provisioning scripts
- Week 5-6: Export/migration tools
- Week 7-8: Self-service signup flow
- Week 9-10: Admin panel for customer management
- Week 11-12: Testing and refinement

---

## Government Contractor Use Case Example

### The Market Opportunity

**Target Customers:**
- Defense contractors (prime and sub-contractors)
- Aerospace companies
- Federal IT service providers
- Cybersecurity firms serving DoD
- Companies with CMMC Level 2+ requirements

**Their Pain Points:**
1. **Document Chaos:** Thousands of RFPs, proposals, technical specs, contracts
2. **Compliance Requirements:** ITAR, CUI, CMMC, FedRAMP
3. **Can't Use Public AI:** ChatGPT/Claude = security violation
4. **Slow Manual Search:** Engineers waste hours finding relevant specs
5. **Knowledge Loss:** When subject matter experts leave, knowledge goes with them

---

### How Unit Industries Solves This

#### Phase 1: Custom Deployment (NOW)

**Setup for Defense Contractor:**

Customer: "ACME Defense Solutions" (500 employees, $200M revenue)

**Day 1: Infrastructure Setup (2 hours)**
- ACME creates Neo4j Aura account (Gov Cloud region)
- ACME creates Qdrant Cloud account (US East)
- ACME creates Supabase account (or self-hosted PostgreSQL)
- ACME provides us credentials (stored in our secure vault)

**Day 2: Deployment (2 hours)**
- We deploy dedicated Render backend (acme-backend.onrender.com)
- We deploy white-labeled frontend (search.acmedefense.com)
- We configure environment variables to point to ACME's databases
- We test connections and run health checks

**Day 3-7: Data Ingestion**
- ACME connects their systems:
  - SharePoint (via API)
  - Google Drive (via OAuth)
  - Local file uploads (proposals, specs)
- Background jobs sync documents to THEIR databases
- Knowledge graph builds in THEIR Neo4j
- Vectors stored in THEIR Qdrant

**Day 8: Production Ready**
- ACME engineers start searching
- "Find all proposals mentioning radar cross-section requirements"
- "What past projects involved hypersonic missile guidance?"
- "Show me every contract with ITAR export control clauses"

**Value Delivered:**
- ✅ Search time: 2 hours → 30 seconds
- ✅ Proposal reuse: Find similar past proposals in seconds
- ✅ Compliance: Full audit trail of who accessed what
- ✅ Security: Their data never leaves their infrastructure
- ✅ Control: They can shut us out anytime and keep everything

**Pricing for ACME:**
- Our Software & Management: $10,000/month
- Their Infrastructure: $200/month (Neo4j + Qdrant + PostgreSQL)
- **Total: $10,200/month**

**ROI for ACME:**
- 50 engineers @ $150K salary = $7.5M/year
- Save 10% of time searching = $750K/year saved
- Win 1 additional contract from better proposals = $5M+ revenue
- **Cost: $122K/year**
- **Value: $5M+ per year**
- **ROI: 40x+**

---

#### Phase 2: SaaS Deployment (2-3 Months)

**Same ACME Customer, Different Setup:**

**Day 1: Self-Service Signup (10 minutes)**
- ACME signs up at unitindustries.com/signup
- Enters company name, admin email, credit card
- Selects "Enterprise - Government Contractor" tier
- **Auto-provisioning kicks off:**
  - Creates dedicated Neo4j database: `acme_defense_solutions`
  - Creates dedicated Qdrant collection: `acme_defense_solutions`
  - Creates dedicated PostgreSQL schema: `acme_defense_solutions`
  - Initializes knowledge graph schema
  - Generates secure credentials
  - Sends onboarding email

**Day 1: Data Connection (1 hour)**
- ACME admin logs in
- Clicks "Connect SharePoint" → OAuth flow
- Clicks "Connect Google Drive" → OAuth flow
- Uploads 50GB of past proposals via web interface
- Background workers start syncing to their dedicated databases

**Day 2-7: Automatic Ingestion**
- System processes all documents
- Builds knowledge graph in their dedicated Neo4j database
- Generates embeddings in their dedicated Qdrant collection
- Stores metadata in their dedicated PostgreSQL schema
- Status updates in dashboard

**Day 8: Production Use**
- Same search capabilities
- Same performance
- Same security
- But instant setup instead of 2-4 hours of manual work

**Data Ownership Features:**

**Export Anytime:**
- Settings → Data Export → "Download Full Knowledge Graph"
- Generates ZIP file:
  - `neo4j_export.cypher` (full knowledge graph)
  - `qdrant_vectors.jsonl` (all embeddings)
  - `documents.json` (all documents + metadata)
  - `migration_guide.md` (how to import to their own infrastructure)

**Migration to Self-Hosted:**
1. ACME decides to bring everything in-house (CMMC Level 3 requirement)
2. They spin up their own:
   - Neo4j Enterprise on-premises
   - Qdrant on-premises
   - PostgreSQL on-premises
3. They click "Export Data" in our platform
4. They run our migration scripts:
   ```bash
   ./import_neo4j.sh --source acme_export.cypher --target neo4j://acme-internal
   ./import_qdrant.sh --source vectors.jsonl --target http://acme-internal:6333
   ./import_postgres.sh --source documents.json --target postgres://acme-internal
   ```
5. We update their configuration to point to their infrastructure
6. System continues working, now hitting their servers
7. Or they cancel, keep all data, and build their own frontend

**Pricing for ACME (SaaS Model):**
- Enterprise Tier: $15,000/month
- Infrastructure included (we manage it)
- Free migration to self-hosted if needed
- **Total: $15,000/month**

**Why ACME Pays More for SaaS:**
- ✅ Instant setup (10 min vs. 2-4 hours)
- ✅ No infrastructure management
- ✅ Auto-scaling included
- ✅ Priority support
- ✅ Continuous backups
- ✅ Can still migrate to self-hosted anytime

---

### Compliance & Security for Gov Contractors

**Current Capabilities:**
- ✅ Customer-owned infrastructure (data isolation)
- ✅ OAuth security (no password management)
- ✅ HTTPS encryption (all data in transit)
- ✅ Background job tracking (audit trail)
- ✅ Error monitoring (Sentry → Slack)

**Needed for CMMC Level 2 (3-6 months):**
- [ ] Multi-factor authentication (MFA)
- [ ] Role-based access control (RBAC)
- [ ] Audit logging (every query, every document access)
- [ ] Data classification system (CUI, ITAR, Public)
- [ ] Encryption at rest (database-level)
- [ ] Incident response plan
- [ ] Third-party security assessment

**Needed for FedRAMP (12-18 months):**
- [ ] FedRAMP authorized cloud (AWS GovCloud, Azure Gov)
- [ ] Continuous monitoring
- [ ] Penetration testing
- [ ] Supply chain risk management
- [ ] Full documentation of security controls

**Pricing Impact:**
- Basic (current): $5-10K/month
- CMMC Level 2: $15-25K/month
- FedRAMP: $50-100K/month

---

## Summary: The Strategy

### Today (Custom Deployments)
- Manual setup, customer provisions infrastructure
- Perfect for testing and first 5-10 customers
- Low risk, high learning
- Charge $5-10K/month
- Focus on validating product-market fit

### In 2-3 Months (True SaaS)
- Auto-provisioning with dedicated databases per customer
- Self-service signup
- Scales to 100+ customers
- Customer still "owns" data via export/migration tools
- Charge $2.5-15K/month depending on tier
- Target: 20 customers = $100K MRR

### In 12 Months (Enterprise Gov Contractor)
- CMMC Level 2 certified
- FedRAMP in progress
- Air-gapped deployments
- Target defense contractors at $15-50K/month
- Target: 10 contractors = $150-500K MRR

---

## Competitive Advantage

**Why We Win:**

1. **Data Ownership is Real:**
   - Not marketing BS
   - Customer literally owns the infrastructure OR
   - Can export/migrate anytime with provided tools

2. **No Lock-In:**
   - Standard formats (Neo4j Cypher, JSON, PostgreSQL dumps)
   - Migration scripts provided
   - Can self-host and keep using our software
   - Or export and build their own

3. **Compliance-Ready:**
   - Architecture designed for CMMC/FedRAMP
   - Audit trails built in
   - Data classification system ready
   - Physical isolation per customer

4. **Fast Time to Value:**
   - Phase 1: 2-4 hours to production
   - Phase 2: 10 minutes to production
   - Start seeing ROI in first week

5. **Government Contractor Focus:**
   - Understand their pain (RFP search, proposal reuse)
   - Understand their requirements (CMMC, ITAR)
   - Pricing that makes sense for their budgets
   - Features they actually need

---

## Next Steps

**This Month:**
- [ ] Close first 2-3 custom deployment customers
- [ ] Validate pricing ($5-10K/month)
- [ ] Get testimonials and case studies
- [ ] Refine onboarding process

**Months 2-4:**
- [ ] Build dynamic database routing
- [ ] Build auto-provisioning system
- [ ] Build export/migration tools
- [ ] Launch self-service signup
- [ ] Target 20 customers

**Months 5-12:**
- [ ] Start CMMC certification process
- [ ] Add compliance features (audit logs, RBAC, MFA)
- [ ] Target defense contractor market
- [ ] Scale to 50+ customers

**The Goal:**
$1M ARR within 12 months, mostly from government contractors paying $15-50K/month each.

