"""
Đông Đô CS Chatbot - User Management CLI
Công cụ quản lý tài khoản nội bộ cho Admin

Cách dùng:
  python manage_users.py list
  python manage_users.py create <username> <password> [full_name] [role]
  python manage_users.py reset-password <username> <new_password>
  python manage_users.py delete <username>
"""
import sys
from database import (
    init_database,
    create_user,
    list_users,
    delete_user,
    reset_user_password,
    get_user_by_username,
)


def print_help():
    print("=" * 60)
    print("👤 ĐÔNG ĐÔ CS - QUẢN LÝ TÀI KHOẢN")
    print("=" * 60)
    print("Lệnh khả dụng:")
    print("  python manage_users.py list")
    print("  python manage_users.py create <username> <password> [\"Họ và tên\"] [role]")
    print("  python manage_users.py reset-password <username> <new_password>")
    print("  python manage_users.py delete <username>")
    print("=" * 60)


def main():
    init_database()
    args = sys.argv[1:]

    if not args:
        print_help()
        return

    cmd = args[0].lower()

    if cmd == "list":
        users = list_users()
        print("\n📋 DANH SÁCH TÀI KHOẢN NỘI BỘ:")
        print("-" * 70)
        print(f"{'ID':<5} {'Username':<15} {'Họ tên':<25} {'Role':<10} {'Trạng thái'}")
        print("-" * 70)
        for u in users:
            status = "🟢 Hoạt động" if u["is_active"] else "🔴 Đã khóa"
            print(f"{u['id']:<5} {u['username']:<15} {u['full_name']:<25} {u['role']:<10} {status}")
        print("-" * 70)
        print(f"Tổng cộng: {len(users)} tài khoản\n")

    elif cmd == "create":
        if len(args) < 3:
            print("❌ Thiếu tham số: python manage_users.py create <username> <password> [\"Họ tên\"] [role]")
            return
        username = args[1]
        password = args[2]
        full_name = args[3] if len(args) > 3 else username
        role = args[4] if len(args) > 4 else "user"

        if get_user_by_username(username):
            print(f"❌ Tên đăng nhập '{username}' đã tồn tại!")
            return

        success = create_user(username, password, full_name, role)
        if success:
            print(f"✅ Đã tạo thành công tài khoản: '{username}' (Họ tên: {full_name}, Vai trò: {role})")
        else:
            print(f"❌ Tạo tài khoản thất bại.")

    elif cmd == "reset-password":
        if len(args) < 3:
            print("❌ Thiếu tham số: python manage_users.py reset-password <username> <new_password>")
            return
        username = args[1]
        new_password = args[2]

        if not get_user_by_username(username):
            print(f"❌ Không tìm thấy tài khoản '{username}'!")
            return

        reset_user_password(username, new_password)
        print(f"✅ Đã đổi mật khẩu thành công cho tài khoản '{username}'.")

    elif cmd == "delete":
        if len(args) < 2:
            print("❌ Thiếu tham số: python manage_users.py delete <username>")
            return
        username = args[1]
        if not get_user_by_username(username):
            print(f"❌ Không tìm thấy tài khoản '{username}'!")
            return

        delete_user(username)
        print(f"✅ Đã xóa tài khoản '{username}'.")

    else:
        print(f"❌ Lệnh không hợp lệ: '{cmd}'")
        print_help()


if __name__ == "__main__":
    main()
