# Đông Đô CS Chatbot

Dự án này là một Chatbot hỗ trợ chăm sóc khách hàng cho Đông Đô Partners, sử dụng mô hình ngôn ngữ của Anthropic (Claude) và hệ thống truy xuất thông tin (RAG) với ChromaDB.

## 🚀 Hướng dẫn cài đặt cho người mới tải về

Vì các thư mục chứa môi trường ảo (`venv`), cơ sở dữ liệu (`chat_history.db`) và dữ liệu vector (`vectordb`) đã được bỏ qua để tối ưu dung lượng, bạn cần thực hiện các bước sau để chạy dự án:

### Bước 1: Tạo môi trường ảo và cài đặt thư viện
Mở terminal tại thư mục dự án và chạy các lệnh sau:

**Trên Windows:**
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**Trên macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Bước 2: Cài đặt API Key
Dự án sử dụng API của Anthropic (Claude). Bạn cần thiết lập biến môi trường `ANTHROPIC_API_KEY`.
- Tạo một file tên `.env` ở thư mục gốc của dự án.
- Thêm dòng sau vào file `.env`:
```env
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxx
```
*(Thay thế đoạn `sk-ant...` bằng API Key thực tế của bạn)*

### Bước 3: Khởi tạo dữ liệu (VectorDB)
Do thư mục `vectordb` không được tải lên Git, bạn cần chạy file `ingest.py` để hệ thống đọc tài liệu từ thư mục `tailieu` và tạo database mới:
```bash
python ingest.py
```

### Bước 4: Chạy ứng dụng
Sau khi đã nạp dữ liệu xong, bạn có thể khởi động server bằng lệnh:
```bash
python main.py
```
Hoặc nếu chạy qua Uvicorn:
```bash
uvicorn main:app --reload
```

Sau đó, truy cập ứng dụng (thường là tại `http://localhost:8000` hoặc port được chỉ định).
