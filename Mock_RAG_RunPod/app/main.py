import asyncio
import gc
import hmac
import logging
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass

import torch
from fastapi import Depends, FastAPI, Header, HTTPException, status
from langchain_chroma import Chroma
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.globals import set_llm_cache
from langchain_core.prompts import PromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings, HuggingFacePipeline
from pydantic import BaseModel, Field
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("runpod-rag")

# Fixed RunPod experiment configuration. Only the API key is external because it is secret.
DATABASE_PATH = "/workspace/workspace/pg19"
COLLECTION_NAME = "gutenberg_completo"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
LLM_MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"
TOP_K = 20
RAG_API_KEY = os.getenv("RAG_API_KEY")
if not RAG_API_KEY:
    raise RuntimeError("RAG_API_KEY environment variable is required")

PROMPT_TEMPLATE = """Eres un asistente analitico. Usa el siguiente contexto para responder a la pregunta.
Regla estricta: si la pregunta trata sobre un termino de baja frecuencia, o si la informacion del contexto es escasa o poco relevante, tu respuesta debe ser unica y exclusivamente la palabra "Baja". No anadas puntos, saludos ni explicaciones adicionales.
Si hay abundante informacion, genera una respuesta detallada y extensa.

Contexto:
{context}

Pregunta: {input}
Respuesta:"""


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)


class ChatResponse(BaseModel):
    answer: str


class HealthResponse(BaseModel):
    status: str
    top_k: int
    collection: str
    cuda_available: bool


@dataclass
class RagRuntime:
    chain: object
    lock: asyncio.Lock


def require_api_key(
    api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    if api_key is None or not hmac.compare_digest(api_key, RAG_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


def build_rag_chain():
    set_llm_cache(None)
    logger.info("Loading LLM %s", LLM_MODEL)
    tokenizer = AutoTokenizer.from_pretrained(LLM_MODEL)
    model = AutoModelForCausalLM.from_pretrained(
        LLM_MODEL,
        torch_dtype="auto",
        device_map="auto",
    )

    text_generation_pipeline = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        max_new_tokens=100,
        min_new_tokens=1,
        min_length=None,
        max_length=None,
        temperature=0.1,
        return_full_text=False,
        truncation=True,
        pad_token_id=tokenizer.eos_token_id,
    )
    llm = HuggingFacePipeline(pipeline=text_generation_pipeline)

    logger.info(
        "Connecting to ChromaDB path=%s collection=%s top_k=%s",
        DATABASE_PATH,
        COLLECTION_NAME,
        TOP_K,
    )
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=DATABASE_PATH,
        embedding_function=embeddings,
    )
    retriever = vectorstore.as_retriever(search_kwargs={"k": TOP_K})
    prompt = PromptTemplate.from_template(PROMPT_TEMPLATE)
    document_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(retriever, document_chain)

    logger.info("Warming up complete RAG chain")
    rag_chain.invoke({"input": "query de calentamiento para cargar en VRAM"})
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    time.sleep(2)
    logger.info("RAG warm-up completed")
    return rag_chain


@asynccontextmanager
async def lifespan(app: FastAPI):
    chain = await asyncio.to_thread(build_rag_chain)
    app.state.runtime = RagRuntime(chain=chain, lock=asyncio.Lock())
    logger.info("RAG service ready with top_k=%s", TOP_K)
    yield
    app.state.runtime = None
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


app = FastAPI(
    title=f"RunPod RAG without cache (k={TOP_K})",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    if getattr(app.state, "runtime", None) is None:
        raise HTTPException(status_code=503, detail="RAG model is not ready")
    return HealthResponse(
        status="ok",
        top_k=TOP_K,
        collection=COLLECTION_NAME,
        cuda_available=torch.cuda.is_available(),
    )


@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_api_key)])
async def chat(payload: ChatRequest) -> ChatResponse:
    runtime: RagRuntime | None = getattr(app.state, "runtime", None)
    if runtime is None:
        raise HTTPException(status_code=503, detail="RAG model is not ready")

    try:
        async with runtime.lock:
            result = await asyncio.to_thread(
                runtime.chain.invoke,
                {"input": payload.question},
            )
    except Exception as exc:
        logger.exception("RAG inference failed")
        raise HTTPException(status_code=500, detail="RAG inference failed") from exc

    answer = result.get("answer")
    if not isinstance(answer, str):
        raise HTTPException(status_code=500, detail="RAG returned an invalid response")
    return ChatResponse(answer=answer)
