import streamlit as st
import cv2
import time
import threading
import serial
from ultralytics import YOLO

# Shared global state manager to handle Streamlit re-runs smoothly
class SharedState:
    def __init__(self):
        self.pothole_flag = 1
        self.running = True
        self.arduino_port = 'COM3'   # Make sure this matches your Arduino COM port
        self.baud_rate = 9600

# Cache the state so it is shared across Streamlit re-runs
@st.cache_resource
def get_shared_state():
    return SharedState()

# Start the background thread for Arduino only once
@st.cache_resource
def start_arduino_thread(_state):
    def arduino_loop(state_obj):
        # Setup Serial connection
        try:
            ser = serial.Serial(state_obj.arduino_port, state_obj.baud_rate, timeout=1)
            print("Arduino connected successfully on", state_obj.arduino_port)
        except Exception as e:
            ser = None
            print("⚠️ Arduino not connected:", e)

        # Initial signal: Turn ON Arduino LED (Assuming '1' means ON and '0' means OFF)
        if ser:
            try:
                ser.write(b'1')
            except:
                pass
            
        # Loop independently from Streamlit UI checking the shared flag
        while state_obj.running:
            if ser:
                try:
                    if state_obj.pothole_flag:
                        ser.write(b'0')  # LED OFF when object detected below line (for 2 sec)
                    else:
                        ser.write(b'1')  # LED ON otherwise (Default state)
                except Exception as e:
                    print("Serial write error:", e)
            
            time.sleep(0.1) # Sleep to prevent high CPU usage
            
        if ser:
            ser.close()

    # Daemon thread exits when the main program stops
    thread = threading.Thread(target=arduino_loop, args=(_state,), daemon=True)
    thread.start()
    return thread

@st.cache_resource
def load_yolo_model():
    # Load model once to save time across UI interacts
    try:
        model = YOLO("my_model/my_model.pt")
        return model
    except Exception as e:
        # Fallback to YOLO default model to prevent app crash if missing
        try:
            return YOLO("yolov8n.pt") 
        except:
            return None

def main():
    st.set_page_config(page_title="AI Pothole Detection & Autonomous Speed Control System", layout="wide")
    
    # 1. Init Shared State
    state = get_shared_state()
    
    # 2. Start Background Arduino Thread immediately when UI opens
    start_arduino_thread(state)
    
    # 3. Load Model
    model = load_yolo_model()
    
    st.title("🚗 AI Pothole Detection & Autonomous Speed Control System")
    st.markdown("**How It Works:**\n"
                "1. Background Arduino Thread starts automatically. Default light turns **ON**.\n"
                "2. Upload a video & click Start. Objects detected **below the middle line** will turn the light **OFF** for 2 secs.")
    
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
        state.pothole_flag = False
        st.warning("🛑 Processing Interrupted. System Reset.")

    # Processing loop when user hits Start
    if start_btn and video_file is not None:
        if model is None:
            st.error("Model could not be loaded!")
            return

        st.session_state['cancel_processing'] = False
        
        status_placeholder.success("✅ Processing Started...")
        
        # Save uploaded video to temp file
        temp_video_path = "web_temp.mp4"
        with open(temp_video_path, "wb") as f:
            f.write(video_file.read())
            
        # Process Video 
        cap = cv2.VideoCapture(temp_video_path)
        labels = model.names
        conf_threshold = 0.5
        
        last_detected_time = 0
        
        while cap.isOpened():
            # Check if user clicked Stop during processing
            if st.session_state.get('cancel_processing', False):
                break
                
            ret, frame = cap.read()
            if not ret:
                break
                
            h, w, _ = frame.shape
            
            # Draw line in the middle of the frame


            # Object Detection
            results = model(frame, imgsz=640, verbose=False)
            detections = results[0].boxes
            
            # Process each detection box
            for det in detections:
                conf = det.conf.item()
                if conf < conf_threshold:
                    state.pothole_flag = 1
                    continue
                last_detected_time = time.time()
                state.pothole_flag = 0
                cv2.putText(frame, "STATUS: Slow Speed", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
                if time.time() - last_detected_time < 2:
                    state.pothole_flag = 1
                else:
                    state.pothole_flag = 0

                xyxy = det.xyxy.cpu().numpy().squeeze().astype(int)
                xmin, ymin, xmax, ymax = xyxy

                class_id = int(det.cls.item())
                try:
                    label = labels[class_id]
                except:
                    label = "Object"
                
                # Draw Box
                cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (0, 0, 255), 2)
                cv2.putText(frame, f"{label}", (xmin, ymin-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)

            # Update the latest time we saw an object below the line
            #if detected_below_line:
            #   last_detected_time = time.time()
                
            # Business Logic: "Wait for 2 seconds"
            # If line crossed recently (< 2 seconds), shared flag changes to True
            #if time.time() - last_detected_time < 2:
            #    state.pothole_flag = True
            #    cv2.putText(frame, "STATUS: LED OFF (Flag True)", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3)
            #else:
            #    state.pothole_flag = False
                
            # Output frame to frontend
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_placeholder.image(frame_rgb, channels="RGB")
            
            # Short sleep to prevent Streamlit UI from completely freezing
            time.sleep(0.01)

        cap.release()
        state.pothole_flag = False  # Ensure LED goes back ON when video is totally finished
        status_placeholder.success("✅ Video Processing Completed!")

if __name__ == "__main__":
    main()
#streamlit run streamlit_app.py
#yolo_env/Scripts/activate  