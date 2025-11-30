import tensorflow as tf
from tensorflow.keras.preprocessing import image
from PIL import Image
import numpy as np
import json
import os

class AIService:
    def __init__(self, model_dir='ml_models'):
        print("--- 🤖 Đang khởi động AI Service... ---")
        self.models = {}
        self.class_names = {}
        self.img_size = (128, 128)
        
        # Đường dẫn tuyệt đối để tránh lỗi không tìm thấy file
        # (Lấy đường dẫn từ thư mục gốc dự án)
        base_path = os.path.abspath(model_dir)

        # Tên hiển thị tiếng Việt đẹp cho các món
        self.display_names = {
            'pho_bo': 'Phở bò', 
            'com_tam': 'Cơm tấm', 
            'banh_xeo': 'Bánh xèo',
            'banh_mi': 'Bánh mì', 
            'cho_ben_thanh': 'Chợ Bến Thành', 
            'ho_guom': 'Hồ Gươm', 
            'nha_tho_duc_ba': 'Nhà thờ Đức Bà',
            'unknown': 'Không xác định'
        }

        try:
            # 1. Load Model Food
            food_path = os.path.join(base_path, 'food_model.h5')
            if os.path.exists(food_path):
                self.models['food'] = tf.keras.models.load_model(food_path)
                with open(os.path.join(base_path, 'food_classes.json'), 'r', encoding='utf-8') as f:
                    self.class_names['food'] = json.load(f)
                print("✅ Đã load xong model Food.")
            else:
                print(f"⚠️ Không tìm thấy file: {food_path}")

            # 2. Load Model Place
            place_path = os.path.join(base_path, 'place_model.h5')
            if os.path.exists(place_path):
                self.models['place'] = tf.keras.models.load_model(place_path)
                with open(os.path.join(base_path, 'place_classes.json'), 'r', encoding='utf-8') as f:
                    self.class_names['place'] = json.load(f)
                print("✅ Đã load xong model Place.")
            else:
                print(f"⚠️ Không tìm thấy file: {place_path}")
                
        except Exception as e:
            print(f"❌ Lỗi nghiêm trọng khi load model AI: {e}")
            # Không làm sập app, chỉ log lỗi

    def predict_image(self, img_path):
        """Hàm nhận diện ảnh và trả về tên món ăn/địa điểm (Tiếng Việt)"""
        if not self.models:
            return "AI chưa sẵn sàng", 0.0

        try:
            # Xử lý ảnh (Pre-processing)
            img_pil = Image.open(img_path)
            # Chuyển đổi sang RGB nếu ảnh là PNG (có kênh Alpha)
            if img_pil.mode != 'RGB':
                img_pil = img_pil.convert('RGB')
            
            img_pil = img_pil.resize(self.img_size)
            img_array = np.array(img_pil)
            img_array = np.expand_dims(img_array, axis=0)

            results = []

            # --- Chạy Model Food ---
            if 'food' in self.models:
                pred = self.models['food'].predict(img_array, verbose=0)
                score = tf.nn.softmax(pred[0])
                idx = np.argmax(score)
                max_score = np.max(score)
                label = self.class_names['food'][idx]
                results.append({'type': 'food', 'label': label, 'score': float(max_score)})

            # --- Chạy Model Place ---
            if 'place' in self.models:
                pred = self.models['place'].predict(img_array, verbose=0)
                score = tf.nn.softmax(pred[0])
                idx = np.argmax(score)
                max_score = np.max(score)
                label = self.class_names['place'][idx]
                results.append({'type': 'place', 'label': label, 'score': float(max_score)})

            if not results:
                return "Lỗi dự đoán", 0.0

            # --- So sánh: Lấy kết quả có độ tin cậy cao nhất ---
            best_match = max(results, key=lambda x: x['score'])
            
            # Nếu độ tin cậy quá thấp (< 40%) thì coi như không biết
            if best_match['score'] < 0.4:
                return "Không nhận diện được", best_match['score']

            raw_name = best_match['label']
            # Dịch sang tiếng Việt
            display_text = self.display_names.get(raw_name, raw_name)
            
            return display_text, best_match['score']

        except Exception as e:
            print(f"Lỗi khi xử lý ảnh: {e}")
            return "Lỗi xử lý ảnh", 0.0