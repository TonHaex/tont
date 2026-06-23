from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from rag_engine import RagEngine


ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("TONGPT_ALLOWED_ORIGINS", "https://tonhaex.nl,http://localhost:8000").split(",")
    if origin.strip()
]

app = FastAPI(title="TonGPT API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

engine = RagEngine()


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=800)


class Source(BaseModel):
    title: str
    url: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source] = []


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/testpagina")
def test_page() -> FileResponse:
    return FileResponse("testpagina.html", headers={"Cache-Control": "no-store"})


@app.get("/widget.js")
def widget_script() -> FileResponse:
    return FileResponse(
        "widget.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> dict:
    try:
        return engine.answer(request.question)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="De kennisbank is nog niet opgebouwd.") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="TonGPT kon de vraag niet verwerken.") from exc
