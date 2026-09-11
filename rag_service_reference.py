
# app/main.py  — reference service, not executed in this notebook
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json, uuid

app = FastAPI(title="RAG Service")


class Principal(BaseModel):
    tenant_id: str
    user_id: str
    access_levels: list[str]


async def current_principal(token: str = Depends(oauth2_scheme)) -> Principal:
    """Decode and VERIFY the JWT. The tenant comes from here and nowhere else."""
    claims = verify_jwt(token)
    return Principal(
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        access_levels=claims.get("access_levels", ["all"]),
    )


@app.post("/documents")
async def upload(file: UploadFile = File(...), principal: Principal = Depends(current_principal)):
    """Accept fast, process later. The HTTP request must not do the work."""
    if file.size > 100 * 1024 * 1024:
        raise HTTPException(413, "File too large")
    key = f"{principal.tenant_id}/{uuid.uuid4()}/{file.filename}"
    await object_store.put(key, await file.read())
    job_id = await queue.enqueue("ingest", key=key, tenant_id=principal.tenant_id)
    return {"job_id": job_id, "status": "queued"}


@app.get("/documents/{document_id}/status")
async def status(document_id: str, principal: Principal = Depends(current_principal)):
    return await registry.get(document_id, tenant_id=principal.tenant_id)


class ChatRequest(BaseModel):
    question: str
    conversation_id: str | None = None
    stream: bool = True
    # NOTE: no tenant_id field. Ever.


@app.post("/chat")
async def chat(req: ChatRequest, principal: Principal = Depends(current_principal)):
    await rate_limiter.check(principal.tenant_id, principal.user_id)
    scope = AccessScope(
        tenant_id=principal.tenant_id,
        access_levels=principal.access_levels,
    )
    history = await conversations.recent(req.conversation_id, limit=3)

    if not req.stream:
        result = pipeline.query(req.question, scope, history)
        return {
            "answer": result.answer,
            "sources": result.sources,
            "grounded": result.grounded,
            "confidence": result.confidence,
        }

    async def event_stream():
        for event in pipeline.stream_query(req.question, scope):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# worker.py — runs outside the request cycle
def ingest_job(key: str, tenant_id: str):
    path = object_store.download(key)
    pipeline.ingest(path, tenant_id=tenant_id)
