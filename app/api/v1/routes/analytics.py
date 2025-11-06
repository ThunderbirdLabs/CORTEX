"""
Analytics API endpoints
Provides business intelligence data for dashboard widgets
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from supabase import Client
from collections import defaultdict

from app.core.security import get_current_user_id
from app.core.dependencies import get_supabase, query_engine

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/entities/trending")
async def get_trending_entities(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=10, ge=1, le=50),
    user_id: str = Depends(get_current_user_id),
):
    """
    Get trending people and companies based on mentions in Neo4j knowledge graph.

    Returns:
    - Top people by mention count
    - Top companies by mention count
    - Trend indicators (if available)
    """
    try:
        logger.info(f"📈 Fetching trending entities for user {user_id}, last {days} days")

        # Calculate timestamp for filtering
        cutoff_timestamp = int((datetime.utcnow() - timedelta(days=days)).timestamp())

        # Access Neo4j via query engine
        if not query_engine or not hasattr(query_engine, 'neo4j_graph_store'):
            logger.warning("Query engine not initialized, returning empty data")
            return {
                "people": [],
                "companies": [],
                "date_range_days": days
            }

        neo4j_driver = query_engine.neo4j_graph_store._driver

        with neo4j_driver.session() as session:
            # Query for top people
            people_query = """
            MATCH (c:Chunk)-[r]->(p:PERSON)
            WHERE c.tenant_id = $tenant_id
              AND c.created_at_timestamp >= $cutoff_timestamp
            WITH p.name AS name, count(*) AS mentions
            RETURN name, mentions
            ORDER BY mentions DESC
            LIMIT $limit
            """

            people_result = session.run(
                people_query,
                tenant_id=user_id,
                cutoff_timestamp=cutoff_timestamp,
                limit=limit
            )

            people = [
                {
                    "name": record["name"],
                    "mentions": record["mentions"],
                    "type": "PERSON",
                    "trend": None  # Could calculate week-over-week trend
                }
                for record in people_result
            ]

            # Query for top companies
            companies_query = """
            MATCH (c:Chunk)-[r]->(comp:COMPANY)
            WHERE c.tenant_id = $tenant_id
              AND c.created_at_timestamp >= $cutoff_timestamp
            WITH comp.name AS name, count(*) AS mentions
            RETURN name, mentions
            ORDER BY mentions DESC
            LIMIT $limit
            """

            companies_result = session.run(
                companies_query,
                tenant_id=user_id,
                cutoff_timestamp=cutoff_timestamp,
                limit=limit
            )

            companies = [
                {
                    "name": record["name"],
                    "mentions": record["mentions"],
                    "type": "COMPANY",
                    "trend": None
                }
                for record in companies_result
            ]

        logger.info(f"Found {len(people)} people, {len(companies)} companies")

        return {
            "people": people,
            "companies": companies,
            "date_range_days": days
        }

    except Exception as e:
        logger.error(f"❌ Error fetching trending entities: {e}")
        # Return empty data instead of failing
        return {
            "people": [],
            "companies": [],
            "date_range_days": days,
            "error": str(e)
        }


@router.get("/communication/patterns")
async def get_communication_patterns(
    days: int = Query(default=30, ge=1, le=365),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Analyze email communication patterns.

    Returns:
    - Top email senders
    - Top email recipients
    - Communication edges (who emails whom)
    - Response time metrics
    """
    try:
        logger.info(f"📧 Analyzing communication patterns for user {user_id}, last {days} days")

        start_date = datetime.utcnow() - timedelta(days=days)

        # Fetch all emails in date range
        response = supabase.table("documents")\
            .select("*")\
            .eq("tenant_id", user_id)\
            .in_("source", ["gmail", "outlook"])\
            .gte("source_created_at", start_date.isoformat())\
            .execute()

        emails = response.data or []
        logger.info(f"Analyzing {len(emails)} emails")

        # Aggregate sender/recipient statistics
        sender_stats = defaultdict(lambda: {"count": 0, "contacts": set()})
        recipient_stats = defaultdict(lambda: {"count": 0, "contacts": set()})
        edges = defaultdict(int)  # (from, to) -> count

        for email in emails:
            metadata = email.get("metadata", {})
            sender = metadata.get("sender_name") or metadata.get("sender_address", "Unknown")
            recipients = metadata.get("to_addresses", [])

            if isinstance(recipients, str):
                recipients = [recipients]

            # Track sender
            sender_stats[sender]["count"] += 1
            for recipient in recipients:
                sender_stats[sender]["contacts"].add(recipient)
                edges[(sender, recipient)] += 1

            # Track recipients
            for recipient in recipients:
                recipient_stats[recipient]["count"] += 1
                recipient_stats[recipient]["contacts"].add(sender)

        # Convert to sorted lists
        top_senders = sorted(
            [
                {
                    "name": name,
                    "email_count": stats["count"],
                    "unique_contacts": len(stats["contacts"])
                }
                for name, stats in sender_stats.items()
            ],
            key=lambda x: x["email_count"],
            reverse=True
        )[:10]

        top_recipients = sorted(
            [
                {
                    "name": name,
                    "email_count": stats["count"],
                    "unique_contacts": len(stats["contacts"])
                }
                for name, stats in recipient_stats.items()
            ],
            key=lambda x: x["email_count"],
            reverse=True
        )[:10]

        # Top edges
        top_edges = sorted(
            [
                {
                    "from": edge[0],
                    "to": edge[1],
                    "count": count
                }
                for edge, count in edges.items()
            ],
            key=lambda x: x["count"],
            reverse=True
        )[:10]

        return {
            "top_senders": top_senders,
            "top_recipients": top_recipients,
            "edges": top_edges,
            "total_emails": len(emails),
            "date_range_days": days
        }

    except Exception as e:
        logger.error(f"❌ Error analyzing communication patterns: {e}")
        return {
            "top_senders": [],
            "top_recipients": [],
            "edges": [],
            "total_emails": 0,
            "date_range_days": days,
            "error": str(e)
        }


@router.get("/deals/momentum")
async def get_deal_momentum(
    days: int = Query(default=30, ge=1, le=365),
    user_id: str = Depends(get_current_user_id),
):
    """
    Track deal momentum based on PURCHASE_ORDER entity mentions.

    Returns:
    - Hot deals (increasing mentions)
    - Warm deals (stable mentions)
    - Cold deals (decreasing/stalled mentions)
    """
    try:
        logger.info(f"🔥 Tracking deal momentum for user {user_id}, last {days} days")

        cutoff_timestamp = int((datetime.utcnow() - timedelta(days=days)).timestamp())
        week_ago_timestamp = int((datetime.utcnow() - timedelta(days=7)).timestamp())

        # Access Neo4j via query engine
        if not query_engine or not hasattr(query_engine, 'neo4j_graph_store'):
            logger.warning("Query engine not initialized, returning empty data")
            return {
                "deals": [],
                "date_range_days": days
            }

        neo4j_driver = query_engine.neo4j_graph_store._driver

        with neo4j_driver.session() as session:
            # Query for purchase orders with mention statistics
            query = """
            MATCH (c:Chunk)-[r]->(po:PURCHASE_ORDER)
            WHERE c.tenant_id = $tenant_id
              AND c.created_at_timestamp >= $cutoff_timestamp
            WITH po.name AS deal_name,
                 collect(c.created_at_timestamp) AS timestamps,
                 count(*) AS total_mentions
            WITH deal_name,
                 total_mentions,
                 [t IN timestamps WHERE t >= $week_ago] AS recent_timestamps,
                 [t IN timestamps WHERE t < $week_ago AND t >= ($week_ago - 604800)] AS prev_week_timestamps,
                 max([t IN timestamps | t]) AS last_mention_timestamp
            RETURN deal_name,
                   total_mentions,
                   size(recent_timestamps) AS touchpoints_this_week,
                   size(prev_week_timestamps) AS touchpoints_last_week,
                   last_mention_timestamp
            ORDER BY touchpoints_this_week DESC
            """

            result = session.run(
                query,
                tenant_id=user_id,
                cutoff_timestamp=cutoff_timestamp,
                week_ago=week_ago_timestamp
            )

            deals = []
            now = datetime.utcnow().timestamp()

            for record in result:
                this_week = record["touchpoints_this_week"]
                last_week = record["touchpoints_last_week"]
                last_mention = record["last_mention_timestamp"]

                # Calculate days since last mention
                days_since = int((now - last_mention) / 86400) if last_mention else 999

                # Determine status and trend
                if this_week >= 5 and days_since <= 2:
                    status = "hot"
                elif days_since > 7:
                    status = "cold"
                else:
                    status = "warm"

                # Calculate velocity
                if last_week > 0:
                    velocity_percent = int(((this_week - last_week) / last_week) * 100)
                    trend = "up" if velocity_percent > 20 else "down" if velocity_percent < -20 else "stable"
                else:
                    velocity_percent = 0
                    trend = "up" if this_week > 0 else "stable"

                deals.append({
                    "name": record["deal_name"],
                    "touchpoints_this_week": this_week,
                    "touchpoints_last_week": last_week,
                    "last_mention_date": datetime.fromtimestamp(last_mention).isoformat() if last_mention else None,
                    "days_since_last_mention": days_since,
                    "status": status,
                    "trend": trend,
                    "velocity_percent": velocity_percent
                })

        logger.info(f"Found {len(deals)} active deals")

        return {
            "deals": deals,
            "date_range_days": days
        }

    except Exception as e:
        logger.error(f"❌ Error tracking deal momentum: {e}")
        return {
            "deals": [],
            "date_range_days": days,
            "error": str(e)
        }


@router.get("/sentiment/analysis")
async def get_sentiment_analysis(
    days: int = Query(default=30, ge=1, le=365),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Analyze sentiment from communications using keyword detection.

    Returns:
    - Positive signals (praise, success keywords)
    - Negative signals (problems, delays, issues)
    - Opportunity signals (expansion, new projects)
    - Risk signals (cancellation, delays, quality issues)
    """
    try:
        logger.info(f"😊 Analyzing sentiment for user {user_id}, last {days} days")

        start_date = datetime.utcnow() - timedelta(days=days)

        # Fetch all documents (emails + docs) in date range
        response = supabase.table("documents")\
            .select("content, metadata")\
            .eq("tenant_id", user_id)\
            .gte("source_created_at", start_date.isoformat())\
            .execute()

        documents = response.data or []
        logger.info(f"Analyzing sentiment in {len(documents)} documents")

        # Define keyword categories
        positive_keywords = ["excellent", "great work", "thank you", "approved", "success", "congratulations", "well done"]
        negative_keywords = ["delay", "problem", "issue", "concern", "disappointed", "urgent", "failed"]
        opportunity_keywords = ["expansion", "new project", "increased order", "growth", "opportunity", "partnership"]
        risk_keywords = ["cancel", "terminate", "quality issue", "behind schedule", "overbudget", "complaint"]

        # Count keyword occurrences
        alerts = []

        def count_keyword(docs, keyword, alert_type):
            count = 0
            for doc in docs:
                content = (doc.get("content") or "").lower()
                count += content.count(keyword.lower())

            if count > 0:
                return {
                    "type": alert_type,
                    "keyword": keyword,
                    "count": count,
                    "severity": "high" if count > 5 else "medium" if count > 2 else "low"
                }
            return None

        # Opportunity alerts (top priority)
        for keyword in opportunity_keywords:
            alert = count_keyword(documents, keyword, "opportunity")
            if alert:
                alert["context"] = f"Potential business opportunity detected"
                alerts.append(alert)

        # Risk alerts
        for keyword in risk_keywords:
            alert = count_keyword(documents, keyword, "risk")
            if alert:
                alert["context"] = f"Requires immediate attention"
                alerts.append(alert)

        # Positive signals
        for keyword in positive_keywords:
            alert = count_keyword(documents, keyword, "positive")
            if alert:
                alert["context"] = f"Customer satisfaction indicator"
                alerts.append(alert)

        # Negative signals
        for keyword in negative_keywords:
            alert = count_keyword(documents, keyword, "negative")
            if alert:
                alert["context"] = f"May require follow-up"
                alerts.append(alert)

        # Sort by count (most mentions first)
        alerts.sort(key=lambda x: x["count"], reverse=True)

        return {
            "alerts": alerts[:20],  # Top 20 alerts
            "total_documents_analyzed": len(documents),
            "date_range_days": days
        }

    except Exception as e:
        logger.error(f"❌ Error analyzing sentiment: {e}")
        return {
            "alerts": [],
            "total_documents_analyzed": 0,
            "date_range_days": days,
            "error": str(e)
        }


@router.get("/relationships/network")
async def get_relationship_network(
    user_id: str = Depends(get_current_user_id),
):
    """
    Get relationship network from Neo4j knowledge graph.

    Returns:
    - People and their relationships
    - Company connections
    - Collaboration patterns
    """
    try:
        logger.info(f"🕸️  Fetching relationship network for user {user_id}")

        # Access Neo4j via query engine
        if not query_engine or not hasattr(query_engine, 'neo4j_graph_store'):
            logger.warning("Query engine not initialized, returning empty data")
            return {
                "relationships": [],
                "node_count": 0,
                "edge_count": 0
            }

        neo4j_driver = query_engine.neo4j_graph_store._driver

        with neo4j_driver.session() as session:
            # Query for WORKS_FOR relationships
            query = """
            MATCH (p:PERSON)-[:WORKS_FOR]->(c:COMPANY)
            WHERE p.tenant_id = $tenant_id
            RETURN p.name AS person, c.name AS company
            LIMIT 50
            """

            result = session.run(query, tenant_id=user_id)

            relationships = [
                {
                    "from": record["person"],
                    "to": record["company"],
                    "type": "WORKS_FOR"
                }
                for record in result
            ]

        return {
            "relationships": relationships,
            "node_count": len(set([r["from"] for r in relationships] + [r["to"] for r in relationships])),
            "edge_count": len(relationships)
        }

    except Exception as e:
        logger.error(f"❌ Error fetching relationship network: {e}")
        return {
            "relationships": [],
            "node_count": 0,
            "edge_count": 0,
            "error": str(e)
        }
