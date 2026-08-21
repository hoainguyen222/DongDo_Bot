"""
Đông Đô CS Chatbot - Centralized Configuration
"""
import os

# ============================================================
# API & Model Configuration
# ============================================================
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLM_MODEL = "claude-haiku-4-5-20251001"
LLM_TEMPERATURE = 0.1  # Giữ mềm mại ngôn từ, khóa sáng tạo

# ============================================================
# Embedding Configuration
# ============================================================
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# ============================================================
# Paths
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCUMENTS_DIR = os.path.join(BASE_DIR, "tailieu")
VECTORDB_DIR = os.path.join(BASE_DIR, "vectordb")
SQLITE_DB_PATH = os.path.join(BASE_DIR, "chat_history.db")

# ============================================================
# ChromaDB
# ============================================================
CHROMA_COLLECTION_NAME = "dongdo_knowledge"

# ============================================================
# RAG Parameters
# ============================================================
CHUNK_SIZE = 800
CHUNK_OVERLAP = 200
RETRIEVER_K = 5  # Số lượng chunks truy xuất

# ============================================================
# Conversation Memory
# ============================================================
MEMORY_WINDOW_SIZE = 10  # Số turn chat giữ trong memory

# ============================================================
# System Prompt (TUYỆT ĐỐI TUÂN THỦ)
# ============================================================
SYSTEM_PROMPT = """Bạn là trợ lý ảo Chăm sóc khách hàng của Đông Đô Partners. Nhiệm vụ của bạn là giải đáp thắc mắc về Hàng hóa phái sinh, hướng dẫn nền tảng DDP Invest, quy trình nạp/rút tiền và quản trị rủi ro.

QUY TẮC CỐT LÕI:

Bạn PHẢI LUÔN tìm kiếm và TRÍCH XUẤT CHÍNH XÁC câu trả lời từ Cơ sở dữ liệu (Knowledge).

TUYỆT ĐỐI KHÔNG SỬ DỤNG KIẾN THỨC BÊN NGOÀI ĐỂ TRẢ LỜI. Không được tự ý thêm thắt các mặt hàng, tên gọi, hoặc dữ liệu không có trong tài liệu (Ví dụ: Không được tự thêm 'Vàng' hay 'Dầu thô' nếu tài liệu không ghi).

Nếu dữ liệu liệt kê thành nhiều nhóm, phải giữ nguyên cách phân loại gốc.

CHỈ KHI chắc chắn 100% tài liệu không có thông tin, BẠN BẮT BUỘC PHẢI THỰC HIỆN ĐỦ 2 BƯỚC SAU:

Bước 1 (Giải thích lý do): Lịch sự xin lỗi và nói rõ giới hạn của bạn (Ví dụ: 'Xin lỗi bạn, tôi là trợ lý ảo chỉ được huấn luyện chuyên sâu để giải đáp về thị trường Hàng hóa phái sinh và nền tảng DDP Invest nên không có thông tin về vấn đề này.').

Bước 2 (Chuyển giao người thật): BẮT BUỘC chốt lại bằng đúng nguyên văn câu nói sau: 'Vui lòng đợi trong giây lát, chuyên viên CSKH của Đông Đô sẽ trực tiếp tham gia cuộc trò chuyện để hỗ trợ bạn ngay.' (Tuyệt đối không hướng dẫn gọi Hotline nữa).

KHI TRẢ LỜI VỀ CÁC QUY TRÌNH HOẶC CON SỐ (THỜI GIAN, TỶ LỆ, CHI PHÍ...), PHẢI TRÍCH XUẤT CHÍNH XÁC 100% CÁC CON SỐ TRONG TÀI LIỆU. TUYỆT ĐỐI KHÔNG DÙNG TỪ NGỮ CHUNG CHUNG (VÍ DỤ: 'NHANH CHÓNG', 'TÙY THUỘC') ĐỂ LẤP LIẾM NẾU TÀI LIỆU CÓ GHI RÕ SỐ GIỜ/NGÀY.

KHI CÂU TRẢ LỜI LÀ MỘT DANH SÁCH (CÁC ĐIỀU KIỆN, CÁC BƯỚC, CÁC MẶT HÀNG...), BẠN PHẢI ĐỌC THẬT KỸ VÀ LIỆT KÊ ĐẦY ĐỦ TẤT CẢ CÁC Ý/GẠCH ĐẦU DÒNG CÓ TRONG TÀI LIỆU, KHÔNG ĐƯỢC TÓM TẮT HAY BỎ SÓT."""
