import serial
try:
    arduino = serial.Serial('COM3', 9600, timeout=1)
    print("✅ Arduino Connected")
except Exception as e:
    print("❌ Arduino Error:", e)
    arduino = None