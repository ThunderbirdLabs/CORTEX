"""
Dashboard API endpoints
Provides aggregated data for executive dashboard widgets
Fetches QuickBooks documents from Supabase with time filters
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from supabase import Client

from app.core.security import get_current_user_id
from app.core.dependencies import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/quickbooks/overview")
async def get_quickbooks_overview(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to look back"),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get QuickBooks overview data for dashboard widgets.

    Returns:
    - Total invoices (count, total amount, outstanding balance)
    - Total bills (count, total amount, unpaid)
    - Total payments (count, total amount)
    - Top customers by revenue
    - Recent transactions
    """
    try:
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        logger.info(f"📊 Fetching QB overview for user {user_id}, last {days} days")

        # Fetch all QuickBooks documents in date range
        response = supabase.table("documents")\
            .select("*")\
            .eq("tenant_id", user_id)\
            .eq("source", "quickbooks")\
            .gte("source_created_at", start_date.isoformat())\
            .order("source_created_at", desc=True)\
            .execute()

        documents = response.data or []
        logger.info(f"Found {len(documents)} QB documents")

        # Aggregate by document type
        invoices = []
        bills = []
        payments = []
        customers = []

        for doc in documents:
            doc_type = doc.get("document_type") or doc.get("metadata", {}).get("source_type")

            if doc_type == "invoice":
                invoices.append(doc)
            elif doc_type == "bill":
                bills.append(doc)
            elif doc_type == "payment":
                payments.append(doc)
            elif doc_type == "customer":
                customers.append(doc)

        # Calculate invoice metrics
        invoice_total = sum(doc.get("metadata", {}).get("total", 0) for doc in invoices)
        invoice_outstanding = sum(doc.get("metadata", {}).get("balance", 0) for doc in invoices)

        # Calculate bill metrics
        bill_total = sum(doc.get("metadata", {}).get("total", 0) for doc in bills)
        bill_unpaid = sum(doc.get("metadata", {}).get("balance", 0) for doc in bills)

        # Calculate payment metrics
        payment_total = sum(doc.get("metadata", {}).get("total", 0) for doc in payments)

        # Top customers by invoice amount
        customer_revenue: Dict[str, float] = {}
        for inv in invoices:
            customer_name = inv.get("metadata", {}).get("customer_name", "Unknown")
            amount = inv.get("metadata", {}).get("total", 0)
            customer_revenue[customer_name] = customer_revenue.get(customer_name, 0) + amount

        top_customers = sorted(
            [{"name": k, "revenue": v} for k, v in customer_revenue.items()],
            key=lambda x: x["revenue"],
            reverse=True
        )[:5]

        # Recent transactions (last 10)
        recent_transactions = []
        for doc in documents[:10]:
            doc_type = doc.get("document_type") or doc.get("metadata", {}).get("source_type")
            metadata = doc.get("metadata", {})

            recent_transactions.append({
                "id": doc.get("id"),
                "type": doc_type,
                "title": doc.get("title"),
                "amount": metadata.get("total", 0),
                "date": doc.get("source_created_at") or doc.get("created_at"),
                "customer_vendor": metadata.get("customer_name") or metadata.get("vendor_name"),
                "status": metadata.get("status")
            })

        result = {
            "period_days": days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "invoices": {
                "count": len(invoices),
                "total_amount": round(invoice_total, 2),
                "outstanding_balance": round(invoice_outstanding, 2),
                "paid_amount": round(invoice_total - invoice_outstanding, 2)
            },
            "bills": {
                "count": len(bills),
                "total_amount": round(bill_total, 2),
                "unpaid_balance": round(bill_unpaid, 2),
                "paid_amount": round(bill_total - bill_unpaid, 2)
            },
            "payments": {
                "count": len(payments),
                "total_amount": round(payment_total, 2)
            },
            "customers": {
                "count": len(customers),
                "top_5": top_customers
            },
            "recent_transactions": recent_transactions,
            "total_documents": len(documents)
        }

        logger.info(f"✅ QB overview: {len(invoices)} invoices, {len(bills)} bills, {len(payments)} payments")
        return result

    except Exception as e:
        logger.error(f"❌ Error fetching QB overview: {e}")
        raise


@router.get("/quickbooks/invoices")
async def get_quickbooks_invoices(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """Get all QuickBooks invoices with details."""
    try:
        start_date = datetime.utcnow() - timedelta(days=days)

        response = supabase.table("documents")\
            .select("*")\
            .eq("tenant_id", user_id)\
            .eq("source", "quickbooks")\
            .eq("document_type", "invoice")\
            .gte("source_created_at", start_date.isoformat())\
            .order("source_created_at", desc=True)\
            .limit(limit)\
            .execute()

        invoices = response.data or []

        # Format response
        formatted_invoices = []
        for inv in invoices:
            metadata = inv.get("metadata", {})
            formatted_invoices.append({
                "id": inv.get("id"),
                "doc_number": metadata.get("doc_number"),
                "customer_name": metadata.get("customer_name"),
                "total": metadata.get("total", 0),
                "balance": metadata.get("balance", 0),
                "status": metadata.get("status"),
                "date": metadata.get("date"),
                "due_date": metadata.get("due_date"),
                "content": inv.get("content")
            })

        return {
            "count": len(formatted_invoices),
            "invoices": formatted_invoices
        }

    except Exception as e:
        logger.error(f"Error fetching invoices: {e}")
        raise


@router.get("/quickbooks/bills")
async def get_quickbooks_bills(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """Get all QuickBooks bills with details."""
    try:
        start_date = datetime.utcnow() - timedelta(days=days)

        response = supabase.table("documents")\
            .select("*")\
            .eq("tenant_id", user_id)\
            .eq("source", "quickbooks")\
            .eq("document_type", "bill")\
            .gte("source_created_at", start_date.isoformat())\
            .order("source_created_at", desc=True)\
            .limit(limit)\
            .execute()

        bills = response.data or []

        formatted_bills = []
        for bill in bills:
            metadata = bill.get("metadata", {})
            formatted_bills.append({
                "id": bill.get("id"),
                "doc_number": metadata.get("doc_number"),
                "vendor_name": metadata.get("vendor_name"),
                "total": metadata.get("total", 0),
                "balance": metadata.get("balance", 0),
                "status": metadata.get("status"),
                "date": metadata.get("date"),
                "content": bill.get("content")
            })

        return {
            "count": len(formatted_bills),
            "bills": formatted_bills
        }

    except Exception as e:
        logger.error(f"Error fetching bills: {e}")
        raise


@router.get("/quickbooks/payments")
async def get_quickbooks_payments(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """Get all QuickBooks payments with details."""
    try:
        start_date = datetime.utcnow() - timedelta(days=days)

        response = supabase.table("documents")\
            .select("*")\
            .eq("tenant_id", user_id)\
            .eq("source", "quickbooks")\
            .eq("document_type", "payment")\
            .gte("source_created_at", start_date.isoformat())\
            .order("source_created_at", desc=True)\
            .limit(limit)\
            .execute()

        payments = response.data or []

        formatted_payments = []
        for payment in payments:
            metadata = payment.get("metadata", {})
            formatted_payments.append({
                "id": payment.get("id"),
                "customer_name": metadata.get("customer_name"),
                "total": metadata.get("total", 0),
                "payment_method": metadata.get("payment_method"),
                "date": metadata.get("date"),
                "content": payment.get("content")
            })

        return {
            "count": len(formatted_payments),
            "payments": formatted_payments
        }

    except Exception as e:
        logger.error(f"Error fetching payments: {e}")
        raise
