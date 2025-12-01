# check_connect.py
import pymysql
import os
from dotenv import load_dotenv

# 1. Load file .env và in ra xem Python có đọc được không
load_dotenv()

print("="*40)
print(" 🕵️‍♂️  CHẨN ĐOÁN KẾT NỐI DATABASE")
print("="*40)

# Lấy cấu hình
db_host = os.getenv("DB_HOST", "localhost")
db_user = os.getenv("DB_USER", "root")
db_pass = os.getenv("DB_PASSWORD") # Không set default để check file env
db_name = os.getenv("DB_DATABASE", "smarttourism")

print(f"[1] Đang thử kết nối với thông tin:")
print(f"    - Host: {db_host}")
print(f"    - User: {db_user}")
print(f"    - Pass: {'(Chưa điền trong .env)' if db_pass is None else '***'}")
print(f"    - Name: {db_name}")

# Thử các PORT phổ biến trên Mac (3306 và 3307)
ports_to_try = [3306, 3307, 8889] # 8889 là MAMP

success = False

for port in ports_to_try:
    print(f"\n[2] Đang thử cổng PORT: {port}...")
    try:
        conn = pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_pass if db_pass is not None else "",
            database=db_name,
            port=port,
            connect_timeout=3
        )
        print(f"✅ KẾT NỐI THÀNH CÔNG ở cổng {port}!")
        
        with conn.cursor() as cur:
            cur.execute("SELECT DATABASE();")
            print(f"    -> Đang kết nối tới DB: {cur.fetchone()}")
            cur.execute("SELECT count(*) as cnt FROM restaurants")
            print(f"    -> Số lượng nhà hàng: {cur.fetchone()['cnt']}")
            
        success = True
        print(f"\n📢 GỢI Ý: Hãy mở file .env và thêm dòng: DB_PORT={port}")
        break 
        
    except pymysql.MySQLError as e:
        err_code = e.args[0]
        err_msg = e.args[1]
        print(f"❌ Thất bại cổng {port}. Mã lỗi: {err_code}")
        print(f"   Chi tiết: {err_msg}")

        if err_code == 1045:
            print("   => SAI MẬT KHẨU hoặc USERNAME! Hãy kiểm tra lại DB_PASSWORD.")
        elif err_code == 2003:
            print("   => SAI HOST hoặc SERVER KHÔNG CHẠY ở cổng này.")
        elif err_code == 1049:
            print(f"   => KHÔNG TÌM THẤY DATABASE tên '{db_name}'.")

print("="*40)
if not success:
    print("🆘 KHÔNG THỂ KẾT NỐI. HÃY CHỤP LẠI MÀN HÌNH KẾT QUẢ NÀY GỬI TÔI.")