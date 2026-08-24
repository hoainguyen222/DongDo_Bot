"""
Test suite for Đông Đô CS Chatbot & CSKH Portal
"""
import os
import sys
import unittest
from fastapi.testclient import TestClient

# Ensure root dir is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from database import init_database
import main
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import AIMessage

class TestCSKHPortal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Mock LLM for local test without Anthropic API Key
        mock_llm = MagicMock()
        async def mock_ainvoke(messages):
            # Check if messages contain cam
            user_msg = messages[-1].content
            if "cam" in user_msg.lower():
                return AIMessage(content="Dạ xin lỗi anh/chị, hiện tại em chưa có thông tin chi tiết về nội dung này trong hệ thống dữ liệu của Đông Đô Partners. Vui lòng đợi trong giây lát, chuyên viên CSKH của Đông Đô sẽ trực tiếp tham gia cuộc trò chuyện để hỗ trợ bạn ngay.")
            return AIMessage(content="Đông Đô Partners là đơn vị tư vấn Hàng hóa phái sinh hàng đầu.")
        mock_llm.ainvoke = AsyncMock(side_effect=mock_ainvoke)
        main.llm = mock_llm

        cls.test_client_ctx = TestClient(app)
        cls.client = cls.test_client_ctx.__enter__()
        main.llm = mock_llm

    @classmethod
    def tearDownClass(cls):
        cls.test_client_ctx.__exit__(None, None, None)

    def test_01_customer_auth_and_chat(self):
        """Khách hàng bắt buộc đăng nhập để chat."""
        # 1. Chat không có token -> 401
        res_no_auth = self.client.post("/chat", json={"message": "Xin chào, Đông Đô Partners có những dịch vụ gì?"})
        self.assertEqual(res_no_auth.status_code, 401)

        # 2. Khách hàng đăng nhập khach01 / DongDo@123
        login_res = self.client.post("/auth/login", json={"username": "khach01", "password": "DongDo@123"})
        self.assertEqual(login_res.status_code, 200)
        data_login = login_res.json()
        self.assertIn("token", data_login)
        self.__class__.customer_token = data_login["token"]

        # 3. Chat có token -> 200 OK
        res = self.client.post(
            "/chat",
            json={"message": "Xin chào, Đông Đô Partners có những dịch vụ gì?"},
            headers={"Authorization": f"Bearer {self.customer_token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("reply", data)
        self.assertIn("session_id", data)
        self.assertIn("status", data)
        print("✅ Test 1 Passed: Customer Auth & Chat OK (Status:", data["status"], ")")

    def test_02_cskh_login(self):
        """Chuyên viên CSKH đăng nhập thành công với tài khoản mặc định."""
        res = self.client.post("/auth/login", json={"username": "cskh01", "password": "DongDo@123"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("token", data)
        self.assertEqual(data["username"], "cskh01")
        self.__class__.token = data["token"]
        print("✅ Test 2 Passed: CSKH Login OK (Token received)")

    def test_03_admin_login(self):
        """Admin đăng nhập thành công với tài khoản admin mặc định."""
        res = self.client.post("/auth/login", json={"username": "admin", "password": "DongDo@2026"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("token", data)
        self.assertEqual(data["role"], "admin")
        print("✅ Test 3 Passed: Admin Login OK")

    def test_04_fallback_and_case_creation(self):
        """Câu hỏi ngoài dữ liệu kích hoạt fallback và tạo case NEEDS_HUMAN_CS."""
        session_id = "test-session-fallback-999"
        res = self.client.post(
            "/chat",
            json={
                "session_id": session_id,
                "message": "Cho tôi hỏi quả cam bao nhiêu tiền một cân?"
            },
            headers={"Authorization": f"Bearer {self.customer_token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "NEEDS_HUMAN_CS")
        self.assertTrue(data["waiting_for_cs"])

        # Kiểm tra API admin lấy danh sách case
        headers = {"Authorization": f"Bearer {self.token}"}
        cases_res = self.client.get("/api/admin/cases?status=NEEDS_HUMAN_CS", headers=headers)
        self.assertEqual(cases_res.status_code, 200)
        cases = cases_res.json()["cases"]
        found = any(c["session_id"] == session_id for c in cases)
        self.assertTrue(found)
        print("✅ Test 4 Passed: Fallback trigger and case inbox OK")

    def test_05_cskh_take_and_reply(self):
        """CSKH tiếp nhận case và gửi tin nhắn trực tiếp."""
        session_id = "test-session-fallback-999"
        headers = {"Authorization": f"Bearer {self.token}"}

        # 1. Take case
        take_res = self.client.post(
            f"/api/admin/cases/{session_id}/take",
            data={"agent_name": "Chuyên viên CSKH 01"},
            headers=headers
        )
        self.assertEqual(take_res.status_code, 200)

        # 2. Reply
        reply_res = self.client.post(
            f"/api/admin/cases/{session_id}/reply",
            json={"agent_name": "Chuyên viên CSKH 01", "message": "Dạ quả cam có giá là 12.000đ/kg ạ!"},
            headers=headers
        )
        self.assertEqual(reply_res.status_code, 200)

        # 3. Client checks history
        hist_res = self.client.get(f"/history/{session_id}")
        self.assertEqual(hist_res.status_code, 200)
        hist = hist_res.json()
        self.assertEqual(hist["status"], "HUMAN_CS_ACTIVE")
        self.assertTrue(any(m["role"] == "human_cs" for m in hist["messages"]))
        print("✅ Test 5 Passed: CSKH Takeover & Reply Realtime OK")

    def test_06_auto_learning_toggle_and_resolve(self):
        """Test cơ chế đóng case và tự động học / duyệt thủ công."""
        session_id = "test-session-fallback-999"
        headers = {"Authorization": f"Bearer {self.token}"}

        # Bật chế độ tự động học (Auto-Learn ON)
        set_res = self.client.post(
            "/api/admin/learning/settings",
            json={"auto_learning_enabled": True},
            headers=headers
        )
        self.assertEqual(set_res.status_code, 200)
        self.assertTrue(set_res.json()["auto_learning_enabled"])

        # Đóng case và trích xuất Q&A
        resolve_res = self.client.post(
            f"/api/admin/cases/{session_id}/resolve",
            json={
                "agent_name": "Chuyên viên CSKH 01",
                "resolution_note": "Đã giải đáp giá cam",
                "extract_question": "Quả cam bao nhiêu tiền?",
                "extract_answer": "Quả cam có giá 12.000 đồng/kg."
            },
            headers=headers
        )
        self.assertEqual(resolve_res.status_code, 200)
        self.assertTrue(resolve_res.json()["auto_learned"])
        print("✅ Test 6 Passed: Auto-Learn ChromaDB embedding OK")

    def test_07_analytics_and_config(self):
        """Test API báo cáo thống kê và cấu hình hệ thống."""
        headers = {"Authorization": f"Bearer {self.token}"}
        
        # Analytics
        ana_res = self.client.get("/api/admin/analytics", headers=headers)
        self.assertEqual(ana_res.status_code, 200)
        stats = ana_res.json()
        self.assertIn("total_cases", stats)
        self.assertIn("total_learned_qa", stats)

        # Config
        cfg_res = self.client.get("/api/admin/config", headers=headers)
        self.assertEqual(cfg_res.status_code, 200)
        cfg = cfg_res.json()
        self.assertIn("system_prompt", cfg)
        self.assertIn("llm_model", cfg)
        print("✅ Test 7 Passed: Analytics and Config OK")

    def test_08_delete_and_clear_cases(self):
        """Test API xóa 1 case và xóa toàn bộ danh sách case."""
        headers = {"Authorization": f"Bearer {self.token}"}

        # 1. Test xóa 1 case
        del_res = self.client.delete("/api/admin/cases/test-session-fallback-999", headers=headers)
        self.assertEqual(del_res.status_code, 200)
        self.assertTrue(del_res.json()["success"])

        # 2. Test xóa toàn bộ danh sách case
        clear_res = self.client.post("/api/admin/cases/clear-all", headers=headers)
        self.assertEqual(clear_res.status_code, 200)
        self.assertTrue(clear_res.json()["success"])
        print("✅ Test 8 Passed: Delete single case & Clear-all cases OK")

    def test_09_reset_learned_knowledge(self):
        """Test API reset toàn bộ tri thức CSKH đã nạp."""
        headers = {"Authorization": f"Bearer {self.token}"}
        reset_res = self.client.post("/api/admin/learning/reset", headers=headers)
        self.assertEqual(reset_res.status_code, 200)
        self.assertTrue(reset_res.json()["success"])
        print("✅ Test 9 Passed: Reset Learned Knowledge OK")

if __name__ == "__main__":
    unittest.main()

