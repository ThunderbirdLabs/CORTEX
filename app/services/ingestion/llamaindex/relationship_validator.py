"""
Relationship Validator - LLM-based Quality Filter for Knowledge Graph

OVERVIEW:
========
Validates relationships and entities extracted by SchemaLLMPathExtractor to ensure
only high-quality, actionable knowledge enters the graph.

DUAL PURPOSE:
============
1. Prevent false relationships (entities mentioned together but not connected)
2. Filter low-insight entities (generic terms like "molding", "plastic", "meeting")

WHY THIS MATTERS:
================
Quality > Quantity for knowledge graphs:
- Vector store handles generic semantic search
- Knowledge graph provides PRECISE, ACTIONABLE business intelligence
- Generic entities pollute the graph without adding insight
- False relationships lead to wrong business decisions

Example Scenarios:
------------------
✅ KEEP: "Unit Industries Inc. (COMPANY) -SUPPLIES_TO-> TriStar (COMPANY)"
   → High-value supply chain intelligence

❌ REJECT: "TriStar (COMPANY) -SUPPLIES-> Molding (MATERIAL)"
   → "Molding" is too generic, no actionable insight

✅ KEEP: "John Smith (PERSON) -WORKS_FOR-> Acme Industries (COMPANY)"
   → Clear organizational structure

❌ REJECT: "Sarah (PERSON) -HAS_ROLE-> Manager (ROLE)"
   → "Manager" too generic without context

ARCHITECTURE:
============
1. SchemaLLMPathExtractor extracts entities + relationships
2. RelationshipValidator verifies EACH relationship against chunk text
3. Only validated relationships inserted into Neo4j

Zero Hallucination Design:
- LLM only answers YES/NO (never generates data)
- Python filters relationships (simple boolean logic)
- Original SchemaLLMPathExtractor objects never modified

COST & PERFORMANCE:
==================
- Model: gpt-4o-mini ($0.15/1M tokens)
- Cost per validation: ~$0.0000225 (~0.002¢)
- Typical document: 50 validations = $0.001125 (~0.1¢)
- Latency: ~200ms per validation (can batch for speed)
"""

import logging
from typing import List
from llama_index.core.llms import LLM
from llama_index.core.graph_stores.types import EntityNode, Relation

logger = logging.getLogger(__name__)


class RelationshipValidator:
    """
    Quality filter for knowledge graph relationships and entities using LLM.

    Design Principles:
    - Read-only: Never modifies SchemaLLMPathExtractor objects
    - Boolean output: LLM returns YES/NO, Python does filtering
    - Quality-focused: Keeps high-insight relationships, rejects generic/low-value entities
    - Dual validation: Checks both relationship accuracy AND entity quality
    - Conservative: When uncertain about quality, reject
    """

    def __init__(self, llm: LLM):
        """
        Initialize validator with LLM.

        Args:
            llm: LlamaIndex LLM instance (typically gpt-4o-mini for cost efficiency)
        """
        self.llm = llm
        logger.info("✅ RelationshipValidator initialized")

    async def validate_relationship(
        self,
        relation: Relation,
        source: EntityNode,
        target: EntityNode,
        chunk_text: str
    ) -> bool:
        """
        Validate a single relationship against source text.

        Args:
            relation: Relation object from SchemaLLMPathExtractor (READ-ONLY)
            source: Source entity node (READ-ONLY)
            target: Target entity node (READ-ONLY)
            chunk_text: Original text where relationship was extracted

        Returns:
            bool: True if relationship is explicitly supported by text, False otherwise

        Design Notes:
        - Objects are NEVER modified (read-only validation)
        - LLM only returns YES/NO (no data generation)
        - Validation is strict (explicit evidence required)
        """

        # Use full chunk text for validation (up to 1200 chars for context)
        # Provides complete context for accurate relationship validation
        text_preview = chunk_text[:1200]

        # Quality-focused validation prompt with business context
        prompt = f"""You are building an enterprise knowledge graph that maps accurate, high-quality relationships inside a business.

MISSION:
This knowledge graph reveals unique connections between documents, emails, messages, and raw data from multiple business apps. Your role is to ensure only actionable, specific relationships enter the graph - relationships that drive business decisions forward by showing what is truly happening across the organization.

SOURCE DATA:
You're analyzing real business communications: emails, documents, chat messages, invoices, purchase orders, and technical specifications. These contain both high-value intelligence (supply chain relationships, organizational structure) and low-value noise (generic terms, vague mentions).

TEXT:
{text_preview}

RELATIONSHIP TO EVALUATE:
{source.name} ({source.label}) -{relation.label}-> {target.name} ({target.label})

QUALITY CRITERIA:

REJECT if entities are too generic or provide no actionable insight:
- Generic materials: "molding", "plastic", "resin" (without specific grades/types)
- Generic roles: "manager", "engineer" (without full context)
- Generic actions: "meeting", "call", "email"
- Vague descriptors that don't identify specific business entities

ACCEPT high-value business relationships that reveal true operations:
- Company-to-company: SUPPLIES_TO, WORKS_WITH (supply chain intelligence)
- Person-to-company: WORKS_FOR (organizational structure)
- Specific materials: "polycarbonate PC-1000", "ABS resin grade 5" (actionable specs)
- Named roles: "VP of Sales", "Quality Engineer" (specific positions)
- Purchase orders with specific companies or materials (transaction tracking)

VALIDATION:
- ACCEPT if explicitly stated or strongly implied in the text
- REJECT if entities are just mentioned together without clear relationship
- When uncertain about business value, REJECT (quality > quantity)

Answer only: YES or NO"""

        try:
            response = await self.llm.acomplete(prompt)
            answer = response.text.strip().upper()

            # Simple boolean check - no parsing, no object modification
            is_valid = "YES" in answer

            # Log validation result for monitoring (Render logs)
            if is_valid:
                logger.info(
                    f"   ✅ APPROVED: {source.name} -{relation.label}-> {target.name}"
                )
            else:
                logger.info(
                    f"   ❌ REJECTED: {source.name} -{relation.label}-> {target.name} "
                    f"(LLM: {answer})"
                )

            return is_valid

        except Exception as e:
            logger.info(
                f"   ⚠️  VALIDATION ERROR: {source.name} -{relation.label}-> {target.name} - {e}"
            )
            # On error, reject (conservative approach)
            return False

    async def validate_relationships(
        self,
        relations: List[Relation],
        entities: List[EntityNode],
        chunk_text: str
    ) -> List[Relation]:
        """
        Validate multiple relationships from a single chunk.

        Args:
            relations: List of Relation objects from SchemaLLMPathExtractor
            entities: List of EntityNode objects (to lookup source/target)
            chunk_text: Original text where relationships were extracted

        Returns:
            List[Relation]: Filtered list containing ONLY validated relationships
                           (original Relation objects, unmodified)

        Design Notes:
        - Returns ORIGINAL Relation objects (preserves SchemaLLMPathExtractor formatting)
        - Simple filtering logic (no object modification)
        - Logs rejection stats for monitoring
        """

        if not relations:
            return []

        validated_relations = []

        for relation in relations:
            # Find source and target entities
            try:
                source = next(e for e in entities if e.id == relation.source_id)
                target = next(e for e in entities if e.id == relation.target_id)
            except StopIteration:
                logger.info(
                    f"   ⚠️  Skipping relationship with missing entity: "
                    f"{relation.source_id} -> {relation.target_id}"
                )
                continue

            # Validate relationship
            is_valid = await self.validate_relationship(
                relation=relation,
                source=source,
                target=target,
                chunk_text=chunk_text
            )

            if is_valid:
                validated_relations.append(relation)  # Original object, unmodified

        # Log validation stats (visible in Render logs)
        rejected_count = len(relations) - len(validated_relations)
        approval_rate = (len(validated_relations) / len(relations) * 100) if relations else 0

        if rejected_count > 0:
            logger.info(
                f"   🔍 VALIDATION SUMMARY: {len(validated_relations)}/{len(relations)} approved "
                f"({approval_rate:.0f}%), {rejected_count} rejected"
            )
        else:
            logger.info(
                f"   🔍 VALIDATION SUMMARY: All {len(validated_relations)} relationships approved"
            )

        return validated_relations
