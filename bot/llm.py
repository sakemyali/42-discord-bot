from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """You are an assistant for 42Tokyo students. Answer questions \
strictly using the provided context. Rules:

1. If the context does not contain enough information to answer, reply exactly: \
"I do not have enough information to answer that. Escalating to staff."
2. Do not invent rules, deadlines, or policies that are not in the context.
3. Keep answers under 5 sentences. Be direct.
4. Cite the source filenames inline like [source.md]."""


@dataclass
class LLMReply:
    text: str
    used_llm: bool


def _format_context(contexts: list[tuple[str, str]]) -> str:
    blocks = []
    for source, text in contexts:
        blocks.append(f"=== {source} ===\n{text}")
    return "\n\n".join(blocks)


def fallback_answer(contexts: list[tuple[str, str]]) -> LLMReply:
    if not contexts:
        return LLMReply(
            text="I do not have enough information to answer that.",
            used_llm=False,
        )
    parts = []
    for source, text in contexts[:3]:
        snippet = text.strip().replace("\n\n", "\n")
        if len(snippet) > 600:
            snippet = snippet[:600].rstrip() + "..."
        parts.append(f"**{source}**\n{snippet}")
    return LLMReply(text="\n\n".join(parts), used_llm=False)


async def answer(
    question: str,
    contexts: list[tuple[str, str]],
) -> LLMReply:
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key or not contexts:
        return fallback_answer(contexts)
    model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    prompt = (
        f"Context:\n{_format_context(contexts)}\n\n"
        f"Question: {question}\n\nAnswer:"
    )
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 400,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()
            return LLMReply(text=text, used_llm=True)
    except Exception:
        return fallback_answer(contexts)
