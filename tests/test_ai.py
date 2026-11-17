from fastapi.testclient import TestClient

from common.security import create_token
from services.ai.app import chunks, concept_map, create_app, summarize

H = {"Authorization": f"Bearer {create_token(1, 'a@b.co')}"}
TEXT = ("La fotosíntesis es el proceso por el cual las plantas convierten la luz en energía. "
        "Las plantas usan clorofila para capturar la luz solar. "
        "El perro de Juan corrió por la calle ayer. "
        "La energía de la fotosíntesis se almacena como glucosa en las plantas.")


def test_summary_prefers_central_sentences():
    out = summarize(TEXT, 2)
    assert len(out) == 2 and not any("perro" in s for s in out)


def test_summary_short_text_returns_all():
    assert summarize("Solo una frase.", 3) == ["Solo una frase."]


def test_concept_map_has_nodes_and_edges():
    m = concept_map(TEXT, 5)
    ids = {n["id"] for n in m["nodes"]}
    assert "plantas" in ids and "fotosíntesis" in ids
    assert all(e["source"] in ids and e["target"] in ids for e in m["edges"])


def test_chunks_respect_limit():
    parts = chunks(TEXT, 90)
    assert all(len(p) <= 90 for p in parts) and " ".join(parts).replace("  ", " ")


def test_http_endpoints():
    c = TestClient(create_app())
    assert c.post("/summary", json={"text": TEXT, "sentences": 2}, headers=H).json()["sentences"].__len__() == 2
    assert c.post("/concepts", json={"text": TEXT}, headers=H).status_code == 200
    assert c.post("/read-aloud", json={"text": TEXT, "max_chars": 100}, headers=H).json()["count"] >= 2
    assert c.post("/summary", json={"text": "   "}, headers=H).status_code == 422
    assert c.post("/summary", json={"text": TEXT}).status_code == 401
