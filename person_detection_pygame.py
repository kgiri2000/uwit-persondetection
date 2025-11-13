import cv2
from ultralytics import YOLO
import numpy as np
import pygame
import time
import csv
import os
from deep_sort_realtime.deepsort_tracker import DeepSort

CAMERA_INDEX = 0
MODEL_PATH = "yolov8n.pt"
MIN_AREA_RATIO = 0.03
GLOBAL_BEEP_COOLDOWN = 10
CSV_FILE = "visitor_log.csv"
SOUND_FILE = "notification.wav"
MESSAGE_DURATION = 5
BEEP_DELAY = 5
CONFIDENCE_THRESHOLD = 0.5  # Minimum confidence for person detection

deepsort = DeepSort(
    max_age=30,
    n_init=3,
    max_cosine_distance=0.3,
    nn_budget=100
)

pygame.mixer.init()

# Check if sound file exists
if not os.path.exists(SOUND_FILE):
    print(f"Warning: {SOUND_FILE} not found. Beeps will be silent.")
    beep_sound = None
else:
    beep_sound = pygame.mixer.Sound(SOUND_FILE)

def play_beep():
    if beep_sound:
        beep_sound.play()

if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Person_ID", "First_Seen", "Last_Seen", "Duration_sec"])

model = YOLO(MODEL_PATH)

cap = cv2.VideoCapture(CAMERA_INDEX)
if not cap.isOpened():
    print(f"Error: Cannot open camera {CAMERA_INDEX}")
    exit(1)

current_ids = set()
last_beep_time = 0
person_times = {}
completed_durations = []
beeped_ids = set()
active_messages = []

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    frame_area = frame.shape[0] * frame.shape[1]

    results = model(frame)[0]

    dets_xyxy = []
    dets_conf = []

    # Filter for person class (class 0) with confidence threshold
    for box in results.boxes:
        if int(box.cls[0]) == 0:  # Person class only
            conf = float(box.conf[0])
            if conf >= CONFIDENCE_THRESHOLD:  # Add confidence check
                x1, y1, x2, y2 = box.xyxy[0].cpu().tolist()
                dets_xyxy.append([float(x1), float(y1), float(x2), float(y2)])
                dets_conf.append(float(conf))

    detections = []
    for (x1, y1, x2, y2), conf in zip(dets_xyxy, dets_conf):
        detections.append(([float(x1), float(y1), float(x2), float(y2)], float(conf), 'person'))

    tracks = deepsort.update_tracks(detections, frame=frame)

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

        if tid not in person_times:
            person_times[tid] = {"first_seen": now, "last_seen": now}
        else:
            person_times[tid]["last_seen"] = now

    for tid in new_ids:
        first_seen = person_times[tid]["first_seen"]
        duration = now - first_seen

        if (duration >= BEEP_DELAY and
            tid not in beeped_ids and
            (now - last_beep_time >= GLOBAL_BEEP_COOLDOWN)):

            msg = f"Person {tid} confirmed after {BEEP_DELAY} sec."
            play_beep()
            beeped_ids.add(tid)
            last_beep_time = now
            active_messages.append((msg, now))

    left_ids = current_ids - new_ids
    for tid in left_ids:
        first = person_times[tid]["first_seen"]
        last = person_times[tid]["last_seen"]
        dur = last - first

        if dur >= 5:
            completed_durations.append(dur)
            with open(CSV_FILE, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    tid,
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(first)),
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last)),
                    round(dur, 2)
                ])

        del person_times[tid]
        beeped_ids.discard(tid)

    # Prevent memory leak by limiting completed_durations list
    if len(completed_durations) > 1000:
        completed_durations = completed_durations[-1000:]

    current_ids = new_ids

    annotated = frame.copy()

    for track in tracks:
        if not track.is_confirmed():
            continue

        tid = int(track.track_id)
        l, t, w, h = track.to_ltwh()
        x1, y1, x2, y2 = int(l), int(t), int(l + w), int(t + h)

        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0,255,0), 2)
        cv2.putText(annotated, f"ID {tid}", (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)

    cv2.putText(annotated, f"Current: {len(current_ids)}", (20,40),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)

    total = len(completed_durations) + len(current_ids)
    cv2.putText(annotated, f"Total Visitors: {total}", (20,80),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)

    avg = round(np.mean(completed_durations), 2) if completed_durations else 0
    cv2.putText(annotated, f"Avg Duration: {avg}s", (20,120),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255,0,0), 2)

    # Clean up old messages efficiently
    active_messages = [(msg, ts) for msg, ts in active_messages if now - ts < MESSAGE_DURATION]
    
    y_offset = annotated.shape[0] - 20
    for msg, ts in active_messages:
        cv2.putText(annotated, msg, (20, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,0), 2)
        y_offset -= 25

    cv2.imshow("Person Detection", annotated)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
pygame.mixer.quit()