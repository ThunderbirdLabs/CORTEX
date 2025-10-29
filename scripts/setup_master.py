#!/usr/bin/env python3
"""
CORTEX Master Control Plane Setup Script
==========================================
Purpose: Securely populate master Supabase with Unit Industries credentials

Usage:
    python scripts/setup_master.py

This script will:
1. Prompt for your master Supabase credentials
2. Prompt for Unit Industries deployment credentials
3. Securely hash passwords/PINs
4. Insert data into master Supabase
5. Verify the setup
"""

import os
import sys
import getpass

try:
    import bcrypt
except ImportError:
    print("❌ Error: bcrypt not installed")
    print("   Run: pip install bcrypt")
    sys.exit(1)

try:
    from supabase import create_client, Client
except ImportError:
    print("❌ Error: supabase not installed")
    print("   Run: pip install supabase")
    sys.exit(1)

def print_header(text):
    """Pretty print section headers."""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80 + "\n")

def print_success(text):
    """Print success message."""
    print(f"✅ {text}")

def print_error(text):
    """Print error message."""
    print(f"❌ {text}")

def print_info(text):
    """Print info message."""
    print(f"ℹ️  {text}")

def hash_password(password: str) -> str:
    """Generate bcrypt hash of password."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def main():
    print_header("CORTEX Master Control Plane Setup")

    print_info("This script will set up your master Supabase project with Unit Industries data.")
    print_info("Make sure you've already run migrations/master/001_create_master_tables.sql")
    input("\nPress ENTER to continue or Ctrl+C to cancel...")

    # ========================================================================
    # Step 1: Connect to Master Supabase
    # ========================================================================
    print_header("Step 1: Master Supabase Connection")

    master_url = input("Enter your master Supabase URL (https://xxx.supabase.co): ").strip()
    master_service_key = getpass.getpass("Enter your master Supabase SERVICE ROLE key: ").strip()

    try:
        master = create_client(master_url, master_service_key)
        # Test connection
        master.table("companies").select("id").limit(1).execute()
        print_success("Connected to master Supabase")
    except Exception as e:
        print_error(f"Failed to connect to master Supabase: {e}")
        sys.exit(1)

    # ========================================================================
    # Step 2: Create Master Admin Account
    # ========================================================================
    print_header("Step 2: Create Your Master Admin Account")

    admin_email = input("Your email (for master admin login): ").strip()
    admin_name = input("Your full name: ").strip()
    admin_password = getpass.getpass("Choose a strong password (min 12 chars): ").strip()
    admin_password_confirm = getpass.getpass("Confirm password: ").strip()

    if admin_password != admin_password_confirm:
        print_error("Passwords don't match!")
        sys.exit(1)

    if len(admin_password) < 12:
        print_error("Password must be at least 12 characters!")
        sys.exit(1)

    admin_password_hash = hash_password(admin_password)

    try:
        result = master.table("master_admins").insert({
            "email": admin_email,
            "name": admin_name,
            "password_hash": admin_password_hash,
            "role": "super_admin",
            "can_create_companies": True,
            "can_delete_companies": True
        }).execute()

        admin_id = result.data[0]["id"]
        print_success(f"Created master admin account: {admin_email}")
    except Exception as e:
        print_error(f"Failed to create admin account: {e}")
        sys.exit(1)

    # ========================================================================
    # Step 3: Create Unit Industries Company
    # ========================================================================
    print_header("Step 3: Create Unit Industries Company Record")

    print_info("Using existing Unit Industries details...")

    try:
        result = master.table("companies").insert({
            "slug": "unit-industries",
            "name": "Unit Industries Group, Inc.",
            "status": "active",
            "plan": "enterprise",
            "backend_url": "https://nango-connection-only.onrender.com",
            "frontend_url": "https://connectorfrontend.vercel.app",
            "company_location": "Santa Ana, CA",
            "company_description": "Progressive plastic injection molding company specializing in innovative manufacturing solutions.",
            "industries_served": ["Communications", "Medical", "Defense/Aerospace", "Industrial/Semiconductor", "Multimedia", "Automotive", "Clean Technology"],
            "key_capabilities": ["Class 100,000 Clean Room (4,800 sq ft)", "End-to-end manufacturing and logistics solutions", "ISO 9001 certified", "Over a century of combined experience"],
            "primary_contact_email": "anthony@unit.com",
            "primary_contact_name": "Anthony Codet",
            "activated_at": "now()"
        }).execute()

        company_id = result.data[0]["id"]
        print_success(f"Created company record (ID: {company_id})")
    except Exception as e:
        print_error(f"Failed to create company: {e}")
        sys.exit(1)

    # ========================================================================
    # Step 4: Add Deployment Credentials
    # ========================================================================
    print_header("Step 4: Unit Industries Deployment Credentials")

    print_info("Enter your EXISTING Unit Industries credentials")
    print_info("(These are already in your Render env vars)")
    print()

    # Supabase
    print("--- Supabase (Company Operational Database) ---")
    supabase_url = input("SUPABASE_URL: ").strip()
    supabase_anon_key = getpass.getpass("SUPABASE_ANON_KEY: ").strip()
    supabase_service_key = getpass.getpass("SUPABASE_SERVICE_KEY: ").strip()

    # Neo4j
    print("\n--- Neo4j (Knowledge Graph) ---")
    neo4j_uri = input("NEO4J_URI: ").strip()
    neo4j_user = input("NEO4J_USER (default: neo4j): ").strip() or "neo4j"
    neo4j_password = getpass.getpass("NEO4J_PASSWORD: ").strip()

    # Qdrant
    print("\n--- Qdrant (Vector Store) ---")
    qdrant_url = input("QDRANT_URL: ").strip()
    qdrant_api_key = getpass.getpass("QDRANT_API_KEY (or press ENTER if none): ").strip() or None
    qdrant_collection = input("QDRANT_COLLECTION_NAME: ").strip()

    # Redis
    print("\n--- Redis (Job Queue) ---")
    redis_url = input("REDIS_URL: ").strip()

    # OpenAI
    print("\n--- OpenAI ---")
    openai_key = getpass.getpass("OPENAI_API_KEY: ").strip()

    # Nango
    print("\n--- Nango (OAuth) ---")
    nango_secret = getpass.getpass("NANGO_SECRET_KEY: ").strip()
    nango_public = input("NANGO_PUBLIC_KEY: ").strip()
    nango_gmail = input("NANGO_PROVIDER_KEY_GMAIL: ").strip()
    nango_outlook = input("NANGO_PROVIDER_KEY_OUTLOOK: ").strip()
    nango_drive = input("NANGO_PROVIDER_KEY_GOOGLE_DRIVE: ").strip()

    # Admin PIN
    print("\n--- Admin Dashboard ---")
    admin_pin = input("Current admin PIN (default: 2525): ").strip() or "2525"
    admin_pin_hash = hash_password(admin_pin)

    try:
        master.table("company_deployments").insert({
            "company_id": company_id,
            "supabase_url": supabase_url,
            "supabase_anon_key": supabase_anon_key,
            "supabase_service_key": supabase_service_key,
            "neo4j_uri": neo4j_uri,
            "neo4j_user": neo4j_user,
            "neo4j_password": neo4j_password,
            "qdrant_url": qdrant_url,
            "qdrant_api_key": qdrant_api_key,
            "qdrant_collection_name": qdrant_collection,
            "redis_url": redis_url,
            "openai_api_key": openai_key,
            "nango_secret_key": nango_secret,
            "nango_public_key": nango_public,
            "nango_provider_key_gmail": nango_gmail,
            "nango_provider_key_outlook": nango_outlook,
            "nango_provider_key_google_drive": nango_drive,
            "admin_pin_hash": admin_pin_hash
        }).execute()

        print_success("Saved deployment credentials")
    except Exception as e:
        print_error(f"Failed to save deployment config: {e}")
        sys.exit(1)

    # ========================================================================
    # Step 5: Add Team Members
    # ========================================================================
    print_header("Step 5: Adding Unit Industries Team")

    team_members = [
        {"name": "Anthony Codet", "title": "President & CEO", "role_description": "Primary decision-maker, lead engineer, oversees all operations", "reports_to": None},
        {"name": "Kevin Trainor", "title": "VP/Sales", "role_description": "Customer relationships, ISO 9001 audits, supervises key employees", "reports_to": "Anthony Codet"},
        {"name": "Sandra", "title": "Head of QA", "role_description": "Works with Ramiro & Hayden, prepares CoC and FOD docs", "reports_to": "Kevin/Tony/Ramiro/Hayden"},
        {"name": "Ramiro", "title": "Production & Shipping Manager/Material Buyer", "role_description": "Oversees production, shipping, procurement for SCP/SMC", "reports_to": "Anthony Codet"},
        {"name": "Paul", "title": "Head of Accounting & Finance", "role_description": "Invoicing, financial reporting, material deliveries", "reports_to": "Anthony Codet"},
        {"name": "Hayden", "title": "Customer Service Lead/Operations Support", "role_description": "Supports all departments, customer comms, production tracking", "reports_to": None}
    ]

    try:
        for member in team_members:
            master.table("company_team_members").insert({
                "company_id": company_id,
                **member
            }).execute()

        print_success(f"Added {len(team_members)} team members")
    except Exception as e:
        print_error(f"Failed to add team members: {e}")
        sys.exit(1)

    # ========================================================================
    # Step 6: Log Setup Action
    # ========================================================================
    try:
        master.table("audit_log_global").insert({
            "company_id": company_id,
            "admin_id": admin_id,
            "action": "create_company",
            "resource_type": "company",
            "resource_id": str(company_id),
            "details": {
                "source": "setup_script",
                "note": "Initial setup of Unit Industries in master control plane"
            },
            "ip_address": "127.0.0.1"
        }).execute()
    except:
        pass  # Non-critical

    # ========================================================================
    # Step 7: Verify Setup
    # ========================================================================
    print_header("Step 7: Verification")

    # Check company
    company = master.table("companies").select("*").eq("id", company_id).single().execute()
    print_success(f"Company: {company.data['name']} ({company.data['slug']})")

    # Check team
    team = master.table("company_team_members").select("name").eq("company_id", company_id).execute()
    print_success(f"Team members: {len(team.data)}")

    # Check deployment
    deployment = master.table("company_deployments").select("id").eq("company_id", company_id).single().execute()
    print_success("Deployment config saved")

    # Check admin
    admin = master.table("master_admins").select("email").eq("id", admin_id).single().execute()
    print_success(f"Admin account: {admin.data['email']}")

    # ========================================================================
    # Success!
    # ========================================================================
    print_header("Setup Complete!")

    print_success("Master control plane is ready!")
    print()
    print_info("Next steps:")
    print("  1. Add these to your Unit Industries Render env vars:")
    print(f"     COMPANY_ID={company_id}")
    print(f"     MASTER_SUPABASE_URL={master_url}")
    print(f"     MASTER_SUPABASE_SERVICE_KEY=<your-service-key>")
    print()
    print("  2. Add these to your local .env for testing:")
    print(f"     COMPANY_ID={company_id}")
    print(f"     MASTER_SUPABASE_URL={master_url}")
    print(f"     MASTER_SUPABASE_SERVICE_KEY=<your-service-key>")
    print()
    print("  3. Build and deploy the master admin dashboard (coming next)")
    print()
    print_info("Master admin login:")
    print(f"  Email: {admin_email}")
    print(f"  Password: <what you entered>")
    print()
    print("🎉 You're all set!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
