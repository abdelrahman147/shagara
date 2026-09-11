# Shagara

Shagara is a grounded document assistant for Cairo rooftop gardeners. Upload growing notes, ask questions about irrigation, pests, heat, compost, or harvesting, and receive an answer with the source passages used to produce it.

Live site: https://shagara.shop

## Features

- PDF, Markdown, and TXT document ingestion
- Section-aware chunking with page and source metadata
- Persisted local vector index
- Tenant and access-level filtering before retrieval
- Query routing for document questions, analytics questions, and chat
- Grounded answers with citations, confidence, abstention, and safety flags
- Optional Gemini generation with a server-side `GEMINI_API_KEY`, plus Ollama support
- React/Vite/Three.js product interface
- Streamlit interface required by the course brief
- FastAPI API with upload and query endpoints

## Architecture

The editable architecture diagram is available at [`docs/shagara-architecture.svg`](docs/shagara-architecture.svg). The Mermaid source and implementation notes are in [`docs/architecture.md`](docs/architecture.md).

```text
Documents -> parse -> clean/chunk -> embeddings -> persisted index
Question -> FastAPI -> classify/filter -> retrieve -> prompt -> Ollama/fallback
         -> validation -> citations/confidence -> Shagara UI
```

## Project structure

```text
backend/                 FastAPI application and persisted index
frontend/src/            React/Vite interface with Three.js scene
frontend/app.py          Streamlit interface
notebooks/rag_pipeline.ipynb
notebooks/SHAGARA_rag_pipeline.ipynb
                         reproducible ingestion and evaluation notebook
rag_demo_data/           rooftop gardening source documents
docs/                    architecture diagram and notes
```

## Local setup

### Backend

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt
$env:PYTHONPATH="backend"
python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

### React frontend

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Set `VITE_API_BASE_URL` in `frontend/.env` to the FastAPI URL.

### Vercel deployment

Deploy the repository root as one Vercel project for the FastAPI function, then deploy `frontend/` as a second Vercel project for the React site. The root project includes `vercel.json` and exposes the API under `/api`. Add `GEMINI_API_KEY` and `API_CORS_ORIGINS` to the root project's server environment. In the frontend project, set `VITE_API_BASE_URL` to the root project's URL followed by `/api`, then redeploy. Add `shagara.shop` as a custom domain on the frontend project.

### Streamlit frontend

```powershell
cd frontend
pip install -r requirements.txt
$env:API_BASE_URL="http://localhost:8000"
streamlit run app.py
```

## AI generation

Add `GEMINI_API_KEY` to the backend Vercel project's environment variables. The key is read only by the backend and is never exposed to the browser. Shagara sends retrieved document context to Gemini 2.0 Flash; if the provider is unavailable, it returns the deterministic grounded answer.

The local Ollama option remains available:

The API uses a deterministic grounded response when Ollama is unavailable. To enable local generation:

```powershell
ollama pull llama3.2:3b
ollama serve
```

Configure `OLLAMA_URL`, `OLLAMA_MODEL`, and `API_CORS_ORIGINS` using `backend/.env`.

## API

Health check: `GET /health`

Question: `POST /query`

Upload: `POST /documents/upload`

```powershell
Invoke-RestMethod http://localhost:8000/query -Method Post -ContentType "application/json" -Body '{"question":"How often should I water basil?","tenant_id":"shagara","access_levels":["all","members"],"use_ollama":true}'
```

Responses include the answer, query type, confidence, grounded status, abstention status, safety flags, and cited source excerpts.

## Evaluation

The notebook evaluates 11 questions covering light, irrigation, heat, pests, compost, harvest timing, and an unsupported analytics question. It records retrieved sources, groundedness, correctness, and abstention behavior. The current local baseline reports Recall@5 1.00, answer correctness 0.86, and abstention accuracy 1.00.

Run the checks:

```powershell
$env:PYTHONPATH="backend"
pytest -q backend/tests
cd frontend
npm run build
```

## Course deliverables

The repository contains the Core Track deliverables from the graduation brief: source corpus, runnable notebook, persisted store, FastAPI backend, Streamlit frontend, tests, environment examples, architecture documentation, and setup instructions. GitHub publication, live demonstration, and video walkthrough are completed through the student's own accounts.

## License

This project is provided for educational and demonstration use.
