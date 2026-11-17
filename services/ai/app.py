"""Servicio de IA ligera: resumen extractivo, mapa de conceptos y lectura en voz alta (fragmentos)."""
import re
from collections import Counter
from itertools import combinations

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from common.security import current_user_id

STOP = set("""a al algo ante con contra cual cuando como de del desde donde el ella ellos en entre era es esa ese eso esta este esto
fue ha han hay la las le les lo los mas más me mi muy no nos o para pero por que qué se si sí sin sobre su sus también tan te
un una uno unos y ya the of and to in is are was were be been it that this for on with as by at from an or not but their its
his her they them we you he she i our your""".split())
SENT_RE = re.compile(r"(?<=[.!?])\s+|\n{2,}")
WORD_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{4,}")


class TextIn(BaseModel):
    text: str = Field(min_length=1, max_length=50_000)


class SummaryIn(TextIn):
    sentences: int = Field(default=3, ge=1, le=10)


class ConceptsIn(TextIn):
    top: int = Field(default=8, ge=2, le=20)


class ChunksIn(TextIn):
    max_chars: int = Field(default=220, ge=60, le=1000)


def sentences_of(text: str) -> list[str]:
    return [s.strip() for s in SENT_RE.split(text) if s and s.strip()]


def words_of(sentence: str) -> list[str]:
    return [w.lower() for w in WORD_RE.findall(sentence) if w.lower() not in STOP]


def summarize(text: str, n: int) -> list[str]:
    sents = sentences_of(text)
    freq = Counter(w for s in sents for w in words_of(s))
    if len(sents) <= n or not freq:
        return sents[:n]
    scored = []
    for i, s in enumerate(sents):
        ws = words_of(s)
        score = sum(freq[w] for w in ws) / (len(ws) ** 0.5) if ws else 0
        scored.append((score, i))
    best = sorted(scored, reverse=True)[:n]
    return [sents[i] for _, i in sorted(best, key=lambda x: x[1])]


def concept_map(text: str, top: int) -> dict:
    sents = sentences_of(text)
    freq = Counter(w for s in sents for w in words_of(s))
    keys = [w for w, _ in freq.most_common(top)]
    edges: Counter = Counter()
    for s in sents:
        present = sorted({w for w in words_of(s) if w in keys})
        for a, b in combinations(present, 2):
            edges[(a, b)] += 1
    return {
        "nodes": [{"id": w, "weight": freq[w]} for w in keys],
        "edges": [{"source": a, "target": b, "weight": c} for (a, b), c in edges.most_common()],
    }


def chunks(text: str, max_chars: int) -> list[str]:
    out, cur = [], ""
    for s in sentences_of(text):
        while len(s) > max_chars:  # frases larguísimas: se cortan en el espacio más cercano
            cut = s.rfind(" ", 0, max_chars) or max_chars
            cut = cut if cut > 0 else max_chars
            out.append(s[:cut].strip())
            s = s[cut:].strip()
        if cur and len(cur) + 1 + len(s) > max_chars:
            out.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        out.append(cur)
    return out


def create_app() -> FastAPI:
    app = FastAPI(title="Servicio de IA")

    def require_text(text: str):
        if not text.strip():
            raise HTTPException(422, "El texto está vacío")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "ai"}

    @app.post("/summary")
    def summary(body: SummaryIn, uid: int = Depends(current_user_id)):
        require_text(body.text)
        picked = summarize(body.text, body.sentences)
        return {"summary": " ".join(picked), "sentences": picked, "original_sentences": len(sentences_of(body.text))}

    @app.post("/concepts")
    def concepts(body: ConceptsIn, uid: int = Depends(current_user_id)):
        require_text(body.text)
        return concept_map(body.text, body.top)

    @app.post("/read-aloud")
    def read_aloud(body: ChunksIn, uid: int = Depends(current_user_id)):
        require_text(body.text)
        parts = chunks(body.text, body.max_chars)
        return {"chunks": parts, "count": len(parts)}

    return app
