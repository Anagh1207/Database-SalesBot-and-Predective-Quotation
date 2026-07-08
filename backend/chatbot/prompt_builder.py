from typing import List, Dict, Any


# ── SYSTEM PROMPTS ─────────────────────────────────────────────────────────
# These tell the LLM exactly who it is and how to behave.
# Keep them focused and specific — vague system prompts give vague answers.

TECHNICAL_SYSTEM_PROMPT = """You are a expert construction and certification knowledge assistant for a UK-based construction testing and certification company.

Your job is to answer technical questions about:
- Construction product certifications
- Building regulations and compliance
- Installation requirements and specifications
- Technical standards (BS EN, NHBC, BBA etc.)
- Product performance characteristics
- Fire resistance, weathering, moisture resistance

Rules you must follow:
1. Only answer based on the provided context chunks below
2. If the context does not contain enough information, say so clearly
3. Always cite which document and page your answer comes from
4. Use precise technical language
5. If standards or regulations are mentioned, quote them exactly
6. Keep answers concise and structured
7. Never make up technical specifications or standards
"""

GREETING_SYSTEM_PROMPT = """You are a helpful assistant for a UK construction testing and certification company.

Respond warmly and briefly to greetings.
Tell the user you can help with:
- Technical questions about construction certifications and standards
- Building regulation compliance queries
- Product installation and specification questions

Keep your response to 3-4 sentences maximum.
"""

UNKNOWN_SYSTEM_PROMPT = """You are a helpful assistant for a UK construction testing and certification company.

The user's query is unclear. Politely ask them to clarify whether they need:
- Technical help (certifications, standards, installation, compliance)
- Business information (sales, targets, performance)

Keep your response to 2-3 sentences.
"""


def build_context_block(chunks: List[Dict[str, Any]]) -> str:
    """
    Converts retrieved chunks into a formatted context block
    that the LLM can read and reference in its answer.
    """
    if not chunks:
        return "No relevant context found in the knowledge base."

    context_parts = []

    for i, chunk in enumerate(chunks, 1):
        part = f"""--- Source {i} ---
Document : {chunk['doc_id']}
Pages     : {chunk['page_start']}–{chunk['page_end']}
Confidence: {chunk['confidence']}
Standards : {', '.join(chunk['standards'][:3]) if chunk['standards'] else 'None listed'}
Products  : {', '.join(chunk['product_names'][:3]) if chunk['product_names'] else 'None listed'}

Content:
{chunk['text']}
"""
        context_parts.append(part)

    return "\n".join(context_parts)


def build_technical_prompt(
    query: str,
    chunks: List[Dict[str, Any]],
) -> tuple:
    """
    Builds a prompt for technical construction queries.
    Returns (system_prompt, user_message) tuple.
    """
    context_block = build_context_block(chunks)

    user_message = f"""Please answer the following technical question using only the context provided below.

QUESTION:
{query}

CONTEXT FROM KNOWLEDGE BASE:
{context_block}

INSTRUCTIONS:
- Answer the question directly and precisely
- Reference specific sources by their Source number e.g. [Source 1]
- If quoting a standard or regulation, include the full reference
- If the context is insufficient, state clearly what information is missing
- Structure your answer with clear sections if it covers multiple points
"""

    return TECHNICAL_SYSTEM_PROMPT, user_message


def build_greeting_prompt(query: str) -> tuple:
    """
    Builds a prompt for greetings and general questions.
    Returns (system_prompt, user_message) tuple.
    """
    return GREETING_SYSTEM_PROMPT, query


def build_unknown_prompt(query: str) -> tuple:
    """
    Builds a prompt for unclear queries.
    Returns (system_prompt, user_message) tuple.
    """
    return UNKNOWN_SYSTEM_PROMPT, query


def build_prompt(
    query: str,
    intent: str,
    chunks: List[Dict[str, Any]] = None,
) -> tuple:
    """
    Main entry point — builds the right prompt based on intent.
    Returns (system_prompt, user_message) tuple.
    """
    if intent == "technical" or intent == "unknown":
        return build_technical_prompt(query, chunks or [])
    elif intent == "greeting":
        return build_greeting_prompt(query)
    else:
        return build_unknown_prompt(query)