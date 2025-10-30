"""
Third-Party Integrations API
Explore and fetch data from QuickBooks, Salesforce, etc.
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
import httpx

from app.core.dependencies import get_current_user, get_http_client
from app.services.integrations import fetch_all_quickbooks_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/quickbooks/explore")
async def explore_quickbooks(
    connection_id: str = Query(None, description="Nango connection ID (defaults to user ID)"),
    http_client: httpx.AsyncClient = Depends(get_http_client),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    🔍 Explore ALL QuickBooks data for a user.

    This endpoint fetches everything available from QuickBooks via Nango:
    - Accounts (Chart of Accounts)
    - Invoices, Bills, Payments
    - Customers, Items
    - Deposits, Transfers, Credit Memos
    - Journal Entries

    Perfect for building CEO dashboards - gives you a complete picture!

    **Usage:**
    1. User connects QuickBooks via Nango OAuth
    2. Call this endpoint (auth required)
    3. Receive comprehensive data dump

    **Example Response:**
    ```json
    {
      "success": true,
      "user_id": "user-123",
      "data": {
        "accounts": [...],
        "invoices": [
          {
            "id": "892",
            "doc_number": "INV-892",
            "customer_name": "Acme Corp",
            "total": 12500.00,
            "balance": 0.00,
            "date": "2025-10-26"
          }
        ],
        "customers": [...],
        "bills": [...],
        "payments": [...],
        ...
      }
    }
    ```

    **Notes:**
    - Requires active QuickBooks connection via Nango
    - Data is fetched from Nango's synced cache (FAST!)
    - Nango syncs QB data automatically in background
    """
    user_id = current_user.get("id") or current_user.get("sub")

    # Default connection_id to user_id if not provided
    if not connection_id:
        connection_id = user_id

    logger.info(f"🔍 Exploring QuickBooks for user {user_id}")

    try:
        data = await fetch_all_quickbooks_data(http_client, connection_id)

        return {
            "success": True,
            "user_id": user_id,
            "data": data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to explore QuickBooks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch QuickBooks data: {str(e)}")


@router.get("/quickbooks/summary")
async def quickbooks_summary(
    connection_id: str = Query(None, description="Nango connection ID (defaults to user ID)"),
    time_range: str = Query("this_month", description="Time range: this_week, this_month, this_quarter, this_year"),
    http_client: httpx.AsyncClient = Depends(get_http_client),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    📊 Get QuickBooks financial summary (cleaned and formatted).

    Unlike `/explore` which dumps everything, this endpoint returns
    a clean, dashboard-ready summary.

    **Response:**
    ```json
    {
      "success": true,
      "time_range": "this_month",
      "company_name": "Acme Manufacturing",
      "revenue": 47500.00,
      "expenses": 22000.00,
      "net_income": 25500.00,
      "outstanding_invoices": 26000.00,
      "cash_on_hand": 125000.00,
      "top_customers": [
        {"name": "Acme Corp", "total": 12500},
        {"name": "Precision Plastics", "total": 20000}
      ],
      "top_vendors": [
        {"name": "Steel Supplier Inc", "total": 8000}
      ],
      "recent_invoices": [...]
    }
    ```
    """
    user_id = current_user.get("id") or current_user.get("sub")

    if not connection_id:
        connection_id = user_id

    logger.info(f"📊 QuickBooks summary for user {user_id}, range: {time_range}")

    try:
        # Fetch all data
        data = await fetch_all_quickbooks_data(http_client, connection_id)

        # Calculate metrics from transaction data
        invoices = data.get("invoices", [])
        bills = data.get("bills", [])
        payments = data.get("payments", [])

        # Calculate revenue (sum of paid invoices)
        revenue = sum(
            float(inv.get("total", 0) or 0)
            for inv in invoices
            if float(inv.get("balance", 0) or 0) == 0  # Paid in full
        )

        # Calculate expenses (sum of bills)
        expenses = sum(
            float(bill.get("total", 0) or 0)
            for bill in bills
        )

        net_income = revenue - expenses

        # Calculate outstanding invoices
        outstanding_invoices = sum(
            float(inv.get("balance", 0) or 0)
            for inv in invoices
            if float(inv.get("balance", 0) or 0) > 0
        )

        # Cash on hand from accounts (Cash/Bank accounts)
        accounts = data.get("accounts", [])
        cash_on_hand = sum(
            float(acc.get("current_balance", 0) or 0)
            for acc in accounts
            if acc.get("account_type", "").lower() in ["bank", "cash"]
        )

        # Top customers (by total invoice amount)
        customer_totals = {}
        for inv in invoices:
            customer_name = inv.get("customer_name") or inv.get("customer", {}).get("name", "Unknown")
            total = float(inv.get("total", 0) or 0)
            customer_totals[customer_name] = customer_totals.get(customer_name, 0) + total

        top_customers = [
            {"name": name, "total": total}
            for name, total in sorted(customer_totals.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        # Top vendors (by total bill amount)
        vendor_totals = {}
        for bill in bills:
            vendor_name = bill.get("vendor_name") or bill.get("vendor", {}).get("name", "Unknown")
            total = float(bill.get("total", 0) or 0)
            vendor_totals[vendor_name] = vendor_totals.get(vendor_name, 0) + total

        top_vendors = [
            {"name": name, "total": total}
            for name, total in sorted(vendor_totals.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        # Recent invoices (last 10)
        recent_invoices = [
            {
                "id": inv.get("id"),
                "doc_number": inv.get("doc_number") or inv.get("invoice_number"),
                "customer": inv.get("customer_name") or inv.get("customer", {}).get("name"),
                "total": float(inv.get("total", 0) or 0),
                "balance": float(inv.get("balance", 0) or 0),
                "date": inv.get("date") or inv.get("created_at"),
                "status": "Paid" if float(inv.get("balance", 0) or 0) == 0 else "Outstanding"
            }
            for inv in sorted(invoices, key=lambda x: x.get("date", "") or x.get("created_at", ""), reverse=True)[:10]
        ]

        return {
            "success": True,
            "time_range": time_range,
            "revenue": revenue,
            "expenses": expenses,
            "net_income": net_income,
            "outstanding_invoices": outstanding_invoices,
            "cash_on_hand": cash_on_hand,
            "top_customers": top_customers,
            "top_vendors": top_vendors,
            "recent_invoices": recent_invoices,
            "data_counts": {
                "total_invoices": len(invoices),
                "total_bills": len(bills),
                "total_customers": len(data.get("customers", [])),
                "total_payments": len(payments)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to generate QuickBooks summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")
