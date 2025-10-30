"""
Third-Party Integrations (QuickBooks, Salesforce, etc.)
Fetches real-time data from external business systems via Nango proxy
"""

from .quickbooks import fetch_all_quickbooks_data

__all__ = ["fetch_all_quickbooks_data"]
