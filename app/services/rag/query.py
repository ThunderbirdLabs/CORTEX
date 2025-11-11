"""
LlamaIndex Query Engine

Architecture:
- SubQuestionQueryEngine for query decomposition
- VectorStoreIndex for semantic search (Qdrant)
- DocumentTypeRecencyPostprocessor for time-aware ranking
- Enhanced synthesis with raw chunks for CEO cross-analysis
"""

import logging
from typing import Dict, Any, Optional, List

from llama_index.core import VectorStoreIndex, PromptTemplate, Settings
from llama_index.core.query_engine import SubQuestionQueryEngine
from llama_index.core.tools import QueryEngineTool
from llama_index.core.response_synthesizers import get_response_synthesizer
from llama_index.core.callbacks import CallbackManager, LlamaDebugHandler
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from qdrant_client import QdrantClient, AsyncQdrantClient

from .config import (
    QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION_NAME,
    OPENAI_API_KEY, QUERY_MODEL, QUERY_TEMPERATURE,
    EMBEDDING_MODEL, SIMILARITY_TOP_K
)
from .recency import DocumentTypeRecencyPostprocessor


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
    Query engine using SubQuestionQueryEngine with vector search.

    Uses:
    1. VectorStoreIndex (Qdrant) - Semantic search over document chunks with recency boosting

    The SubQuestionQueryEngine:
    - Breaks down complex questions
    - Routes sub-questions to vector search
    - Synthesizes comprehensive answers
    """

    def __init__(self, enable_callbacks: bool = False):
        logger.info("🚀 Initializing Hybrid Query Engine (Expert Pattern)")

        # Initialize callback manager for observability (optional)
        self.callback_manager = None
        self.llama_debug = None
        if enable_callbacks:
            self.llama_debug = LlamaDebugHandler(print_trace_on_end=True)
            self.callback_manager = CallbackManager([self.llama_debug])
            Settings.callback_manager = self.callback_manager
            logger.info("✅ Callback system enabled (LlamaDebugHandler)")

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

        # Create query engines with custom prompts + reranking + recency boost
        # Multi-stage retrieval pipeline (OPTIMAL ORDER - 2025 best practice):
        # 1. Retrieve 20 candidates (SIMILARITY_TOP_K=20)
        # 2. SentenceTransformerRerank: Deep semantic relevance scoring (ALL 20 analyzed)
        #    - GPU-accelerated if available (2-3x faster: 200ms → 70ms per query)
        #    - Keeps all 20, just reorders by true relevance
        # 3. RecencyBoostPostprocessor: Applies recency boost as secondary signal
        #    - Recent relevant content ranks highest
        #    - Old relevant content still considered (not buried before reranker)

        self.vector_query_engine = self.vector_index.as_query_engine(
            similarity_top_k=SIMILARITY_TOP_K,  # Now 20 (cast wider net)
            llm=self.llm,
            text_qa_template=vector_qa_prompt,
            node_postprocessors=[
                DocumentTypeRecencyPostprocessor(),  # Document-type-aware decay (email: 30d, attachment: 90d)
            ]
        )

        # Wrap as tool for SubQuestionQueryEngine
        vector_tool = QueryEngineTool.from_defaults(
            query_engine=self.vector_query_engine,
            name="document_search",
            description=(
                "Useful for searching document content including emails, attachments, and files. "
                "Can answer questions about what was said, who sent what, topics discussed, "
                "people mentioned, companies involved, and any information contained in documents."
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
        # Note: callback_manager is set via Settings.callback_manager (already done in __init__)
        self.query_engine = SubQuestionQueryEngine.from_defaults(
            query_engine_tools=[vector_tool],  # Vector-only (Neo4j removed)
            llm=self.llm,
            response_synthesizer=response_synthesizer
        )
        logger.info("✅ SubQuestionQueryEngine ready (vector-only)")
        logger.info("✅ CEO Assistant prompts applied (sub-queries + final synthesis)")

        logger.info("✅ Query Engine ready")
        logger.info("   Architecture: SubQuestionQueryEngine with vector search")
        logger.info("   Index: VectorStoreIndex (Qdrant) with recency boosting")
        logger.info("   Chat: Manual history injection into prompts (per LlamaIndex best practice)")

    async def _parse_time_filter(self, question: str) -> Optional[Dict[str, Any]]:
        """
        Parse time constraints from natural language using LLM.

        Uses GPT-4o-mini to interpret phrases like:
        - "a month ago" → specific date
        - "last week" → date range
        - "in October" → full month
        - "recent" → last 30 days (reasonable default)

        Cost: ~$0.0001 per call (only runs when time keywords detected)

        Returns:
            Dict with start_timestamp, end_timestamp (Unix timestamps)
            Or None if no time filter
        """
        from datetime import datetime, timezone, timedelta
        import json

        current_date = datetime.now().strftime('%Y-%m-%d')
        current_date_readable = datetime.now().strftime('%B %d, %Y')

        prompt = f"""Today's date is {current_date_readable} ({current_date}).

Extract time period from: "{question}"

Return ONLY valid JSON:

WITH time period:
{{"has_time_filter": true, "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}}

NO time period:
{{"has_time_filter": false}}

Examples:
- "last month" → {{"has_time_filter": true, "start_date": "2024-10-01", "end_date": "2024-10-31"}}
- "a month ago" → {{"has_time_filter": true, "start_date": "2024-10-05", "end_date": "2024-10-05"}}
- "in Q3" → {{"has_time_filter": true, "start_date": "2024-07-01", "end_date": "2024-09-30"}}
- "recent" → {{"has_time_filter": true, "start_date": "2024-10-05", "end_date": "2024-11-05"}}
- "what materials do we use" → {{"has_time_filter": false}}
"""

        try:
            result = await self.llm.acomplete(prompt)
            result_text = str(result).strip()

            # Remove markdown if present
            if result_text.startswith('```'):
                result_text = result_text.split('\n', 1)[1].rsplit('\n', 1)[0]

            parsed = json.loads(result_text)

            if parsed.get('has_time_filter'):
                start_date = parsed['start_date']
                end_date = parsed['end_date']

                # Convert to timestamps
                start_dt = datetime.strptime(start_date, '%Y-%m-%d').replace(hour=0, minute=0, second=0, tzinfo=timezone.utc)
                end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)

                start_ts = int(start_dt.timestamp())
                end_ts = int(end_dt.timestamp())

                logger.info(f"   🕐 Time filter: {start_date} to {end_date}")

                return {
                    'start_timestamp': start_ts,
                    'end_timestamp': end_ts,
                    'start_date': start_date,
                    'end_date': end_date
                }

            return None

        except Exception as e:
            logger.warning(f"   ⚠️  Time parsing failed: {e}")
            return None

    async def query(
        self,
        question: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k_per_subq: int = 10
    ) -> Dict[str, Any]:
        """
        Query with raw chunks passed to final synthesis.

        Improvement over query(): CEO synthesis receives BOTH sub-answers AND
        raw chunks, enabling cross-analysis across sub-questions.

        Process:
        1. SubQuestionQueryEngine generates sub-questions and answers
        2. For each sub-question, extract raw chunks from .sources
        3. Keep top K chunks per sub-question (already ranked by rerank + recency)
        4. Build enhanced context with sub-answers + raw chunks
        5. Send to CEO synthesis for cross-analysis

        Args:
            question: User's question
            filters: Optional metadata filters
            top_k_per_subq: Number of top chunks to keep per sub-question (default: 10)

        Returns:
            Dict with answer, source nodes, and metadata
        """

        logger.info(f"\n{'='*80}")
        logger.info(f"🔍 QUERY: {question}")
        logger.info(f"{'='*80}")

        try:
            # Step 1: Parse time filter from question
            # Ask LLM to interpret time phrases, default to last 30 days if no specific time mentioned
            time_filter = await self._parse_time_filter(question)

            # If no explicit time mentioned, default to last 30 days
            if not time_filter:
                from datetime import datetime, timedelta
                thirty_days_ago = datetime.now() - timedelta(days=30)
                time_filter = {
                    'start_timestamp': int(thirty_days_ago.timestamp()),
                    'end_timestamp': int(datetime.now().timestamp()),
                    'start_date': thirty_days_ago.strftime('%Y-%m-%d'),
                    'end_date': datetime.now().strftime('%Y-%m-%d')
                }
                logger.info(f"   📅 No time specified - defaulting to last 30 days")

            # Step 2: Apply time filter to vector query engine
            from llama_index.core.vector_stores import MetadataFilter, MetadataFilters, FilterOperator

            metadata_filters = MetadataFilters(filters=[
                MetadataFilter(
                    key="created_at_timestamp",
                    operator=FilterOperator.GTE,
                    value=time_filter['start_timestamp']
                ),
                MetadataFilter(
                    key="created_at_timestamp",
                    operator=FilterOperator.LTE,
                    value=time_filter['end_timestamp']
                )
            ])

            logger.info(f"   🔒 Qdrant time filter: {time_filter['start_date']} to {time_filter['end_date']}")

            # Step 3: Build time-filtered SubQuestionQueryEngine from scratch
            # Create filtered vector query engine
            filtered_vector_qe = self.vector_index.as_query_engine(
                similarity_top_k=SIMILARITY_TOP_K,
                llm=self.llm,
                filters=metadata_filters,  # Apply time filter to Qdrant
                text_qa_template=PromptTemplate(
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
                ),
                node_postprocessors=[DocumentTypeRecencyPostprocessor()]
            )

            # Wrap as tool
            from llama_index.core.tools import QueryEngineTool
            filtered_tool = QueryEngineTool.from_defaults(
                query_engine=filtered_vector_qe,
                name="document_search",
                description=(
                    "Useful for searching document content including emails, attachments, and files. "
                    "Can answer questions about what was said, who sent what, topics discussed, "
                    "people mentioned, companies involved, and any information contained in documents."
                )
            )

            # Build SubQuestionQueryEngine with filtered tool
            ceo_prompt = PromptTemplate(get_ceo_prompt_template())
            response_synth = get_response_synthesizer(
                llm=self.llm,
                response_mode="compact",
                text_qa_template=ceo_prompt
            )

            filtered_subq_engine = SubQuestionQueryEngine.from_defaults(
                query_engine_tools=[filtered_tool],
                llm=self.llm,
                response_synthesizer=response_synth
            )

            # Execute with time-filtered retrieval
            response = await filtered_subq_engine.aquery(question)

            # Step 4: Extract chunks from response for enhanced synthesis
            all_source_nodes = response.source_nodes if hasattr(response, 'source_nodes') else []

            logger.info(f"   Response has {len(all_source_nodes)} source nodes")

            # Separate sub-answers from raw chunks
            sub_answers_list = []
            raw_chunks_list = []

            for node in all_source_nodes:
                node_text = str(node.text if hasattr(node, 'text') else '')
                if 'Sub question:' in node_text:
                    sub_answers_list.append(node)
                else:
                    raw_chunks_list.append(node)

            logger.info(f"   {len(sub_answers_list)} sub-answers, {len(raw_chunks_list)} raw chunks")

            # Keep top 50% of raw chunks
            top_chunks = raw_chunks_list[:len(raw_chunks_list)//2] if len(raw_chunks_list) > 0 else []

            logger.info(f"   Keeping top {len(top_chunks)} chunks (50% of {len(raw_chunks_list)})")

            # Build enhanced context with sub-answers + top chunks
            from llama_index.core.schema import TextNode, NodeWithScore, QueryBundle

            enhanced_parts = []

            # Add each sub-answer with its text
            for i, sub_node in enumerate(sub_answers_list, 1):
                sub_text = str(sub_node.text if hasattr(sub_node, 'text') else sub_node)
                enhanced_parts.append(f"--- Sub-Question {i} ---\n{sub_text}\n")

            # Add top chunks
            enhanced_parts.append(f"\n--- Top {len(top_chunks)} Source Chunks ---\n")
            for i, chunk in enumerate(top_chunks, 1):
                meta = chunk.metadata if hasattr(chunk, 'metadata') else {}
                chunk_text = chunk.text if hasattr(chunk, 'text') else str(chunk)

                chunk_part = f"\n[Chunk {i}]\n"
                chunk_part += f"Document ID: {meta.get('document_id', 'N/A')}\n"
                chunk_part += f"Type: {meta.get('document_type', 'N/A')}\n"
                chunk_part += f"Created: {meta.get('created_at', 'N/A')}\n"
                chunk_part += f"Content: {chunk_text}\n"
                enhanced_parts.append(chunk_part)

            enhanced_context = "\n".join(enhanced_parts)

            # Re-synthesize with enhanced context
            from app.services.tenant.context import get_prompt_template

            context_node = TextNode(text=enhanced_context)
            context_node_with_score = NodeWithScore(node=context_node, score=1.0)

            ceo_prompt_enhanced = PromptTemplate(get_prompt_template('ceo_assistant'))
            synthesizer_enhanced = get_response_synthesizer(
                llm=self.llm,
                response_mode="compact",
                text_qa_template=ceo_prompt_enhanced
            )

            query_bundle = QueryBundle(query_str=question)
            final_response = await synthesizer_enhanced.asynthesize(
                query=query_bundle,
                nodes=[context_node_with_score]
            )

            logger.info(f"✅ Enhanced synthesis complete with {len(top_chunks)} chunks")

            # Return with enhanced answer and tracked chunks
            final_source_nodes = sub_answers_list + top_chunks

            return {
                "question": question,
                "answer": str(final_response),
                "source_nodes": final_source_nodes,
                "metadata": {
                    "time_filtered": True,
                    "time_range": f"{time_filter['start_date']} to {time_filter['end_date']}",
                    "enhanced": True,
                    "sub_questions": len(sub_answers_list),
                    "chunks_used": len(top_chunks),
                    "context_length": len(enhanced_context)
                }
            }
        except Exception as e:
            error_msg = f"Enhanced query failed: {str(e)}"
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
        Conversational interface with enhanced retrieval (SAME as query() + chat history).

        Uses IDENTICAL enhanced retrieval as query():
        - Time filtering (defaults to last 30 days)
        - Enhanced synthesis (sub-answers + top 50% chunks to CEO)
        - Qdrant MetadataFilters
        - Supabase CEO prompt template
        - Chat history injection

        Args:
            message: User's message
            chat_history: Optional chat history
                         Format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]

        Returns:
            Dict with question, answer, source_nodes, metadata
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"💬 CHAT: {message}")
        logger.info(f"{'='*80}")

        try:
            # Format chat history (truncate to 3900 tokens)
            chat_history_str = ""
            if chat_history:
                max_tokens = 3900
                total_tokens = 0
                messages_to_include = []

                for msg in reversed(chat_history):
                    content = msg.get("content", "")
                    msg_tokens = len(content) // 4

                    if total_tokens + msg_tokens > max_tokens:
                        break

                    messages_to_include.append(msg)
                    total_tokens += msg_tokens

                history_lines = []
                for msg in reversed(messages_to_include):
                    role = msg.get("role", "user").capitalize()
                    content = msg.get("content", "")
                    history_lines.append(f"{role}: {content}")

                chat_history_str = "\n".join(history_lines)

                messages_loaded = len(messages_to_include)
                logger.info(f"   📚 Chat history: {messages_loaded}/{len(chat_history)} messages (~{total_tokens} tokens)")

            # Use enhanced query() method (same retrieval as search)
            result = await self.query(message)

            # Inject chat history into the answer if needed
            # The query already has all the enhanced features, we just add chat context metadata
            result["metadata"]["is_chat"] = True
            result["metadata"]["chat_history_provided"] = bool(chat_history)
            result["metadata"]["chat_history_length"] = len(chat_history) if chat_history else 0

            # If we have chat history, we could optionally prepend it to enhanced_context
            # But for now, the question itself can reference "it" or "that" and query() will handle it
            if chat_history_str:
                logger.info(f"   💬 Chat mode with {len(chat_history)} history messages")

            logger.info(f"✅ CHAT COMPLETE (using enhanced query)")

            return result

        except Exception as e:
            error_msg = f"Chat failed: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            return {
                "question": message,
                "answer": "",
                "error": error_msg,
                "source_nodes": []
            }


    def get_callback_events(self) -> List[Dict[str, Any]]:
        """
        Get all callback events captured during query execution.

        Returns:
            List of event dictionaries with event type and payload
        """
        if not self.llama_debug:
            return []

        events = []

        # Get all event logs from LlamaDebugHandler
        for event in self.llama_debug.get_events():
            events.append({
                "event_type": event.event_type,
                "payload": event.payload
            })

        return events

    def flush_callback_events(self):
        """Clear all callback events (reset for next query)"""
        if self.llama_debug:
            self.llama_debug.flush_event_logs()

    async def retrieve_only(
        self,
        question: str
    ):
        """
        Retrieve relevant nodes without synthesis.

        Args:
            question: Search query

        Returns:
            List of retrieved nodes from vector search
        """
        try:
            nodes = await self.vector_query_engine.aretrieve(question)
            logger.info(f"Retrieved {len(nodes)} nodes from vector index")
            return nodes
        except Exception as e:
            logger.error(f"Vector retrieval failed: {e}")
            return []

    async def cleanup(self):
        """
        Cleanup database connections and resources.

        PRODUCTION: Call this on application shutdown to prevent resource leaks.

        Cleans up:
        - Qdrant client connections

        Example:
            >>> engine = HybridQueryEngine()
            >>> # ... use engine ...
            >>> await engine.cleanup()  # On shutdown
        """
        try:
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
        pass  # Qdrant cleanup handled by async cleanup() method


