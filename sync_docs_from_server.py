#!/usr/bin/env python3
"""
Đông Đô Partners - Đồng Bộ Tài Liệu Từ Server Render Về Máy Local
Tải toàn bộ tài liệu đã upload trên Dashboard (Render) về thư mục tailieu/ của máy tính cá nhân.
"""
import os
import sys
import requests

SERVER_URL = os.environ.get("DONGDO_SERVER_URL", "https://dongdo-cs-chatbot.onrender.com")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "DongDo@2026")

LOCAL_DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tailieu")

def main():
    print("=" * 60)
    print("🚀 Đang kết nối tới server Render để đồng bộ tài liệu...")
    print(f"   Server: {SERVER_URL}")
    print("=" * 60)

    # 1. Đăng nhập lấy Bearer token
    login_url = f"{SERVER_URL}/auth/login"
    try:
        res = requests.post(login_url, json={"username": ADMIN_USER, "password": ADMIN_PASS}, timeout=15)
        if not res.ok:
            print(f"❌ Đăng nhập thất bại: {res.status_code} - {res.text}")
            return
        token = res.json().get("token")
    except Exception as e:
        print(f"❌ Lỗi kết nối tới server: {e}")
        return

    headers = {"Authorization": f"Bearer {token}"}

    # 2. Lấy danh sách tài liệu trên server
    list_url = f"{SERVER_URL}/api/admin/knowledge"
    try:
        res = requests.get(list_url, headers=headers, timeout=15)
        if not res.ok:
            print(f"❌ Không thể lấy danh sách tài liệu: {res.text}")
            return
        data = res.json()
        docs = data.get("documents", [])
    except Exception as e:
        print(f"❌ Lỗi lấy danh sách tài liệu: {e}")
        return

    os.makedirs(LOCAL_DOCS_DIR, exist_ok=True)
    print(f"📚 Tìm thấy {len(docs)} tài liệu trên server. Đang kiểm tra thư mục '{LOCAL_DOCS_DIR}'...")

    synced_count = 0
    for doc in docs:
        fname = doc["filename"]
        local_path = os.path.join(LOCAL_DOCS_DIR, fname)
        if not os.path.exists(local_path):
            print(f"   📥 Đang tải về: {fname} ({doc.get('size_kb', 0)} KB)...")
            dl_url = f"{SERVER_URL}/api/admin/knowledge/{fname}/download"
            try:
                dl_res = requests.get(dl_url, headers=headers, timeout=30)
                if dl_res.ok:
                    with open(local_path, "wb") as f:
                        f.write(dl_res.content)
                    print(f"   ✅ Đã lưu vào: tailieu/{fname}")
                    synced_count += 1
                else:
                    print(f"   ⚠️ Lỗi tải file {fname}: {dl_res.status_code}")
            except Exception as de:
                print(f"   ⚠️ Lỗi tải {fname}: {de}")
        else:
            print(f"   ✓ Đã có sẵn trên máy: {fname}")

    print("=" * 60)
    print(f"🎉 Hoàn tất! Đã đồng bộ thêm {synced_count} file mới về máy.")
    print("=" * 60)

if __name__ == "__main__":
    main()
