from app import create_app

# Gọi hàm create_app() từ file app/__init__.py
app = create_app()

if __name__ == '__main__':
    # Chạy server ở chế độ debug (sẽ tự khởi động lại khi bạn sửa code)
    app.run(debug=True)