import tensorflow as tf
from tensorflow.keras.preprocessing import image
from PIL import Image
import numpy as np
import os
import json # Cần thêm json

class Predictor:
    def __init__(self):
        # Đường dẫn sẽ đi từ file (app/prediction/predictor.py)
        # Đi lên 3 cấp (app/prediction -> app -> SmartTourism)
        # Rồi đi xuống 'ml_models/'
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.model_dir = os.path.join(base_dir, 'ml_models')
        
        self.models = {}
        self.class_names = {}
        self.img_height = 128
        self.img_width = 128
        
        print("--- Đang tải các model .h5 và classes.json... ---")
        try:
            # Tải model Food
            self.models['food'] = tf.keras.models.load_model(os.path.join(self.model_dir, 'food_model.h5'))
            with open(os.path.join(self.model_dir, 'food_classes.json'), 'r', encoding='utf-8') as f:
                self.class_names['food'] = json.load(f)
            
            # Tải model Place
            self.models['place'] = tf.keras.models.load_model(os.path.join(self.model_dir, 'place_model.h5'))
            with open(os.path.join(self.model_dir, 'place_classes.json'), 'r', encoding='utf-8') as f:
                self.class_names['place'] = json.load(f)
            
            print("--- Tải model .h5 thành công. ---")

        except Exception as e:
            print(f"LỖI NGHIÊM TRỌNG: Không thể tải model .h5. Lỗi: {e}")
            raise e

    def predict_image(self, img_path, model_type):
        """
        Dự đoán ảnh, trả về (tên_lớp, điểm_tin_cậy).
        """
        model_to_use = self.models.get(model_type)
        classes_to_use = self.class_names.get(model_type)
        if not model_to_use or not classes_to_use:
            return "unknown", 0.0 # Lỗi không tìm thấy model

        try:
            # Xử lý ảnh PNG trong suốt (dán lên nền trắng)
            img_pil = Image.open(img_path)
            if img_pil.mode == 'RGBA' or 'transparency' in img_pil.info:
                background = Image.new('RGB', img_pil.size, (255, 255, 255))
                background.paste(img_pil, (0, 0), img_pil.convert('RGBA'))
                img_pil = background
            else:
                img_pil = img_pil.convert('RGB')

            img_pil = img_pil.resize((self.img_width, self.img_height))
            img_array = np.array(img_pil)
            img_array = np.expand_dims(img_array, axis=0)

        except Exception as e:
            print(f"LỖI KHI ĐỌC ẢNH: {e}")
            return "unknown", 0.0 # Lỗi đọc file ảnh

        # Dùng model được chọn để dự đoán
        predictions = model_to_use.predict(img_array)
        
        # Lấy kết quả
        score = tf.nn.softmax(predictions[0])
        max_score = np.max(score)
        class_index = np.argmax(score)
        
        # Tra tên lớp từ danh sách class tương ứng
        result_name = classes_to_use[class_index]
        
        return result_name, max_score