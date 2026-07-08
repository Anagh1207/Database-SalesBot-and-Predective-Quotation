"""
Session ID middleware for CertIQ FastAPI app.

THE CORE PROBLEM THIS SOLVES:
Every multi-turn flow (estimation, KNN) requires the same session_id
across all turns of a conversation. If the FastAPI route generates a
new ID per request (e.g. uuid4() each time), sessions are lost and
questions repeat forever.

HOW TO USE:
Replace whatever you currently pass as session_id in your route with
get_session_id(request). This reads from a cookie, creates one if missing,
and the cookie persists across all requests in the same browser session.

In your FastAPI route:
    from app.session_middleware import get_session_id

    @router.post("/chat")
    async def chat_endpoint(request: Request, body: ChatRequest):
        session_id = get_session_id(request)
        response_data = chat(query=body.message, session_id=session_id)
        
        response = JSONResponse(content=response_data)
        set_session_cookie(response, session_id)
        return response

If you're using WebSockets or a React frontend that manages its own
session (e.g. localStorage), pass that ID directly from the frontend
in the request body instead.
"""

import uuid
from fastapi import Request
from fastapi.responses import JSONResponse


SESSION_COOKIE_NAME = "certiq_session_id"
SESSION_COOKIE_MAX_AGE = 60 * 60 * 8  # 8 hours


def get_session_id(request: Request) -> str:
    """
    Returns a stable session_id for this browser session.
    Priority:
    1. Body field 'session_id' (if frontend sends it explicitly)
    2. Cookie (persistent across page reloads)
    3. Header 'X-Session-ID'
    4. Generate new UUID (first visit)
    """
    # Check cookie first — most reliable for browser clients
    cookie_id = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie_id:
        return cookie_id

    # Check header (useful for API clients / Postman)
    header_id = request.headers.get("X-Session-ID")
    if header_id:
        return header_id

    # Generate new — will be set as cookie in response
    return str(uuid.uuid4())


def set_session_cookie(response: JSONResponse, session_id: str) -> None:
    """
    Sets the session cookie on the response so the next request
    from this browser automatically carries the same session_id.
    """
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=SESSION_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )