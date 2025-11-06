from flask import Flask, render_template, request, url_for
from werkzeug.utils import secure_filename
import os
import json
import numpy as np
import tensorflow as tf
from tensorflow.keras.preprocessing import image
from PIL import Image

# --- 1. TẢI TẤT CẢ MODEL VÀ TÊN LỚP ---
print("--- Đang tải các model và tên lớp... ---")
models = {}
class_names = {}
IMG_HEIGHT = 128 # Kích thước ảnh phải đồng nhất
IMG_WIDTH = 128

try:
    # Tải model Món ăn
    models['food'] = tf.keras.models.load_model('food_model.h5')
    with open('food_classes.json', 'r', encoding='utf-8') as f:
        class_names['food'] = json.load(f)
    print("Tải model 'food' thành công.")

    # Tải model Địa điểm
    models['place'] = tf.keras.models.load_model('place_model.h5')
    with open('place_classes.json', 'r', encoding='utf-8') as f:
        class_names['place'] = json.load(f)
    print("Tải model 'place' thành công.")

except Exception as e:
    print(f"LỖI: Không thể tải model. Lỗi: {e}")
    exit()

# --- 2. CẤU HÌNH FLASK ---
STATIC_FOLDER = 'uploaded_images'
app = Flask(__name__, static_folder=STATIC_FOLDER)
app.config['UPLOAD_FOLDER'] = STATIC_FOLDER

# TỪ ĐIỂN DỊCH TÊN
FOOD_DISPLAY_NAMES = {
    'pho_bo': 'Phở bò',
    'com_tam': 'Cơm tấm',
    'banh_xeo': 'Bánh xèo',
    'banh_mi': 'Bánh mì',
    'unknown': 'Không thể định dạng hình ảnh này được.' # Xử lý lớp 'unknown'
}
PLACE_DISPLAY_NAMES = {
    'cho_ben_thanh': 'Chợ Bến Thành',
    'ho_guom': 'Hồ Gươm',
    'nha_tho_duc_ba': 'Nhà thờ Đức Bà',
    'unknown': 'Không thể định dạng hình ảnh này được.' # Xử lý lớp 'unknown'
}
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- 3. HÀM DỰ ĐOÁN (CẬP NHẬT) ---
# --- HÀM NÀY GIỜ SẼ TRẢ VỀ 2 GIÁ TRỊ: (tên_kết_quả, điểm_tin_cậy) ---
def predict_image(img_path, model_to_use, classes_to_use):
    
    try:
        # Xử lý ảnh PNG trong suốt (dán lên nền trắng)
        img_pil = Image.open(img_path)
        if img_pil.mode == 'RGBA' or 'transparency' in img_pil.info:
            background = Image.new('RGB', img_pil.size, (255, 255, 255))
            background.paste(img_pil, (0, 0), img_pil.convert('RGBA'))
            img_pil = background
        else:
            img_pil = img_pil.convert('RGB')

        img_pil = img_pil.resize((IMG_WIDTH, IMG_HEIGHT))
        img_array = np.array(img_pil)
        img_array = np.expand_dims(img_array, axis=0)

    except Exception as e:
        print(f"LỖI KHI ĐỌC ẢNH: {e}")
        return "unknown", 0.0 # Trả về "unknown" và 0%

    # Dùng model được chọn để dự đoán
    predictions = model_to_use.predict(img_array)
    
    # Lấy kết quả
    score = tf.nn.softmax(predictions[0])
    class_index = np.argmax(score) # Vị trí (index) có điểm cao nhất
    max_score = np.max(score)      # Điểm cao nhất (xác suất)
    
    # Tra tên lớp từ danh sách class tương ứng
    result_name = classes_to_use[class_index]
    
    # Trả về cả tên và điểm số
    return result_name, max_score

# --- 4. ĐỊNH TUYẾN CHÍNH (CẬP NHẬT) ---
@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        
        # --- Lấy dữ liệu từ form ---
        if 'file' not in request.files:
            return render_template('index.html', error='Không tìm thấy phần file trong request.')
        
        file = request.files['file']
        
        if file.filename == '':
            return render_template('index.html', error='Chưa chọn file.')

        # --- Xử lý file ---
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # --- LOGIC MỚI: CHẠY CẢ 2 MODEL VÀ SO SÁNH ---
            try:
                # 1. Chạy model Món ăn
                food_result, food_score = predict_image(filepath, models['food'], class_names['food'])
                print(f"--- Food Model: {food_result} ({food_score*100:.2f}%) ---")

                # 2. Chạy model Địa điểm
                place_result, place_score = predict_image(filepath, models['place'], class_names['place'])
                print(f"--- Place Model: {place_result} ({place_score*100:.2f}%) ---")

                # 3. So sánh kết quả: Lấy model nào "tự tin" hơn
                if food_score > place_score:
                    # Nếu Food tự tin hơn
                    final_result_name = food_result
                    display_name = FOOD_DISPLAY_NAMES.get(final_result_name, final_result_name)
                
                elif place_score > food_score:
                    # Nếu Place tự tin hơn
                    final_result_name = place_result
                    display_name = PLACE_DISPLAY_NAMES.get(final_result_name, final_result_name)
                
                else:
                    # Nếu cả 2 đều bằng 0 (ví dụ lỗi đọc ảnh) hoặc bằng nhau
                    display_name = "Lỗi: Không thể định dạng hình ảnh này được."

                # Xử lý trường hợp cả 2 đều "unknown"
                if final_result_name == "unknown":
                     display_name = "Lỗi: Không thể định dạng hình ảnh này được."


                # 4. Trả kết quả về cho 'index.html'
                return render_template('index.html', 
                                       result=display_name,
                                       filename=filename)
                
            except Exception as e:
                print(f"LỖI khi dự đoán: {e}")
                return render_template('index.html', 
                                       error="Gặp lỗi trong quá trình nhận diện.")
        
        else:
            return render_template('index.html', 
                                   error='Định dạng file không hợp lệ (Chỉ hỗ trợ PNG, JPG, JPEG).')
    
    # Nếu là GET (lần đầu truy cập), chỉ hiển thị trang
    return render_template('index.html')

# --- 5. CHẠY ỨNG DỤNG ---
if __name__ == '__main__':
    # Đảm bảo thư mục (mà Flask coi là 'static') tồn tại
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Chạy server
    app.run(debug=False)