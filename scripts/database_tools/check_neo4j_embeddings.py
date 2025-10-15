from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

with driver.session(database="neo4j") as session:
    # Check if Chunk nodes have embeddings
    result = session.run("""
        MATCH (c:Chunk)
        RETURN c.id as id, c.embedding as embedding, c.text as text
        LIMIT 3
    """)
    
    print("Chunk nodes - checking for embeddings:\n")
    for i, record in enumerate(result, 1):
        print(f"Chunk {i}:")
        print(f"  ID: {record['id']}")
        has_text = "YES" if record['text'] else "NO"
        has_embedding = "YES" if record['embedding'] else "NO"
        print(f"  Has text: {has_text}")
        print(f"  Has embedding: {has_embedding}")
        if record['embedding']:
            print(f"  Embedding dimensions: {len(record['embedding'])}")
        print()

driver.close()
