"""Check what relationship types exist in Neo4j"""
import asyncio
from dotenv import load_dotenv
load_dotenv()

from app.services.ingestion.llamaindex import UniversalIngestionPipeline

async def main():
    pipeline = UniversalIngestionPipeline()
    stats = pipeline.get_stats()

    print(f"Neo4j nodes: {stats.get('neo4j_nodes', 0)}")
    print(f"Neo4j relationships: {stats.get('neo4j_relationships', 0)}")

    # Get relationship type breakdown
    with pipeline.graph_store._driver.session(database=pipeline.graph_store._database) as session:
        result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) as rel_type, count(*) as count
            ORDER BY count DESC
        """)

        print("\nRelationship types:")
        for record in result:
            print(f"  {record['rel_type']}: {record['count']}")

asyncio.run(main())
