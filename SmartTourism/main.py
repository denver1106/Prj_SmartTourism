from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)

# --- CẤU HÌNH ---
UPLOAD_FOLDER = 'uploaded_images'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'} 

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
def predict_food(filename):
    name = filename.lower()
    if 'comtam' in name or 'com_tam' in name:
        return "Cơm tấm"
    elif 'bunbo' in name or 'bun_bo' in name:
        return "Bún bò Huế"
    elif 'pho' in name:
        return "Phở bò"
    elif 'banhmi' in name or 'banh_mi' in name:
        return "Bánh mì"
    else:
        return "Không nhận dạng được món ăn"

# --- ĐỊNH TUYẾN CHÍNH ---
@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # 1. Xử lý Upload File
        if 'file' not in request.files:
            return render_template('index.html', error='Không tìm thấy phần file trong request.')

        file = request.files['file']

        if file.filename == '':
            return render_template('index.html', error='Chưa chọn file.')

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # 2. GỌI CHỨC NĂNG HỌC MÁY TẠI ĐÂY
            # Tạm thời trả về tên file như là kết quả
            result_name = f"Đã tải lên thành công: {filename}" 
            
            # Trả về kết quả và hiển thị lại trang chủ
            return render_template('index.html', result=result_name, filename=filename)
        else:
             return render_template('index.html', error='Định dạng file không hợp lệ (Chỉ hỗ trợ PNG, JPG, JPEG).')

    # Nếu là phương thức GET, hiển thị trang upload (index.html)
    return render_template('index.html')


if __name__ == '__main__':
    # Đảm bảo thư mục upload tồn tại
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(debug=True)
