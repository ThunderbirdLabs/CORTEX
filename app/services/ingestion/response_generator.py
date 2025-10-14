"""
Response Generation - Creates conversational AI responses from search results
"""
import os
from typing import List, Dict
from openai import OpenAI


# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def generate_conversational_response(
    query: str,
    vector_results: List[Dict],
    graph_results: List[Dict],
    conversation_history: List[Dict] = []
) -> str:
    """
    Generate a conversational AI response using search results and conversation history

    This implements the RAG (Retrieval-Augmented Generation) pattern:
    1. Retrieve relevant context from vector DB and knowledge graph
    2. Combine with conversation history
    3. Generate natural language response with LLM

    Args:
        query: The user's original question
        vector_results: Document chunks from vector search
        graph_results: Facts and relationships from knowledge graph
        conversation_history: Previous conversation messages

    Returns:
        str: Natural language response from the AI assistant
    """
    # Build context from search results
    context_parts = []

    if vector_results:
        context_parts.append("DOCUMENT CONTENT:")
        for i, result in enumerate(vector_results[:3], 1):
            doc_name = result.get('document_name', 'Unknown')
            source = result.get('source', 'Unknown')
            content = result.get('content', '')[:300]
            context_parts.append(f"{i}. From {doc_name} ({source}): {content}")

    if graph_results:
        context_parts.append("\nKNOWLEDGE GRAPH FACTS:")
        for i, result in enumerate(graph_results[:5], 1):
            fact = result.get('fact', '')
            context_parts.append(f"{i}. {fact}")

    context = "\n".join(context_parts)

    # Build messages array with conversation history
    system_prompt = """You are a helpful AI assistant with access to a company's knowledge base.
Your job is to answer questions using the provided context from documents and knowledge graph.

Guidelines:
- Be conversational and natural
- Remember and reference previous parts of the conversation
- Answer directly and concisely
- Use specific details from the context
- If the context doesn't contain relevant information, say so politely
- For greetings or small talk, respond naturally without forcing document references
- When user refers to "this document" or "that person", use conversation history to understand what they mean
- Cite sources when providing specific information (e.g., "According to the MedTech proposal...")"""

    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history (last 10 messages = 5 exchanges)
    for msg in conversation_history[-10:]:
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    # Add current query with context
    user_prompt = f"""Question: {query}

Context from knowledge base:
{context}

Provide a helpful, conversational response based on this context and our previous conversation."""

    messages.append({"role": "user", "content": user_prompt})

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content

    except Exception as e:
        error_msg = f"I found some relevant information but had trouble generating a response. Error: {str(e)}"
        print(f"⚠️  Response generation failed: {str(e)}")
        return error_msg
