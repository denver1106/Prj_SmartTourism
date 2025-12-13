#db_pool.py
import mysql.connector.pooling
import os

# --- LẤY THÔNG TIN TỪ BIẾN MÔI TRƯỜNG ---
POOL_CONFIG = {
    'user': os.environ.get("DB_USER", "root"),
    'password': os.environ.get("DB_PASSWORD", "password"),
    'host': os.environ.get("DB_HOST", "127.0.0.1"),
    'database': os.environ.get("DB_DATABASE", "smarttourism"),
    'pool_size': 10,  # Giữ tối đa 10 kết nối hoạt động
    'pool_name': "SmartFoodPool",
    'charset': 'utf8mb4'
}


# Khởi tạo Connection Pool một lần duy nhất
try:
    db_pool = mysql.connector.pooling.MySQLConnectionPool(**POOL_CONFIG)
except Exception as e:
    print("------------------------------------------------------------------")
    print(f"LỖI KHỞI TẠO POOL: {e}")
    print("VUI LÒNG KIỂM TRA LẠI DB_USER/DB_PASSWORD/DB_DATABASE trong biến môi trường.")
    print("------------------------------------------------------------------")
    db_pool = None # Đảm bảo app không chạy nếu DB lỗi


def get_connection():
    """Lấy một kết nối từ Pool"""
    if db_pool:
        try:
            return db_pool.get_connection()
        except Exception as e:
            print(f"LỖI LẤY KẾT NỐI: {e}")
            return None
    return None