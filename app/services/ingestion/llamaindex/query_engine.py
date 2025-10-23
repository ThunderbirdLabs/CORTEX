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

logger = logging.getLogger(__name__)


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

        # Create query engines with custom prompts
        self.vector_query_engine = self.vector_index.as_query_engine(
            similarity_top_k=SIMILARITY_TOP_K,
            llm=self.llm,
            text_qa_template=vector_qa_prompt
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
        ceo_assistant_prompt = PromptTemplate(
            "You are an intelligent personal assistant to the CEO. You have access to the entire company's knowledge. "
            "All emails, documents, deals, activities, orders, etc. that go on in this business are in your knowledge bases. "
            "Because of this, you know more about what is happening in the company than anyone. "
            "You can access and uncover unique relationships and patterns that otherwise would go unseen.\n\n"
            "Below are answers from the knowledge base:\n"
            "---------------------\n"
            "{context_str}\n"
            "---------------------\n\n"
            "Synthesize a comprehensive, conversational response to the CEO's question. "
            "Use direct quotes ONLY when they add real value - specific numbers, impactful statements, or unique insights (quote 1-2 full sentences). "
            "Don't quote mundane facts or simple status updates. "
            "Cite sources by mentioning document titles naturally (e.g., 'The ISO checklist shows...', 'According to the QC report...') "
            "when making important claims or switching between different documents. Don't use technical IDs like 'document_id: 180'. "
            "When you find information from multiple sources, cross-reference and combine it naturally. "
            "Make cool connections, provide insightful suggestions, and point the CEO in the right direction. "
            "Be conversational and direct - skip formal report language. "
            "Your job is to knock the CEO's socks off with how much you know about the business.\n\n"
            "FORMATTING: Always format your responses with markdown for better readability:\n"
            "- Use emoji section headers (📦 🚨 📊 🚛 💰 ⚡ 🎯) to organize information\n"
            "- Use **bold** for important numbers, names, and key points\n"
            "- Use bullet points and numbered lists for structured information\n"
            "- Use markdown tables for data comparisons or structured data\n"
            "- Use ✅ checkmarks for completed items and ❌ for issues\n"
            "- Use code blocks for metrics, dates, or technical details\n"
            "- Keep sections clean and well-organized\n\n"
            "Question: {query_str}\n"
            "Answer: "
        )

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

        logger.info("✅ Hybrid Query Engine ready")
        logger.info("   Architecture: SubQuestionQueryEngine")
        logger.info("   Indexes: VectorStoreIndex (Qdrant) + PropertyGraphIndex (Neo4j)")

    async def _extract_time_filter(self, question: str) -> Optional[Dict[str, Any]]:
        """
        Extract time constraints from natural language query using LLM.

        Args:
            question: User's natural language question

        Returns:
            Dict with has_time_filter, start_timestamp, end_timestamp
            Or None if no time reference found
        """
        from datetime import datetime
        import json

        current_date = datetime.now().strftime('%Y-%m-%d')
        current_date_readable = datetime.now().strftime('%B %d, %Y')

        prompt = f"""Today's date is {current_date_readable} ({current_date}).

Analyze this question and extract any time constraints: "{question}"

If there's a time reference (like "in October", "last month", "after January 15th", "this week"),
return the start and end Unix timestamps for that time period.

Return ONLY valid JSON in this exact format:
{{"has_time_filter": true, "start_timestamp": <unix_timestamp_int>, "end_timestamp": <unix_timestamp_int>}}

If NO time reference exists, return:
{{"has_time_filter": false}}

Examples:
- "in October" (current year) → Oct 1 00:00 to Nov 1 00:00
- "last month" → Previous month's first day to current month's first day
- "after January 15th" → Jan 15 00:00 to far future timestamp
- "this week" → Monday 00:00 to next Monday 00:00
- "yesterday" → Yesterday 00:00 to today 00:00

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
                logger.info(f"   🕐 Time filter detected: {parsed.get('start_timestamp')} to {parsed.get('end_timestamp')}")

            return parsed
        except Exception as e:
            logger.warning(f"   ⚠️  Could not extract time filter: {e}")
            return None

    def _build_metadata_filters(self, time_filter: Optional[Dict]) -> Optional[Any]:
        """
        Convert time filter dict to Qdrant MetadataFilters.

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
                    operator=FilterOperator.GTE,
                    value=time_filter['start_timestamp']
                )
            )

        if 'end_timestamp' in time_filter and time_filter['end_timestamp']:
            filters_list.append(
                MetadataFilter(
                    key="created_at_timestamp",
                    operator=FilterOperator.LT,
                    value=time_filter['end_timestamp']
                )
            )

        if filters_list:
            metadata_filters = MetadataFilters(filters=filters_list)
            logger.info(f"   ✅ Built metadata filters: {len(filters_list)} conditions")
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

                # Create filtered vector query engine
                vector_query_engine = self.vector_index.as_query_engine(
                    similarity_top_k=SIMILARITY_TOP_K,
                    llm=self.llm,
                    filters=metadata_filters  # Apply time filter to Qdrant
                )

                # Graph query engine (no filtering for now - could add Cypher filters later)
                graph_query_engine = self.graph_query_engine

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
                from llama_index.core import PromptTemplate

                # Use the same improved CEO Assistant prompt
                ceo_assistant_prompt = PromptTemplate(
                    "You are an intelligent personal assistant to the CEO. You have access to the entire company's knowledge. "
                    "All emails, documents, deals, activities, orders, etc. that go on in this business are in your knowledge bases. "
                    "Because of this, you know more about what is happening in the company than anyone. "
                    "You can access and uncover unique relationships and patterns that otherwise would go unseen.\n\n"
                    "Below are answers from the knowledge base:\n"
                    "---------------------\n"
                    "{context_str}\n"
                    "---------------------\n\n"
                    "Synthesize a comprehensive, conversational response to the CEO's question. "
                    "Use direct quotes ONLY when they add real value - specific numbers, impactful statements, or unique insights (quote 1-2 full sentences). "
                    "Don't quote mundane facts or simple status updates. "
                    "Cite sources by mentioning document titles naturally (e.g., 'The ISO checklist shows...', 'According to the QC report...') "
                    "when making important claims or switching between different documents. Don't use technical IDs like 'document_id: 180'. "
                    "When you find information from multiple sources, cross-reference and combine it naturally. "
                    "Make cool connections, provide insightful suggestions, and point the CEO in the right direction. "
                    "Be conversational and direct - skip formal report language. "
                    "Your job is to knock the CEO's socks off with how much you know about the business.\n\n"
                    "Question: {query_str}\n"
                    "Answer: "
                )

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


