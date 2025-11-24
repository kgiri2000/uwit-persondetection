import cv2
from ultralytics import YOLO
import numpy as np
import pygame
import time
import csv
import os
from deep_sort_realtime.deepsort_tracker import DeepSort
from flask import Flask, Response, render_template_string
import threading
import json

# Configuration
CAMERA_INDEX = 0
MODEL_PATH = "yolov8n.pt"
MIN_AREA_RATIO = 0.03
GLOBAL_BEEP_COOLDOWN = 10
CSV_FILE = "visitor_log.csv"
SOUND_FILE = "notification.wav"
MESSAGE_DURATION = 5
BEEP_DELAY = 5
CONFIDENCE_THRESHOLD = 0.5
DASHBOARD_PORT = 5000
FACE_MATCH_THRESHOLD = 0.6

# Initialize DeepSort
deepsort = DeepSort(
    max_age=30,
    n_init=3,
    max_cosine_distance=0.3,
    nn_budget=100
)

# Initialize pygame for sound
pygame.mixer.init()
if not os.path.exists(SOUND_FILE):
    print(f"Warning: {SOUND_FILE} not found. Beeps will be silent.")
    beep_sound = None
else:
    beep_sound = pygame.mixer.Sound(SOUND_FILE)

def play_beep():
    if beep_sound:
        beep_sound.play()

# Initialize CSV
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Person_ID", "Face_ID", "First_Seen", "Last_Seen", "Duration_sec"])

# Load YOLO model
model = YOLO(MODEL_PATH)

# Load OpenCV face detector and recognizer
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
face_recognizer = cv2.face.LBPHFaceRecognizer_create()
face_recognizer_trained = False

# Initialize camera
cap = cv2.VideoCapture(CAMERA_INDEX)
if not cap.isOpened():
    print(f"Error: Cannot open camera {CAMERA_INDEX}")
    exit(1)

# Global state variables
current_ids = set()
last_beep_time = 0
person_times = {}
completed_durations = []
beeped_ids = set()
active_messages = []
face_data_db = {}  # Store face data: {face_id: {'image': gray_face, 'histogram': hist}}
person_face_map = {}  # Map person_id to face_id
next_face_id = 1
heatmap_data = None
latest_frame = None
frame_lock = threading.Lock()

# Dashboard statistics
dashboard_stats = {
    'live_count': 0,
    'unique_visitors': 0,
    'total_visits': 0,
    'avg_duration': 0,
    'heatmap': []
}

def compute_face_histogram(face_img):
    """Compute color histogram for face comparison"""
    if face_img is None or face_img.size == 0:
        return None
    
    # Resize to standard size
    face_resized = cv2.resize(face_img, (100, 100))
    
    # Convert to HSV for better color representation
    hsv = cv2.cvtColor(face_resized, cv2.COLOR_BGR2HSV)
    
    # Compute histogram
    hist = cv2.calcHist([hsv], [0, 1, 2], None, [8, 8, 8], [0, 180, 0, 256, 0, 256])
    hist = cv2.normalize(hist, hist).flatten()
    
    return hist

def compare_faces(hist1, hist2):
    """Compare two face histograms using correlation"""
    if hist1 is None or hist2 is None:
        return 0
    
    correlation = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
    return correlation

def recognize_face(frame, bbox):
    """Extract and recognize face from bounding box using OpenCV"""
    global next_face_id
    
    x1, y1, x2, y2 = bbox
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(frame.shape[1], x2), min(frame.shape[0], y2)
    
    # Extract person region
    person_img = frame[y1:y2, x1:x2]
    
    if person_img.size == 0:
        return None
    
    # Convert to grayscale for face detection
    gray = cv2.cvtColor(person_img, cv2.COLOR_BGR2GRAY)
    
    # Detect faces in person region
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    
    if len(faces) == 0:
        return None
    
    # Get largest face
    largest_face = max(faces, key=lambda f: f[2] * f[3])
    fx, fy, fw, fh = largest_face
    
    # Extract face region
    face_img = person_img[fy:fy+fh, fx:fx+fw]
    
    if face_img.size == 0:
        return None
    
    # Compute face histogram
    face_hist = compute_face_histogram(face_img)
    
    if face_hist is None:
        return None
    
    # Compare with known faces
    best_match_id = None
    best_match_score = 0
    
    for face_id, face_info in face_data_db.items():
        score = compare_faces(face_info['histogram'], face_hist)
        if score > best_match_score:
            best_match_score = score
            best_match_id = face_id
    
    # If good match found (correlation > threshold)
    if best_match_score > FACE_MATCH_THRESHOLD:
        return best_match_id
    
    # New face - assign new ID
    face_id = f"F{next_face_id:04d}"
    next_face_id += 1
    
    # Store face data
    face_data_db[face_id] = {
        'image': cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY),
        'histogram': face_hist
    }
    
    return face_id

def update_heatmap(frame, tracks):
    """Update heatmap based on person positions"""
    global heatmap_data
    
    if heatmap_data is None:
        heatmap_data = np.zeros((frame.shape[0] // 10, frame.shape[1] // 10), dtype=np.float32)
    
    for track in tracks:
        if not track.is_confirmed():
            continue
        
        l, t, w, h = track.to_ltwh()
        center_x = int((l + w/2) // 10)
        center_y = int((t + h/2) // 10)
        
        if 0 <= center_y < heatmap_data.shape[0] and 0 <= center_x < heatmap_data.shape[1]:
            heatmap_data[center_y, center_x] += 1

def generate_heatmap_image():
    """Generate heatmap visualization"""
    if heatmap_data is None:
        return None
    
    # Normalize heatmap
    normalized = cv2.normalize(heatmap_data, None, 0, 255, cv2.NORM_MINMAX)
    normalized = normalized.astype(np.uint8)
    
    # Apply colormap
    heatmap_colored = cv2.applyColorMap(normalized, cv2.COLORMAP_JET)
    
    # Resize to match original dimensions
    heatmap_resized = cv2.resize(heatmap_colored, (heatmap_data.shape[1] * 10, heatmap_data.shape[0] * 10))
    
    return heatmap_resized

# Flask app for dashboard
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Visitor Detection Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            text-align: center;
            transition: transform 0.3s ease;
        }
        .stat-card:hover {
            transform: translateY(-5px);
        }
        .stat-value {
            font-size: 56px;
            font-weight: bold;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .stat-label {
            font-size: 14px;
            color: #666;
            margin-top: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .feeds-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 20px;
        }
        .feed-card {
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .feed-card h2 {
            margin-top: 0;
            margin-bottom: 15px;
            color: #333;
            font-size: 24px;
        }
        .feed-card img {
            width: 100%;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        .auto-refresh {
            color: #999;
            font-size: 12px;
            text-align: center;
            margin-top: 10px;
        }
        .pulse {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #4CAF50;
            border-radius: 50%;
            margin-right: 5px;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        @media (max-width: 768px) {
            .feeds-grid {
                grid-template-columns: 1fr;
            }
            h1 {
                font-size: 1.8em;
            }
        }
    </style>
    <script>
        function updateStats() {
            fetch('/stats')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('live-count').textContent = data.live_count;
                    document.getElementById('unique-visitors').textContent = data.unique_visitors;
                    document.getElementById('total-visits').textContent = data.total_visits;
                    document.getElementById('avg-duration').textContent = data.avg_duration;
                });
        }
        
        setInterval(updateStats, 1000);
        setInterval(() => {
            document.getElementById('camera-feed').src = '/video_feed?' + new Date().getTime();
            document.getElementById('heatmap-feed').src = '/heatmap_feed?' + new Date().getTime();
        }, 100);
    </script>
</head>
<body>
    <div class="container">
        <h1>Visitor Detection Dashboard</h1>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value" id="live-count">0</div>
                <div class="stat-label">Live Count</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="unique-visitors">0</div>
                <div class="stat-label">Unique Visitors</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="total-visits">0</div>
                <div class="stat-label">Total Visits</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="avg-duration">0</div>
                <div class="stat-label"> Avg Duration (s)</div>
            </div>
        </div>
        
        <div class="feeds-grid">
            <div class="feed-card">
                <h2>Live Camera Feed</h2>
                <img id="camera-feed" src="/video_feed" alt="Camera Feed">
                <div class="auto-refresh">
                    <span class="pulse"></span>Live streaming
                </div>
            </div>
            <div class="feed-card">
                <h2>Activity Heatmap</h2>
                <img id="heatmap-feed" src="/heatmap_feed" alt="Heatmap">
                <div class="auto-refresh">
                    <span class="pulse"></span>Live streaming
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/stats')
def stats():
    return json.dumps(dashboard_stats)

@app.route('/video_feed')
def video_feed():
    def generate():
        while True:
            with frame_lock:
                if latest_frame is not None:
                    ret, buffer = cv2.imencode('.jpg', latest_frame)
                    if ret:
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.033)  # ~30 FPS
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/heatmap_feed')
def heatmap_feed():
    def generate():
        while True:
            heatmap_img = generate_heatmap_image()
            if heatmap_img is not None:
                ret, buffer = cv2.imencode('.jpg', heatmap_img)
                if ret:
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.1)  # 10 FPS for heatmap
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

def run_flask():
    app.run(host='0.0.0.0', port=DASHBOARD_PORT, debug=False, threaded=True, use_reloader=False)

# Start Flask in separate thread
flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()

print(f"\n{'='*60}")
print(f"Dashboard running at: http://localhost:{DASHBOARD_PORT}")
print(f"{'='*60}\n")

# Main detection loop
while True:
    ret, frame = cap.read()
    if not ret:
        continue

    frame_area = frame.shape[0] * frame.shape[1]

    # YOLO Detection
    results = model(frame)[0]

    dets_xyxy = []
    dets_conf = []

    for box in results.boxes:
        if int(box.cls[0]) == 0:  # Person class only
            conf = float(box.conf[0])
            if conf >= CONFIDENCE_THRESHOLD:
                x1, y1, x2, y2 = box.xyxy[0].cpu().tolist()
                dets_xyxy.append([float(x1), float(y1), float(x2), float(y2)])
                dets_conf.append(float(conf))

    detections = []
    for (x1, y1, x2, y2), conf in zip(dets_xyxy, dets_conf):
        detections.append(([float(x1), float(y1), float(x2), float(y2)], float(conf), 'person'))

    # DeepSort Tracking
    tracks = deepsort.update_tracks(detections, frame=frame)

    # Update heatmap
    update_heatmap(frame, tracks)

    new_ids = set()
    now = time.time()

    for track in tracks:
        if not track.is_confirmed():
            continue

        tid = int(track.track_id)
        l, t, w, h = track.to_ltwh()
        x1, y1, x2, y2 = int(l), int(t), int(l + w), int(t + h)

        if (w * h) / frame_area < MIN_AREA_RATIO:
            continue

        new_ids.add(tid)

        # Face recognition for new person or every 30 frames for existing
        if tid not in person_face_map or (int(now * 30) % 30 == 0):
            face_id = recognize_face(frame, (x1, y1, x2, y2))
            if face_id:
                person_face_map[tid] = face_id

        if tid not in person_times:
            person_times[tid] = {"first_seen": now, "last_seen": now}
        else:
            person_times[tid]["last_seen"] = now

    # Beep notification
    for tid in new_ids:
        first_seen = person_times[tid]["first_seen"]
        duration = now - first_seen

        if (duration >= BEEP_DELAY and
            tid not in beeped_ids and
            (now - last_beep_time >= GLOBAL_BEEP_COOLDOWN)):

            face_id = person_face_map.get(tid, "Unknown")
            msg = f"Person {tid} (Face: {face_id}) confirmed"
            play_beep()
            beeped_ids.add(tid)
            last_beep_time = now
            active_messages.append((msg, now))

    # Handle departures
    left_ids = current_ids - new_ids
    for tid in left_ids:
        first = person_times[tid]["first_seen"]
        last = person_times[tid]["last_seen"]
        dur = last - first

        if dur >= 5:
            completed_durations.append(dur)
            face_id = person_face_map.get(tid, "Unknown")
            
            with open(CSV_FILE, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    tid,
                    face_id,
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(first)),
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last)),
                    round(dur, 2)
                ])

        del person_times[tid]
        beeped_ids.discard(tid)
        if tid in person_face_map:
            del person_face_map[tid]

    if len(completed_durations) > 1000:
        completed_durations = completed_durations[-1000:]

    current_ids = new_ids

    # Update dashboard stats
    dashboard_stats['live_count'] = len(current_ids)
    dashboard_stats['unique_visitors'] = len(face_data_db)
    dashboard_stats['total_visits'] = len(completed_durations) + len(current_ids)
    dashboard_stats['avg_duration'] = round(np.mean(completed_durations), 2) if completed_durations else 0

    # Annotate frame
    annotated = frame.copy()

    for track in tracks:
        if not track.is_confirmed():
            continue

        tid = int(track.track_id)
        l, t, w, h = track.to_ltwh()
        x1, y1, x2, y2 = int(l), int(t), int(l + w), int(t + h)

        face_id = person_face_map.get(tid, "Unknown")
        
        # Draw rectangle
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0,255,0), 2)
        
        # Draw label background
        label = f"ID {tid} - {face_id}"
        (label_width, label_height), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(annotated, (x1, y1 - label_height - 10), (x1 + label_width, y1), (0,255,0), -1)
        
        # Draw label text
        cv2.putText(annotated, label, (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,0), 2)

    # Display stats on frame
    cv2.putText(annotated, f"Live: {len(current_ids)}", (20,40),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)
    cv2.putText(annotated, f"Unique: {len(face_data_db)}", (20,80),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)
    cv2.putText(annotated, f"Avg: {dashboard_stats['avg_duration']}s", (20,120),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255,0,0), 2)

    # Display messages
    active_messages = [(msg, ts) for msg, ts in active_messages if now - ts < MESSAGE_DURATION]
    
    y_offset = annotated.shape[0] - 20
    for msg, ts in active_messages:
        # Draw message background
        (msg_width, msg_height), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        cv2.rectangle(annotated, (15, y_offset - msg_height - 5), (25 + msg_width, y_offset + 5), (0,0,0), -1)
        
        cv2.putText(annotated, msg, (20, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
        y_offset -= 35

    # Update latest frame for dashboard
    with frame_lock:
        latest_frame = annotated.copy()

    cv2.imshow("Person Detection", annotated)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
pygame.mixer.quit()