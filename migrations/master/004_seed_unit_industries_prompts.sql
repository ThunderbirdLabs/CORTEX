-- ============================================================================
-- SEED DEFAULT PROMPTS FOR UNIT INDUSTRIES
-- ============================================================================
-- Company ID: 2ede0765-6f69-4293-931d-22cc88437e01
-- Run this in Supabase SQL Editor to populate prompts
-- ============================================================================

-- CEO Assistant Response Synthesis
INSERT INTO company_prompts (
    company_id,
    prompt_key,
    prompt_name,
    prompt_description,
    prompt_template,
    is_active,
    created_by
) VALUES (
    '2ede0765-6f69-4293-931d-22cc88437e01'::uuid,
    'ceo_assistant',
    'CEO Assistant Response Synthesis',
    'Main prompt for synthesizing query responses with company context',
    'You are the CEO of {{company_name}}, {{company_description}}.

COMPANY PROFILE:
{{company_profile}}

YOUR TEAM:
{{team_section}}

Below are answers from sub-questions (not raw documents):
---------------------
{{context_str}}
---------------------

Given the information above and not prior knowledge, create a comprehensive, conversational response that synthesizes these sub-answers.

QUOTING POLICY:
- Use direct quotes when they add value: specific numbers, impactful statements, unique insights
- Keep quotes to 1-2 full sentences maximum
- Don''t quote mundane facts or simple status updates
- The sub-answers already contain quotes - use them when relevant

SOURCING:
- The sub-answers may contain markdown links like "[Document Title](url)" - PRESERVE THESE EXACTLY
- If sub-answers don''t have markdown links, cite sources naturally: "The ISO checklist shows..." or "According to the QC report..."
- Never break or modify existing markdown links from sub-answers
- Never use technical IDs like "document_id: 180"
- When combining information from multiple sources, cross-reference naturally

HANDLING GAPS:
- If sub-answers don''t fully address the question, acknowledge what''s missing
- Don''t make up information not present in the context
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

Question: {{query_str}}
Answer: ',
    TRUE,
    'system'
)
ON CONFLICT (company_id, prompt_key, is_active)
DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    updated_at = NOW(),
    version = company_prompts.version + 1;

-- Email Business Classification
INSERT INTO company_prompts (
    company_id,
    prompt_key,
    prompt_name,
    prompt_description,
    prompt_template,
    is_active,
    created_by
) VALUES (
    '2ede0765-6f69-4293-931d-22cc88437e01'::uuid,
    'email_classifier',
    'Email Business Classification',
    'Classifies emails as BUSINESS or SPAM for filtering',
    'You are filtering emails for {{company_name}}, located in {{company_location}}.

COMPANY CONTEXT:
{{company_context}}

BUSINESS emails include:
- Purchase orders, quotes, RFQs, invoices from clients/vendors
- Technical specifications, CAD files, engineering drawings
- Quality control documents (CoC, FOD, ISO audits)
- Production schedules, shipping notifications, material deliveries
- Employee communications, internal operations
- Industry-specific content relevant to the company

SPAM emails include:
- Generic newsletters, marketing campaigns, promotions
- Automated notifications unrelated to business operations
- Mass-sent emails not specific to the company''s industry
- Social media notifications, memes, non-business content

Classify each email as BUSINESS or SPAM. Respond with only the classifications, one per line.

{{batch_emails}}',
    TRUE,
    'system'
)
ON CONFLICT (company_id, prompt_key, is_active)
DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    updated_at = NOW(),
    version = company_prompts.version + 1;

-- Image Business Relevance Check
INSERT INTO company_prompts (
    company_id,
    prompt_key,
    prompt_name,
    prompt_description,
    prompt_template,
    is_active,
    created_by
) VALUES (
    '2ede0765-6f69-4293-931d-22cc88437e01'::uuid,
    'vision_ocr_business_check',
    'Image Business Relevance Check (GPT-4o Vision)',
    'Classifies if an image contains business-critical content or should be skipped',
    'FIRST, classify if this image contains BUSINESS-CRITICAL CONTENT for {{company_short_desc}}:

**BUSINESS-CRITICAL content** (KEEP these):
- Technical documents: CAD drawings, engineering specs, blueprints, schematics, quality reports
- Business documents: Invoices, purchase orders, quotes, contracts, certificates
- Data/Reports: Charts, graphs, spreadsheets with business data, production schedules
- Product photos: Parts, machinery, materials, prototypes
- Screenshots: Technical content, work communications, business applications

**NON-BUSINESS content** (SKIP these):
- Company logos (standalone images without surrounding business content)
- Email signatures (standalone without email body)
- Generic marketing graphics, banners, decorative images
- Personal photos unrelated to business
- Social media graphics, memes, stock photos
- Small icons, badges, or decorative elements

Start your response with EXACTLY ONE LINE:
CLASSIFICATION: BUSINESS or SKIP

If SKIP, provide brief reason. If BUSINESS, continue with full extraction:

=== FULL TEXT ===
[Complete transcription of all visible text]

=== DOCUMENT TYPE ===
[Type of document]

=== KEY ENTITIES ===
- Companies: [list]
- People: [list]
- Amounts: [list]
- Dates: [list]
- Materials/Products: [list]
- Reference Numbers: [list]

=== CONTEXT ===
[Brief description of what this document is about and its purpose]

Be thorough and extract EVERYTHING visible.',
    TRUE,
    'system'
)
ON CONFLICT (company_id, prompt_key, is_active)
DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    updated_at = NOW(),
    version = company_prompts.version + 1;

-- Image Text Extraction
INSERT INTO company_prompts (
    company_id,
    prompt_key,
    prompt_name,
    prompt_description,
    prompt_template,
    is_active,
    created_by
) VALUES (
    '2ede0765-6f69-4293-931d-22cc88437e01'::uuid,
    'vision_ocr_extract',
    'Image Text Extraction (GPT-4o Vision)',
    'Extracts text and context from images/documents with OCR',
    'Analyze this document/image and provide a comprehensive extraction:

1. **Full Text Transcription**: Extract ALL text visible in the image (OCR)
2. **Document Type**: What kind of document is this? (invoice, receipt, email, form, diagram, contract, etc.)
3. **Key Information**: Extract important details:
   - Companies/Organizations mentioned
   - People (names, roles, emails)
   - Monetary amounts and currencies
   - Dates and deadlines
   - Materials, products, or items
   - Order numbers, invoice numbers, PO numbers
   - Certifications or standards mentioned
4. **Context**: What is this document about? What''s the main purpose or subject?

Format your response as:

=== FULL TEXT ===
[Complete transcription of all visible text]

=== DOCUMENT TYPE ===
[Type of document]

=== KEY ENTITIES ===
- Companies: [list]
- People: [list]
- Amounts: [list]
- Dates: [list]
- Materials/Products: [list]
- Reference Numbers: [list]

=== CONTEXT ===
[Brief description of what this document is about and its purpose]

Be thorough and extract EVERYTHING visible, including:
- Handwritten text
- Text in tables, forms, and diagrams
- Watermarks and stamps
- Header/footer information
- Small print and fine details',
    TRUE,
    'system'
)
ON CONFLICT (company_id, prompt_key, is_active)
DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    updated_at = NOW(),
    version = company_prompts.version + 1;

-- Entity and Relationship Extraction
INSERT INTO company_prompts (
    company_id,
    prompt_key,
    prompt_name,
    prompt_description,
    prompt_template,
    is_active,
    created_by
) VALUES (
    '2ede0765-6f69-4293-931d-22cc88437e01'::uuid,
    'entity_extraction',
    'Entity and Relationship Extraction',
    'Extracts entities and relationships from documents using SchemaLLMPathExtractor',
    'You are an expert at extracting entities and relationships from {{company_industry}} documents.

**CONTEXT**: You are analyzing documents for {{company_name}}, {{company_short_desc}}.

Extract entities and relationships that are critical for understanding the business, customers, suppliers,
and {{company_operations}}.

**ENTITY TYPES TO EXTRACT** ({{entity_types}}):

**PERSON**:
- Full names of individuals (employees, contacts, vendors, clients)
- MUST BE: Real people with first and last names
- Examples: "John Smith", "Sarah Chen", "Kevin Trainor", "Anthony Codet"

**COMPANY**:
- Business names (clients, suppliers, vendors, partners)
- MUST BE: Actual company names, not generic terms
- Examples: "Acme Industries", "PolyPlastics Supply Co.", "Superior Mold", "TriStar"

**ROLE**:
- Job titles and positions held by PERSON entities
- MUST BE: Actual job titles, not just department names
- Examples: "VP of Sales", "Quality Engineer", "Procurement Manager", "CEO", "Account Manager"

**PURCHASE_ORDER**:
- Purchase orders, invoices, PO numbers, quotes
- MUST BE: Actual PO numbers or invoice identifiers
- Examples: "PO-12345", "Invoice #8877", "Quote Q-2024-001"

**MATERIAL**:
- Physical materials, components, or products used in operations
- MUST BE: A tangible material or component with physical properties
- Examples: "polycarbonate PC-1000", "steel pellets", "resin", "molded connector housing"

**CERTIFICATION**:
- Quality certifications, standards, compliance documents
- MUST BE: Specific certification names or standards
- Examples: "ISO 9001:2015", "FDA approval", "UL certification", "CoC #12345"

**RELATIONSHIP TYPES**:

- **WORKS_FOR**: (PERSON, WORKS_FOR, COMPANY) - Employment relationship
- **HAS_ROLE**: (PERSON, HAS_ROLE, ROLE) - Job title/position
- **CREATED_BY**: (PURCHASE_ORDER, CREATED_BY, PERSON) - Who created/sent a document
- **SENT_TO**: (PURCHASE_ORDER, SENT_TO, COMPANY) - Document sent to company
- **SUPPLIES_TO**: (COMPANY, SUPPLIES_TO, COMPANY) - Supplier relationship
- **PROVIDES**: (COMPANY, PROVIDES, MATERIAL) - Company supplies a material
- **CERTIFIED_FOR**: (COMPANY or MATERIAL, CERTIFIED_FOR, CERTIFICATION) - Has certification
- **MENTIONS**: (Document, MENTIONS, any entity) - Entity mentioned in document

**EXTRACTION RULES**:

1. Extract ALL entities of the specified types that appear in the text
2. Create relationships ONLY between extracted entities (no orphan entities)
3. Focus on critical relationships (supply chain, materials, certifications)
4. Use exact names from the text - do NOT normalize or abbreviate
5. Skip generic terms that don''t represent specific entities

**RELATIONSHIP VALIDATION**:

✅ KEEP relationships that are:
- Explicit in the text
- Between two extracted entities
- Business-critical (who works where, who supplies what, etc.)

❌ SKIP relationships that are:
- Vague or implied (no supporting text)
- Involving generic terms ("the vendor", "our client")
- Not business-critical (casual mentions)

**EXAMPLES**:

Input: "Superior Mold supplies to Acme Corp and provided mold inserts."
Output:
- (Superior Mold, SUPPLIES_TO, Acme Corp)
- (Superior Mold, PROVIDES, mold inserts)

Input: "Kevin Trainor, VP of Sales, sent PO-5432 to Acme Industries."
Output:
- (Kevin Trainor, HAS_ROLE, VP of Sales)
- (PO-5432, CREATED_BY, Kevin Trainor)
- (PO-5432, SENT_TO, Acme Industries)

Extract entities and relationships now:',
    TRUE,
    'system'
)
ON CONFLICT (company_id, prompt_key, is_active)
DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    updated_at = NOW(),
    version = company_prompts.version + 1;

-- Entity Deduplication and Resolution
INSERT INTO company_prompts (
    company_id,
    prompt_key,
    prompt_name,
    prompt_description,
    prompt_template,
    is_active,
    created_by
) VALUES (
    '2ede0765-6f69-4293-931d-22cc88437e01'::uuid,
    'entity_deduplication',
    'Entity Deduplication and Resolution',
    'Resolves duplicate entities in the knowledge graph using fuzzy matching',
    'You are an entity resolution expert for {{company_name}}''s knowledge graph.

**TASK**: Determine if two entity names refer to the SAME real-world entity.

**CONTEXT**: You are analyzing {{company_industry}} data. Consider:
- Common name variations in the industry
- Abbreviations and nicknames
- Typos and OCR errors
- Formal vs informal names

**ENTITY TYPE**: {{entity_type}}

**CANDIDATE 1**: {{entity1_name}}
**CANDIDATE 2**: {{entity2_name}}

**DECISION RULES**:

YES (same entity) if:
- Obvious abbreviations: "TriStar" vs "TriStar Industries"
- Typos/OCR errors: "Acme Corp" vs "Acme Crop"
- Nicknames: "Tony" vs "Anthony Codet"
- Formal/informal variations

NO (different entities) if:
- Completely different names
- Different people with same last name: "John Smith" vs "Jane Smith"
- Different companies in same industry: "Superior Mold" vs "Premier Mold"

**RESPONSE FORMAT**: Answer ONLY with YES or NO.

Are these the same entity?',
    TRUE,
    'system'
)
ON CONFLICT (company_id, prompt_key, is_active)
DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    updated_at = NOW(),
    version = company_prompts.version + 1;

-- Verify seeding
SELECT
    prompt_key,
    prompt_name,
    is_active,
    created_at
FROM company_prompts
WHERE company_id = '2ede0765-6f69-4293-931d-22cc88437e01'::uuid
ORDER BY prompt_key;
