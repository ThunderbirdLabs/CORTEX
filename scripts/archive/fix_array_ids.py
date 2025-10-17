"""
Fix Array ID Issue in Neo4j

Problem: Entity deduplication created array IDs like ['Cortex', 'Cortex Solutions']
This breaks Neo4j queries that expect single string values.

Solution: Convert all array IDs to single strings (use first element)
"""

from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

def fix_array_ids():
    """Fix all entities that have array IDs."""
    
    driver = GraphDatabase.driver(
        os.getenv('NEO4J_URI'),
        auth=('neo4j', os.getenv('NEO4J_PASSWORD'))
    )
    
    with driver.session(database='neo4j') as session:
        print("=" * 80)
        print("FIXING ARRAY IDs IN NEO4J")
        print("=" * 80)
        
        # Check how many entities have array IDs
        check_query = """
        MATCH (e:__Entity__)
        WHERE NOT e.id IS NULL
          AND (valueType(e.id) STARTS WITH 'LIST' OR valueType(e.id) = 'LIST')
        RETURN count(e) AS array_count
        """
        
        result = session.run(check_query)
        record = result.single()
        array_count = record['array_count']

        print(f"\nEntities with array IDs: {array_count}")
        
        if array_count == 0:
            print("\nNo array IDs found - nothing to fix!")
            driver.close()
            return
        
        # Fix array IDs - use first element
        fix_query = """
        MATCH (e:__Entity__)
        WHERE NOT e.id IS NULL
          AND (valueType(e.id) STARTS WITH 'LIST' OR valueType(e.id) = 'LIST')
        WITH e, e.id AS old_id
        SET e.id = CASE
            WHEN size(e.id) > 0 THEN e.id[0]
            ELSE e.name
        END
        RETURN e.name AS name, old_id, e.id AS new_id
        """
        
        print(f"\nFixing {array_count} entities...")
        result = session.run(fix_query)

        fixed_count = 0
        for record in result:
            print(f"  Fixed: {record['name']}")
            print(f"    Old ID: {record['old_id']}")
            print(f"    New ID: {record['new_id']}")
            fixed_count += 1

        print(f"\nFixed {fixed_count} entities")
        
        # Verify fix
        verify_result = session.run(check_query)
        verify_record = verify_result.single()
        remaining_arrays = verify_record['array_count']
        
        print(f"\nVerification:")
        print(f"  Remaining array IDs: {remaining_arrays}")
        
        if remaining_arrays == 0:
            print("\n" + "=" * 80)
            print("SUCCESS: All array IDs fixed!")
            print("=" * 80)
        else:
            print("\nWARNING: Some array IDs remain")
    
    driver.close()

if __name__ == "__main__":
    fix_array_ids()
