import streamlit as st
import cv2
import time
import numpy as np
import threading
import serial
from ultralytics import YOLO

# ===== CONFIG =====
model_path = "my_model/my_model.pt"
conf_threshold = 0.5

# ===== GLOBAL VARIABLES =====
pothole_flag = False
last_detected_time = 0
running = False

# ===== ARDUINO SERIAL =====
try:
    ser = serial.Serial('COM3', 9600, timeout=1)
except:
    ser = None
    print("⚠️ Arduino not connected")

# ===== LOAD MODEL =====
model = YOLO(model_path)
labels = model.names

# ===== DETECTION THREAD =====
def detect_video(video_path, frame_placeholder):
    global pothole_flag, last_detected_time, running

    cap = cv2.VideoCapture(video_path)

    while running:
        ret, frame = cap.read()
        if not ret:
            break

        h, w, _ = frame.shape

        # Draw reference line
        line_y = int(h * 0.6)
        cv2.line(frame, (0, line_y), (w, line_y), (255, 0, 0), 3)

        results = model(frame, imgsz=640, verbose=False)
        detections = results[0].boxes

        detected_below_line = False

        for det in detections:
            conf = det.conf.item()
            if conf < conf_threshold:
                continue

            xyxy = det.xyxy.cpu().numpy().squeeze().astype(int)
            xmin, ymin, xmax, ymax = xyxy

            class_id = int(det.cls.item())
            label = labels[class_id]

            # Draw bounding box
            cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (0, 0, 255), 2)
            cv2.putText(frame, f"{label}", (xmin, ymin-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)

            # Check below line
            if ymax > line_y:
                detected_below_line = True

        # ===== FLAG LOGIC =====
        if detected_below_line:
            last_detected_time = time.time()

        if time.time() - last_detected_time < 2:
            pothole_flag = True
        else:
            pothole_flag = False

        # Convert BGR → RGB for Streamlit
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Show in Streamlit
        frame_placeholder.image(frame, channels="RGB")

    cap.release()


# ===== ARDUINO THREAD =====
def arduino_control():
    global pothole_flag, running

    while running:
        if ser:
            if pothole_flag:
                ser.write(b'0')  # LED OFF
            else:
                ser.write(b'1')  # LED ON

        time.sleep(0.1)


# ===== STREAMLIT UI =====
st.set_page_config(page_title="Pothole Detection", layout="wide")

st.title("🚗 AI Pothole Detection System")

col1, col2 = st.columns(2)

with col1:
    video_file = st.file_uploader("📂 Upload Video", type=["mp4", "avi"])

    start_btn = st.button("▶️ Start Project")
    stop_btn = st.button("⛔ Stop")

with col2:
    st.markdown("### 🎥 Live Detection Feed")
    frame_placeholder = st.empty()

# ===== CONTROL LOGIC =====
if start_btn and video_file is not None:
    running = True

    # Save video
    with open("temp.mp4", "wb") as f:
        f.write(video_file.read())

    st.success("✅ Project Started")

    # Start threads
    t1 = threading.Thread(target=detect_video, args=("temp.mp4", frame_placeholder))
    t2 = threading.Thread(target=arduino_control)

    t1.start()
    t2.start()

if stop_btn:
    running = False
    st.warning("🛑 Project Stopped")