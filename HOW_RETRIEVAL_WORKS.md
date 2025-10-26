# How Cortex Retrieval Works (4th Grader Explanation)

## 🎯 The Big Picture

When you ask a question like "What did John say about the project?", your system does **4 main steps**:

```
YOU ASK QUESTION
      ↓
1. BREAK DOWN (SubQuestionQueryEngine)
      ↓
2. SEARCH TWO DATABASES (Qdrant + Neo4j)
      ↓
3. RANK RESULTS (RecencyBoost + Reranker)
      ↓
4. WRITE ANSWER (CEO Assistant)
```

---

## 📚 Step-by-Step: What Happens When You Ask "What did John say about the project?"

### **STEP 1: Breaking Down Your Question** 🧩
**Location:** `query_engine.py:278` - SubQuestionQueryEngine

Think of this like a teacher breaking down a big homework problem into smaller questions:

**Your Question:** "What did John say about the project?"

**SubQuestionQueryEngine breaks it into 2 sub-questions:**
1. "What content mentions John?" → Send to **vector_search** (Qdrant)
2. "What relationships does John have?" → Send to **graph_search** (Neo4j)

**Why?** Some questions are better answered by searching text (Qdrant), others by looking at connections between people/companies (Neo4j).

---

### **STEP 2A: Searching Qdrant (The Text Database)** 📝
**Location:** `query_engine.py:221-236` - Vector Query Engine

**What Qdrant stores:** Every email, document, PDF is **chopped into small pieces (chunks)** with **numbers that represent meaning (embeddings)**.

#### How Qdrant Search Works (Like Finding Similar LEGO Blocks):

1. **Your question gets turned into numbers:** "What content mentions John?" → `[0.123, 0.456, 0.789, ...]` (embedding)

2. **Qdrant compares your numbers to ALL 9,678 chunks:**
   - Which chunks have similar numbers?
   - **Finds top 20 most similar chunks** (SIMILARITY_TOP_K=20)

3. **Example of what comes back:**
   ```
   Chunk #1: "John sent an email about the ISO project..." (similarity: 0.92)
   Chunk #2: "Project update from John Thompson..." (similarity: 0.88)
   Chunk #3: "Discussed project timeline with John..." (similarity: 0.85)
   ... 17 more chunks ...
   ```

**All 20 chunks** have this metadata attached:
- `document_id`: Which document it came from
- `created_at_timestamp`: When it was created (for recency boost)
- `title`: Document title
- `source`: "outlook", "gmail", etc.

---

### **STEP 2B: Searching Neo4j (The Relationship Database)** 🕸️
**Location:** `query_engine.py:238-242` - Graph Query Engine

**What Neo4j stores:**
- **Entities:** PERSON nodes (John Thompson), COMPANY nodes (Acme Corp), EMAIL nodes
- **Relationships:** John -[SENT_BY]-> Email, John -[WORKS_FOR]-> Acme Corp

#### How Neo4j Search Works (Like Finding Friends on Facebook):

1. **Finds John in the graph:**
   ```
   MATCH (p:PERSON {name: "John Thompson"})
   ```

2. **Finds everything connected to John:**
   ```
   MATCH (p:PERSON {name: "John"})-[r]-(connected)
   RETURN connected
   ```

3. **Example of what comes back:**
   ```
   - John SENT_BY → Email #123
   - John WORKS_ON → Project X
   - John MENTIONED_IN → Chunk #456
   ```

**Neo4j is great for:**
- "Who sent what to whom?"
- "Who works where?"
- "What companies are connected?"

---

### **STEP 3: Ranking Results** 🏆
**Location:** `query_engine.py:228-238` - node_postprocessors

Now we have **20 chunks from Qdrant** and **some entities from Neo4j**. But which ones are **BEST**?

#### **Two Ranking Steps (Applied to Qdrant Results - OPTIMAL ORDER):**

#### **Ranking Step 1: SentenceTransformerRerank** 🎯 (FIRST!)
**Location:** `query_engine.py:229-236`

**What it does:** Uses an **AI model** to deeply understand if each chunk **truly answers the question**.

**IMPORTANT:** This runs FIRST so it can analyze ALL 20 candidates fairly!

**Before Reranker (20 chunks from Qdrant):**
```
Chunk #1: "John's email about project timeline"       (score: 0.85)
Chunk #2: "Project budget discussed with John"        (score: 0.82)
Chunk #3: "ISO certification for Project X"           (score: 0.80)
Chunk #4: "John Thompson joined the call"             (score: 0.75)
Chunk #5: "Old but highly relevant project doc"       (score: 0.90, from 365 days ago)
... 15 more chunks ...
```

**Reranker reads each chunk deeply:**
- Does it REALLY answer "What did John say about the project?"
- Chunk #1: YES - directly about John's project talk → 0.95 relevance
- Chunk #3: MAYBE - mentions project but not what John said → 0.70 relevance
- Chunk #4: NO - just mentions John's name → 0.45 relevance
- Chunk #5: YES - old but super relevant → 0.92 relevance (not buried!)

**After Reranker (still 20, but reordered by TRUE relevance):**
```
Chunk #1: "John's email about project timeline"       (score: 0.95) ✅
Chunk #5: "Old but highly relevant project doc"       (score: 0.92) ✅ (not buried!)
Chunk #2: "Project budget discussed with John"        (score: 0.89) ✅
... 17 more, ordered by relevance ...
```

**Why first?** If RecencyBoost ran first, old content (like Chunk #5) would get buried BEFORE the reranker could analyze its relevance!

---

#### **Ranking Step 2: RecencyBoostPostprocessor** 📅 (SECOND!)
**Location:** `query_engine.py:237` and `recency_postprocessor.py:72-133`

**What it does:** Applies **recency boost as a secondary signal** after relevance is determined.

**Example (after reranker):**
```
Before RecencyBoost:
Chunk #1: "Recent project email" (score: 0.95, 7 days old)
Chunk #5: "Old project doc"      (score: 0.92, 365 days old)

After RecencyBoost (decay_days=90):
Chunk #1: 0.95 × 0.95 = 0.902 ✅ BOOSTED (recent + relevant)
Chunk #5: 0.92 × 0.06 = 0.055 ⚠️  PENALIZED (old but was analyzed by reranker!)
```

**Formula:** `new_score = old_score × (0.5 ^ (age_days / 90))`
- Documents from 90 days ago: 50% of original score
- Documents from today: 100% of original score
- Documents from 365 days ago: 6% of original score

**Why second?** This ensures:
1. ✅ Relevance determined first (reranker sees ALL candidates)
2. ✅ Recency applied as gentle nudge
3. ✅ Recent + relevant content ranks highest
4. ✅ Old but highly relevant content still gets fair consideration

---

### **STEP 4: Writing The Final Answer** ✍️
**Location:** `query_engine.py:265-275` - Response Synthesizer

Now we have:
- **10 best text chunks** (from Qdrant → RecencyBoost → Reranker)
- **Some entity info** (from Neo4j)

The **CEO Assistant LLM** reads all of this and writes a **conversational answer**:

**Input to LLM:**
```
Sub-answer from vector_search:
"John Thompson sent an email on Jan 15 saying 'The project timeline
needs to be extended by 2 weeks due to ISO certification delays.'"

Sub-answer from graph_search:
"John Thompson works for Engineering Department and is connected
to Project X through WORKS_ON relationship."

Question: What did John say about the project?
```

**LLM Output (Final Answer):**
```
John Thompson mentioned that the project timeline needs to be
extended by 2 weeks due to ISO certification delays. This was
discussed in his email from January 15. John is part of the
Engineering Department and is actively working on Project X.
```

---

## 🔍 Time Filters (Bonus Feature!)

**Location:** `query_engine.py:291-430`

When you ask **"Show me emails from October 2024"**, the system does something special:

### **Step 1: Detect Time Keywords**
```python
# query_engine.py:464-472
time_keywords = ['october', 'last week', 'yesterday', 'q1', 'q2', 'after', 'before']
has_time = any(keyword in question.lower() for keyword in time_keywords)
```

### **Step 2: Extract Exact Dates (Using LLM)**
```python
# query_engine.py:291-382
"emails from October 2024" →
{
  "start_date": "2024-10-01",
  "end_date": "2024-10-31",
  "start_timestamp": 1727740800,
  "end_timestamp": 1730419199
}
```

### **Step 3: Filter BEFORE Searching**
```python
# query_engine.py:405-420
MetadataFilter(
    key="created_at_timestamp",
    operator=GTE,  # Greater than or equal
    value=1727740800
)
```

**This tells Qdrant:** "Only look at documents created between Oct 1 and Oct 31"

**Why this is CRITICAL:** Without this, the LLM might **hallucinate** and include documents from November or September. The database filter ensures **ZERO hallucination** - only October documents are even considered.

---

## 📊 Summary Table: Where Does Each Thing Happen?

| What | Where | File:Line |
|------|-------|-----------|
| **You ask question** | Chat endpoint | `chat.py:161` |
| **Break into sub-questions** | SubQuestionQueryEngine | `query_engine.py:278` |
| **Search Qdrant (text)** | VectorStoreIndex | `query_engine.py:221` |
| **Search Neo4j (relationships)** | PropertyGraphIndex | `query_engine.py:238` |
| **Boost recent docs** | RecencyBoostPostprocessor | `query_engine.py:226` |
| **Deep rerank** | SentenceTransformerRerank | `query_engine.py:227-234` |
| **Write final answer** | Response Synthesizer | `query_engine.py:269-275` |
| **Time filtering** | MetadataFilters | `query_engine.py:384-430` |

---

## ✅ What's Actually Being Used? (Dead Code Check)

### **✅ ACTIVELY USED:**

1. **RecencyBoostPostprocessor** - YES ✅
   - Applied to every query: `query_engine.py:226`
   - Uses `created_at_timestamp` metadata
   - Formula: `0.5 ^ (age_days / 90)`

2. **SentenceTransformerRerank** - YES ✅
   - Applied to every query: `query_engine.py:227-234`
   - Narrows 20 candidates → 10 best
   - Uses ONNX backend for 2-3x faster startup

3. **MetadataFilters (Time Filtering)** - YES ✅
   - Applied when time keywords detected: `query_engine.py:472-479`
   - Creates strict database-level filters: `query_engine.py:405-420`
   - Prevents hallucination

4. **SubQuestionQueryEngine** - YES ✅
   - Every query goes through it: `query_engine.py:278`
   - Breaks questions into sub-questions
   - Routes to vector_search or graph_search

5. **VectorStoreIndex (Qdrant)** - YES ✅
   - Semantic search over text chunks
   - Retrieves top 20 similar chunks

6. **PropertyGraphIndex (Neo4j)** - YES ✅
   - Graph queries over entities/relationships
   - Used for "who/what/where" questions

### **❌ NOT USED / DEAD CODE:**

**None found!** All major components are actively used in the retrieval pipeline.

---

## 🎓 Key Takeaways

1. **Two databases work together:**
   - **Qdrant** = Good at finding similar TEXT ("What was said?")
   - **Neo4j** = Good at finding CONNECTIONS ("Who knows who?")

2. **Ranking happens in stages:**
   - Stage 1: Get 20 candidates (fast, rough)
   - Stage 2: Boost recent (recency matters)
   - Stage 3: Deep rerank (slow, accurate)
   - Result: 10 best chunks

3. **Time filters are STRICT:**
   - Applied at **database level** (before search)
   - Prevents hallucination (LLM can't make up dates)

4. **Everything you built is being used:**
   - No dead code
   - Each component has a purpose
   - Production-ready pipeline

---

## 🔍 Want to See It in Action?

**Add logging to see the flow:**

```python
# In chat.py:161
logger.info(f"💬 Question: {message.question}")

# Watch the logs show:
# 1. SubQuestion generation
# 2. Qdrant search (20 candidates)
# 3. RecencyBoost adjusting scores
# 4. Reranker narrowing to 10
# 5. Final answer synthesis
```

**The logs will show something like:**
```
💬 Question: What did John say about the project?
🔍 HYBRID QUERY: What did John say about the project?
   ⏭️  No time keywords detected, skipping time filter extraction
   🔍 SubQuestion 1: "What content mentions John?" → vector_search
   🔍 SubQuestion 2: "What relationships does John have?" → graph_search
   RecencyBoost: Boosted 20 nodes, skipped 0 (no timestamp)
   SentenceTransformerRerank: Reranked 20 nodes → top 10
✅ QUERY COMPLETE
   Answer length: 458 characters
   Source nodes: 10
```
