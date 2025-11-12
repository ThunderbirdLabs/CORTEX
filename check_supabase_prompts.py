#!/usr/bin/env python3
"""
Check Supabase company_prompts table
"""
import sys
import os

# Add app to path and load environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

# Load .env manually
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from supabase import create_client

# Get env vars
MASTER_URL = os.getenv('MASTER_SUPABASE_URL')
MASTER_KEY = os.getenv('MASTER_SUPABASE_SERVICE_KEY')
COMPANY_ID = os.getenv('COMPANY_ID')

print("="*80)
print("CHECKING SUPABASE company_prompts TABLE")
print("="*80)
print()

print(f"Master Supabase URL: {MASTER_URL}")
print(f"Company ID: {COMPANY_ID}")
print()

if not MASTER_URL or not MASTER_KEY:
    print("❌ Master Supabase credentials not set in .env")
    sys.exit(1)

# Connect
master = create_client(MASTER_URL, MASTER_KEY)
print("✅ Connected to master Supabase")
print()

# Query for this company's prompts
print(f"Querying company_prompts WHERE company_id = '{COMPANY_ID}'...")
result = master.table('company_prompts')\
    .select('*')\
    .eq('company_id', COMPANY_ID)\
    .execute()

print(f"Found: {len(result.data)} rows")
print()

if result.data:
    for i, row in enumerate(result.data, 1):
        print(f"[{i}] Prompt Key: {row['prompt_key']}")
        print(f"    Active: {row.get('is_active')}")
        print(f"    Created: {row.get('created_at')}")
        print(f"    Template length: {len(row.get('prompt_template', ''))} chars")
        print(f"    First 200 chars:")
        print(f"    {row.get('prompt_template', '')[:200]}")
        print()
else:
    print("❌ NO PROMPTS FOUND FOR THIS COMPANY_ID")
    print()
    print("Let me check what company_ids exist in the table...")
    all_companies = master.table('company_prompts')\
        .select('company_id, prompt_key')\
        .execute()

    unique_companies = set(r['company_id'] for r in all_companies.data)
    print(f"Found {len(unique_companies)} unique company_ids in table:")
    for cid in list(unique_companies)[:10]:
        count = len([r for r in all_companies.data if r['company_id'] == cid])
        print(f"  - {cid}: {count} prompts")

print()
print("="*80)
