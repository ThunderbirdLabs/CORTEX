"""
Deep Analysis of Neo4j Graph Structure
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from neo4j import GraphDatabase
from app.services.ingestion.llamaindex.config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE
import json

def analyze_graph():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    with driver.session(database=NEO4J_DATABASE) as session:
        print("="*80)
        print("COMPREHENSIVE NEO4J GRAPH ANALYSIS")
        print("="*80)
        print()

        # 1. ALL NODES WITH FULL PROPERTIES
        print("="*80)
        print("ALL NODES (Full Properties)")
        print("="*80)
        print()

        result = session.run('''
            MATCH (n)
            RETURN labels(n) as labels, properties(n) as props, id(n) as node_id
            ORDER BY labels(n)[0], node_id
        ''')

        node_count = 0
        for record in result:
            node_count += 1
            print(f"Node {node_count} (ID: {record['node_id']})")
            print(f"  Labels: {record['labels']}")
            print(f"  Properties:")
            for key, value in record['props'].items():
                if isinstance(value, str) and len(value) > 200:
                    print(f"    {key}: {value[:200]}... (truncated)")
                else:
                    print(f"    {key}: {value}")
            print()

        print(f"Total nodes: {node_count}")
        print()

        # 2. ALL RELATIONSHIPS WITH FULL PROPERTIES
        print("="*80)
        print("ALL RELATIONSHIPS (Full Details)")
        print("="*80)
        print()

        result = session.run('''
            MATCH (a)-[r]->(b)
            RETURN type(r) as rel_type, properties(r) as props,
                   labels(a) as source_labels, properties(a) as source_props,
                   labels(b) as target_labels, properties(b) as target_props,
                   id(r) as rel_id
            ORDER BY rel_type
        ''')

        rel_count = 0
        for record in result:
            rel_count += 1
            source_name = record['source_props'].get('name') or record['source_props'].get('title') or 'N/A'
            target_name = record['target_props'].get('name') or record['target_props'].get('title') or 'N/A'

            print(f"Relationship {rel_count} (ID: {record['rel_id']})")
            print(f"  {record['source_labels']}[{source_name}] -[{record['rel_type']}]-> {record['target_labels']}[{target_name}]")
            if record['props']:
                print(f"  Relationship properties: {record['props']}")
            print()

        print(f"Total relationships: {rel_count}")
        print()

        # 3. LABEL STATISTICS
        print("="*80)
        print("LABEL STATISTICS")
        print("="*80)
        print()

        result = session.run('''
            MATCH (n)
            UNWIND labels(n) as label
            RETURN label, count(*) as count
            ORDER BY count DESC
        ''')

        print("Label distribution:")
        for record in result:
            print(f"  {record['label']}: {record['count']}")
        print()

        # 4. RELATIONSHIP TYPE STATISTICS
        print("="*80)
        print("RELATIONSHIP TYPE STATISTICS")
        print("="*80)
        print()

        result = session.run('''
            MATCH ()-[r]->()
            RETURN type(r) as rel_type, count(*) as count
            ORDER BY count DESC
        ''')

        print("Relationship types:")
        for record in result:
            print(f"  {record['rel_type']}: {record['count']}")
        print()

        # 5. PROPERTY KEYS ANALYSIS
        print("="*80)
        print("PROPERTY KEYS ANALYSIS")
        print("="*80)
        print()

        result = session.run('''
            MATCH (n)
            UNWIND keys(n) as key
            RETURN DISTINCT key
            ORDER BY key
        ''')

        print("All node property keys:")
        for record in result:
            print(f"  - {record['key']}")
        print()

        # 6. GRAPH PATTERNS
        print("="*80)
        print("COMMON GRAPH PATTERNS")
        print("="*80)
        print()

        result = session.run('''
            MATCH (a)-[r]->(b)
            RETURN labels(a)[0] as source, type(r) as rel, labels(b)[0] as target, count(*) as count
            ORDER BY count DESC
            LIMIT 20
        ''')

        print("Top 20 node-relationship-node patterns:")
        for record in result:
            print(f"  {record['source']} -[{record['rel']}]-> {record['target']}: {record['count']}")
        print()

        # 7. DOCUMENT NODES ANALYSIS
        print("="*80)
        print("DOCUMENT NODES DETAILED ANALYSIS")
        print("="*80)
        print()

        result = session.run('''
            MATCH (n)
            WHERE NOT '__Node__' IN labels(n) AND NOT '__Entity__' IN labels(n)
            RETURN labels(n) as labels, properties(n) as props
            LIMIT 10
        ''')

        print("Sample custom nodes (non-system labels):")
        for record in result:
            print(f"Labels: {record['labels']}")
            print(f"Properties: {list(record['props'].keys())}")
            print()

    driver.close()

if __name__ == "__main__":
    analyze_graph()
