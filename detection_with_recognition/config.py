"""
Configuration Settings
All constants and settings for the person detection system
"""

# Camera Settings
CAMERA_INDEX = 0

# Model Settings
MODEL_PATH = "yolov8n.pt"
CONFIDENCE_THRESHOLD = 0.5

# Detection Settings
MIN_AREA_RATIO = 0.03  # Minimum detection size (3% of frame)

# Notification Settings
GLOBAL_BEEP_COOLDOWN = 10  # Seconds between beeps
BEEP_DELAY = 5  # Seconds before confirming person
SOUND_FILE = "notification.wav"
MESSAGE_DURATION = 5  # Seconds to show messages

# Logging Settings
CSV_FILE = "visitor_log.csv"

# Dashboard Settings
DASHBOARD_PORT = 5000

# Face Recognition Settings
FACE_MATCH_THRESHOLD = 0.6  # Correlation threshold (0.0 to 1.0)

# Display Settings
WINDOW_NAME = "Person Detection"