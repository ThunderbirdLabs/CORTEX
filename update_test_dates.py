"""
Update Supabase documents with test dates from April 2024 to October 2025
"""
from supabase import create_client
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import random

load_dotenv()

# Check env vars
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY') or os.getenv('SUPABASE_ANON_KEY')

if not supabase_key:
    print("ERROR: No Supabase key found. Checking available env vars...")
    for key in os.environ:
        if 'SUPABASE' in key.upper():
            print(f"  {key}: {'<set>' if os.environ[key] else '<not set>'}")
    exit(1)

supabase = create_client(supabase_url, supabase_key)

# Get all documents
result = supabase.table('documents').select('id, title, source_created_at, document_type').execute()
docs = result.data

print(f'Found {len(docs)} documents\n')

# Define date ranges from April 2024 to October 2025
# Spread documents evenly across this range
start_date = datetime(2024, 4, 1)
end_date = datetime(2025, 10, 17)
date_range_days = (end_date - start_date).days

print(f'Updating dates from {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}')
print(f'Date range: {date_range_days} days\n')

# Update each document with a random date in the range
updated = 0
for i, doc in enumerate(docs):
    # Random date within range
    random_days = random.randint(0, date_range_days)
    new_date = start_date + timedelta(days=random_days)
    new_date_iso = new_date.isoformat()

    # Update in Supabase
    supabase.table('documents').update({
        'source_created_at': new_date_iso
    }).eq('id', doc['id']).execute()

    updated += 1
    print(f'{i+1}/{len(docs)} - ID {doc["id"]}: {doc["title"][:40]:40} -> {new_date.strftime("%Y-%m-%d")}')

print(f'\n✅ Updated {updated} documents with dates from April 2024 to October 2025')

# Show distribution by month
from collections import defaultdict
month_counts = defaultdict(int)
for doc in docs:
    result = supabase.table('documents').select('source_created_at').eq('id', doc['id']).execute()
    if result.data:
        created_at = result.data[0]['source_created_at']
        if created_at:
            month = created_at[:7]  # YYYY-MM
            month_counts[month] += 1

print('\nDistribution by month:')
for month in sorted(month_counts.keys()):
    print(f'  {month}: {month_counts[month]} documents')
