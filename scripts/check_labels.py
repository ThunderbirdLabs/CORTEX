"""Quick check of Neo4j labels and node counts"""
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
)

with driver.session(database="neo4j") as session:
    # Count all nodes
    result = session.run("MATCH (n) RETURN count(n) as total")
    total = result.single()["total"]
    print(f"Total nodes: {total}")

    # Count relationships
    result = session.run("MATCH ()-[r]->() RETURN count(r) as total")
    total_rels = result.single()["total"]
    print(f"Total relationships: {total_rels}")

    # Show first 10 nodes with labels
    print("\nFirst 10 nodes with labels:")
    result = session.run("MATCH (n) RETURN labels(n) as labels, n LIMIT 10")
    for record in result:
        print(f"  Labels: {record['labels']}")
        print(f"  Properties: {dict(record['n'])}")
        print()

driver.close()
