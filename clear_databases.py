"""
Clear both Qdrant and Neo4j databases for fresh testing
"""
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from neo4j import GraphDatabase

load_dotenv()

# Qdrant
print("🗑️  Clearing Qdrant...")
qdrant_client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)

collection_name = os.getenv("QDRANT_COLLECTION_NAME", "cortex_documents")

try:
    qdrant_client.delete_collection(collection_name)
    print(f"✅ Deleted Qdrant collection: {collection_name}")
except Exception as e:
    print(f"⚠️  Collection doesn't exist or already deleted: {e}")

# Recreate collection
try:
    qdrant_client.create_collection(
        collection_name=collection_name,
        vectors_config={"size": 1536, "distance": "Cosine"}
    )
    print(f"✅ Recreated Qdrant collection: {collection_name}")
except Exception as e:
    print(f"❌ Failed to recreate collection: {e}")

# Neo4j
print("\n🗑️  Clearing Neo4j...")
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))  # Fixed: NEO4J_USER not NEO4J_USERNAME
)

with driver.session(database="neo4j") as session:
    # Delete all nodes and relationships
    result = session.run("MATCH (n) DETACH DELETE n")
    print("✅ Deleted all Neo4j nodes and relationships")

    # Verify empty
    result = session.run("MATCH (n) RETURN count(n) as count")
    count = result.single()["count"]
    print(f"✅ Neo4j verification: {count} nodes remaining")

driver.close()

print("\n✅ Both databases cleared and ready for testing!")
