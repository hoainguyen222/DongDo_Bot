"""
Đông Đô CS Chatbot - FastAPI Main Server
RAG Chat API + Guest Public Chat + CSKH Live Takeover & Admin Portal + Continuous Learning
"""
import os
import glob
import uuid
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header, Depends, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from langchain_anthropic import ChatAnthropic
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from langchain_chroma import Chroma
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter

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
    DOCUMENTS_DIR,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
)
from database import (
    init_database,
    save_message,
    get_session_history,
    verify_user,
    create_session,
    verify_session,
    delete_session,
    upsert_chat_case,
    list_chat_cases,
    get_chat_case,
    assign_chat_case,
    resolve_chat_case,
    delete_chat_case,
    clear_all_cases,
    add_to_learning_queue,
    list_learning_items,
    get_learning_item,
    update_learning_item,
    mark_learning_item_status,
    clear_learned_knowledge,
    get_analytics_stats,
    get_setting,
    set_setting,
    save_uploaded_document,
    list_uploaded_documents,
    get_uploaded_document_bytes,
    delete_uploaded_document,
)
from ingest import extract_text_from_docx

# ============================================================
# Global State
# ============================================================
vector_store: Chroma | None = None
llm: ChatAnthropic | None = None
embeddings: FastEmbedEmbeddings | None = None
conversation_memories: dict[str, list] = {}


# ============================================================
# Auth Dependency for CSKH & Admin
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
            detail="Vui lòng đăng nhập để sử dụng tính năng này."
        )

    user = verify_session(token)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Phiên đăng nhập đã hết hạn hoặc không hợp lệ. Vui lòng đăng nhập lại."
        )

    return {**user, "token": token}


# ============================================================
# Vector DB & Learning Helpers
# ============================================================
def embed_qa_to_chromadb(question: str, answer: str, session_id: str = "") -> int:
    """Nhúng trực tiếp một cặp Q&A đã được duyệt vào ChromaDB."""
    global vector_store
    if vector_store is None:
        print("⚠️ Vector store chưa sẵn sàng để nạp Q&A")
        return 0

    content = (
        f"CÂU HỎI / CHỦ ĐỀ CỦA KHÁCH HÀNG: {question.strip()}\n"
        f"CÂU TRẢ LỜI / THÔNG TIN CHÍNH THỨC CỦA ĐÔNG ĐÔ PARTNERS: {answer.strip()}"
    )
    doc_id = f"learned_qa_{int(datetime.now().timestamp() * 1000)}_{uuid.uuid4().hex[:6]}"
    metadata = {
        "source": "CSKH_Learning",
        "session_id": session_id,
        "type": "learned_qa",
        "question": question.strip(),
        "learned_at": datetime.now().isoformat(),
    }

    vector_store.add_texts(
        texts=[content],
        metadatas=[metadata],
        ids=[doc_id],
    )
    print(f"🧠 Đã nạp thành công Q&A vào ChromaDB (ID: {doc_id}) -> {question.strip()} | {answer.strip()}")
    return 1


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

    try:
        results = vector_store.similarity_search_with_relevance_scores(
            query, k=RETRIEVER_K
        )
    except Exception as e:
        results = []

    if not results:
        try:
            docs = vector_store.similarity_search(query, k=RETRIEVER_K)
            results = [(d, 0.5) for d in docs]
        except Exception:
            return "", []

    context_parts = []
    sources = set()
    for doc, score in results:
        is_learned = doc.metadata.get("source") == "CSKH_Learning"
        # Chấp nhận tài liệu phù hợp hoặc là tri thức CSKH đã nạp
        if score >= 0.05 or is_learned:
            context_parts.append(doc.page_content)
            if "source" in doc.metadata:
                sources.add(doc.metadata["source"])

    context = "\n\n---\n\n".join(context_parts)
    return context, list(sources)


async def generate_response(query: str, session_id: str, save_user_msg: bool = True) -> tuple[str, list[str], bool]:
    """
    Pipeline chính: Retrieve → Context → LLM → Response.
    Trả về (reply, sources, is_fallback)
    """
    context, sources = retrieve_context(query)

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
Hãy thực hiện đúng 2 bước: Xin lỗi + Chuyển giao chuyên viên CSKH với đúng nguyên văn câu chốt."""

    current_prompt = get_setting("system_prompt", SYSTEM_PROMPT)
    history = get_conversation_history(session_id)

    messages = [
        SystemMessage(content=current_prompt + "\n\n" + context_block),
        *history,
        HumanMessage(content=query),
    ]

    response = await llm.ainvoke(messages)
    reply = response.content

    # Update memory & database
    if save_user_msg:
        add_to_conversation(session_id, "user", query)
        save_message(session_id, "user", query)
    add_to_conversation(session_id, "assistant", reply)
    save_message(session_id, "assistant", reply)

    # Kiểm tra xem có kích hoạt fallback hay không
    fallback_phrase = "chuyên viên CSKH của Đông Đô sẽ trực tiếp tham gia cuộc trò chuyện để hỗ trợ bạn ngay"
    is_fallback = (fallback_phrase.lower() in reply.lower()) or (not context)

    return reply, sources, is_fallback


# ============================================================
# FastAPI App Lifespan
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup & Shutdown events."""
    global vector_store, llm, embeddings

    print("🚀 Khởi tạo Đông Đô CS Chatbot Server...")

    # 1. Khởi tạo Database
    init_database()

    # 2. Khởi tạo Embeddings (FastEmbed ONNX)
    print(f"🔧 Loading FastEmbed model: {EMBEDDING_MODEL}")
    embeddings = FastEmbedEmbeddings(model_name=EMBEDDING_MODEL)

    # 3. Khởi tạo Vector Store
    if os.path.exists(VECTORDB_DIR):
        print(f"📦 Loading vector store từ: {VECTORDB_DIR}")
        vector_store = Chroma(
            collection_name=CHROMA_COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=VECTORDB_DIR,
        )
        count = vector_store._collection.count()
        print(f"   → {count} chunks trong vector store")
    else:
        print("⚠️ Vector store chưa tồn tại, đang tự động nạp từ thư mục tailieu/...")
        try:
            from ingest import main as run_ingest
            run_ingest()
            vector_store = Chroma(
                collection_name=CHROMA_COLLECTION_NAME,
                embedding_function=embeddings,
                persist_directory=VECTORDB_DIR,
            )
        except Exception as e:
            print(f"❌ Lỗi tự động ingest: {e}")

    # 3.1. Đồng bộ các tài liệu đã tải lên từ Database (bảo toàn tri thức qua các lần deploy Render)
    try:
        os.makedirs(DOCUMENTS_DIR, exist_ok=True)
        persisted_docs = list_uploaded_documents()
        if persisted_docs:
            print(f"📥 Tìm thấy {len(persisted_docs)} tài liệu upload trong Database, đang đồng bộ...")
            for pdoc in persisted_docs:
                fname = pdoc["filename"]
                fpath = os.path.join(DOCUMENTS_DIR, fname)
                if not os.path.exists(fpath):
                    fbytes = get_uploaded_document_bytes(fname)
                    if fbytes:
                        with open(fpath, "wb") as bf:
                            bf.write(fbytes)
                        print(f"   💾 Đã khôi phục file vào tailieu/: {fname}")

                if vector_store and os.path.exists(fpath):
                    try:
                        existing_chunks = vector_store._collection.get(where={"source": fname})
                        if not existing_chunks or not existing_chunks.get("ids"):
                            doc_text = extract_text_from_docx(fpath)
                            if doc_text and doc_text.strip():
                                ts = RecursiveCharacterTextSplitter(
                                    chunk_size=CHUNK_SIZE,
                                    chunk_overlap=CHUNK_OVERLAP,
                                    length_function=len,
                                    separators=["\n\n", "\n", ". ", ", ", " ", ""],
                                )
                                d_chunks = ts.split_text(doc_text)
                                d_metas = [
                                    {"source": fname, "chunk_id": i, "ingested_at": pdoc["uploaded_at"], "type": "uploaded_doc"}
                                    for i in range(len(d_chunks))
                                ]
                                d_ids = [f"db_sync_{int(datetime.now().timestamp())}_{i}" for i in range(len(d_chunks))]
                                vector_store.add_texts(texts=d_chunks, metadatas=d_metas, ids=d_ids)
                                print(f"   ⚡ Đã nạp {len(d_chunks)} chunks của tài liệu '{fname}' vào VectorDB")
                    except Exception as ve:
                        print(f"   ⚠️ Lỗi index tài liệu {fname}: {ve}")
    except Exception as se:
        print(f"⚠️ Lỗi đồng bộ tài liệu từ Database: {se}")

    # 4. Khởi tạo LLM
    current_model = get_setting("llm_model", LLM_MODEL)
    current_temp = float(get_setting("temperature", str(LLM_TEMPERATURE)))

    if not ANTHROPIC_API_KEY:
        print("⚠️ ANTHROPIC_API_KEY chưa được cấu hình!")
    else:
        print(f"🤖 Khởi tạo LLM: {current_model} (temp={current_temp})")
        llm = ChatAnthropic(
            model=current_model,
            anthropic_api_key=ANTHROPIC_API_KEY,
            temperature=current_temp,
            max_tokens=4096,
        )

    print("✅ Hệ thống Đông Đô CS Chatbot & Studio sẵn sàng hoạt động!")
    yield
    print("👋 Shutting down...")


app = FastAPI(
    title="Đông Đô CS Chatbot & Management Studio API",
    description="Hệ thống Chatbot CSKH & Quản trị tri thức thông minh Đông Đô Partners",
    version="2.0.0",
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

# Static files
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
    waiting_for_cs: bool = False
    status: str = "AI_ACTIVE"
    cs_agent: str | None = None
    ai_locked: bool = False


class CSReplyRequest(BaseModel):
    agent_name: str
    message: str


class QAPairItem(BaseModel):
    question: str
    answer: str


class CSResolveRequest(BaseModel):
    agent_name: str
    resolution_note: str = ""
    extract_question: str = ""
    extract_answer: str = ""
    extract_pairs: list[QAPairItem] = []


class LearningSettingsRequest(BaseModel):
    auto_learning_enabled: bool


class SystemConfigRequest(BaseModel):
    system_prompt: str
    llm_model: str
    temperature: float


# ============================================================
# Frontend Route Handlers
# ============================================================
NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}

@app.api_route("/", methods=["GET", "HEAD"])
async def serve_client_chat():
    """Phục vụ giao diện Chat Client cho Khách hàng (Không cần đăng nhập)."""
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, headers=NO_CACHE_HEADERS)
    return {"message": "Đông Đô CS Chatbot API is running."}


@app.api_route("/admin", methods=["GET", "HEAD"])
async def serve_admin_portal():
    """Phục vụ giao diện Trang Quản trị CSKH & Dạy AI (CSKH Portal)."""
    admin_path = os.path.join(frontend_dir, "admin.html")
    if os.path.exists(admin_path):
        return FileResponse(admin_path, headers=NO_CACHE_HEADERS)
    return {"message": "Admin portal frontend not found."}


@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    """Health check endpoint (24/7 uptime keep-alive)."""
    return {
        "status": "healthy",
        "llm_ready": llm is not None,
        "vector_store_ready": vector_store is not None,
        "timestamp": datetime.now().isoformat(),
    }


# ============================================================
# Public Chat Endpoints (Khách hàng)
# ============================================================
@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user: dict = Depends(get_current_user),
):
    """
    Chat endpoint cho Khách hàng (Yêu cầu đăng nhập tài khoản Khách hàng).
    """
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message không được để trống")

    session_id = request.session_id or f"session-{int(datetime.now().timestamp()*1000)}-{uuid.uuid4().hex[:6]}"
    clean_msg = request.message.strip()
    customer_display_name = user.get("full_name") or user.get("username") or "Khách hàng"

    try:
        # ── Kiểm tra trạng thái case trước khi gọi AI ──
        existing_case = get_chat_case(session_id)
        current_status = existing_case.get("status") if existing_case else "AI_ACTIVE"
        assigned_cs = existing_case.get("assigned_cs") if existing_case else None

        # 1. Chuyên viên CSKH đang trực tiếp trò chuyện với KH (HUMAN_CS_ACTIVE): AI tuyệt đối không can thiệp
        if current_status == "HUMAN_CS_ACTIVE":
            save_message(session_id, "user", clean_msg)
            add_to_conversation(session_id, "user", clean_msg)
            upsert_chat_case(
                session_id=session_id,
                customer_name=customer_display_name,
                status="HUMAN_CS_ACTIVE",
                last_user_query=clean_msg,
            )
            wait_msg = f"Dạ anh/chị vui lòng chờ, chuyên viên {assigned_cs} đang hỗ trợ trực tiếp ạ." if assigned_cs else "Dạ anh/chị vui lòng chờ trong giây lát, chuyên viên CSKH đang hỗ trợ anh/chị ạ."
            return ChatResponse(
                reply=wait_msg,
                session_id=session_id,
                sources=[],
                waiting_for_cs=True,
                status="HUMAN_CS_ACTIVE",
                cs_agent=assigned_cs,
                ai_locked=True,
            )

        # 2. Case đang "Chờ CSKH" (NEEDS_HUMAN_CS): CSKH chưa trả lời, KH hỏi thêm câu khác
        # Kiểm tra xem câu hỏi mới có trong Cơ sở tri thức hay không
        if current_status == "NEEDS_HUMAN_CS":
            context, sources = retrieve_context(clean_msg)
            if context and context.strip():
                # Tìm thấy tri thức trong tài liệu! AI trả lời ngay và chuyển case về AI_ACTIVE ("AI đang tư vấn")
                if llm is not None:
                    reply, sources, is_fallback = await generate_response(clean_msg, session_id, save_user_msg=True)
                    if not is_fallback:
                        upsert_chat_case(
                            session_id=session_id,
                            customer_name=customer_display_name,
                            status="AI_ACTIVE",
                            last_user_query=clean_msg,
                            force_status=True,
                        )
                        return ChatResponse(
                            reply=reply,
                            session_id=session_id,
                            sources=sources,
                            waiting_for_cs=False,
                            status="AI_ACTIVE",
                            cs_agent=None,
                            ai_locked=False,
                        )
                    else:
                        upsert_chat_case(
                            session_id=session_id,
                            customer_name=customer_display_name,
                            status="NEEDS_HUMAN_CS",
                            last_user_query=clean_msg,
                        )
                        return ChatResponse(
                            reply=reply,
                            session_id=session_id,
                            sources=sources,
                            waiting_for_cs=True,
                            status="NEEDS_HUMAN_CS",
                            cs_agent=None,
                            ai_locked=False,
                        )

            # Không tìm thấy thông tin trong kho tri thức: tiếp tục giữ chờ CSKH
            save_message(session_id, "user", clean_msg)
            add_to_conversation(session_id, "user", clean_msg)
            upsert_chat_case(
                session_id=session_id,
                customer_name=customer_display_name,
                status="NEEDS_HUMAN_CS",
                last_user_query=clean_msg,
            )
            return ChatResponse(
                reply="Dạ anh/chị vui lòng chờ trong giây lát, chuyên viên CSKH sẽ hỗ trợ anh/chị ngay ạ.",
                session_id=session_id,
                sources=[],
                waiting_for_cs=True,
                status="NEEDS_HUMAN_CS",
                cs_agent=None,
                ai_locked=True,
            )

        # 3. Trạng thái bình thường: AI trả lời
        if llm is None:
            raise HTTPException(status_code=503, detail="LLM chưa được khởi tạo. Hãy set ANTHROPIC_API_KEY.")

        if vector_store is None:
            raise HTTPException(status_code=503, detail="Vector store chưa được khởi tạo.")

        reply, sources, is_fallback = await generate_response(clean_msg, session_id, save_user_msg=True)

        case_status = "NEEDS_HUMAN_CS" if is_fallback else "AI_ACTIVE"
        upsert_chat_case(
            session_id=session_id,
            customer_name=customer_display_name,
            status=case_status,
            last_user_query=clean_msg,
        )

        return ChatResponse(
            reply=reply,
            session_id=session_id,
            sources=sources,
            waiting_for_cs=is_fallback,
            status=case_status,
            cs_agent=None,
            ai_locked=False,
        )
    except Exception as e:
        print(f"❌ Error in chat: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý: {str(e)}")


@app.get("/history/{session_id}")
async def get_history(session_id: str):
    """Lấy lịch sử chat và trạng thái case để Client và CSKH đồng bộ realtime."""
    messages = get_session_history(session_id)
    case = get_chat_case(session_id)
    return {
        "session_id": session_id,
        "status": case.get("status", "AI_ACTIVE") if case else "AI_ACTIVE",
        "assigned_cs": case.get("assigned_cs") if case else None,
        "messages": messages,
    }


# ============================================================
# CSKH & Admin Authentication Endpoints
# ============================================================
@app.post("/auth/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """Đăng nhập tài khoản chuyên viên CSKH hoặc Admin."""
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
    """Lấy thông tin người dùng đang đăng nhập."""
    return {
        "username": user["username"],
        "full_name": user["full_name"],
        "role": user["role"],
    }


@app.post("/auth/logout")
async def logout(user: dict = Depends(get_current_user)):
    """Đăng xuất khỏi hệ thống."""
    delete_session(user["token"])
    return {"message": "Đã đăng xuất thành công."}


# ============================================================
# CSKH Portal API: Live CS Inbox (Tab 1)
# ============================================================
@app.get("/api/admin/cases")
async def api_list_cases(status: str = "", user: dict = Depends(get_current_user)):
    """Lấy danh sách các case hội thoại."""
    cases = list_chat_cases(status_filter=status)
    return {"cases": cases}


@app.post("/api/admin/cases/{session_id}/take")
async def api_take_case(
    session_id: str,
    agent_name: str = Form(default="Chuyên viên CSKH"),
    user: dict = Depends(get_current_user),
):
    """Chuyên viên CSKH tiếp nhận hỗ trợ case."""
    cs_name = user.get("full_name") or agent_name or user.get("username")
    assign_chat_case(session_id, cs_name)

    # Gửi tin nhắn chào từ CSKH vào luồng chat
    intro_msg = f"Dạ em chào anh/chị, em là {cs_name} - Chuyên viên CSKH của Đông Đô Partners. Em đã tham gia cuộc trò chuyện và sẽ hỗ trợ anh/chị ngay đây ạ!"
    save_message(session_id, "human_cs", intro_msg, username=user.get("username"))
    add_to_conversation(session_id, "human_cs", intro_msg)

    return {"success": True, "message": f"Đã tiếp nhận case cho {cs_name}"}


@app.post("/api/admin/cases/{session_id}/reply")
async def api_reply_case(
    session_id: str,
    req: CSReplyRequest,
    user: dict = Depends(get_current_user),
):
    """CSKH gửi tin nhắn phản hồi trực tiếp tới khách hàng."""
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Tin nhắn không được để trống")

    cs_name = user.get("full_name") or req.agent_name or user.get("username")
    clean_msg = req.message.strip()

    save_message(session_id, "human_cs", clean_msg, username=user.get("username"))
    add_to_conversation(session_id, "human_cs", clean_msg)
    upsert_chat_case(session_id, status="HUMAN_CS_ACTIVE", assigned_cs=cs_name, force_status=True)

    return {"success": True, "message": "Đã gửi tin nhắn thành công"}


@app.post("/api/admin/cases/{session_id}/resume-ai")
async def api_resume_ai(
    session_id: str,
    user: dict = Depends(get_current_user),
):
    """CSKH yêu cầu AI tiếp tục tham gia trả lời trong cuộc hội thoại (hoàn toàn âm thầm với KH)."""
    cs_name = user.get("full_name") or user.get("username") or "Chuyên viên CSKH"

    # Chuyển trạng thái case về AI_ACTIVE (force_status bỏ qua luật bảo vệ)
    upsert_chat_case(session_id, status="AI_ACTIVE", assigned_cs=cs_name, force_status=True)

    # KHÔNG gửi thông báo cho khách hàng biết đã bật lại AI (chuyển giao âm thầm)

    # Tự động giải đáp câu hỏi đang chờ của khách hàng nếu có
    history = get_session_history(session_id)
    answered_pending = False
    ai_reply_preview = ""
    if history:
        last_client_msg = history[-1]
        if last_client_msg.get("role") == "user":
            pending_query = (last_client_msg.get("content") or "").strip()
            if pending_query and llm is not None and vector_store is not None:
                try:
                    reply, sources, is_fallback = await generate_response(pending_query, session_id, save_user_msg=False)
                    answered_pending = True
                    ai_reply_preview = reply[:120]
                    if is_fallback:
                        upsert_chat_case(session_id, status="NEEDS_HUMAN_CS", last_user_query=pending_query, force_status=True)
                except Exception as e:
                    print(f"❌ Error auto-answering pending query on resume-ai: {e}")

    return {
        "success": True,
        "message": f"Đã bật lại AI cho case {session_id}",
        "answered_pending": answered_pending,
        "ai_reply": ai_reply_preview,
    }


@app.post("/api/admin/cases/{session_id}/resolve")
async def api_resolve_case(
    session_id: str,
    req: CSResolveRequest,
    user: dict = Depends(get_current_user),
):
    """Đóng case và xử lý nạp tri thức mới (Tự động hoặc Chờ duyệt)."""
    cs_name = user.get("full_name") or req.agent_name or user.get("username")
    resolve_chat_case(session_id, cs_name, req.resolution_note)

    auto_learn = get_setting("auto_learning_enabled", "0") == "1"

    # Thu thập tất cả các cặp Q&A cần học
    pairs_to_process = []
    if req.extract_pairs:
        for p in req.extract_pairs:
            q_txt = p.question.strip() if p.question else ""
            a_txt = p.answer.strip() if p.answer else ""
            if q_txt and a_txt:
                pairs_to_process.append((q_txt, a_txt))
    elif req.extract_question and req.extract_answer:
        q_txt = req.extract_question.strip()
        a_txt = req.extract_answer.strip()
        if q_txt and a_txt:
            pairs_to_process.append((q_txt, a_txt))

    if pairs_to_process:
        learned_count = 0
        for q, a in pairs_to_process:
            if auto_learn:
                item_id = add_to_learning_queue(session_id, q, a, created_by=cs_name, status="APPROVED")
                mark_learning_item_status(item_id, "APPROVED", approved_by=cs_name)
                embed_qa_to_chromadb(q, a, session_id)
                learned_count += 1
            else:
                add_to_learning_queue(session_id, q, a, created_by=cs_name, status="PENDING")
                learned_count += 1

        if auto_learn:
            return {
                "success": True,
                "auto_learned": True,
                "learned_count": learned_count,
                "message": f"Đã đóng case và TỰ ĐỘNG nạp {learned_count} cặp câu hỏi & câu trả lời vào ChromaDB thành công! Lần sau AI sẽ tự trả lời.",
            }
        else:
            return {
                "success": True,
                "auto_learned": False,
                "learned_count": learned_count,
                "message": f"Đã đóng case và đưa {learned_count} cặp Q&A vào Hàng đợi phê duyệt tri thức mới.",
            }

    return {"success": True, "auto_learned": False, "message": "Đã đóng case thành công."}


@app.post("/api/admin/cases/clear-all")
async def api_clear_all_cases(user: dict = Depends(get_current_user)):
    """Xóa toàn bộ danh sách case hỗ trợ, lịch sử chat và hàng đợi tri thức test."""
    clear_all_cases()
    conversation_memories.clear()
    return {"success": True, "message": "Đã xóa sạch toàn bộ danh sách case hỗ trợ và lịch sử chat test thành công!"}


@app.delete("/api/admin/cases/{session_id}")
async def api_delete_case(session_id: str, user: dict = Depends(get_current_user)):
    """Xóa 1 case hỗ trợ và lịch sử chat của nó."""
    delete_chat_case(session_id)
    if session_id in conversation_memories:
        del conversation_memories[session_id]
    return {"success": True, "message": f"Đã xóa case {session_id} thành công!"}


# ============================================================
# CSKH Portal API: Continuous Learning Queue (Tab 2)
# ============================================================
@app.get("/api/admin/learning/pending")
async def api_get_pending_learning(user: dict = Depends(get_current_user)):
    """Lấy danh sách các mẩu Q&A đang chờ phê duyệt."""
    items = list_learning_items(status="PENDING")
    return {"pending_items": items}


@app.post("/api/admin/learning/approve/{item_id}")
async def api_approve_learning(item_id: int, user: dict = Depends(get_current_user)):
    """Phê duyệt mẩu Q&A và nạp trực tiếp vào ChromaDB."""
    item = get_learning_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Không tìm thấy mẩu tri thức này")

    approver = user.get("full_name") or user.get("username")
    embed_qa_to_chromadb(item["question"], item["answer"], item.get("session_id", ""))
    mark_learning_item_status(item_id, "APPROVED", approved_by=approver)

    return {
        "success": True,
        "message": f"Đã phê duyệt và nạp tri thức vào ChromaDB thành công bởi {approver}!",
    }


@app.post("/api/admin/learning/reject/{item_id}")
async def api_reject_learning(item_id: int, user: dict = Depends(get_current_user)):
    """Từ chối / bỏ qua mẩu Q&A."""
    mark_learning_item_status(item_id, "REJECTED", approved_by=user.get("username"))
    return {"success": True, "message": "Đã từ chối mẩu tri thức"}


@app.get("/api/admin/learning/settings")
async def api_get_learning_settings(user: dict = Depends(get_current_user)):
    """Lấy trạng thái nút gạt: Tự động nạp vào ChromaDB hay Duyệt thủ công."""
    return {
        "auto_learning_enabled": get_setting("auto_learning_enabled", "0") == "1",
    }


@app.post("/api/admin/learning/settings")
async def api_set_learning_settings(
    req: LearningSettingsRequest,
    user: dict = Depends(get_current_user),
):
    """Cập nhật nút gạt tự động nạp tri thức vào ChromaDB."""
    set_setting("auto_learning_enabled", "1" if req.auto_learning_enabled else "0")
    return {
        "success": True,
        "auto_learning_enabled": req.auto_learning_enabled,
        "message": f"Đã {'BẬT' if req.auto_learning_enabled else 'TẮT'} chế độ tự động nạp tri thức vào ChromaDB.",
    }


@app.post("/api/admin/learning/reset")
async def api_reset_learned_knowledge(user: dict = Depends(get_current_user)):
    """Xóa toàn bộ các tri thức CSKH đã nạp vào ChromaDB và CSDL."""
    global vector_store
    deleted_count = 0
    if vector_store:
        try:
            data = vector_store.get()
            ids_to_delete = [
                doc_id for doc_id, meta in zip(data["ids"], data["metadatas"])
                if (meta and meta.get("source") == "CSKH_Learning") or str(doc_id).startswith("learned_qa")
            ]
            if ids_to_delete:
                vector_store.delete(ids=ids_to_delete)
                deleted_count = len(ids_to_delete)
        except Exception as e:
            print(f"Error resetting chromadb: {e}")

    clear_learned_knowledge()
    return {
        "success": True,
        "deleted_count": deleted_count,
        "message": f"Đã xóa thành công {deleted_count} mẩu tri thức CSKH khỏi ChromaDB và đặt lại toàn bộ hàng đợi tri thức!",
    }


# ============================================================
# CSKH Portal API: Knowledge Base Manager (Tab 3)
# ============================================================
@app.get("/api/admin/knowledge")
async def api_get_knowledge(user: dict = Depends(get_current_user)):
    """Lấy tổng quan kho tri thức Vector DB và danh sách file tài liệu."""
    chunk_count = 0
    if vector_store and hasattr(vector_store, "_collection"):
        try:
            chunk_count = vector_store._collection.count()
        except Exception:
            pass

    # Lấy danh sách file .docx trong thư mục tailieu
    os.makedirs(DOCUMENTS_DIR, exist_ok=True)
    docx_files = glob.glob(os.path.join(DOCUMENTS_DIR, "*.docx"))

    db_docs = {d["filename"]: d for d in list_uploaded_documents()}
    doc_list = []
    seen = set()

    for fpath in docx_files:
        fname = os.path.basename(fpath)
        fsize = round(os.path.getsize(fpath) / 1024, 1)
        seen.add(fname)
        doc_list.append({
            "filename": fname,
            "size_kb": fsize,
            "can_delete": True,
        })

    # Nếu có file trong DB mà chưa có trên đĩa
    for fname, d in db_docs.items():
        if fname not in seen:
            doc_list.append({
                "filename": fname,
                "size_kb": d["size_kb"],
                "can_delete": True,
            })

    return {
        "total_chunks": chunk_count,
        "total_documents": len(doc_list),
        "embedding_model": EMBEDDING_MODEL,
        "documents": doc_list,
    }


@app.post("/api/admin/knowledge/upload")
async def api_upload_document(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Tải lên file tài liệu .docx mới, lưu vào folder tailieu/, nhúng ChromaDB và lưu Database vĩnh viễn."""
    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ định dạng file tài liệu Microsoft Word (.docx)")

    os.makedirs(DOCUMENTS_DIR, exist_ok=True)
    save_path = os.path.join(DOCUMENTS_DIR, file.filename)

    content = await file.read()
    with open(save_path, "wb") as buffer:
        buffer.write(content)

    # Đọc và chia nhỏ tài liệu
    text = extract_text_from_docx(save_path)
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="File tài liệu rỗng hoặc không có nội dung văn bản.")

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", ", ", " ", ""],
    )
    chunks = text_splitter.split_text(text)

    # Nhúng vào ChromaDB (xóa chunks cũ của file này nếu có để cập nhật mới)
    ingested_at = datetime.now().isoformat()
    if vector_store and hasattr(vector_store, "_collection"):
        try:
            vector_store._collection.delete(where={"source": file.filename})
        except Exception:
            pass

    metadatas = [
        {"source": file.filename, "chunk_id": i, "ingested_at": ingested_at, "type": "uploaded_doc"}
        for i in range(len(chunks))
    ]
    ids = [f"upload_{int(datetime.now().timestamp())}_{i}" for i in range(len(chunks))]

    if vector_store:
        vector_store.add_texts(texts=chunks, metadatas=metadatas, ids=ids)

    # Lưu file nhị phân vào Database để bảo toàn qua các lần deploy Render
    fsize_kb = round(len(content) / 1024, 1)
    save_uploaded_document(file.filename, content, fsize_kb, len(chunks))

    return {
        "success": True,
        "filename": file.filename,
        "chunks_added": len(chunks),
        "message": f"Đã lưu vào thư mục tailieu/ và nạp thành công '{file.filename}' ({len(chunks)} chunks) vào VectorDB!",
    }


@app.delete("/api/admin/knowledge/{filename}")
async def api_delete_document(
    filename: str,
    user: dict = Depends(get_current_user),
):
    """Xóa tài liệu khỏi folder tailieu/, gỡ khỏi ChromaDB và Database."""
    # 1. Xóa trong database
    delete_uploaded_document(filename)

    # 2. Xóa file trong folder tailieu/
    fpath = os.path.join(DOCUMENTS_DIR, filename)
    file_deleted = False
    if os.path.exists(fpath):
        try:
            os.remove(fpath)
            file_deleted = True
        except Exception as e:
            print(f"Lỗi xóa file {fpath}: {e}")

    # 3. Gỡ các vector chunks tương ứng khỏi ChromaDB
    chunks_deleted = False
    if vector_store and hasattr(vector_store, "_collection"):
        try:
            vector_store._collection.delete(where={"source": filename})
            chunks_deleted = True
        except Exception as e:
            print(f"Lỗi gỡ chunks ChromaDB cho {filename}: {e}")

    return {
        "success": True,
        "message": f"Đã xóa vĩnh viễn tài liệu '{filename}' khỏi folder tailieu/ và gỡ toàn bộ tri thức khỏi VectorDB!",
        "file_deleted": file_deleted,
        "chunks_deleted": chunks_deleted,
    }


@app.get("/api/admin/knowledge/{filename}/download")
async def api_download_document(
    filename: str,
    token: str = None,
    authorization: str = Header(None),
):
    """Tải file tài liệu về máy (trực tiếp từ đĩa tailieu/ hoặc trích từ Database)."""
    auth_token = None
    if authorization and authorization.startswith("Bearer "):
        auth_token = authorization.split(" ")[1]
    elif token:
        auth_token = token

    user = verify_session(auth_token) if auth_token else None
    if not user:
        raise HTTPException(status_code=401, detail="Chưa xác thực hoặc phiên làm việc hết hạn")

    fpath = os.path.join(DOCUMENTS_DIR, filename)
    if not os.path.exists(fpath):
        fbytes = get_uploaded_document_bytes(filename)
        if fbytes:
            os.makedirs(DOCUMENTS_DIR, exist_ok=True)
            with open(fpath, "wb") as f:
                f.write(fbytes)
        else:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy tài liệu '{filename}'")

    return FileResponse(
        path=fpath,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )




# ============================================================
# CSKH Portal API: Analytics & Reports (Tab 4)
# ============================================================
@app.get("/api/admin/analytics")
async def api_get_analytics(user: dict = Depends(get_current_user)):
    """Trả về các số liệu thống kê tự động hóa và tăng trưởng tri thức."""
    stats = get_analytics_stats()
    return stats


# ============================================================
# CSKH Portal API: System Configuration (Tab 5)
# ============================================================
@app.get("/api/admin/config")
async def api_get_config(user: dict = Depends(get_current_user)):
    """Lấy cấu hình System Prompt và tham số LLM."""
    return {
        "system_prompt": get_setting("system_prompt", SYSTEM_PROMPT),
        "llm_model": get_setting("llm_model", LLM_MODEL),
        "temperature": float(get_setting("temperature", str(LLM_TEMPERATURE))),
    }


@app.post("/api/admin/config")
async def api_save_config(
    req: SystemConfigRequest,
    user: dict = Depends(get_current_user),
):
    """Lưu cấu hình và khởi tạo lại LLM runtime."""
    global llm

    set_setting("system_prompt", req.system_prompt)
    set_setting("llm_model", req.llm_model)
    set_setting("temperature", str(req.temperature))

    if ANTHROPIC_API_KEY:
        llm = ChatAnthropic(
            model=req.llm_model,
            anthropic_api_key=ANTHROPIC_API_KEY,
            temperature=req.temperature,
            max_tokens=4096,
        )

    return {"success": True, "message": "Đã lưu cấu hình và cập nhật LLM Engine thành công!"}


# ============================================================
# Run Application
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
