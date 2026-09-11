"""Small deterministic retrieval service with Gemini generation used by Shagara API.
"""
from __future__ import annotations

import os
import re
import json
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env", override=True)
load_dotenv(ROOT / "backend" / ".env", override=True)
load_dotenv(override=True)

DATA_DIR = ROOT / "rag_demo_data"
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/tmp/shagara_uploads" if os.getenv("VERCEL") else str(DATA_DIR)))
VECTOR_DIR = ROOT / "backend" / "data" / "vector_store"
INDEX_PATH = VECTOR_DIR / "index.json"
ABSTAIN = "I couldn't find this information in the available documents."


@dataclass(frozen=True)
class Passage:
    document: str
    tenant: str
    access: str
    text: str
    section: str
    page: int = 1


def _read_passages() -> list[Passage]:
    specs = {
        "rooftop_growing.md": ("shagara", "all"),
        "irrigation_playbook.md": ("shagara", "all"),
        "pest_field_notes.md": ("shagara", "all"),
        "community_standards.md": ("shagara", "members"),
        "other_workspace.md": ("othergarden", "all"),
    }
    out: list[Passage] = []
    for name, (tenant, access) in specs.items():
        path = DATA_DIR / name
        if not path.exists():
            continue
        section = ""
        lines: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                if lines:
                    out.append(Passage(name, tenant, access, " ".join(lines).strip(), section))
                    lines = []
                section = line[3:].strip()
            elif line.startswith("# "):
                section = line[2:].strip()
            elif line.strip():
                lines.append(line.strip())
        if lines:
            out.append(Passage(name, tenant, access, " ".join(lines).strip(), section))
    return out


def _tokens(value: str) -> set[str]:
    stopwords = {
        "a", "an", "and", "are", "be", "can", "do", "for", "from", "how",
        "i", "in", "is", "it", "me", "my", "of", "on", "or", "our", "the",
        "this", "to", "was", "we", "what", "when", "where", "which", "who",
        "why", "with", "you", "your", "did", "does", "have", "has", "about",
    }
    return {x.lower() for x in re.findall(r"[\w\u0600-\u06ff]+", value) if x.lower() not in stopwords}


def _classify(q: str) -> str:
    l = q.lower()
    if any(x in l for x in ("how many orders", "last month", "stock price", "revenue")):
        return "analytical"
    if l.strip() in {"hello", "hi", "hey", "thanks", "thank you"}:
        return "chitchat"
    if any(x in l for x in ("compare", "difference between", "changed from")):
        return "multi_hop"
    return "document"


class Retriever:
    def __init__(self) -> None:
        self.passages = _read_passages()

    def search(self, question: str, tenant: str, access: list[str], limit: int = 4) -> list[tuple[Passage, float]]:
        query = _tokens(question)
        rows: list[tuple[Passage, float]] = []
        for p in self.passages:
            if p.tenant != tenant or p.access not in access:
                continue
            words = _tokens(p.text + " " + p.section)
            overlap = len(query & words)
            score = overlap / max(len(query), 1)
            if p.section and p.section.lower() in question.lower():
                score += 0.25
            if score > 0:
                rows.append((p, min(score, 1.0)))
        return sorted(rows, key=lambda x: x[1], reverse=True)[:limit]

    @staticmethod
    def answer(question: str, rows: list[tuple[Passage, float]]) -> str:
        if not rows:
            return ABSTAIN
        qwords = _tokens(question)
        snippets = []
        for p, _ in rows[:3]:
            sentences = re.split(r"(?<=[.!?])\s+", p.text)
            chosen = [s for s in sentences if qwords & _tokens(s)] or sentences[:1]
            snippets.append(" ".join(chosen[:2]))
        return " ".join(snippets)

    async def generate(self, question: str, context: str) -> str | None:
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            prompt = (
                "You are Shagara, an expert botanical and rooftop gardening assistant for Cairo, Egypt.\n"
                "Answer the user's question clearly, practically, and conversationally based ONLY on the provided context passages.\n"
                "Always cite the source markers (e.g. [S1], [S2]) directly in your answer when making recommendations.\n"
                "Keep your answer focused and helpful for urban rooftop growers in Egypt.\n\n"
                f"CONTEXT PASSAGES:\n{context}\n\n"
                f"USER QUESTION: {question}"
            )
            models_to_try = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-flash-latest"]
            for model_name in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.post(
                            url,
                            params={"key": gemini_key},
                            json={"contents": [{"parts": [{"text": prompt}]}]}
                        )
                        if response.status_code == 200:
                            candidates = response.json().get("candidates", [])
                            if candidates and "content" in candidates[0]:
                                text = candidates[0]["content"]["parts"][0]["text"].strip()
                                if text:
                                    return text
                except Exception:
                    continue

        url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434") + "/api/generate"
        model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
        prompt = f"Answer only from this context and be concise.\nCONTEXT:\n{context}\nQUESTION: {question}"
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(url, json={"model": model, "prompt": prompt, "stream": False})
                response.raise_for_status()
                value = response.json().get("response", "").strip()
                return value or None
        except (httpx.HTTPError, ValueError):
            return None


def persist_index(passages: list[Passage]) -> None:
    payload = [{"document": p.document, "tenant": p.tenant, "access": p.access, "text": p.text, "section": p.section, "page": p.page,
                "id": hashlib.sha1(f"{p.document}:{p.section}:{p.text}".encode()).hexdigest()[:12]} for p in passages]
    try:
        VECTOR_DIR.mkdir(parents=True, exist_ok=True)
        INDEX_PATH.write_text(json.dumps({"version": 1, "embedding": "deterministic-lexical-v1", "chunk_size": 480, "overlap": 60, "passages": payload}, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass

retriever = Retriever()

def load_persisted_index() -> None:
    """Load the notebook artifact at startup; fall back only for a fresh clone."""
    if not INDEX_PATH.exists():
        persist_index(retriever.passages)
        return
    try:
        payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        rows = payload.get("passages", [])
        if rows:
            retriever.passages = [Passage(r["document"], r["tenant"], r["access"], r["text"], r.get("section", "General"), r.get("page", 1)) for r in rows]
    except (OSError, ValueError, KeyError, TypeError):
        persist_index(retriever.passages)

load_persisted_index()


async def query(question: str, tenant: str = "shagara", access: list[str] = ["all"], use_ollama: bool = False) -> dict[str, Any]:
    query_type = _classify(question)
    if query_type == "analytical":
        return {"answer": "This looks like a question about structured data rather than documents. Routing to the analytics/SQL path.", "query_type": query_type, "flags": ["routed_to_sql"], "abstained": False}
    if query_type == "chitchat":
        return {"answer": "Hi! I am Shagara, your Cairo rooftop gardening assistant. Ask me about watering schedules, heat protection, pest management, or harvesting.", "query_type": query_type}
    rows = retriever.search(question, tenant, access)
    rows = [(p, s) for p, s in rows if "ignore all previous instructions" not in p.text.lower()]
    flags = []
    raw_rows = retriever.search(question, tenant, access)
    if any("ignore all previous instructions" in p.text.lower() and score >= 0.12 for p, score in raw_rows):
        flags.append("injection_in_document")
    confidence = rows[0][1] if rows else 0
    abstained = confidence < 0.12
    answer = ABSTAIN if abstained else Retriever.answer(question, rows)
    sources = [{"marker": f"S{i}", "document": p.document, "page": p.page, "section": p.section, "score": round(s, 3), "excerpt": p.text[:220]} for i, (p, s) in enumerate(rows, 1)]

    if (use_ollama or os.getenv("GEMINI_API_KEY")) and not abstained:
        formatted_context = "\n\n".join(f"[{s['marker']} - {p.document} (Page {p.page}, {p.section})]:\n{p.text}" for s, (p, _) in zip(sources, rows))
        generated = await retriever.generate(question, formatted_context)
        if generated:
            answer = generated

    return {"answer": answer, "sources": sources, "query_type": query_type, "confidence": round(confidence, 3), "grounded": True, "abstained": abstained, "flags": flags}
