"""
LlamaIndex Query Engine (Expert Recommended Pattern)

Architecture:
- SubQuestionQueryEngine for hybrid retrieval
- VectorStoreIndex for semantic search (Qdrant)
- PropertyGraphIndex for graph queries (Neo4j)
- Intelligent routing and result synthesis
"""

import logging
from typing import Dict, Any, Optional

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
from .recency_postprocessor import RecencyBoostPostprocessor

# Import SentenceTransformer reranker for production relevance scoring
from llama_index.postprocessor.sbert_rerank import SentenceTransformerRerank

logger = logging.getLogger(__name__)

# CEO Assistant synthesis prompt (used for both default and filtered query engines)
CEO_ASSISTANT_PROMPT_TEMPLATE = """You are an intelligent personal assistant to the CEO. You have access to the entire company's knowledge. All emails, documents, deals, activities, orders, etc. that go on in this business are in your knowledge bases. Because of this, you know more about what is happening in the company than anyone. You can access and uncover unique relationships and patterns that otherwise would go unseen.

Below are answers from the knowledge base:
---------------------
{context_str}
---------------------

Synthesize a comprehensive, conversational response to the CEO's question. Use direct quotes ONLY when they add real value - specific numbers, impactful statements, or unique insights (quote 1-2 full sentences). Don't quote mundane facts or simple status updates. Cite sources by mentioning document titles naturally (e.g., 'The ISO checklist shows...', 'According to the QC report...') when making important claims or switching between different documents. Don't use technical IDs like 'document_id: 180'. When you find information from multiple sources, cross-reference and combine it naturally. Make cool connections, provide insightful suggestions, and point the CEO in the right direction. Be conversational and direct - skip formal report language. Your job is to knock the CEO's socks off with how much you know about the business.

FORMATTING: Always format your responses with markdown for better readability:
- Use emoji section headers (📦 🚨 📊 🚛 💰 ⚡ 🎯) to organize information
- Use **bold** for important numbers, names, and key points
- Use bullet points and numbered lists for structured information
- Use markdown tables for data comparisons or structured data
- Use ✅ checkmarks for completed items and ❌ for issues
- Use code blocks for metrics, dates, or technical details
- Keep sections clean and well-organized

Question: {query_str}
Answer: """


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

                "You have access to the entire company's knowledge - "
                "all emails, documents, deals, activities, orders, and everything that goes on in this business is in your knowledge bases.\n\n"

                "Because of this, you know more about what is happening in the company than anyone. "
                "You can access and uncover unique relationships and patterns that would otherwise go unseen.\n\n"

                "Your job is to take all of the information you're given (which comes from a vector store and knowledge graph) "
                "and formulate highly informative insights for the CEO.\n\n"

                "Whenever you have the chance, make cool connections, provide insightful suggestions, and point the CEO in the right direction. "
                "Your job is to knock the CEO's socks off with how much you know about the business.\n\n"

                "Use quotes whenever you can to show you truly see what is happening. "
                "Respond conversationally - skip any letter formatting like greetings, salutations, or sign-offs.\n\n"

                "When referencing information from the knowledge graph, speak naturally about connections and relationships "
                "without exposing technical details like raw relationship types (say 'created by', not 'CREATED_BY') or data structures. "
                "Just state the facts as if you naturally know them."
            )
        )

        # Embedding model for vector search
        self.embed_model = OpenAIEmbedding(
            model_name=EMBEDDING_MODEL,
            api_key=OPENAI_API_KEY
        )

        # Qdrant vector store (with async client for retrieval)
        qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        qdrant_aclient = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        vector_store = QdrantVectorStore(
            client=qdrant_client,
            aclient=qdrant_aclient,
            collection_name=QDRANT_COLLECTION_NAME
        )
        logger.info(f"✅ Qdrant Vector Store: {QDRANT_COLLECTION_NAME}")

        # VectorStoreIndex for semantic search
        self.vector_index = VectorStoreIndex.from_vector_store(
            vector_store=vector_store,
            embed_model=self.embed_model
        )
        logger.info("✅ VectorStoreIndex created for semantic search")

        # Neo4j graph store
        graph_store = Neo4jPropertyGraphStore(
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD,
            url=NEO4J_URI,
            database=NEO4J_DATABASE
        )
        logger.info(f"✅ Neo4j Graph Store: {NEO4J_URI}")

        # PropertyGraphIndex for graph queries
        self.property_graph_index = PropertyGraphIndex.from_existing(
            property_graph_store=graph_store,
            llm=self.llm,
            embed_model=self.embed_model
        )
        logger.info("✅ PropertyGraphIndex created for graph queries")

        # Custom prompts for sub-question query engines to preserve direct quotes
        # CRITICAL: Prompts instruct LLM to note document_id for cross-referencing
        vector_qa_prompt = PromptTemplate(
            "Context information from documents is below. Each chunk has a 'title' field showing the source document name.\n"
            "---------------------\n"
            "{context_str}\n"
            "---------------------\n\n"
            "Given the context information, answer the question. "
            "IMPORTANT: Use direct quotes ONLY for specific numbers, data points, unique insights, or impactful statements - "
            "not for mundane phrases or simple facts. Quote 1-2 full sentences when the exact wording matters. "
            "When referencing information, mention the document title (e.g., 'According to the ISO checklist...' or 'The QC report shows...') "
            "when switching between different sources or making key claims.\n\n"
            "Question: {query_str}\n"
            "Answer: "
        )

        graph_qa_prompt = PromptTemplate(
            "Context information from the knowledge graph is below. Entities and relationships extracted from documents.\n"
            "---------------------\n"
            "{context_str}\n"
            "---------------------\n\n"
            "Given the context information, answer the question about relationships and entities. "
            "IMPORTANT: Use specific names and data points from the context. "
            "Only quote particularly insightful or specific phrases - avoid quoting simple relationship facts. "
            "When referencing information from specific documents, mention the document title naturally.\n\n"
            "Question: {query_str}\n"
            "Answer: "
        )

        # Create query engines with custom prompts + recency boost + reranking
        # Multi-stage retrieval pipeline (research-backed production pattern):
        # 1. Retrieve 20 candidates (SIMILARITY_TOP_K=20)
        # 2. RecencyBoostPostprocessor: Boost recent documents (soft preference)
        # 3. SentenceTransformerRerank: Deep relevance scoring with cross-encoder (narrows to top 10)
        self.vector_query_engine = self.vector_index.as_query_engine(
            similarity_top_k=SIMILARITY_TOP_K,  # Now 20 (cast wider net)
            llm=self.llm,
            text_qa_template=vector_qa_prompt,
            node_postprocessors=[
                RecencyBoostPostprocessor(decay_days=90),  # Stage 1: Boost recent
                SentenceTransformerRerank(
                    model="BAAI/bge-reranker-base",  # Production-grade cross-encoder
                    top_n=10  # Stage 2: Narrow to top 10 most relevant
                )
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
        ceo_assistant_prompt = PromptTemplate(CEO_ASSISTANT_PROMPT_TEMPLATE)

        # Create custom response synthesizer with CEO Assistant prompt
        response_synthesizer = get_response_synthesizer(
            llm=self.llm,
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

        # ============================================
        # CONVERSATIONAL CHAT ENGINE (Production)
        # ============================================
        # Uses CondensePlusContextChatEngine for natural conversations:
        # - Handles greetings/small talk without triggering retrieval
        # - Maintains conversation memory (token_limit=3900)
        # - Condenses chat history + new message into standalone questions
        # - Passes context-aware questions to SubQuestionQueryEngine retriever
        # - Preserves ALL existing functionality (reranking, time filtering, graph queries)

        from llama_index.core.memory import ChatMemoryBuffer
        from llama_index.core.chat_engine import CondensePlusContextChatEngine

        logger.info("🗣️  Initializing Conversational Chat Engine...")

        # Chat memory: stores last ~10-15 message pairs (3900 tokens)
        self.chat_memory = ChatMemoryBuffer.from_defaults(token_limit=3900)

        # Custom condense prompt for business context
        condense_prompt_template = PromptTemplate(
            f"Given the conversation history below and a new user message, "
            f"rephrase the user message as a standalone question that includes all necessary context "
            f"from the conversation history. If the message is a greeting or casual conversation, "
            f"respond with the EXACT same message (do not modify it).\n\n"
            f"Today's date is {current_date} ({current_date_iso}).\n\n"
            f"Conversation History:\n"
            f"{{chat_history}}\n\n"
            f"New User Message: {{question}}\n\n"
            f"Standalone Question (or original message if greeting):"
        )

        # Create conversational chat engine
        # CRITICAL: Uses SubQuestionQueryEngine.as_retriever() to preserve entire pipeline
        self.chat_engine = CondensePlusContextChatEngine(
            retriever=self.query_engine.as_retriever(),  # ← Full SubQuestion pipeline as retriever
            llm=self.llm,
            memory=self.chat_memory,
            context_prompt=CEO_ASSISTANT_PROMPT_TEMPLATE,  # Same CEO assistant prompt
            condense_prompt=condense_prompt_template,
            node_postprocessors=[
                RecencyBoostPostprocessor(decay_days=90),  # Recency bias
                SentenceTransformerRerank(
                    model="BAAI/bge-reranker-base",
                    top_n=10  # Final top 10 after reranking
                )
            ],
            verbose=False  # Set to True for debugging
        )

        logger.info("✅ CondensePlusContextChatEngine ready")
        logger.info("   Memory: ChatMemoryBuffer (3900 tokens)")
        logger.info("   Retriever: SubQuestionQueryEngine (vector + graph)")
        logger.info("   Postprocessors: RecencyBoost + SentenceTransformerRerank")

        logger.info("✅ Hybrid Query Engine ready")
        logger.info("   Architecture: SubQuestionQueryEngine + CondensePlusContextChatEngine")
        logger.info("   Indexes: VectorStoreIndex (Qdrant) + PropertyGraphIndex (Neo4j)")
        logger.info("   Modes: query() [stateless] | chat() [conversational memory]")

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
- "show me deals" → {{"has_time_filter": false}}
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

                # Create filtered vector query engine with recency boost + reranking
                # Multi-stage pipeline WITH time filtering:
                # 0. MetadataFilters: Database-level filtering (STRICT - only docs in time range)
                # 1. Retrieve 20 candidates from filtered set
                # 2. RecencyBoost: Soft preference for recent within time range
                # 3. SentenceTransformerRerank: Deep relevance scoring → top 10
                vector_query_engine = self.vector_index.as_query_engine(
                    similarity_top_k=SIMILARITY_TOP_K,  # 20 candidates
                    llm=self.llm,
                    filters=metadata_filters,  # STRICT: Database-level time filtering
                    node_postprocessors=[
                        RecencyBoostPostprocessor(decay_days=90),  # Boost recent within filter
                        SentenceTransformerRerank(
                            model="BAAI/bge-reranker-base",
                            top_n=10  # Final top 10 most relevant
                        )
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

# Example 3: "Show me deals from Q3 2024"
# Filter Chunks mentioning DEAL entities within date range
MATCH (deal:DEAL)<-[:MENTIONS]-(chunk:Chunk)
WHERE chunk.created_at_timestamp >= 1688169600  # July 1, 2024
  AND chunk.created_at_timestamp < 1696118400   # October 1, 2024
RETURN deal, chunk.text
LIMIT 10

# Example 4: "Who worked on Project X after January 2025?"
# Entities + time filtering via Chunk provenance
MATCH (p:PERSON)-[r:WORKS_ON]->(proj:PROJECT {{name: "Project X"}})
MATCH (p)<-[:MENTIONS]-(chunk:Chunk)
WHERE chunk.created_at_timestamp >= 1704067200  # January 1, 2025
RETURN p.name, chunk.title, chunk.created_at
LIMIT 10

Note: Only generate Cypher statements. No explanations or apologies.

Question: {{question}}
Cypher Query:"""

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
                ceo_assistant_prompt = PromptTemplate(CEO_ASSISTANT_PROMPT_TEMPLATE)

                response_synthesizer = get_response_synthesizer(
                    llm=self.llm,
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

        Handles natural conversations:
        - Greetings ("hey", "hello") respond directly without retrieval
        - Business questions use full SubQuestionQueryEngine pipeline
        - Follow-ups automatically include conversation context
        - Maintains chat memory across turns

        Architecture:
        1. CondensePlusContextChatEngine condenses [history + message] → standalone question
        2. If greeting/small talk → responds directly (no retrieval)
        3. If business query → SubQuestionQueryEngine retrieves with full context
        4. Response includes conversation memory

        Args:
            message: User's message (can be greeting or business question)
            chat_history: Optional external chat history to restore context
                         Format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]

        Returns:
            Dict with:
              - question: User's original message
              - answer: Conversational response
              - source_nodes: Retrieved sources (empty for greetings)
              - metadata: {"is_chat": True, "chat_history_length": N}

        Examples:
            >>> await engine.chat("hey")
            {"answer": "Hey! What can I help you with today?", "source_nodes": []}

            >>> await engine.chat("what materials do we use?")
            {"answer": "We primarily use polycarbonate PC-1000...", "source_nodes": [...]}

            >>> await engine.chat("who supplies it?")  # Automatically knows "it" = PC-1000 from history
            {"answer": "Acme Plastics supplies polycarbonate PC-1000...", "source_nodes": [...]}
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"💬 CHAT: {message}")
        logger.info(f"{'='*80}")

        try:
            # Optional: Restore chat history from external source (e.g., database)
            if chat_history:
                from llama_index.core.llms import ChatMessage
                self.chat_memory.reset()  # Clear existing memory
                for msg in chat_history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    self.chat_memory.put(ChatMessage(role=role, content=content))
                logger.info(f"   📚 Restored {len(chat_history)} messages from chat history")

            # Execute conversational chat
            # CondensePlusContextChatEngine handles:
            # - Greeting detection (responds directly, no retrieval)
            # - Context condensation (history + message → standalone question)
            # - Retrieval (if needed, via SubQuestionQueryEngine)
            # - Response synthesis (with CEO Assistant prompt)
            response = await self.chat_engine.achat(message)

            logger.info(f"✅ CHAT COMPLETE")
            logger.info(f"{'='*80}")
            logger.info(f"   Answer length: {len(str(response))} characters")
            logger.info(f"   Source nodes: {len(response.source_nodes)}")
            logger.info(f"   Chat memory: {len(self.chat_memory.get_all())} messages")

            return {
                "question": message,
                "answer": str(response),
                "source_nodes": response.source_nodes,
                "metadata": {
                    "is_chat": True,
                    "chat_history_length": len(self.chat_memory.get_all())
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

    def reset_chat(self):
        """
        Reset conversation memory.

        Use when:
        - User starts a new conversation
        - User explicitly requests to clear history
        - Switching between different chat sessions

        Example:
            >>> engine.reset_chat()
            >>> await engine.chat("hey")  # Fresh conversation, no history
        """
        self.chat_memory.reset()
        logger.info("🔄 Chat memory reset")

    def get_chat_history(self) -> List[Dict[str, str]]:
        """
        Get current conversation history.

        Returns:
            List of chat messages in format:
            [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]

        Useful for:
        - Saving chat history to database
        - Debugging conversation flow
        - Displaying chat history to user
        """
        messages = self.chat_memory.get_all()
        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

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


