"""LLM + embedding helpers with a pluggable backend switch.

Default path is Ollama (local, free, no API key). gemini / openai are optional.
"""
import json
import os
import re

import config

# ---------------------------------------------------------------------------
# Embeddings (sentence-transformers, all-MiniLM-L6-v2 -> 384 dims)
# ---------------------------------------------------------------------------
_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer(config.EMBEDDING_MODEL)
    return _embedder


def embed(texts):
    """Embed a list of strings -> list of 384-dim float vectors."""
    model = _get_embedder()
    vectors = model.encode(list(texts), normalize_embeddings=True)
    return [v.tolist() for v in vectors]


# ---------------------------------------------------------------------------
# JSON extraction helper (be forgiving of stray prose / fences)
# ---------------------------------------------------------------------------
def _extract_json(text):
    text = text.strip()
    # strip markdown fences if present
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # fall back to first balanced {...} or [...] block
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end != -1 and end > start:
            snippet = text[start : end + 1]
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                continue
    raise ValueError(f"Could not parse JSON from model output: {text[:500]!r}")


# ---------------------------------------------------------------------------
# chat()
# ---------------------------------------------------------------------------
JSON_INSTRUCTION = "Output ONLY valid JSON, no markdown fences."


def chat(system, user, json=True, temperature=0.1):
    """Call the configured LLM backend.

    If json=True -> returns a parsed dict (or list). Else -> returns a string.
    """
    backend = config.MINUTEMIND_BACKEND.lower()
    sys_prompt = system
    if json:
        sys_prompt = f"{system}\n\n{JSON_INSTRUCTION}"

    if backend == "ollama":
        raw = _chat_ollama(sys_prompt, user, json, temperature)
    elif backend == "gemini":
        raw = _chat_gemini(sys_prompt, user, json, temperature)
    elif backend == "groq":
        raw = _chat_groq(sys_prompt, user, json, temperature)
    elif backend == "openai":
        raw = _chat_openai(sys_prompt, user, json, temperature)
    else:
        raise ValueError(f"Unknown MINUTEMIND_BACKEND: {backend}")

    if json:
        return _extract_json(raw)
    return raw


def _chat_ollama(system, user, json_mode, temperature):
    import ollama

    kwargs = {
        "model": config.MINUTEMIND_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {"temperature": temperature},
    }
    if json_mode:
        kwargs["format"] = "json"
    resp = ollama.chat(**kwargs)
    return resp["message"]["content"]


def _chat_gemini(system, user, json_mode, temperature):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        response_mime_type="application/json" if json_mode else "text/plain",
    )
    resp = client.models.generate_content(
        model=model_name, contents=user, config=config
    )
    return resp.text


def _chat_groq(system, user, json_mode, temperature):
    from groq import Groq

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    kwargs = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content


def _chat_openai(system, user, json_mode, temperature):
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    kwargs = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content
