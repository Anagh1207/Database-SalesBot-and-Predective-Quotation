import os
import time
from groq import Groq
from dotenv import load_dotenv
from app.config import settings
from app.logger import get_logger

load_dotenv()
logger = get_logger("llm_client")

# ── GROQ CLIENT ────────────────────────────────────────────────────────────
# Initialised once and reused for every request
_client = None


def get_client() -> Groq:
    """
    Returns the Groq client.
    Initialised once — reused on every call.
    """
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY") or settings.GROQ_API_KEY
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY not found. "
                "Add it to your .env file: GROQ_API_KEY=gsk_..."
            )
        _client = Groq(api_key=api_key)
        logger.info("✅ Groq client initialised")
    return _client


def call_llm(
    system_prompt: str,
    user_message: str,
    model: str = None,
    max_tokens: int = None,
    temperature: float = None,
    retries: int = 3,
    retry_delay: float = 2.0,
) -> str:
    """
    Sends a prompt to Groq and returns the response text.

    Parameters:
        system_prompt  — tells the LLM who it is and how to behave
        user_message   — the actual question + context
        model          — which Groq model to use (default from config)
        max_tokens     — max length of response (default from config)
        temperature    — creativity 0.0=focused, 1.0=creative (default from config)
        retries        — how many times to retry on failure
        retry_delay    — seconds to wait between retries

    Returns the LLM response as a plain string.
    """
    model = model or settings.GROQ_MODEL
    max_tokens = max_tokens or settings.GROQ_MAX_TOKENS
    temperature = temperature if temperature is not None else settings.GROQ_TEMPERATURE

    client = get_client()

    # ── RETRY LOOP ─────────────────────────────────────────────────────────
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"Calling Groq — model: {model} — attempt {attempt}/{retries}")
            start = time.time()

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )

            elapsed = round(time.time() - start, 3)
            answer = response.choices[0].message.content

            logger.info(
                f"✅ Groq response received — "
                f"{len(answer)} chars — {elapsed}s"
            )
            return answer

        except Exception as e:
            last_error = e
            logger.warning(f"Groq attempt {attempt} failed: {str(e)}")
            if attempt < retries:
                logger.info(f"Retrying in {retry_delay}s...")
                time.sleep(retry_delay)

    # ── ALL RETRIES FAILED ─────────────────────────────────────────────────
    logger.error(f"All {retries} Groq attempts failed. Last error: {last_error}")
    raise RuntimeError(
        f"Groq API failed after {retries} attempts: {str(last_error)}"
    )


def test_connection() -> bool:
    """
    Quick test to verify Groq API key and connection work.
    Returns True if working, False if not.
    """
    try:
        response = call_llm(
            system_prompt="You are a helpful assistant.",
            user_message="Reply with exactly: CONNECTION OK",
            max_tokens=10,
        )
        logger.info(f"Groq connection test: {response.strip()}")
        return True
    except Exception as e:
        logger.error(f"Groq connection test failed: {str(e)}")
        return False