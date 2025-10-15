"""
Simple script to connect and read contents from Qdrant and Neo4j
"""
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from neo4j import GraphDatabase

load_dotenv()

def check_qdrant():
    """Connect to Qdrant and read collection contents"""
    print("\n" + "="*80)
    print("QDRANT CLOUD - CHECKING CONNECTION AND CONTENTS")
    print("="*80)

    try:
        client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY")
        )

        collection_name = os.getenv("QDRANT_COLLECTION_NAME", "cortex_documents")

        # Check if collection exists
        collections = client.get_collections()
        print(f"\n📊 Available collections: {[c.name for c in collections.collections]}")

        # Get collection info
        collection_info = client.get_collection(collection_name)
        print(f"\n✅ Collection '{collection_name}' found!")
        print(f"   Points count: {collection_info.points_count}")
        print(f"   Vector size: {collection_info.config.params.vectors.size}")

        # Get some sample points
        if collection_info.points_count > 0:
            print("\n📄 Sample points (first 5):")
            points = client.scroll(
                collection_name=collection_name,
                limit=5,
                with_payload=True,
                with_vectors=False
            )

            for i, point in enumerate(points[0], 1):
                print(f"\n   Point {i}:")
                print(f"   ID: {point.id}")
                if point.payload:
                    print(f"   Document: {point.payload.get('document_name', 'N/A')}")
                    print(f"   Source: {point.payload.get('source', 'N/A')}")
                    print(f"   Type: {point.payload.get('document_type', 'N/A')}")
                    print(f"   Episode ID: {point.payload.get('graphiti_episode_id', 'N/A')}")
                    content = point.payload.get('content', '')
                    print(f"   Content preview: {content[:100]}...")
        else:
            print("\n⚠️  Collection is empty - no documents ingested yet")

    except Exception as e:
        print(f"\n❌ Error connecting to Qdrant: {e}")
        return False

    return True


def check_neo4j():
    """Connect to Neo4j and read graph contents"""
    print("\n" + "="*80)
    print("NEO4J - CHECKING CONNECTION AND CONTENTS")
    print("="*80)

    try:
        driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI"),
            auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
        )

        with driver.session() as session:
            # Check connection
            result = session.run("RETURN 1 as test")
            print(f"\n✅ Connected to Neo4j successfully!")

            # Count nodes
            result = session.run("MATCH (n) RETURN count(n) as node_count")
            node_count = result.single()["node_count"]
            print(f"\n📊 Total nodes: {node_count}")

            # Count relationships
            result = session.run("MATCH ()-[r]->() RETURN count(r) as rel_count")
            rel_count = result.single()["rel_count"]
            print(f"📊 Total relationships: {rel_count}")

            # Get node labels
            result = session.run("CALL db.labels()")
            labels = [record["label"] for record in result]
            print(f"\n🏷️  Node labels: {labels}")

            # Get relationship types
            result = session.run("CALL db.relationshipTypes()")
            rel_types = [record["relationshipType"] for record in result]
            print(f"🔗 Relationship types: {rel_types}")

            # Get sample episodes (Graphiti stores documents as episodes)
            if node_count > 0:
                print("\n📄 Sample episodes (first 5):")
                result = session.run("""
                    MATCH (e:EpisodicNode)
                    RETURN e.name as name, e.created_at as created_at, e.source_description as source
                    LIMIT 5
                """)

                for i, record in enumerate(result, 1):
                    print(f"\n   Episode {i}:")
                    print(f"   Name: {record['name']}")
                    print(f"   Source: {record['source']}")
                    print(f"   Created: {record['created_at']}")

                # Get sample entities
                print("\n👥 Sample entities (first 5):")
                result = session.run("""
                    MATCH (n:Entity)
                    RETURN n.name as name, labels(n) as labels
                    LIMIT 5
                """)

                for i, record in enumerate(result, 1):
                    print(f"\n   Entity {i}:")
                    print(f"   Name: {record['name']}")
                    print(f"   Labels: {record['labels']}")
            else:
                print("\n⚠️  Database is empty - no documents ingested yet")

        driver.close()

    except Exception as e:
        print(f"\n❌ Error connecting to Neo4j: {e}")
        return False

    return True


if __name__ == "__main__":
    print("\n🔍 CHECKING DATABASE CONNECTIONS AND CONTENTS\n")

    qdrant_ok = check_qdrant()
    neo4j_ok = check_neo4j()

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Qdrant: {'✅ Connected' if qdrant_ok else '❌ Failed'}")
    print(f"Neo4j: {'✅ Connected' if neo4j_ok else '❌ Failed'}")
    print()
