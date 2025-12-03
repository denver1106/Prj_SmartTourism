import mysql.connector
from mysql.connector import pooling

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Nhom4@36",
    "database": "smarttourism",
    "port": 3306,
    "charset": "utf8mb4"
}

# --- Connection Pool (giúp app chạy nhanh, ổn định) ---
try:
    db_pool = pooling.MySQLConnectionPool(
        pool_name="SmartPool",
        pool_size=10,
        **DB_CONFIG
    )
    print("✅ MySQL Connection Pool đã sẵn sàng!")
except Exception as e:
    print("❌ LỖI KHỞI TẠO POOL:", e)
    db_pool = None


def get_connection():
    """Trả về 1 connection từ pool."""
    if not db_pool:
        print("❌ Không thể lấy connection: Pool lỗi hoặc chưa khởi tạo.")
        return None
    try:
        return db_pool.get_connection()
    except Exception as e:
        print("❌ Không lấy được connection:", e)
        return None
