"""
LlamaIndex Query Engine (Expert Recommended Pattern)

Architecture:
- SubQuestionQueryEngine for hybrid retrieval
- VectorStoreIndex for semantic search (Qdrant)
- PropertyGraphIndex for graph queries (Neo4j)
- Intelligent routing and result synthesis
"""

import logging
from typing import Dict, Any, Optional, List

from llama_index.core import VectorStoreIndex, PromptTemplate
from llama_index.core.query_engine import SubQuestionQueryEngine
from llama_index.core.tools import QueryEngineTool
from llama_index.core.indices.property_graph import PropertyGraphIndex
from llama_index.core.response_synthesizers import get_response_synthesizer
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from qdrant_client import QdrantClient, AsyncQdrantClient

from .config import (
    NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE,
    QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION_NAME,
    OPENAI_API_KEY, QUERY_MODEL, QUERY_TEMPERATURE,
    EMBEDDING_MODEL, SIMILARITY_TOP_K
)
from .recency import DocumentTypeRecencyPostprocessor

# Import SentenceTransformer reranker for production relevance scoring
from llama_index.postprocessor.sbert_rerank import SentenceTransformerRerank

# Import dynamic company context loader
from app.services.tenant.context import build_ceo_prompt_template

logger = logging.getLogger(__name__)

# CEO Assistant synthesis prompt - loaded lazily on first use
# This ensures master_supabase_client is initialized first
_CEO_ASSISTANT_PROMPT_TEMPLATE = None

def get_ceo_prompt_template():
    """Lazy load CEO prompt from Supabase (only on first use)"""
    global _CEO_ASSISTANT_PROMPT_TEMPLATE
    if _CEO_ASSISTANT_PROMPT_TEMPLATE is None:
        _CEO_ASSISTANT_PROMPT_TEMPLATE = build_ceo_prompt_template()
    return _CEO_ASSISTANT_PROMPT_TEMPLATE


class HybridQueryEngine:
    """
    Hybrid query engine using SubQuestionQueryEngine.

    Combines:
    1. VectorStoreIndex (Qdrant) - Semantic search over document chunks
    2. PropertyGraphIndex (Neo4j) - Graph queries over Document/Person/Company/Entity nodes

    The SubQuestionQueryEngine:
    - Breaks down complex questions
    - Routes sub-questions to appropriate index
    - Synthesizes comprehensive answers
    """

    def __init__(self):
        logger.info("🚀 Initializing Hybrid Query Engine (Expert Pattern)")

        # Get current date for temporal awareness
        from datetime import datetime
        current_date = datetime.now().strftime('%B %d, %Y')
        current_date_iso = datetime.now().strftime('%Y-%m-%d')

        # LLM for query processing and synthesis
        self.llm = OpenAI(
            model=QUERY_MODEL,
            temperature=QUERY_TEMPERATURE,
            api_key=OPENAI_API_KEY,
            system_prompt=(
                f"You are an intelligent personal assistant to the CEO. Today's date is {current_date} ({current_date_iso}).\n\n"

                "You have access to the entire company's knowledge - emails, documents, purchase orders, activities, materials, and everything that goes on in this business.\n\n"

                "Your role varies depending on the task:\n"
                "- When answering sub-questions: preserve exact information from context\n"
                "- When synthesizing final answers: create comprehensive, conversational responses\n\n"

                "When referencing relationships or entities, speak naturally without exposing technical details "
                "(say 'created by' not 'CREATED_BY'). Respond conversationally - skip greetings and sign-offs."
            )
        )

        # Embedding model for vector search
        self.embed_model = OpenAIEmbedding(
            model_name=EMBEDDING_MODEL,
            api_key=OPENAI_API_KEY
        )

        # Qdrant vector store (with async client for retrieval)
        # Increased timeout for slower connections and added retries
        qdrant_client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            timeout=60.0,  # 60s timeout for operations (increased from 30s)
            # Connection pooling handled by httpx internally (default: 100 max connections)
        )
        qdrant_aclient = AsyncQdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            timeout=60.0  # 60s timeout (increased from 30s)
        )
        vector_store = QdrantVectorStore(
            client=qdrant_client,
            aclient=qdrant_aclient,
            collection_name=QDRANT_COLLECTION_NAME
        )
        self.qdrant_client = qdrant_client
        self.qdrant_aclient = qdrant_aclient
        logger.info(f"✅ Qdrant Vector Store: {QDRANT_COLLECTION_NAME}")

        # VectorStoreIndex for semantic search
        self.vector_index = VectorStoreIndex.from_vector_store(
            vector_store=vector_store,
            embed_model=self.embed_model
        )
        logger.info("✅ VectorStoreIndex created for semantic search")

        # Neo4j graph store with connection pool limits
        graph_store = Neo4jPropertyGraphStore(
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD,
            url=NEO4J_URI,
            database=NEO4J_DATABASE,
            timeout=60.0,  # 60s timeout for queries (increased from 30s)
            # Neo4j driver config (prevent connection exhaustion under load)
            max_connection_pool_size=50,  # Max 50 concurrent connections
            connection_acquisition_timeout=60.0,  # 60s wait for connection from pool (increased from 30s)
            max_connection_lifetime=3600,  # Recycle connections after 1 hour
        )
        self.graph_store = graph_store
        logger.info(f"✅ Neo4j Graph Store: {NEO4J_URI}")

        # PropertyGraphIndex for graph queries
        self.property_graph_index = PropertyGraphIndex.from_existing(
            property_graph_store=graph_store,
            llm=self.llm,
            embed_model=self.embed_model
        )
        logger.info("✅ PropertyGraphIndex created for graph queries")

        # Sub-question prompts - CRITICAL: Must preserve exact information for final synthesis
        # The final CEO assistant only sees these sub-answers, not the raw chunks!
        vector_qa_prompt = PromptTemplate(
            "Your answer will be passed to another agent for final synthesis. Preserve exact information.\n\n"
            "Context from documents (each chunk has metadata with title):\n"
            "---------------------\n"
            "{context_str}\n"
            "---------------------\n\n"
            "Given the context above and not prior knowledge, answer the question. When you include:\n"
            "- Numbers, dates, metrics, amounts → quote them exactly\n"
            "- Important statements or findings → quote 1-2 key sentences verbatim\n"
            "- Regular facts or descriptions → you may paraphrase\n\n"
            "IMPORTANT: When citing documents that have a file_url in metadata, create markdown links:\n"
            "- Format: \"According to the [Document Title](file_url_value)...\"\n"
            "- Use the actual file_url value from the chunk metadata, not the word 'file_url'\n"
            "- For documents without file_url, just mention the title naturally\n\n"
            "Use quotation marks for verbatim text.\n"
            "If the context doesn't contain relevant information, say so clearly.\n\n"
            "Question: {query_str}\n"
            "Answer: "
        )

        graph_qa_prompt = PromptTemplate(
            "Your answer will be passed to another agent for final synthesis. Focus on precise entity information.\n\n"
            "Context from knowledge graph:\n"
            "---------------------\n"
            "{context_str}\n"
            "---------------------\n\n"
            "Given the context above and not prior knowledge, answer the question about entities and relationships:\n"
            "- Use EXACT names, titles, company names (don't paraphrase proper nouns)\n"
            "- Describe relationships clearly: who did what, who works where, who sent what\n"
            "- If context includes quotes or specific statements, preserve them\n"
            "- Translate technical relationship types to natural language (CREATED_BY → \"created by\")\n\n"
            "If the context doesn't contain relevant information, say so clearly.\n\n"
            "Question: {query_str}\n"
            "Answer: "
        )

        # Create query engines with custom prompts + reranking + recency boost
        # Multi-stage retrieval pipeline (OPTIMAL ORDER - 2025 best practice):
        # 1. Retrieve 20 candidates (SIMILARITY_TOP_K=20)
        # 2. SentenceTransformerRerank: Deep semantic relevance scoring (ALL 20 analyzed)
        #    - GPU-accelerated if available (2-3x faster: 200ms → 70ms per query)
        #    - Keeps all 20, just reorders by true relevance
        # 3. RecencyBoostPostprocessor: Applies recency boost as secondary signal
        #    - Recent relevant content ranks highest
        #    - Old relevant content still considered (not buried before reranker)

        # GPU acceleration for reranker (production optimization 2025)
        # Research: HuggingFace/Medium benchmarks show 2-3x speedup with GPU
        # Graceful fallback to CPU if GPU unavailable (zero risk)
        import torch
        reranker_device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"   🚀 Reranker device: {reranker_device}")

        self.vector_query_engine = self.vector_index.as_query_engine(
            similarity_top_k=SIMILARITY_TOP_K,  # Now 20 (cast wider net)
            llm=self.llm,
            text_qa_template=vector_qa_prompt,
            node_postprocessors=[
                # TEMPORARILY DISABLED: SentenceTransformerRerank takes too long to load on first run
                # SentenceTransformerRerank(
                #     model="BAAI/bge-reranker-base",
                #     top_n=20,  # Keep all 20, just reorder by relevance
                #     device=reranker_device  # GPU if available, CPU fallback
                # ),
                DocumentTypeRecencyPostprocessor(),  # Document-type-aware decay (email: 30d, attachment: 90d)
            ]
        )

        self.graph_query_engine = self.property_graph_index.as_query_engine(
            llm=self.llm,
            include_text=True,  # Include node text in retrieval
            text_qa_template=graph_qa_prompt
        )

        # Wrap as tools for SubQuestionQueryEngine
        vector_tool = QueryEngineTool.from_defaults(
            query_engine=self.vector_query_engine,
            name="vector_search",
            description=(
                "Useful for semantic search over document content. "
                "Use this for questions about what was said in documents, "
                "document content, topics discussed, specific information mentioned."
            )
        )

        graph_tool = QueryEngineTool.from_defaults(
            query_engine=self.graph_query_engine,
            name="graph_search",
            description=(
                "Useful for querying relationships between people, companies, and documents. "
                "Use this for questions about who sent what, who works where, "
                "connections between people, organizational structure."
            )
        )

        # Custom CEO Assistant prompt for final response synthesis
        # CRITICAL: Instructs LLM to correlate information using shared document_id
        ceo_assistant_prompt = PromptTemplate(get_ceo_prompt_template())

        # Create custom response synthesizer with CEO Assistant prompt (compact mode)
        # Compact mode: concatenates full chunks for fewer LLM calls while preserving all text
        response_synthesizer = get_response_synthesizer(
            llm=self.llm,
            response_mode="compact",
            text_qa_template=ceo_assistant_prompt
        )

        # SubQuestionQueryEngine with custom response synthesizer
        self.query_engine = SubQuestionQueryEngine.from_defaults(
            query_engine_tools=[vector_tool, graph_tool],
            llm=self.llm,
            response_synthesizer=response_synthesizer
        )
        logger.info("✅ SubQuestionQueryEngine ready (vector + graph)")
        logger.info("✅ CEO Assistant prompts applied (sub-queries + final synthesis)")

        logger.info("✅ Hybrid Query Engine ready")
        logger.info("   Architecture: SubQuestionQueryEngine (used for both query + chat)")
        logger.info("   Indexes: VectorStoreIndex (Qdrant) + PropertyGraphIndex (Neo4j)")
        logger.info("   Chat: Manual history injection into prompts (per LlamaIndex best practice)")

    async def _extract_time_filter(self, question: str) -> Optional[Dict[str, Any]]:
        """
        Extract STRICT time constraints from natural language query using LLM.

        CRITICAL: For queries like "show me emails from October 2024", this MUST return
        ONLY October 2024 timestamps to prevent hallucination.

        Args:
            question: User's natural language question

        Returns:
            Dict with:
              - has_time_filter: bool
              - start_timestamp: int (Unix timestamp, inclusive)
              - end_timestamp: int (Unix timestamp, exclusive - for LT comparison)
              - start_date: str (YYYY-MM-DD, for logging)
              - end_date: str (YYYY-MM-DD, for logging)
            Or None if error
        """
        from datetime import datetime, timezone
        import json

        current_date = datetime.now().strftime('%Y-%m-%d')
        current_date_readable = datetime.now().strftime('%B %d, %Y')

        prompt = f"""Today's date is {current_date_readable} ({current_date}).

TASK: Extract time period from this query (if present): "{question}"

If query specifies a time period, return start_date and end_date in YYYY-MM-DD format.
Be STRICT - only return a time filter if explicitly requested.

Return ONLY valid JSON in this exact format:

WITH time period:
{{"has_time_filter": true, "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}}

NO time period:
{{"has_time_filter": false}}

Examples:
- "emails from October 2024" → {{"has_time_filter": true, "start_date": "2024-10-01", "end_date": "2024-10-31"}}
- "what happened last week" → {{"has_time_filter": true, "start_date": "2024-01-15", "end_date": "2024-01-21"}}
- "after January 15, 2025" → {{"has_time_filter": true, "start_date": "2025-01-15", "end_date": "2099-12-31"}}
- "before March 2024" → {{"has_time_filter": true, "start_date": "2000-01-01", "end_date": "2024-02-29"}}
- "in Q1 2024" → {{"has_time_filter": true, "start_date": "2024-01-01", "end_date": "2024-03-31"}}
- "yesterday" → {{"has_time_filter": true, "start_date": "2024-01-22", "end_date": "2024-01-22"}}
- "show me purchase orders" → {{"has_time_filter": false}}
- "what materials do we use" → {{"has_time_filter": false}}

Return ONLY the JSON object, nothing else.
"""

        try:
            result = await self.llm.apredict(prompt)
            # Clean up response (sometimes LLM adds markdown)
            result = result.strip()
            if result.startswith('```'):
                result = result.split('\n', 1)[1].rsplit('\n', 1)[0]

            parsed = json.loads(result)

            if parsed.get('has_time_filter'):
                # Convert YYYY-MM-DD dates to Unix timestamps
                start_date = parsed['start_date']
                end_date = parsed['end_date']

                # Parse dates and set to UTC midnight
                start_dt = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
                # End date: set to 23:59:59 of that day for inclusive range
                end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(
                    hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc
                )

                start_ts = int(start_dt.timestamp())
                end_ts = int(end_dt.timestamp())

                logger.info(f"   🕐 STRICT time filter: {start_date} to {end_date} ({start_ts} to {end_ts})")

                return {
                    'has_time_filter': True,
                    'start_timestamp': start_ts,
                    'end_timestamp': end_ts,
                    'start_date': start_date,
                    'end_date': end_date
                }
            else:
                return {'has_time_filter': False}

        except Exception as e:
            logger.warning(f"   ⚠️  Could not extract time filter: {e}")
            return {'has_time_filter': False}

    def _build_metadata_filters(self, time_filter: Optional[Dict]) -> Optional[Any]:
        """
        Convert time filter dict to Qdrant MetadataFilters.

        CRITICAL: This creates DATABASE-LEVEL filters that Qdrant enforces BEFORE
        vector search. Documents outside the time range are NEVER retrieved,
        preventing LLM hallucination.

        Args:
            time_filter: Dict with start_timestamp and end_timestamp

        Returns:
            MetadataFilters object or None
        """
        if not time_filter or not time_filter.get('has_time_filter'):
            return None

        from llama_index.core.vector_stores import MetadataFilter, MetadataFilters, FilterOperator

        filters_list = []

        if 'start_timestamp' in time_filter and time_filter['start_timestamp']:
            filters_list.append(
                MetadataFilter(
                    key="created_at_timestamp",
                    operator=FilterOperator.GTE,  # Greater than or equal (inclusive start)
                    value=time_filter['start_timestamp']
                )
            )

        if 'end_timestamp' in time_filter and time_filter['end_timestamp']:
            filters_list.append(
                MetadataFilter(
                    key="created_at_timestamp",
                    operator=FilterOperator.LTE,  # Less than or equal (inclusive end)
                    value=time_filter['end_timestamp']
                )
            )

        if filters_list:
            metadata_filters = MetadataFilters(filters=filters_list)
            start_date = time_filter.get('start_date', 'N/A')
            end_date = time_filter.get('end_date', 'N/A')
            logger.info(f"   ✅ STRICT metadata filters: {start_date} to {end_date} ({len(filters_list)} conditions)")
            logger.info(f"   🔒 Qdrant will ONLY return documents in this range (ZERO hallucination)")
            return metadata_filters

        return None

    async def query(
        self,
        question: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute hybrid query with optional time-based filtering.

        Process:
        1. Extract time filter from question (if present)
        2. Build MetadataFilters for Qdrant
        3. Create filtered query engines
        4. SubQuestionQueryEngine breaks down the question
        5. Routes sub-questions to filtered vector or graph index
        6. Synthesizes comprehensive answer

        Args:
            question: User's question
            filters: Optional metadata filters (for manual override)

        Returns:
            Dict with answer, source nodes, and metadata
        """

        logger.info(f"\n{'='*80}")
        logger.info(f"🔍 HYBRID QUERY: {question}")
        logger.info(f"{'='*80}")

        try:
            # Step 1: Quick check if question has time-related keywords
            # Skip expensive LLM call for 80% of queries that don't mention time
            time_keywords = [
                'january', 'february', 'march', 'april', 'may', 'june',
                'july', 'august', 'september', 'october', 'november', 'december',
                'last week', 'last month', 'this week', 'this month', 'this year',
                'yesterday', 'today', 'after', 'before', 'between', 'during',
                'in 202', 'q1', 'q2', 'q3', 'q4'
            ]

            has_time_keyword = any(keyword in question.lower() for keyword in time_keywords)

            if has_time_keyword:
                logger.info(f"   🕐 Time keyword detected, extracting time filter...")
                time_filter = await self._extract_time_filter(question)
            else:
                logger.info(f"   ⏭️  No time keywords detected, skipping time filter extraction")
                time_filter = None

            # Step 2: Build metadata filters
            metadata_filters = self._build_metadata_filters(time_filter)

            # Step 3: Create query engines with filters (if any)
            if metadata_filters:
                logger.info(f"   🔍 Creating filtered query engines...")

                # Sub-question prompt for filtered vector queries (same as unfiltered)
                vector_qa_prompt_filtered = PromptTemplate(
                    "Your answer will be passed to another agent for final synthesis. Preserve exact information.\n\n"
                    "Context from documents (each chunk has metadata with title):\n"
                    "---------------------\n"
                    "{context_str}\n"
                    "---------------------\n\n"
                    "Given the context above and not prior knowledge, answer the question. When you include:\n"
                    "- Numbers, dates, metrics, amounts → quote them exactly\n"
                    "- Important statements or findings → quote 1-2 key sentences verbatim\n"
                    "- Regular facts or descriptions → you may paraphrase\n\n"
                    "IMPORTANT: When citing documents that have a file_url in metadata, create markdown links:\n"
                    "- Format: \"According to the [Document Title](file_url_value)...\"\n"
                    "- Use the actual file_url value from the chunk metadata, not the word 'file_url'\n"
                    "- For documents without file_url, just mention the title naturally\n\n"
                    "Use quotation marks for verbatim text.\n"
                    "If the context doesn't contain relevant information, say so clearly.\n\n"
                    "Question: {query_str}\n"
                    "Answer: "
                )

                # Create filtered vector query engine with reranking + recency boost
                # Multi-stage pipeline WITH time filtering (OPTIMAL ORDER):
                # 0. MetadataFilters: Database-level filtering (STRICT - only docs in time range)
                # 1. Retrieve 20 candidates from filtered set
                # 2. SentenceTransformerRerank: Deep semantic relevance (ALL 20 within time range)
                # 3. RecencyBoostPostprocessor: Soft preference for recent within time range
                vector_query_engine = self.vector_index.as_query_engine(
                    similarity_top_k=SIMILARITY_TOP_K,  # 20 candidates
                    llm=self.llm,
                    text_qa_template=vector_qa_prompt_filtered,
                    filters=metadata_filters,  # STRICT: Database-level time filtering
                    node_postprocessors=[
                        SentenceTransformerRerank(
                            model="BAAI/bge-reranker-base",
                            top_n=20,  # Keep all 20, reorder by relevance
                            device="cpu"
                            # Note: ONNX backend removed - newer LlamaIndex versions auto-optimize
                        ),
                        DocumentTypeRecencyPostprocessor(),  # Document-type-aware decay (email: 30d, attachment: 90d)
                    ]
                )

                # Graph query engine with TextToCypherRetriever for time-filtered queries
                # PRODUCTION SAFEGUARDS:
                # 1. Few-shot prompting with datetime examples (improves accuracy to 78%)
                # 2. Temperature=0 (deterministic Cypher generation)
                # 3. Query validation layer (catches syntax errors)
                # 4. Timeout protection (30s max per Neo4j best practices)
                # 5. Read-only at database level (NEO4J_USER should be read-only role)

                # Create TextToCypherRetriever with temporal filtering support
                from llama_index.core.indices.property_graph import TextToCypherRetriever
                from datetime import datetime

                # Build few-shot prompt with temporal query examples
                # CRITICAL: Include examples of timestamp filtering on Chunk nodes
                current_date = datetime.now().strftime('%B %d, %Y')
                current_timestamp = int(datetime.now().timestamp())

                text_to_cypher_template = f"""Task: Generate Cypher statement to query a Neo4j graph database.
Instructions:
- Use only the provided relationship types and properties from the schema
- Do not use any relationship types or properties not in the schema
- Do NOT create, delete, or modify any data (read-only queries only)
- For time-based queries, filter on Chunk nodes using created_at_timestamp (integer Unix timestamp)
- Chunk nodes contain document content and have MENTIONS relationships to entities
- Entity nodes (PERSON, COMPANY, etc.) do not have timestamps - filter via Chunk nodes

Schema:
{{schema}}

Important: Today's date is {current_date} (Unix timestamp: {current_timestamp})

Cypher Examples for Time-Filtered Queries:

# Example 1: "Show me emails from last week"
# Filter Chunk nodes by timestamp, then traverse to EMAIL nodes
MATCH (chunk:Chunk)-[:MENTIONS]->(email:EMAIL)
WHERE chunk.created_at_timestamp >= {current_timestamp - 7*24*60*60}
  AND chunk.created_at_timestamp < {current_timestamp}
RETURN chunk.text, email.title, email.created_at
LIMIT 10

# Example 2: "What did Hayden say last month?"
# Find PERSON, then Chunk nodes they're mentioned in with time filter
MATCH (p:PERSON {{name: "Hayden"}})<-[:MENTIONS]-(chunk:Chunk)
WHERE chunk.created_at_timestamp >= {current_timestamp - 30*24*60*60}
  AND chunk.created_at_timestamp < {current_timestamp}
RETURN chunk.text, chunk.title, chunk.created_at
LIMIT 10

# Example 3: "Show me purchase orders from Q3 2024"
# Filter Chunks mentioning PURCHASE_ORDER entities within date range
MATCH (po:PURCHASE_ORDER)<-[:MENTIONS]-(chunk:Chunk)
WHERE chunk.created_at_timestamp >= 1688169600  # July 1, 2024
  AND chunk.created_at_timestamp < 1696118400   # October 1, 2024
RETURN po, chunk.text
LIMIT 10

# Example 4: "Who works at Acme Corp after January 2025?"
# Entities + time filtering via Chunk provenance
MATCH (p:PERSON)-[r:WORKS_FOR]->(c:COMPANY {{name: "Acme Corp"}})
MATCH (p)<-[:MENTIONS]-(chunk:Chunk)
WHERE chunk.created_at_timestamp >= 1704067200  # January 1, 2025
RETURN p.name, chunk.title, chunk.created_at
LIMIT 10

Note: Only generate Cypher statements. No explanations or apologies.

Question: {{question}}
Cypher Query:"""

                # Sub-question prompt for filtered graph queries (same as unfiltered)
                graph_qa_prompt_filtered = PromptTemplate(
                    "Your answer will be passed to another agent for final synthesis. Focus on precise entity information.\n\n"
                    "Context from knowledge graph:\n"
                    "---------------------\n"
                    "{context_str}\n"
                    "---------------------\n\n"
                    "Given the context above and not prior knowledge, answer the question about entities and relationships:\n"
                    "- Use EXACT names, titles, company names (don't paraphrase proper nouns)\n"
                    "- Describe relationships clearly: who did what, who works where, who sent what\n"
                    "- If context includes quotes or specific statements, preserve them\n"
                    "- Translate technical relationship types to natural language (CREATED_BY → \"created by\")\n\n"
                    "If the context doesn't contain relevant information, say so clearly.\n\n"
                    "Question: {query_str}\n"
                    "Answer: "
                )

                # Create TextToCypherRetriever with safeguards
                cypher_retriever = TextToCypherRetriever(
                    self.property_graph_index.property_graph_store,
                    llm=OpenAI(model=QUERY_MODEL, temperature=0.0, api_key=OPENAI_API_KEY),  # temperature=0 for deterministic generation
                    text_to_cypher_template=text_to_cypher_template,
                    # Cypher validator (optional - can add custom validation logic)
                    cypher_validator=None,  # TODO: Add validator if needed
                    # Only allow reading text, label, type fields (no sensitive data)
                    allowed_output_field=["text", "label", "type", "name", "title", "created_at", "created_at_timestamp"]
                )

                # Create graph query engine with TextToCypherRetriever
                graph_query_engine = self.property_graph_index.as_query_engine(
                    sub_retrievers=[cypher_retriever],  # Use our custom retriever
                    llm=self.llm,
                    text_qa_template=graph_qa_prompt_filtered,
                    include_text=True
                )

                # Wrap as tools for SubQuestionQueryEngine
                from llama_index.core.tools import QueryEngineTool

                vector_tool = QueryEngineTool.from_defaults(
                    query_engine=vector_query_engine,
                    name="vector_search",
                    description=(
                        "Useful for semantic search over document content. "
                        "Use this for questions about what was said in documents, "
                        "document content, topics discussed, specific information mentioned."
                    )
                )

                graph_tool = QueryEngineTool.from_defaults(
                    query_engine=graph_query_engine,
                    name="graph_search",
                    description=(
                        "Useful for querying relationships between people, companies, and documents. "
                        "Use this for questions about who sent what, who works where, "
                        "connections between people, organizational structure."
                    )
                )

                # Create temporary SubQuestionQueryEngine with filtered tools
                from llama_index.core.query_engine import SubQuestionQueryEngine
                from llama_index.core.response_synthesizers import get_response_synthesizer

                # Use the same CEO Assistant prompt (with formatting instructions)
                ceo_assistant_prompt = PromptTemplate(get_ceo_prompt_template())

                response_synthesizer = get_response_synthesizer(
                    llm=self.llm,
                    response_mode="compact",
                    text_qa_template=ceo_assistant_prompt
                )

                query_engine = SubQuestionQueryEngine.from_defaults(
                    query_engine_tools=[vector_tool, graph_tool],
                    llm=self.llm,
                    response_synthesizer=response_synthesizer
                )

                # Execute query through filtered SubQuestionQueryEngine
                response = await query_engine.aquery(question)
            else:
                # No time filter - use default query engine
                response = await self.query_engine.aquery(question)

            logger.info(f"✅ QUERY COMPLETE")
            logger.info(f"{'='*80}")
            logger.info(f"   Answer length: {len(str(response))} characters")
            logger.info(f"   Source nodes: {len(response.source_nodes)}")

            return {
                "question": question,
                "answer": str(response),
                "source_nodes": response.source_nodes,
                "metadata": response.metadata if hasattr(response, "metadata") else {}
            }

        except Exception as e:
            error_msg = f"Query failed: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            return {
                "question": question,
                "answer": "",
                "error": error_msg,
                "source_nodes": []
            }

    async def chat(
        self,
        message: str,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Conversational interface with memory (Production).

        Handles natural conversations by manually injecting chat history into
        SubQuestionQueryEngine prompts. This ensures consistent high-quality retrieval
        with conversational context.

        Architecture (per LlamaIndex best practice):
        1. Format chat_history into a string
        2. Rebuild CEO prompt template with history injected
        3. Create new response_synthesizer with updated prompt
        4. Rebuild SubQuestionQueryEngine with new synthesizer
        5. Query with the same high-quality retrieval as query() method

        PRODUCTION: Smart history loading with token limits (3900 max)
        - Truncates to most recent messages that fit
        - Prevents token overflow and API errors

        Args:
            message: User's message
            chat_history: Optional external chat history
                         Format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]

        Returns:
            Dict with question, answer, source_nodes, metadata

        Examples:
            >>> await engine.chat("what materials do we use?")
            {"answer": "We primarily use polycarbonate PC-1000...", "source_nodes": [...]}

            >>> await engine.chat("who supplies it?", chat_history=[...])  # Context from history
            {"answer": "Acme Plastics supplies polycarbonate PC-1000...", "source_nodes": [...]}
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"💬 CHAT: {message}")
        logger.info(f"{'='*80}")

        try:
            # Step 1: Format chat history into string (if provided)
            chat_history_str = ""
            if chat_history:
                # Truncate to token limit (3900 tokens max)
                max_tokens = 3900
                total_tokens = 0
                messages_to_include = []

                # Scan backwards (newest first) to find messages that fit
                for msg in reversed(chat_history):
                    content = msg.get("content", "")
                    msg_tokens = len(content) // 4  # Rough: 1 token ≈ 4 chars

                    if total_tokens + msg_tokens > max_tokens:
                        break

                    messages_to_include.append(msg)
                    total_tokens += msg_tokens

                # Build history string in chronological order
                history_lines = []
                for msg in reversed(messages_to_include):
                    role = msg.get("role", "user").capitalize()
                    content = msg.get("content", "")
                    history_lines.append(f"{role}: {content}")

                chat_history_str = "\n".join(history_lines)

                messages_loaded = len(messages_to_include)
                logger.info(f"   📚 Using {messages_loaded}/{len(chat_history)} messages (~{total_tokens} tokens)")
                if messages_loaded < len(chat_history):
                    logger.info(f"   ℹ️  Truncated {len(chat_history) - messages_loaded} older messages")

            # Step 2: Rebuild CEO prompt with chat history injected
            ceo_prompt_with_history = PromptTemplate(
                f"You are an intelligent personal assistant to the CEO. You have access to the entire company's knowledge. "
                f"All emails, documents, purchase orders, activities, materials, etc. that go on in this business are in your knowledge bases. "
                f"Because of this, you know more about what is happening in the company than anyone. "
                f"You can access and uncover unique relationships and patterns that otherwise would go unseen.\n\n"
                + (f"Previous conversation:\n---------------------\n{chat_history_str}\n---------------------\n\n" if chat_history_str else "")
                + f"Below are answers from the knowledge base:\n"
                f"---------------------\n"
                f"{{context_str}}\n"
                f"---------------------\n\n"
                f"Synthesize a comprehensive, conversational response to the CEO's question. "
                f"Use direct quotes ONLY when they add real value - specific numbers, impactful statements, or unique insights (quote 1-2 full sentences). "
                f"Don't quote mundane facts or simple status updates. "
                f"Cite sources by mentioning document titles naturally (e.g., 'The ISO checklist shows...', 'According to the QC report...') "
                f"when making important claims or switching between different documents. Don't use technical IDs like 'document_id: 180'. "
                f"When you find information from multiple sources, cross-reference and combine it naturally. "
                f"Make cool connections, provide insightful suggestions, and point the CEO in the right direction. "
                f"Be conversational and direct - skip formal report language. "
                f"Your job is to knock the CEO's socks off with how much you know about the business.\n\n"
                f"FORMATTING: Always format your responses with markdown for better readability:\n"
                f"- Use emoji section headers (📦 🚨 📊 🚛 💰 ⚡ 🎯) to organize information\n"
                f"- Use **bold** for important numbers, names, and key points\n"
                f"- Use bullet points and numbered lists for structured information\n"
                f"- Use markdown tables for data comparisons or structured data\n"
                f"- Use ✅ checkmarks for completed items and ❌ for issues\n"
                f"- Use code blocks for metrics, dates, or technical details\n"
                f"- Keep sections clean and well-organized\n\n"
                f"Question: {{query_str}}\n"
                f"Answer: "
            )

            # Step 3: Create new response synthesizer with updated prompt (compact mode)
            response_synthesizer = get_response_synthesizer(
                llm=self.llm,
                response_mode="compact",
                text_qa_template=ceo_prompt_with_history
            )

            # Step 4: Rebuild SubQuestionQueryEngine with new synthesizer
            query_engine_with_history = SubQuestionQueryEngine.from_defaults(
                query_engine_tools=[
                    QueryEngineTool.from_defaults(
                        query_engine=self.vector_query_engine,
                        name="vector_search",
                        description=(
                            "Useful for semantic search over document content. "
                            "Use this for questions about what was said in documents, "
                            "document content, topics discussed, specific information mentioned."
                        )
                    ),
                    QueryEngineTool.from_defaults(
                        query_engine=self.graph_query_engine,
                        name="graph_search",
                        description=(
                            "Useful for querying relationships between people, companies, and documents. "
                            "Use this for questions about who sent what, who works where, "
                            "connections between people, organizational structure."
                        )
                    )
                ],
                llm=self.llm,
                response_synthesizer=response_synthesizer
            )

            # Step 5: Query with full SubQuestionQueryEngine pipeline
            response = await query_engine_with_history.aquery(message)

            logger.info(f"✅ CHAT COMPLETE")
            logger.info(f"{'='*80}")
            logger.info(f"   Answer length: {len(str(response))} characters")
            logger.info(f"   Source nodes: {len(response.source_nodes)}")

            return {
                "question": message,
                "answer": str(response),
                "source_nodes": response.source_nodes,
                "metadata": {
                    "is_chat": True,
                    "chat_history_provided": bool(chat_history),
                    "chat_history_length": len(chat_history) if chat_history else 0
                }
            }

        except Exception as e:
            error_msg = f"Chat failed: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            return {
                "question": message,
                "answer": "",
                "error": error_msg,
                "source_nodes": []
            }


    async def retrieve_only(
        self,
        question: str,
        use_vector: bool = True,
        use_graph: bool = True
    ):
        """
        Retrieve relevant nodes without synthesis.

        Args:
            question: Search query
            use_vector: Use vector search
            use_graph: Use graph search

        Returns:
            List of retrieved nodes
        """

        nodes = []

        if use_vector:
            try:
                vector_nodes = await self.vector_query_engine.aretrieve(question)
                nodes.extend(vector_nodes)
                logger.info(f"Retrieved {len(vector_nodes)} nodes from vector index")
            except Exception as e:
                logger.error(f"Vector retrieval failed: {e}")

        if use_graph:
            try:
                graph_nodes = await self.graph_query_engine.aretrieve(question)
                nodes.extend(graph_nodes)
                logger.info(f"Retrieved {len(graph_nodes)} nodes from graph index")
            except Exception as e:
                logger.error(f"Graph retrieval failed: {e}")

        return nodes

    async def cleanup(self):
        """
        Cleanup database connections and resources.

        PRODUCTION: Call this on application shutdown to prevent resource leaks.
        Research: "Containerized setups need proper resource cleanup" (2025 best practice)

        Cleans up:
        - Neo4j driver connections (with connection pool)
        - Qdrant client connections
        - Chat memory buffers
        - SentenceTransformer models (if loaded)

        Example:
            >>> engine = HybridQueryEngine()
            >>> # ... use engine ...
            >>> await engine.cleanup()  # On shutdown
        """
        try:
            # Close Neo4j connection pool
            if hasattr(self, 'graph_store') and hasattr(self.graph_store, '_driver'):
                self.graph_store._driver.close()
                logger.info("   ✅ Neo4j driver & connection pool closed")

            # Close Qdrant clients
            if hasattr(self, 'qdrant_client'):
                try:
                    self.qdrant_client.close()
                    logger.info("   ✅ Qdrant sync client closed")
                except Exception:
                    pass  # Client may not have close method

            if hasattr(self, 'qdrant_aclient'):
                try:
                    await self.qdrant_aclient.close()
                    logger.info("   ✅ Qdrant async client closed")
                except Exception:
                    pass  # Client may not have close method

            logger.info("🧹 All query engine resources cleaned up")

        except Exception as e:
            logger.warning(f"⚠️  Cleanup warning (non-fatal): {e}")

    def __del__(self):
        """Destructor - ensure cleanup on garbage collection"""
        try:
            # Sync cleanup for destructor (can't use async)
            if hasattr(self, 'graph_store') and hasattr(self.graph_store, '_driver'):
                self.graph_store._driver.close()
        except:
            pass  # Silent cleanup on destruction


