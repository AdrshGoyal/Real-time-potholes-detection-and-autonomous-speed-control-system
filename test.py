import streamlit as st
import cv2
import time
import threading
import serial
from ultralytics import YOLO
from collections import deque   # ✅ added

# Shared global state manager to handle Streamlit re-runs smoothly
class SharedState:
    def __init__(self):
        self.pothole_flag = 1
        self.running = True
        self.arduino_port = 'COM3'
        self.baud_rate = 9600

@st.cache_resource
def get_shared_state():
    return SharedState()

@st.cache_resource
def start_arduino_thread(_state):
    def arduino_loop(state_obj):
        try:
            ser = serial.Serial(state_obj.arduino_port, state_obj.baud_rate, timeout=1)
            print("Arduino connected successfully on", state_obj.arduino_port)
        except Exception as e:
            ser = None
            print("⚠️ Arduino not connected:", e)

        if ser:
            try:
                ser.write(b'1')
            except:
                pass
            
        while state_obj.running:
            if ser:
                try:
                    if state_obj.pothole_flag:
                        ser.write(b'1')
                    else:
                        ser.write(b'0')
                except Exception as e:
                    print("Serial write error:", e)
            
            time.sleep(0.1)
            
        if ser:
            ser.close()

    thread = threading.Thread(target=arduino_loop, args=(_state,), daemon=True)
    thread.start()
    return thread

@st.cache_resource
def load_yolo_model():
    try:
        return YOLO("my_model/my_model.pt")
    except:
        try:
            return YOLO("yolov8n.pt") 
        except:
            return None

def main():
    st.set_page_config(page_title="AI Pothole Detection & Autonomous Speed Control System", layout="wide")
    
    state = get_shared_state()
    start_arduino_thread(state)
    model = load_yolo_model()
    
    st.title("🚗 AI Pothole Detection & Autonomous Speed Control System")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        video_file = st.file_uploader("📂 Upload Video", type=["mp4", "avi", "mov"])
        start_btn = st.button("▶️ Start Processing", use_container_width=True, type="primary")
        stop_btn = st.button("⛔ Stop / Reset", use_container_width=True)
            
    with col2:
        st.markdown("### 🎥 Live Detection Feed")
        frame_placeholder = st.empty()
        status_placeholder = st.empty()
        
    if stop_btn:
        st.session_state['cancel_processing'] = True
        state.pothole_flag = 1
        st.warning("🛑 Processing Interrupted. System Reset.")

    if start_btn and video_file is not None:
        if model is None:
            st.error("Model could not be loaded!")
            return

        st.session_state['cancel_processing'] = False
        status_placeholder.success("✅ Processing Started...")
        
        temp_video_path = "web_temp.mp4"
        with open(temp_video_path, "wb") as f:
            f.write(video_file.read())
            
        cap = cv2.VideoCapture(temp_video_path)
        labels = model.names
        conf_threshold = 0.5

        # 🔥 BUFFER INIT
        buffer = deque(maxlen=10)

        while cap.isOpened():
            if st.session_state.get('cancel_processing', False):
                break
                
            ret, frame = cap.read()
            if not ret:
                break
                
            # YOLO Detection
            results = model(frame, imgsz=640, verbose=False)
            detections = results[0].boxes
            
            detected = False   # ✅ new flag
            
            # Process detections
            for det in detections:
                conf = det.conf.item()
                if conf < conf_threshold:
                    continue

                detected = True   # ✅ detection found

                xyxy = det.xyxy.cpu().numpy().squeeze().astype(int)
                xmin, ymin, xmax, ymax = xyxy

                class_id = int(det.cls.item())
                try:
                    label = labels[class_id]
                except:
                    label = "Object"
                
                cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (0, 0, 255), 2)
                cv2.putText(frame, f"{label}", (xmin, ymin-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)

            # 🔥 BUFFER LOGIC
            buffer.append(1 if detected else 0)

            if sum(buffer) > len(buffer) // 2:
                state.pothole_flag = 0   # LOW SPEED
                cv2.putText(frame, "STATUS: LOW SPEED", (50, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
            else:
                state.pothole_flag = 1   # HIGH SPEED
                cv2.putText(frame, "STATUS: HIGH SPEED", (50, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_placeholder.image(frame_rgb, channels="RGB")
            
            time.sleep(0.02)

        cap.release()
        #state.pothole_flag = 1
        status_placeholder.success("✅ Video Processing Completed!")

if __name__ == "__main__":
    main()

#streamlit run test.py