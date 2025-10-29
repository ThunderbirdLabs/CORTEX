"""
Temporary workaround: Run ingestion with SSL verification disabled
WARNING: Only use for local development with trusted connections
"""
import os
import ssl
import asyncio

# Disable SSL verification for httpx (used by Supabase client)
os.environ['PYTHONHTTPSVERIFY'] = '0'
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['CURL_CA_BUNDLE'] = ''

# Monkey patch ssl for Python's urllib
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Now run the ingestion script
import sys
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

# Import and run
exec(open('scripts/dev/clear_and_reingest.py').read())
