import tensorflow as tf
from tensorflow.keras import layers, models
from tensorflow.keras.preprocessing import image_dataset_from_directory
import os
import json

# --- 1. CẤU HÌNH ---
IMG_WIDTH = 128
IMG_HEIGHT = 128
BATCH_SIZE = 16
EPOCHS = 15 

BASE_DIR = '.' 
# THAY ĐỔI 1: Trỏ đến thư mục data/place/train
TRAIN_DIR = os.path.join(BASE_DIR, 'data/place/train') 
# THAY ĐỔI 2: Trỏ đến thư mục data/place/val
VAL_DIR = os.path.join(BASE_DIR, 'data/place/val')   

print(f"Đang tải dữ liệu huấn luyện từ: {TRAIN_DIR}")
print(f"Đang tải dữ liệu kiểm thử từ: {VAL_DIR}")

# --- 2. TẢI DỮ LIỆU ---
train_dataset = image_dataset_from_directory(
    TRAIN_DIR,
    validation_split=None,
    image_size=(IMG_HEIGHT, IMG_WIDTH),
    batch_size=BATCH_SIZE,
    label_mode='categorical'
)

validation_dataset = image_dataset_from_directory(
    VAL_DIR,
    validation_split=None,
    image_size=(IMG_HEIGHT, IMG_WIDTH),
    batch_size=BATCH_SIZE,
    label_mode='categorical'
)

class_names = train_dataset.class_names
NUM_CLASSES = len(class_names)
print(f"Đã tìm thấy {NUM_CLASSES} lớp: {class_names}")

# THAY ĐỔI 3: Lưu tên lớp vào file 'place_classes.json'
with open('place_classes.json', 'w', encoding='utf-8') as f:
    json.dump(class_names, f, ensure_ascii=False, indent=2)
print("Đã lưu tên các lớp vào file 'place_classes.json'")

AUTOTUNE = tf.data.AUTOTUNE
train_dataset = train_dataset.cache().shuffle(1000).prefetch(buffer_size=AUTOTUNE)
validation_dataset = validation_dataset.cache().prefetch(buffer_size=AUTOTUNE)

# --- 3. XÂY DỰNG MODEL ---
# Giữ nguyên kiến trúc model
data_augmentation = models.Sequential([
    layers.RandomFlip("horizontal", input_shape=(IMG_HEIGHT, IMG_WIDTH, 3)),
    layers.RandomRotation(0.1),
    layers.RandomZoom(0.1),
])

model = models.Sequential([
    layers.Rescaling(1./255, input_shape=(IMG_HEIGHT, IMG_WIDTH, 3)),
    data_augmentation,
    layers.Conv2D(32, (3, 3), activation='relu'),
    layers.MaxPooling2D((2, 2)),
    layers.Conv2D(64, (3, 3), activation='relu'),
    layers.MaxPooling2D((2, 2)),
    layers.Conv2D(128, (3, 3), activation='relu'),
    layers.MaxPooling2D((2, 2)),
    layers.Flatten(),
    layers.Dense(128, activation='relu'),
    layers.Dropout(0.5),
    layers.Dense(NUM_CLASSES, activation='softmax') 
])

# --- 4. BIÊN DỊCH MODEL ---
model.compile(optimizer='adam',
              loss='categorical_crossentropy',
              metrics=['accuracy'])

model.summary()

# --- 5. HUẤN LUYỆN MODEL ---
print("\nBẮT ĐẦU QUÁ TRÌNH HUẤN LUYỆN MODEL 'PLACE'...")
history = model.fit(
    train_dataset,
    validation_data=validation_dataset,
    epochs=EPOCHS
)

print("HUẤN LUYỆN HOÀN TẤT!")

# --- 6. LƯU MODEL ---
# THAY ĐỔI 4: Lưu model vào file 'place_model.h5'
model.save('place_model.h5')
print("Đã lưu model huấn luyện vào file 'place_model.h5'")