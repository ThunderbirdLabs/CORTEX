"""
Update Supabase documents with realistic dates from April 2024 to October 2025
This gives us a date range to test time-filtering queries
"""
from supabase import create_client
import os
from datetime import datetime, timedelta
import random
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))

# Get all documents
result = supabase.table('documents').select('id, title, document_type').execute()
docs = result.data

print(f'Found {len(docs)} documents\n')

# Define date range from April 2024 to October 2025
start_date = datetime(2024, 4, 1)
end_date = datetime(2025, 10, 23)  # Today
date_range_days = (end_date - start_date).days

print(f'Updating dates from {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}')
print(f'Date range: {date_range_days} days\n')

# Update each document with a random date in the range
updated = 0
for i, doc in enumerate(docs):
    # Random date within range
    random_days = random.randint(0, date_range_days)
    new_date = start_date + timedelta(days=random_days)
    new_date_iso = new_date.isoformat() + 'Z'

    # Update in Supabase
    supabase.table('documents').update({
        'source_created_at': new_date_iso
    }).eq('id', doc['id']).execute()

    updated += 1
    doc_type = doc.get('document_type', 'unknown')
    print(f'{i+1}/{len(docs)} - {doc_type:12} {doc["title"][:45]:45} -> {new_date.strftime("%Y-%m-%d")}')

print(f'\n✅ Updated {updated} documents with dates from April 2024 to October 2025')

# Show distribution by month
from collections import defaultdict
month_counts = defaultdict(int)
result = supabase.table('documents').select('source_created_at').execute()
for doc in result.data:
    created_at = doc.get('source_created_at')
    if created_at:
        month = created_at[:7]  # YYYY-MM
        month_counts[month] += 1

print('\nDistribution by month:')
for month in sorted(month_counts.keys()):
    print(f'  {month}: {month_counts[month]} documents')

print('\n=== SUGGESTED TEST QUERIES ===')
print('1. "Show me documents from October 2024"')
print('2. "What emails did I get in June 2024?"')
print('3. "Documents from last month"')
print('4. "Show me everything from Q2 2024"')
print('5. "What happened after January 2025?"')
