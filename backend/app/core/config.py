import os

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
API_CORS_ORIGINS = os.getenv("API_CORS_ORIGINS", "http://localhost:5173,http://localhost:8501").split(",")
