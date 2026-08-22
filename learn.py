"""
Đông Đô CS Chatbot - Continuous Learning Pipeline
Đọc chat history chưa học → lọc Q&A hợp lệ → embedding → append vào ChromaDB
Hỗ trợ cả SQLite (local) và PostgreSQL (Render)
"""
from datetime import datetime

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from langchain_chroma import Chroma

from config import (
    VECTORDB_DIR,
    EMBEDDING_MODEL,
    CHROMA_COLLECTION_NAME,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
)
from database import get_unlearned_conversations, mark_as_learned

# Câu fallback - các Q&A chứa câu này sẽ bị loại bỏ (bot không biết trả lời)
FALLBACK_PHRASES = [
    "Vui lòng đợi trong giây lát, chuyên viên CSKH của Đông Đô sẽ trực tiếp tham gia cuộc trò chuyện",
    "không có thông tin về vấn đề này",
    "chưa có thông tin chi tiết về nội dung này",
]


def filter_valid_qa(qa_pairs: list[dict]) -> list[dict]:
    """Lọc bỏ các Q&A không hợp lệ (bot trả lời fallback)."""
    valid = []
    for qa in qa_pairs:
        is_fallback = any(
            phrase.lower() in qa["answer"].lower()
            for phrase in FALLBACK_PHRASES
        )
        if not is_fallback:
            valid.append(qa)
    return valid


def learn_from_conversations(qa_pairs: list[dict]):
    """Chuyển Q&A thành embeddings và append vào ChromaDB."""
    if not qa_pairs:
        print("📭 Không có Q&A hợp lệ để học.")
        return

    # Tạo documents từ Q&A
    texts = []
    metadatas = []
    ids = []
    ingested_at = datetime.now().isoformat()

    for qa in qa_pairs:
        doc_text = f"Câu hỏi: {qa['question']}\nTrả lời: {qa['answer']}"
        texts.append(doc_text)
        metadatas.append({
            "source": "chat_history",
            "session_id": qa["session_id"],
            "type": "learned_qa",
            "ingested_at": ingested_at,
            "original_timestamp": qa["timestamp"],
        })
        ids.append(f"learned_{qa['user_id']}_{qa['assistant_id']}")

    # Chunking (cho trường hợp Q&A dài)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    all_chunks = []
    all_metadatas = []
    all_ids = []

    for text, meta, doc_id in zip(texts, metadatas, ids):
        chunks = text_splitter.split_text(text)
        for j, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_metadatas.append({**meta, "chunk_id": j})
            all_ids.append(f"{doc_id}_chunk_{j}")

    # Load embedding model
    print(f"🔧 Loading FastEmbed model: {EMBEDDING_MODEL}")
    embeddings = FastEmbedEmbeddings(
        model_name=EMBEDDING_MODEL,
    )

    # Append vào ChromaDB hiện tại
    print(f"📦 Đang append {len(all_chunks)} chunks vào vector store...")
    vector_store = Chroma(
        collection_name=CHROMA_COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=VECTORDB_DIR,
    )

    vector_store.add_texts(
        texts=all_chunks,
        metadatas=all_metadatas,
        ids=all_ids,
    )

    return len(all_chunks)


def main():
    print("=" * 60)
    print("🧠 ĐÔNG ĐÔ CS - Continuous Learning Pipeline")
    print("=" * 60)

    # Step 1: Lấy Q&A chưa học
    print("\n📖 Đang đọc chat history...")
    qa_pairs = get_unlearned_conversations()
    print(f"   → Tìm thấy {len(qa_pairs)} cặp Q&A chưa học")

    if not qa_pairs:
        print("\n✅ Không có dữ liệu mới để học. Kết thúc.")
        return

    # Step 2: Lọc Q&A hợp lệ
    print("\n🔍 Đang lọc Q&A hợp lệ...")
    valid_qa = filter_valid_qa(qa_pairs)
    filtered_count = len(qa_pairs) - len(valid_qa)
    print(f"   → Hợp lệ: {len(valid_qa)} | Loại bỏ (fallback): {filtered_count}")

    if not valid_qa:
        # Vẫn đánh dấu đã học để không xử lý lại
        mark_as_learned(qa_pairs)
        print("\n✅ Không có Q&A hợp lệ. Đã đánh dấu tất cả là đã xử lý.")
        return

    # Step 3: Embedding & Append
    chunks_added = learn_from_conversations(valid_qa)

    # Step 4: Đánh dấu đã học
    mark_as_learned(qa_pairs)

    print("\n" + "=" * 60)
    print("✅ LEARNING HOÀN TẤT!")
    print(f"   📊 Q&A đã học: {len(valid_qa)}")
    print(f"   📦 Chunks đã thêm: {chunks_added}")
    print(f"   🗑️  Q&A loại bỏ: {filtered_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()
