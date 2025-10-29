#!/usr/bin/env python3
"""
Migrate Default Schemas and Company Info to Master Supabase
"""

import os
from supabase import create_client

# Master Supabase - from env vars
MASTER_URL = os.getenv("MASTER_SUPABASE_URL")
MASTER_KEY = os.getenv("MASTER_SUPABASE_SERVICE_KEY")
COMPANY_ID = os.getenv("COMPANY_ID")

if not MASTER_URL or not MASTER_KEY or not COMPANY_ID:
    print("❌ Error: Missing required environment variables!")
    print("   Please set:")
    print("   - MASTER_SUPABASE_URL")
    print("   - MASTER_SUPABASE_SERVICE_KEY")
    print("   - COMPANY_ID")
    exit(1)

# Default entity types for Unit Industries
DEFAULT_SCHEMAS = [
    {
        "override_type": "entity",
        "entity_type": "PERSON",
        "description": "Employees, contacts, account managers, suppliers"
    },
    {
        "override_type": "entity",
        "entity_type": "COMPANY",
        "description": "Clients, suppliers, vendors, partners"
    },
    {
        "override_type": "entity",
        "entity_type": "ROLE",
        "description": "Job titles: VP Sales, Quality Engineer, Procurement Manager, Account Manager"
    },
    {
        "override_type": "entity",
        "entity_type": "PURCHASE_ORDER",
        "description": "Purchase orders, invoices, PO numbers"
    },
    {
        "override_type": "entity",
        "entity_type": "MATERIAL",
        "description": "Raw materials: polycarbonate, resins, steel, pellets, components"
    },
    {
        "override_type": "entity",
        "entity_type": "CERTIFICATION",
        "description": "ISO certs, material certifications, quality certifications"
    },
]

# Correct Unit Industries company info
COMPANY_INFO = {
    "company_description": "Progressive plastic injection molding company specializing in innovative manufacturing solutions. Over a century of combined experience in integrated connectors, high-temp thermoplastics, printed circuitry, wire harnessing, and electro/mechanical assembly. Class 100,000 Clean Room facility (4,800 sq ft) for medical molding.",
    "company_location": "Santa Ana, CA",
    "industries_served": [
        "Communications",
        "Medical",
        "Defense/Aerospace",
        "Industrial/Semiconductor",
        "Multimedia",
        "Automotive",
        "Clean Technology"
    ],
    "key_capabilities": [
        "Integrated Connectors",
        "High-Temp Thermoplastics",
        "Printed Circuitry",
        "Wire Harnessing",
        "Electro/Mechanical Assembly",
        "Medical Molding",
        "Clean Room Manufacturing"
    ],
    "primary_contact_email": "nicolas@highforce.ai",
    "primary_contact_name": "Anthony Codet",
    "backend_url": "https://nango-connection-only.onrender.com",
    "frontend_url": "https://connectorfrontend.vercel.app"
}

# Team members
TEAM_MEMBERS = [
    {
        "name": "Anthony Codet",
        "title": "President & CEO",
        "role_description": "Primary decision-maker, lead engineer, oversees all operations",
        "reports_to": None,
        "email": "nicolas@highforce.ai"
    },
    {
        "name": "Kevin Trainor",
        "title": "VP/Sales",
        "role_description": "Customer relationships, ISO 9001 audits, supervises key employees",
        "reports_to": "Anthony Codet",
        "email": None
    },
    {
        "name": "Mike Jones",
        "title": "Operations Manager",
        "role_description": "Production oversight, equipment maintenance, quality control",
        "reports_to": "Anthony Codet",
        "email": None
    }
]


def main():
    print("=" * 80)
    print("  Migrating to Master Supabase Schemas")
    print("=" * 80)
    print()

    master = create_client(MASTER_URL, MASTER_KEY)

    # Step 1: Update company info
    print("Step 1: Updating Unit Industries company info...")
    try:
        master.table("companies")\
            .update(COMPANY_INFO)\
            .eq("id", COMPANY_ID)\
            .execute()
        print("✅ Company info updated")
        print(f"   Description: {COMPANY_INFO['company_description'][:80]}...")
        print(f"   Location: {COMPANY_INFO['company_location']}")
        print(f"   Contact: {COMPANY_INFO['primary_contact_email']}")
        print(f"   Backend: {COMPANY_INFO['backend_url']}")
        print(f"   Frontend: {COMPANY_INFO['frontend_url']}")
    except Exception as e:
        print(f"❌ Failed to update company: {e}")
        return

    print()

    # Step 2: Insert default schemas
    print("Step 2: Inserting default schemas...")
    for schema in DEFAULT_SCHEMAS:
        try:
            # Check if already exists
            existing = master.table("company_schemas")\
                .select("id")\
                .eq("company_id", COMPANY_ID)\
                .eq("entity_type", schema["entity_type"])\
                .execute()

            if existing.data:
                print(f"⚠️  {schema['entity_type']} already exists, skipping")
                continue

            # Insert
            master.table("company_schemas").insert({
                "company_id": COMPANY_ID,
                **schema,
                "created_by": "system",
                "is_active": True
            }).execute()

            print(f"✅ Added {schema['entity_type']}: {schema['description']}")

        except Exception as e:
            print(f"❌ Failed to add {schema['entity_type']}: {e}")

    print()

    # Step 3: Update team members
    print("Step 3: Updating team members...")
    for member in TEAM_MEMBERS:
        try:
            # Check if exists
            existing = master.table("company_team_members")\
                .select("id")\
                .eq("company_id", COMPANY_ID)\
                .eq("name", member["name"])\
                .execute()

            if existing.data:
                # Update
                master.table("company_team_members")\
                    .update(member)\
                    .eq("id", existing.data[0]["id"])\
                    .execute()
                print(f"✅ Updated {member['name']} - {member['title']}")
            else:
                # Insert
                master.table("company_team_members").insert({
                    "company_id": COMPANY_ID,
                    **member,
                    "is_active": True
                }).execute()
                print(f"✅ Added {member['name']} - {member['title']}")

        except Exception as e:
            print(f"❌ Failed to update {member['name']}: {e}")

    print()
    print("=" * 80)
    print("  ✅ Migration Complete!")
    print("=" * 80)
    print()
    print("Next steps:")
    print("1. Restart Unit Industries backend on Render")
    print("2. Check logs for:")
    print("   '✅ Loaded 6 custom entities for this company: [PERSON, COMPANY, ...]'")
    print("3. Default schemas are now in master Supabase!")
    print()


if __name__ == "__main__":
    main()
