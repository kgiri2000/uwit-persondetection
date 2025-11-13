"""
Main Detection Script
Handles person detection, tracking, and face recognition
"""

import cv2
from ultralytics import YOLO
import numpy as np
import pygame
import time
import csv
import os
from deep_sort_realtime.deepsort_tracker import DeepSort
import threading

from config import *
from face_recognition_module import FaceRecognizer
from heatmap_module import HeatmapGenerator
from dashboard import start_dashboard, update_dashboard_stats, update_latest_frame

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
print("Loading YOLO model...")
model = YOLO(MODEL_PATH)

# Initialize camera
print("Initializing camera...")
cap = cv2.VideoCapture(CAMERA_INDEX)
if not cap.isOpened():
    print(f"Error: Cannot open camera {CAMERA_INDEX}")
    exit(1)

# Initialize modules
face_recognizer = FaceRecognizer()
heatmap_gen = HeatmapGenerator()

# Global state variables
current_ids = set()
last_beep_time = 0
person_times = {}
completed_durations = []
beeped_ids = set()
active_messages = []
person_face_map = {}

# Start dashboard in separate thread
print(f"\n{'='*60}")
print(f"Starting dashboard at: http://localhost:{DASHBOARD_PORT}")
print(f"{'='*60}\n")

# Pass heatmap generator to dashboard
from dashboard import set_heatmap_generator
set_heatmap_generator(heatmap_gen)

dashboard_thread = threading.Thread(target=start_dashboard, daemon=True)
dashboard_thread.start()

print("Starting detection loop...")
print("View the live feed at: http://localhost:5000")
print("Press Ctrl+C to stop\n")

# Main detection loop
try:
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
        heatmap_gen.update(frame, tracks)

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

            # Face recognition for new person or periodically
            if tid not in person_face_map or (int(now * 30) % 30 == 0):
                face_id = face_recognizer.recognize_face(frame, (x1, y1, x2, y2))
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
        stats = {
            'live_count': len(current_ids),
            'unique_visitors': face_recognizer.get_unique_count(),
            'total_visits': len(completed_durations) + len(current_ids),
            'avg_duration': round(np.mean(completed_durations), 2) if completed_durations else 0
        }
        update_dashboard_stats(stats)

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
        cv2.putText(annotated, f"Live: {stats['live_count']}", (20,40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)
        cv2.putText(annotated, f"Unique: {stats['unique_visitors']}", (20,80),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)
        cv2.putText(annotated, f"Avg: {stats['avg_duration']}s", (20,120),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255,0,0), 2)

        # Display messages
        active_messages = [(msg, ts) for msg, ts in active_messages if now - ts < MESSAGE_DURATION]
        
        y_offset = annotated.shape[0] - 20
        for msg, ts in active_messages:
            (msg_width, msg_height), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            cv2.rectangle(annotated, (15, y_offset - msg_height - 5), (25 + msg_width, y_offset + 5), (0,0,0), -1)
            
            cv2.putText(annotated, msg, (20, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
            y_offset -= 35

        # Update latest frame for dashboard
        update_latest_frame(annotated)

        # Check for 'q' key press to quit (console input)
        # Note: cv2.imshow is disabled due to GUI issues
        # View the feed through the web dashboard at http://localhost:5000

except KeyboardInterrupt:
    print("\n\nStopping detection...")

cap.release()
pygame.mixer.quit()
print("Shutdown complete!")