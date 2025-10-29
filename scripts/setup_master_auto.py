#!/usr/bin/env python3
"""
Automated Master Supabase Setup Script for Unit Industries
Non-interactive version for automated deployment
"""

import os
import sys
import json
from supabase import create_client, Client
import bcrypt
from datetime import datetime

# Master Supabase credentials
# NOTE: This script was already run successfully. Credentials are stored in master Supabase.
# To run again, set these from your environment or edit this file locally (don't commit).
MASTER_SUPABASE_URL = os.getenv("MASTER_SUPABASE_URL", "YOUR_MASTER_SUPABASE_URL")
MASTER_SUPABASE_SERVICE_KEY = os.getenv("MASTER_SUPABASE_SERVICE_KEY", "YOUR_MASTER_SERVICE_KEY")

# Unit Industries deployment credentials (from Render)
# NOTE: Already populated in master Supabase. Edit these if running again.
UNIT_CREDENTIALS = {
    "supabase_url": os.getenv("SUPABASE_URL", "YOUR_SUPABASE_URL"),
    "supabase_anon_key": os.getenv("SUPABASE_ANON_KEY", "YOUR_ANON_KEY"),
    "supabase_service_role_key": os.getenv("SUPABASE_SERVICE_KEY", "YOUR_SERVICE_KEY"),
    "neo4j_uri": os.getenv("NEO4J_URI", "YOUR_NEO4J_URI"),
    "neo4j_user": os.getenv("NEO4J_USER", "neo4j"),
    "neo4j_password": os.getenv("NEO4J_PASSWORD", "YOUR_NEO4J_PASSWORD"),
    "qdrant_url": os.getenv("QDRANT_URL", "YOUR_QDRANT_URL"),
    "qdrant_api_key": os.getenv("QDRANT_API_KEY", "YOUR_QDRANT_KEY"),
    "qdrant_collection_name": os.getenv("QDRANT_COLLECTION_NAME", "cortex_embeddings"),
    "redis_host": os.getenv("REDIS_HOST", "YOUR_REDIS_HOST"),
    "redis_port": os.getenv("REDIS_PORT", "6379"),
    "redis_password": os.getenv("REDIS_PASSWORD", "YOUR_REDIS_PASSWORD"),
    "redis_url": os.getenv("REDIS_URL", "redis://YOUR_REDIS_URL"),
    "openai_api_key": os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_KEY"),
    "nango_secret_key": os.getenv("NANGO_SECRET_KEY", "YOUR_NANGO_KEY"),
    "backend_url": os.getenv("BACKEND_URL", "https://your-backend.onrender.com"),
    "frontend_url": os.getenv("FRONTEND_URL", "https://your-frontend.vercel.app"),
}

# Master admin account
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@yourcompany.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "CHANGE_ME")  # Change this!

# Company details
COMPANY_DATA = {
    "slug": "unit-industries",
    "name": "Unit Industries Group, Inc.",
    "company_location": "United States",
    "company_description": "Enterprise AI-powered business intelligence platform",
    "industries_served": ["Technology", "SaaS", "Enterprise Software"],
    "key_capabilities": ["AI", "Data Integration", "Knowledge Graph", "Email Intelligence"],
    "primary_contact_email": "nicolas@unit.com",
    "primary_contact_name": "Nicolas Codet",
    "backend_url": UNIT_CREDENTIALS["backend_url"],
    "frontend_url": UNIT_CREDENTIALS["frontend_url"],
    "plan": "enterprise",
}

# Team members
TEAM_MEMBERS = [
    {
        "email": "nicolas@unit.com",
        "name": "Nicolas Codet",
        "title": "Founder & CEO",
        "role_description": "Overall leadership and product vision",
    },
]


def hash_password(password: str) -> str:
    """Hash password with bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def main():
    print("=" * 80)
    print("  🚀 CORTEX Master Control Plane - Automated Setup")
    print("=" * 80)
    print()

    # Connect to master Supabase
    print("📡 Connecting to master Supabase...")
    try:
        master: Client = create_client(MASTER_SUPABASE_URL, MASTER_SUPABASE_SERVICE_KEY)
        print("✅ Connected to master Supabase\n")
    except Exception as e:
        print(f"❌ Failed to connect to master Supabase: {e}")
        sys.exit(1)

    # Step 1: Create master admin account
    print("=" * 80)
    print("Step 1: Creating Master Admin Account")
    print("=" * 80)

    try:
        # Check if admin exists
        existing = master.table("master_admins").select("id").eq("email", ADMIN_EMAIL).execute()

        if existing.data:
            print(f"⚠️  Admin account already exists: {ADMIN_EMAIL}")
            admin_id = existing.data[0]["id"]
        else:
            password_hash = hash_password(ADMIN_PASSWORD)

            result = master.table("master_admins").insert({
                "email": ADMIN_EMAIL,
                "name": "Nicolas Codet",
                "password_hash": password_hash,
                "role": "super_admin",
                "can_create_companies": True,
                "can_delete_companies": True,
                "can_view_schemas": True,
                "can_edit_schemas": True,
                "can_view_deployments": True,
                "can_edit_deployments": True,
                "is_active": True,
            }).execute()

            admin_id = result.data[0]["id"]
            print(f"✅ Created master admin: {ADMIN_EMAIL}")
            print(f"   Password: {ADMIN_PASSWORD}")
            print(f"   Admin ID: {admin_id}\n")

    except Exception as e:
        print(f"❌ Failed to create admin account: {e}")
        sys.exit(1)

    # Step 2: Create company record
    print("=" * 80)
    print("Step 2: Creating Company Record")
    print("=" * 80)

    try:
        # Check if company exists
        existing = master.table("companies").select("id").eq("slug", COMPANY_DATA["slug"]).execute()

        if existing.data:
            print(f"⚠️  Company already exists: {COMPANY_DATA['slug']}")
            company_id = existing.data[0]["id"]
        else:
            result = master.table("companies").insert({
                **COMPANY_DATA,
                "status": "active",
                "created_at": datetime.utcnow().isoformat(),
            }).execute()

            company_id = result.data[0]["id"]
            print(f"✅ Created company: {COMPANY_DATA['name']}")
            print(f"   Slug: {COMPANY_DATA['slug']}")
            print(f"   Company ID: {company_id}\n")

    except Exception as e:
        print(f"❌ Failed to create company: {e}")
        sys.exit(1)

    # Step 3: Store deployment credentials
    print("=" * 80)
    print("Step 3: Storing Deployment Credentials")
    print("=" * 80)

    try:
        # Check if deployment exists
        existing = master.table("company_deployments").select("id").eq("company_id", company_id).execute()

        if existing.data:
            print(f"⚠️  Deployment already exists for company {company_id}")
        else:
            # Generate a default admin PIN hash (can be changed later)
            admin_pin_hash = hash_password("1234")  # Default PIN

            result = master.table("company_deployments").insert({
                "company_id": company_id,
                "supabase_url": UNIT_CREDENTIALS["supabase_url"],
                "supabase_anon_key": UNIT_CREDENTIALS["supabase_anon_key"],
                "supabase_service_key": UNIT_CREDENTIALS["supabase_service_role_key"],
                "neo4j_uri": UNIT_CREDENTIALS["neo4j_uri"],
                "neo4j_user": UNIT_CREDENTIALS["neo4j_user"],
                "neo4j_password": UNIT_CREDENTIALS["neo4j_password"],
                "qdrant_url": UNIT_CREDENTIALS["qdrant_url"],
                "qdrant_api_key": UNIT_CREDENTIALS["qdrant_api_key"],
                "qdrant_collection_name": UNIT_CREDENTIALS["qdrant_collection_name"],
                "redis_url": UNIT_CREDENTIALS["redis_url"],
                "openai_api_key": UNIT_CREDENTIALS["openai_api_key"],
                "nango_secret_key": UNIT_CREDENTIALS["nango_secret_key"],
                "admin_pin_hash": admin_pin_hash,
            }).execute()

            print("✅ Stored deployment credentials")
            print(f"   Supabase: {UNIT_CREDENTIALS['supabase_url']}")
            print(f"   Neo4j: {UNIT_CREDENTIALS['neo4j_uri']}")
            print(f"   Qdrant: {UNIT_CREDENTIALS['qdrant_collection_name']}\n")

    except Exception as e:
        print(f"❌ Failed to store deployment credentials: {e}")
        sys.exit(1)

    # Step 4: Add team members
    print("=" * 80)
    print("Step 4: Adding Team Members")
    print("=" * 80)

    for member in TEAM_MEMBERS:
        try:
            # Check if member exists
            existing = master.table("company_team_members").select("id")\
                .eq("company_id", company_id)\
                .eq("email", member["email"])\
                .execute()

            if existing.data:
                print(f"⚠️  Team member already exists: {member['email']}")
            else:
                master.table("company_team_members").insert({
                    "company_id": company_id,
                    **member,
                    "is_active": True,
                }).execute()

                print(f"✅ Added team member: {member['name']} ({member['email']})")

        except Exception as e:
            print(f"⚠️  Failed to add team member {member['email']}: {e}")

    print()

    # Step 5: Log audit event
    print("=" * 80)
    print("Step 5: Logging Audit Event")
    print("=" * 80)

    try:
        master.table("audit_log_global").insert({
            "admin_id": admin_id,
            "company_id": company_id,
            "action": "company_created",
            "details": {
                "company_slug": COMPANY_DATA["slug"],
                "setup_method": "automated_script",
            },
        }).execute()

        print("✅ Logged audit event\n")

    except Exception as e:
        print(f"⚠️  Failed to log audit event: {e}\n")

    # Print final instructions
    print("=" * 80)
    print("  ✅ Setup Complete!")
    print("=" * 80)
    print()
    print("📋 Next Steps:")
    print()
    print("1️⃣  Add these environment variables to Unit Industries Render service:")
    print()
    print(f"   COMPANY_ID={company_id}")
    print(f"   MASTER_SUPABASE_URL={MASTER_SUPABASE_URL}")
    print(f"   MASTER_SUPABASE_SERVICE_KEY={MASTER_SUPABASE_SERVICE_KEY}")
    print()
    print("2️⃣  Redeploy the backend service")
    print()
    print("3️⃣  Check logs for: '🏢 Multi-tenant mode ENABLED'")
    print()
    print("4️⃣  Test that Unit Industries still works normally")
    print()
    print("=" * 80)
    print()
    print("🎉 Your master control plane is ready!")
    print()
    print(f"Master Admin Login: {ADMIN_EMAIL}")
    print(f"Master Admin Password: {ADMIN_PASSWORD}")
    print(f"Company ID: {company_id}")
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
