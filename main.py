"""
Đông Đô CS Chatbot - FastAPI Main Server
RAG Chat API + Authentication + Conversation Memory + Chat History Storage
"""
import os
import uuid
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from langchain_anthropic import ChatAnthropic
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from langchain_chroma import Chroma
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from config import (
    ANTHROPIC_API_KEY,
    LLM_MODEL,
    LLM_TEMPERATURE,
    EMBEDDING_MODEL,
    VECTORDB_DIR,
    CHROMA_COLLECTION_NAME,
    RETRIEVER_K,
    MEMORY_WINDOW_SIZE,
    SYSTEM_PROMPT,
    BASE_DIR,
)
from database import (
    init_database,
    save_message,
    get_session_history,
    verify_user,
    create_session,
    verify_session,
    delete_session,
)

# ============================================================
# Global State
# ============================================================
vector_store = None
llm = None
embeddings = None
# In-memory conversation history per session_id
conversation_memories: dict[str, list] = {}


# ============================================================
# Auth Dependency
# ============================================================
async def get_current_user(
    authorization: str | None = Header(default=None),
    x_auth_token: str | None = Header(default=None),
) -> dict:
    """Xác thực người dùng dựa trên Session Token."""
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    elif x_auth_token:
        token = x_auth_token

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Vui lòng đăng nhập để sử dụng hệ thống."
        )

    user = verify_session(token)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Phiên đăng nhập đã hết hạn hoặc không hợp lệ. Vui lòng đăng nhập lại."
        )

    return {**user, "token": token}


# ============================================================
# Conversation Memory (per session)
# ============================================================
def get_conversation_history(session_id: str) -> list:
    """Lấy lịch sử hội thoại của session, giới hạn window size."""
    if session_id not in conversation_memories:
        conversation_memories[session_id] = []
    history = conversation_memories[session_id]
    max_messages = MEMORY_WINDOW_SIZE * 2
    if len(history) > max_messages:
        history = history[-max_messages:]
        conversation_memories[session_id] = history
    return history


def add_to_conversation(session_id: str, role: str, content: str):
    """Thêm message vào conversation memory."""
    if session_id not in conversation_memories:
        conversation_memories[session_id] = []
    if role == "user":
        conversation_memories[session_id].append(HumanMessage(content=content))
    else:
        conversation_memories[session_id].append(AIMessage(content=content))


# ============================================================
# RAG Pipeline
# ============================================================
def retrieve_context(query: str) -> tuple[str, list[str]]:
    """Truy xuất context từ Vector DB."""
    if vector_store is None:
        return "", []

    results = vector_store.similarity_search_with_relevance_scores(
        query, k=RETRIEVER_K
    )

    if not results:
        return "", []

    context_parts = []
    sources = set()
    for doc, score in results:
        if score >= 0.2:  # Ngưỡng relevance tối thiểu
            context_parts.append(doc.page_content)
            if "source" in doc.metadata:
                sources.add(doc.metadata["source"])

    context = "\n\n---\n\n".join(context_parts)
    return context, list(sources)


async def generate_response(
    query: str, session_id: str, username: str = None
) -> tuple[str, list[str]]:
    """Pipeline chính: Retrieve → Inject Context → LLM → Response."""
    # Step 1: Retrieve relevant context
    context, sources = retrieve_context(query)

    # Step 2: Build prompt with context
    context_block = ""
    if context:
        context_block = f"""
DỮ LIỆU TỪ CƠ SỞ KIẾN THỨC (Knowledge Base):
===
{context}
===

Hãy dựa HOÀN TOÀN vào dữ liệu trên để trả lời câu hỏi của khách hàng. KHÔNG ĐƯỢC sử dụng bất kỳ kiến thức nào bên ngoài dữ liệu này."""
    else:
        context_block = """
KHÔNG TÌM THẤY DỮ LIỆU LIÊN QUAN trong Cơ sở kiến thức.
Hãy thực hiện đúng 2 bước: Xin lỗi + Chuyển giao chuyên viên CSKH."""

    # Step 3: Get conversation history
    history = get_conversation_history(session_id)

    # Step 4: Build messages
    messages = [
        SystemMessage(content=SYSTEM_PROMPT + "\n\n" + context_block),
        *history,
        HumanMessage(content=query),
    ]

    # Step 5: Call LLM
    response = await llm.ainvoke(messages)
    reply = response.content

    # Step 6: Update memory
    add_to_conversation(session_id, "user", query)
    add_to_conversation(session_id, "assistant", reply)

    # Step 7: Save to database for learning
    save_message(session_id, "user", query, username=username)
    save_message(session_id, "assistant", reply, username=username)

    return reply, sources


# ============================================================
# FastAPI App
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup & Shutdown events."""
    global vector_store, llm, embeddings

    print("🚀 Khởi tạo Đông Đô CS Chatbot...")

    # Init Database (PostgreSQL trên Render, SQLite local)
    init_database()

    # Init Embeddings (Lightweight FastEmbed ONNX - ~50MB RAM)
    print(f"🔧 Loading FastEmbed ONNX embedding model: {EMBEDDING_MODEL}")
    embeddings = FastEmbedEmbeddings(
        model_name=EMBEDDING_MODEL,
    )

    # Init Vector Store
    if os.path.exists(VECTORDB_DIR):
        print(f"📦 Loading vector store từ: {VECTORDB_DIR}")
        vector_store = Chroma(
            collection_name=CHROMA_COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=VECTORDB_DIR,
        )
        collection = vector_store._collection
        print(f"   → {collection.count()} chunks trong vector store")
        
        # Chạy học từ lịch sử chat cũ (khi database đã sẵn sàng ở runtime)
        try:
            from learn import main as run_learning
            run_learning()
        except Exception as e:
            print(f"⚠️ Learning check on startup: {e}")
    else:
        print("⚠️  Vector store chưa tồn tại. Hãy chạy: python ingest.py")

    # Init LLM
    if not ANTHROPIC_API_KEY:
        print("⚠️  ANTHROPIC_API_KEY chưa được set!")
        print("   Hãy chạy: export ANTHROPIC_API_KEY='sk-ant-...'")
    else:
        print(f"🤖 Khởi tạo LLM: {LLM_MODEL} (temp={LLM_TEMPERATURE})")
        llm = ChatAnthropic(
            model=LLM_MODEL,
            anthropic_api_key=ANTHROPIC_API_KEY,
            temperature=LLM_TEMPERATURE,
            max_tokens=4096,
        )

    print("✅ Chatbot sẵn sàng!")
    print("🌐 Frontend: http://localhost:8000")
    print("📡 API: http://localhost:8000/docs")

    yield

    print("👋 Shutting down...")


app = FastAPI(
    title="Đông Đô CS Chatbot API",
    description="AI Customer Service Chatbot cho Đông Đô Partners",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files
frontend_dir = os.path.join(BASE_DIR, "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


# ============================================================
# Pydantic Models
# ============================================================
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str
    full_name: str
    role: str


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    sources: list[str] = []


# ============================================================
# Authentication Endpoints
# ============================================================
@app.post("/auth/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """Xác thực đăng nhập tài khoản nội bộ."""
    user = verify_user(req.username, req.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Tên đăng nhập hoặc mật khẩu không chính xác."
        )

    token = create_session(user["username"])
    return LoginResponse(
        token=token,
        username=user["username"],
        full_name=user["full_name"],
        role=user["role"],
    )


@app.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Lấy thông tin người dùng hiện tại từ session token."""
    return {
        "username": user["username"],
        "full_name": user["full_name"],
        "role": user["role"],
    }


@app.post("/auth/logout")
async def logout(user: dict = Depends(get_current_user)):
    """Đăng xuất và hủy token."""
    delete_session(user["token"])
    return {"message": "Đã đăng xuất thành công."}


# ============================================================
# Main Endpoints
# ============================================================
@app.api_route("/", methods=["GET", "HEAD"])
async def serve_frontend():
    """Serve the frontend chat UI."""
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Đông Đô CS Chatbot API is running. Frontend not found."}


@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    """Health check endpoint (supports GET & HEAD for uptime monitors)."""
    return {
        "status": "healthy",
        "llm_ready": llm is not None,
        "vector_store_ready": vector_store is not None,
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user: dict = Depends(get_current_user)):
    """
    Chat endpoint chính (Yêu cầu Đăng nhập).
    Nhận message từ user, truy xuất Vector DB, inject vào System Prompt, gọi LLM.
    """
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message không được để trống")

    if llm is None:
        raise HTTPException(
            status_code=503,
            detail="LLM chưa được khởi tạo. Hãy set ANTHROPIC_API_KEY.",
        )

    if vector_store is None:
        raise HTTPException(
            status_code=503,
            detail="Vector store chưa được khởi tạo. Hãy chạy: python ingest.py",
        )

    session_id = request.session_id or str(uuid.uuid4())

    try:
        reply, sources = await generate_response(
            query=request.message.strip(),
            session_id=session_id,
            username=user["username"],
        )
        return ChatResponse(
            reply=reply,
            session_id=session_id,
            sources=sources,
        )
    except Exception as e:
        print(f"❌ Error in chat: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý: {str(e)}")


@app.get("/history/{session_id}")
async def get_history(session_id: str, user: dict = Depends(get_current_user)):
    """Lấy lịch sử chat của một session (Yêu cầu Đăng nhập)."""
    messages = get_session_history(session_id)
    return {
        "session_id": session_id,
        "messages": messages,
    }


# ============================================================
# Run Server
# ============================================================
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )
