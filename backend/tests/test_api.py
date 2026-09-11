from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_query_and_source():
    response = client.post("/query", json={"question": "How much light does basil need?"})
    body = response.json()
    assert response.status_code == 200
    assert "6 to 8" in body["answer"]
    assert body["sources"][0]["document"] == "rooftop_growing.md"


def test_tenant_isolation():
    response = client.post("/query", json={"question": "What is the return policy?", "tenant_id": "shagara"})
    assert all(s["document"] != "globex_policy.md" for s in response.json()["sources"])


def test_invalid_question():
    response = client.post("/query", json={"question": ""})
    assert response.status_code == 422


def test_unsupported_question_abstains():
    response = client.post("/query", json={"question": "What is the stock price of shagara?"})
    assert response.status_code == 200
    assert response.json()["query_type"] == "analytical"


def test_upload_indexes_markdown(tmp_path):
    response = client.post("/documents/upload", files={"file": ("test_upload.md", b"# Test\n## Note\nBasil needs sunlight.", "text/markdown")})
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    path = Path("rag_demo_data/test_upload.md")
    if path.exists(): path.unlink()



