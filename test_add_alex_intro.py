"""
Test script to add Alex's introduction document and see chunk nodes created in Neo4j
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.ingestion.llamaindex import UniversalIngestionPipeline

async def main():
    print("🚀 Initializing UniversalIngestionPipeline...")
    pipeline = UniversalIngestionPipeline()

    document_text = """Subject: Cortex Company Update - Q4 2024

Hello team,

I'm Alex Kashkarian, and I founded Cortex in January 2024 to revolutionize enterprise knowledge management. I wanted to share an important company update covering our recent progress, team expansion, and upcoming initiatives.

COMPANY OVERVIEW:
Cortex is a hybrid RAG (Retrieval-Augmented Generation) search system that combines retrieval-based methods with generative AI capabilities. We're currently working with three major clients: Acme Corporation, TechVentures Inc, and GlobalSoft Solutions. Acme Corporation is our largest client, while we also serve as a vendor for DataFlow Systems, providing them with our API integration tools.

TEAM & ORGANIZATION:
Our team has grown significantly. Sarah Chen recently joined as our VP of Engineering and reports directly to me. She works closely with Michael Rodriguez, our Senior ML Engineer, who is leading the development of our new semantic search features. Jessica Park, our Head of Product, is collaborating with Sarah on the Q4 roadmap.

I'm also pleased to introduce our very first employees - Chloe, a dedicated bomb-sniffing dog, and Sprinkles, a charming cat. While they may spend most of their time napping, they bring invaluable joy to our office culture.

CURRENT PROJECTS & DEALS:
We have several exciting deals in progress. The Enterprise AI Deal with Acme Corporation was created by Sarah and is assigned to Michael for technical implementation. This deal relates to our Machine Learning Infrastructure topic and requires completion of the API Integration Task before we can move forward.

Jessica created the Product Roadmap Q4 document last week, which mentions both the semantic search improvements and our new vector database architecture. This document is attached to the email she sent to the entire engineering team on Monday.

MEETINGS & EVENTS:
Last Tuesday, we held our Q4 Planning Meeting about the enterprise expansion strategy. Sarah, Michael, and Jessica all attended this meeting. The meeting followed up on our previous Strategy Session from September and relates to our long-term growth plans.

We're also planning to attend the AI Summit 2024 conference next month. This event is about artificial intelligence and enterprise applications, and I've assigned Michael the task of preparing our demo presentation for the conference.

FINANCIAL UPDATE:
We recently received our Series A payment from Sequoia Ventures, which was paid to Cortex. We also paid our Q4 consulting fees to DataFlow Systems for their integration support. The payment relates to our infrastructure expansion topic.

TASKS & ACTION ITEMS:
I've created several critical tasks for the team:
- The API Integration Task, which Michael is assigned to complete. This task requires the Technical Specification Document to be finished first.
- The Security Audit Task, assigned to Sarah, which resolves our compliance concerns and relates to the enterprise security topic.
- The Documentation Update Task is about improving our developer documentation and relates to the API Integration Task.

The Security Audit Task follows up on the compliance email we received from our legal team last week. That email mentioned several security requirements and relates to our enterprise clients' needs.

PARTNERSHIPS & COLLABORATIONS:
We're excited to announce a partnership where Cortex works with OpenAI Labs on advanced RAG techniques. Additionally, TechVentures Inc is a client of GlobalSoft Solutions, creating an interesting network effect for our platform.

DOCUMENTS & RESOURCES:
Sarah created the Technical Architecture Document, which is about our system design and mentions the vector database and knowledge graph components. This document is attached to the Product Requirements Document that Jessica prepared. Both documents relate to the Machine Learning Infrastructure topic.

UPCOMING MILESTONES:
The Product Launch Event is scheduled for December 15th and will be about our new enterprise features. This event mentions our partnership with Acme Corporation and relates to our go-to-market strategy.

FOLLOW-UPS:
The Q4 Planning Meeting will be followed by a Strategy Review Meeting next month. The API Integration Task, once completed, will resolve the Technical Debt Task that has been pending. The Enterprise AI Deal follows up on the initial sales meeting we had with Acme Corporation in August.

I'm incredibly proud of what we've built and excited about where we're headed. The combination of our talented team, strong client relationships, and innovative technology positions us well for continued growth.

Looking forward to an amazing Q4!

Best regards,
Alex Kashkarian
Founder & CEO, Cortex
alex@cortex.ai"""

    # Create a fake document row (simulating Supabase structure)
    document_row = {
        "id": "test-alex-intro-001",
        "name": "Alex's Introduction to Cortex",
        "mime_type": "text/plain",
        "file_path": "test/alex_intro.txt",
        "content": document_text,
        "document_type": "googledoc",
        "source": "test"
    }

    print("\n" + "="*80)
    print("📄 INGESTING ALEX'S INTRODUCTION")
    print("="*80)
    print(f"Document: {document_row['name']}")
    print(f"Length: {len(document_text)} characters")
    print("="*80 + "\n")

    # Ingest the document with entity extraction enabled
    result = await pipeline.ingest_document(
        document_row=document_row,
        extract_entities=True
    )

    print("\n" + "="*80)
    print("✅ INGESTION COMPLETE")
    print("="*80)
    print(f"Status: {result.get('status')}")
    print(f"Document ID: {result.get('document_id')}")
    print(f"Vector nodes: {result.get('vector_nodes', 0)}")
    print(f"Graph nodes: {result.get('graph_nodes', 0)}")
    print("="*80)

    print("\n🔍 Now run: python3 test_chunk_nodes.py")
    print("   To see the Chunk nodes and MENTIONS relationships in Neo4j!")

if __name__ == "__main__":
    asyncio.run(main())
