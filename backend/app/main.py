from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import shutil
import re

from .schemas import QueryRequest, QueryResponse
from .services import query, DATA_DIR, UPLOAD_DIR, retriever, persist_index, Passage, load_persisted_index
from .core.config import API_CORS_ORIGINS

@asynccontextmanager
async def lifespan(_: FastAPI):
    load_persisted_index()
    yield

app = FastAPI(title="shagara RAG API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=API_CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent.parent
DIST_CANDIDATES = [
    ROOT / "frontend" / "dist",
    Path.cwd() / "frontend" / "dist",
    Path("/var/task/frontend/dist"),
    Path(__file__).resolve().parent / "dist",
]
DIST_DIR = next((d for d in DIST_CANDIDATES if (d / "index.html").exists()), DIST_CANDIDATES[0])
INDEX_HTML = DIST_DIR / "index.html"

if (DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
@router.get("/index.html", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
async def root_endpoint():
    if INDEX_HTML.exists():
        return HTMLResponse(INDEX_HTML.read_text(encoding="utf-8"))
    return HTMLResponse("<!doctype html><html><body><h1>shagara</h1></body></html>")


@router.get("/assets/{asset_path:path}")
@app.get("/assets/{asset_path:path}")
async def asset_endpoint(asset_path: str):
    for d in DIST_CANDIDATES:
        f = d / "assets" / asset_path
        if f.exists():
            media_type = "application/javascript" if asset_path.endswith(".js") else "text/css" if asset_path.endswith(".css") else None
            return FileResponse(f, media_type=media_type)
    for d in DIST_CANDIDATES:
        assets_dir = d / "assets"
        if assets_dir.exists():
            pattern = "*.js" if asset_path.endswith(".js") else "*.css" if asset_path.endswith(".css") else None
            if pattern:
                matches = list(assets_dir.glob(pattern))
                if matches:
                    media_type = "application/javascript" if asset_path.endswith(".js") else "text/css" if asset_path.endswith(".css") else None
                    return FileResponse(matches[0], media_type=media_type)
    raise HTTPException(status_code=404, detail="Asset not found")




@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "shagara-rag"}


@router.get("/debug")
@app.get("/api/debug")
async def debug_endpoint():
    import os
    all_files = []
    for root, _, files in os.walk("/var/task" if Path("/var/task").exists() else "."):
        if any(skip in root for skip in [".git", "node_modules"]):
            continue
        for f in files:
            all_files.append(str(Path(root) / f))
    return {
        "cwd": str(Path.cwd()),
        "dist_candidates": [str(d) + f" (exists={d.exists()})" for d in DIST_CANDIDATES],
        "dist_dir": str(DIST_DIR),
        "index_html_exists": INDEX_HTML.exists(),
        "files_sample": all_files[:50]
    }




@router.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest) -> QueryResponse:
    result = await query(request.question, request.tenant_id, request.access_levels, request.use_ollama)
    return QueryResponse(**result)


@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)) -> dict:
    name = Path(file.filename or "document").name
    suffix = Path(name).suffix.lower()
    if suffix not in {".md", ".txt", ".pdf"}:
        raise HTTPException(status_code=415, detail="Upload a .md, .txt, or .pdf file")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    target = UPLOAD_DIR / name
    raw = await file.read()
    import hashlib
    checksum = hashlib.sha256(raw).hexdigest()
    target.write_bytes(raw)
    text = ""
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            text = "\n".join((page.extract_text() or "") for page in PdfReader(str(target)).pages)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Could not parse PDF: {exc}")
    else:
        text = target.read_text(encoding="utf-8", errors="ignore")
    section = "Uploaded document"
    chunks = []
    for block in re.split(r"\n(?=##? )", text):
        clean = " ".join(block.split())
        if clean:
            if block.lstrip().startswith("## "): section = block.lstrip()[3:].split("\n", 1)[0].strip()
            chunks.append(Passage(name, "shagara", "all", clean[:1200], section))
    retriever.passages = [p for p in retriever.passages if p.document != name] + chunks
    persist_index(retriever.passages)
    return {"document": name, "status": "ready", "chunks": len(chunks), "checksum": checksum, "index_path": "backend/data/vector_store/index.json"}


@router.get("/documents")
async def list_documents() -> dict:
    docs = sorted({p.document for p in retriever.passages if p.tenant == "shagara"})
    return {"documents": docs, "count": len(docs)}


app.include_router(router)
app.include_router(router, prefix="/api")
