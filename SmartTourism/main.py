from flask import Flask, render_template, request, url_for
from werkzeug.utils import secure_filename
import os
import json
import numpy as np
import tensorflow as tf
from tensorflow.keras.preprocessing import image

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

# === THÊM KHỐI NÀY VÀO ===
# TẠO TỪ ĐIỂN ĐỂ "DỊCH" KẾT QUẢ
FOOD_DISPLAY_NAMES = {
    'pho_bo': 'Phở bò',
    'com_tam': 'Cơm tấm',
    'banh_xeo': 'Bánh xèo',
    'banh_mi': 'Bánh mì'
    # Bổ sung thêm các món khác của bạn ở đây...
}

PLACE_DISPLAY_NAMES = {
    'cho_ben_thanh': 'Chợ Bến Thành',
    'ho_guom': 'Hồ Gươm',
    'nha_tho_duc_ba': 'Nhà thờ Đức Bà'
    # Bổ sung thêm các địa điểm khác của bạn ở đây...
}
# ===========================

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- 3. HÀM XỬ LÝ VÀ DỰ ĐOÁN ẢNH (Dùng chung) ---
def predict_image(img_path, model_to_use, classes_to_use):
    # Tải ảnh từ đường dẫn, resize về đúng kích thước
    img = image.load_img(img_path, target_size=(IMG_HEIGHT, IMG_WIDTH))
    
    # Chuyển ảnh thành mảng numpy
    img_array = image.img_to_array(img)
    
    # Thêm chiều "batch"
    img_array = np.expand_dims(img_array, axis=0)
    
    # Dùng model được chọn để dự đoán
    predictions = model_to_use.predict(img_array)
    
    # Lấy kết quả
    score = tf.nn.softmax(predictions[0])
    class_index = np.argmax(score)
    
    # Tra tên lớp từ danh sách class tương ứng
    result_name = classes_to_use[class_index]
    
    return result_name

# --- 4. ĐỊNH TUYẾN CHÍNH ---
@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        
        # --- Lấy dữ liệu từ form ---
        if 'file' not in request.files:
            return render_template('index.html', error='Không tìm thấy phần file trong request.')
        
        file = request.files['file']
        
        # Lấy loại model người dùng đã chọn (từ radio button)
        model_type = request.form.get('model_type') 
        
        if file.filename == '':
            return render_template('index.html', error='Chưa chọn file.', selected_model=model_type)

        if not model_type:
            return render_template('index.html', error='Chưa chọn loại nhận diện (Món ăn hay Địa điểm).')

        # --- Xử lý file ---
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

           # --- GỌI MODEL TƯƠNG ỨNG ---
            try:
                # Lấy "bộ não" và "từ điển" dựa trên lựa chọn của người dùng
                selected_model = models[model_type]
                selected_classes = class_names[model_type]
                
                # Gọi hàm dự đoán (nó sẽ trả về tên gốc như 'pho_bo')
                result_name = predict_image(filepath, selected_model, selected_classes)
                
                # === THÊM MỚI: DỊCH TÊN SANG TIẾNG VIỆT ===
                if model_type == 'food':
                    display_name = FOOD_DISPLAY_NAMES.get(result_name, result_name)
                elif model_type == 'place':
                    display_name = PLACE_DISPLAY_NAMES.get(result_name, result_name)
                else:
                    display_name = result_name # Để dự phòng
                
                print(f"--- Model: {model_type} | Tên gốc: {result_name} | Tên hiển thị: {display_name} ---")
                # ============================================

                # Trả kết quả về cho 'index.html'
                return render_template('index.html', 
                                       result=display_name, # <--- ĐÃ THAY BẰNG TÊN HIỂN THỊ
                                       filename=filename, 
                                       selected_model=model_type)
                
            except Exception as e:
                print(f"LỖI khi dự đoán: {e}")
                return render_template('index.html', 
                                       error="Gặp lỗi trong quá trình nhận diện.", 
                                       selected_model=model_type)
        
        else:
            return render_template('index.html', 
                                   error='Định dạng file không hợp lệ (Chỉ hỗ trợ PNG, JPG, JPEG).', 
                                   selected_model=model_type)
    
    # Nếu là GET (lần đầu truy cập), chỉ hiển thị trang
    return render_template('index.html', selected_model='food') # Mặc định chọn 'food'

# --- 5. CHẠY ỨNG DỤNG ---
if __name__ == '__main__':
    # Đảm bảo thư mục (mà Flask coi là 'static') tồn tại
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Chạy server (đã BỎ 'static_folder=static_dir' vì nó sai)
    app.run(debug=False)