import tensorflow as tf
from tensorflow.keras import layers, models
from tensorflow.keras.preprocessing import image_dataset_from_directory
import os
import json

# --- 1. CẤU HÌNH ---
IMG_WIDTH = 128
IMG_HEIGHT = 128
BATCH_SIZE = 16
EPOCHS = 15 # Số lần học (bạn có thể tăng lên nếu độ chính xác thấp)

# Đường dẫn tới thư mục data (vì train.py cùng cấp với data)
BASE_DIR = '.' 
TRAIN_DIR = os.path.join(BASE_DIR, 'data/food/train')
VAL_DIR = os.path.join(BASE_DIR, 'data/food/val')

print(f"Đang tải dữ liệu huấn luyện từ: {TRAIN_DIR}")
print(f"Đang tải dữ liệu kiểm thử từ: {VAL_DIR}")

# --- 2. TẢI DỮ LIỆU ---
# Tự động tải ảnh từ các thư mục con và gán nhãn
train_dataset = image_dataset_from_directory(
    TRAIN_DIR,
    validation_split=None, # Không cần split vì đã có thư mục val
    image_size=(IMG_HEIGHT, IMG_WIDTH),
    batch_size=BATCH_SIZE,
    label_mode='categorical' # Sử dụng 'categorical' vì model cuối dùng softmax
)

validation_dataset = image_dataset_from_directory(
    VAL_DIR,
    validation_split=None,
    image_size=(IMG_HEIGHT, IMG_WIDTH),
    batch_size=BATCH_SIZE,
    label_mode='categorical'
)

# Lấy tên các lớp (ví dụ: ['banh_xeo', 'com_tam', 'pho_bo'])
class_names = train_dataset.class_names
NUM_CLASSES = len(class_names)
print(f"Đã tìm thấy {NUM_CLASSES} lớp: {class_names}")

# Lưu tên các lớp này ra file để main.py có thể dùng
with open('food_classes.json', 'w', encoding='utf-8') as f:
    json.dump(class_names, f, ensure_ascii=False, indent=2)
print("Đã lưu tên các lớp vào file 'food_classes.json'")

# Tối ưu hóa việc đọc dữ liệu
AUTOTUNE = tf.data.AUTOTUNE
train_dataset = train_dataset.cache().shuffle(1000).prefetch(buffer_size=AUTOTUNE)
validation_dataset = validation_dataset.cache().prefetch(buffer_size=AUTOTUNE)

# --- 3. XÂY DỰNG MODEL ---
# Thêm các lớp "tăng cường dữ liệu" (Data Augmentation)
# Giúp model học tốt hơn bằng cách xoay, lật ảnh ngẫu nhiên
data_augmentation = models.Sequential([
    layers.RandomFlip("horizontal", input_shape=(IMG_HEIGHT, IMG_WIDTH, 3)),
    layers.RandomRotation(0.1),
    layers.RandomZoom(0.1),
])

model = models.Sequential([
    # Lớp chuẩn hóa giá trị pixel về [0, 1]
    layers.Rescaling(1./255, input_shape=(IMG_HEIGHT, IMG_WIDTH, 3)),
    # Lớp tăng cường dữ liệu
    data_augmentation,
    
    # Các lớp CNN
    layers.Conv2D(32, (3, 3), activation='relu'),
    layers.MaxPooling2D((2, 2)),
    layers.Conv2D(64, (3, 3), activation='relu'),
    layers.MaxPooling2D((2, 2)),
    layers.Conv2D(128, (3, 3), activation='relu'),
    layers.MaxPooling2D((2, 2)),
    
    # Lớp "làm phẳng" dữ liệu
    layers.Flatten(),
    
    # Lớp "thần kinh"
    layers.Dense(128, activation='relu'),
    layers.Dropout(0.5), # Lớp Dropout để tránh học vẹt
    
    # Lớp đầu ra: số nơ-ron = số lớp (món ăn)
    layers.Dense(NUM_CLASSES, activation='softmax') 
])

# --- 4. BIÊN DỊCH MODEL ---
model.compile(optimizer='adam',
              loss='categorical_crossentropy',
              metrics=['accuracy'])

# In cấu trúc model ra
model.summary()

# --- 5. HUẤN LUYỆN MODEL ---
print("\nBẮT ĐẦU QUÁ TRÌNH HUẤN LUYỆN...")
history = model.fit(
    train_dataset,
    validation_data=validation_dataset,
    epochs=EPOCHS
)

print("HUẤN LUYỆN HOÀN TẤT!")

# --- 6. LƯU MODEL ---
model.save('food_model.h5')
print("Đã lưu model huấn luyện vào file 'food_model.h5'")