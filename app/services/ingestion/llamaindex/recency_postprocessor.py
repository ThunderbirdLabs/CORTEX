"""
Recency Boost Postprocessor for LlamaIndex

Applies exponential decay to favor recent documents over old ones.
Prevents stale data from polluting query results over time.

Research: Based on LlamaIndex community best practices (GitHub Discussion #8446)
Formula: score * (0.5 ** (age_days / decay_days))
"""

from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle
from datetime import datetime
from typing import List, Optional
from pydantic import Field
import logging

logger = logging.getLogger(__name__)


class RecencyBoostPostprocessor(BaseNodePostprocessor):
    """
    Boost recent documents with exponential decay.

    Uses exponential decay to favor recent documents:
    - Documents from today: 100% score
    - Documents from decay_days ago: 50% score
    - Documents from 2*decay_days ago: 25% score

    Example:
        With decay_days=90:
        - 30 days old: score * 0.79 (79% of original)
        - 90 days old: score * 0.50 (50% of original)
        - 180 days old: score * 0.25 (25% of original)
        - 365 days old: score * 0.06 (6% of original)

    This prevents old data (e.g., "John manages Acme") from ranking higher
    than recent data (e.g., "Mary now manages Acme") when both have similar
    semantic similarity scores.
    """

    # Pydantic field declarations
    decay_days: int = Field(
        default=90,
        description="Number of days for score to decay to 50%"
    )
    timestamp_key: str = Field(
        default="created_at_timestamp",
        description="Metadata key containing Unix timestamp"
    )

    def __init__(
        self,
        decay_days: int = 90,
        timestamp_key: str = "created_at_timestamp",
        **kwargs
    ):
        """
        Initialize RecencyBoostPostprocessor.

        Args:
            decay_days: Number of days for score to decay to 50%.
                       Smaller = more aggressive decay (favor very recent).
                       Larger = gentler decay (consider older docs).
                       Recommended: 90 for business data, 30 for news/social.
            timestamp_key: Metadata key containing Unix timestamp.
                          Default: "created_at_timestamp"
        """
        super().__init__(decay_days=decay_days, timestamp_key=timestamp_key, **kwargs)
        logger.info(f"RecencyBoostPostprocessor initialized (decay_days={decay_days})")

    def _postprocess_nodes(
        self,
        nodes: List[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None
    ) -> List[NodeWithScore]:
        """
        Apply recency boost to node scores.

        Args:
            nodes: List of nodes with similarity scores
            query_bundle: Optional query information (unused)

        Returns:
            Nodes with boosted scores, re-sorted by new scores
        """
        if not nodes:
            return nodes

        now_ts = datetime.now().timestamp()
        boosted_count = 0
        skipped_count = 0

        for node in nodes:
            # Get document timestamp from metadata
            created_at_ts = node.node.metadata.get(self.timestamp_key)

            if created_at_ts:
                # Calculate age in days
                age_seconds = now_ts - created_at_ts
                age_days = age_seconds / (60 * 60 * 24)

                # Exponential decay: 100% at 0 days, 50% at decay_days
                # Formula: 0.5 ** (age_days / decay_days)
                recency_score = 0.5 ** (age_days / self.decay_days)

                # Boost original score with recency
                original_score = node.score
                node.score = node.score * recency_score

                boosted_count += 1

                # Log significant boosts/penalties
                if recency_score < 0.3 or age_days < 7:
                    logger.debug(
                        f"Recency boost applied: age={age_days:.1f} days, "
                        f"original_score={original_score:.4f}, "
                        f"recency_score={recency_score:.4f}, "
                        f"final_score={node.score:.4f}"
                    )
            else:
                # No timestamp = no boost (keep original score)
                skipped_count += 1

        # Re-sort by new scores (highest first)
        nodes.sort(key=lambda x: x.score, reverse=True)

        logger.info(
            f"RecencyBoost: Boosted {boosted_count} nodes, "
            f"skipped {skipped_count} (no timestamp)"
        )

        return nodes
