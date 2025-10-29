"""
Relationship Validator - LLM-based Verification for Knowledge Graph Quality

OVERVIEW:
========
Validates relationships extracted by SchemaLLMPathExtractor against source text
to prevent false relationships from entering the knowledge graph.

WHY THIS MATTERS:
================
False relationships are worse than missing relationships:
- Vector store handles semantic search (no relationships needed)
- Knowledge graph provides PRECISE entity connections
- One false relationship → wrong business decision

Example False Relationship:
---------------------------
Text: "John from Acme called about the order for Superior Mold"

SchemaLLMPathExtractor might extract:
- John WORKS_FOR Superior Mold ❌ (both mentioned, but incorrect)

Validator checks:
- Is "John WORKS_FOR Superior Mold" explicitly stated? → NO → Reject

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
    Validates knowledge graph relationships against source text using LLM.

    Design Principles:
    - Read-only: Never modifies SchemaLLMPathExtractor objects
    - Boolean output: LLM returns YES/NO, Python does filtering
    - Explicit evidence: Relationship must be clearly stated in text
    - False negative tolerance: Better to miss a true relationship than accept a false one
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

        # Truncate text to reasonable length (500 chars = ~125 tokens)
        # Most relationships are evident in local context
        text_preview = chunk_text[:500]

        # Simple, strict prompt - requires explicit evidence
        prompt = f"""Does this text EXPLICITLY support the relationship?

TEXT:
{text_preview}

RELATIONSHIP:
{source.name} -{relation.label}-> {target.name}

Rules:
- Answer YES only if the relationship is clearly stated or strongly implied
- Answer NO if entities are just mentioned together without clear relationship
- Answer NO if you're uncertain

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
