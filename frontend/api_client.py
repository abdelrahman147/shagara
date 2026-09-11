import os
import requests

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")

def query(question: str, tenant_id: str = "shagara") -> dict:
    response = requests.post(f"{API_BASE_URL}/query", json={"question": question, "tenant_id": tenant_id, "access_levels": ["all", "members"]}, timeout=60)
    response.raise_for_status()
    return response.json()



