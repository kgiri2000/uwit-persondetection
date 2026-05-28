import cv2
import numpy as np
import time
import os
import csv
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort
import pygame

class DetectionEngine:
    def __init__(self, model_path="yolov8n.pt", sound_file="static/notification.wav", csv_file="visitor_log.csv", imgsz=320):
        self.model_path = model_path
        self.sound_file = sound_file
        self.csv_file = csv_file
        self.imgsz = imgsz
        
        # Load YOLO model
        print("Loading YOLO model in DetectionEngine...")
        self.model = YOLO(self.model_path)
        
        # Initialize DeepSort
        self.deepsort = DeepSort(
            max_age=30,
            n_init=3,
            max_cosine_distance=0.3,
            nn_budget=100
        )
        
        # Initialize pygame for server-side audio if available
        self.beep_sound = None
        try:
            pygame.mixer.init()
            if os.path.exists(self.sound_file):
                self.beep_sound = pygame.mixer.Sound(self.sound_file)
                print("Server-side audio initialized successfully.")
            else:
                print(f"Warning: Sound file {self.sound_file} not found for server-side playback.")
        except Exception as e:
            print(f"Server-side audio not available (pygame.mixer init failed): {e}")

        # Initialize CSV log file
        if not os.path.exists(self.csv_file):
            try:
                with open(self.csv_file, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Person_ID", "First_Seen", "Last_Seen", "Duration_sec"])
            except Exception as e:
                print(f"Error initializing CSV log: {e}")

        # Tracking state
        self.person_times = {}  # {track_id: {"first_seen": timestamp, "last_seen": timestamp}}
        self.beeped_ids = set()
        self.last_beep_time = 0
        self.global_beep_cooldown = 10.0  # seconds between server play beeps
        self.beep_delay = 5.0  # seconds a person must be in frame before beeping
        
    def play_sound(self):
        if self.beep_sound:
            try:
                self.beep_sound.play()
            except Exception as e:
                print(f"Failed to play sound on server: {e}")

    def process_frame(self, frame_bytes: bytes):
        """
        Process a single JPEG frame.
        Returns:
            annotated_frame_bytes (bytes): The JPEG encoded frame with bounding boxes and track IDs.
            play_beep (bool): True if a new person has been in frame for 5 seconds and sound should play.
            log_message (str or None): A string logging the detection event.
        """
        # Decode JPEG bytes to OpenCV frame
        nparr = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            return None, False, None

        h, w, _ = frame.shape
        frame_area = h * w
        
        # Run YOLOv8 on the frame
        results = self.model(frame, imgsz=self.imgsz, verbose=False)[0]
        
        dets_xyxy = []
        dets_conf = []
        
        for box in results.boxes:
            if int(box.cls[0]) == 0:  # Class 0 is Person
                conf = float(box.conf[0])
                if conf >= 0.5:  # Confidence threshold
                    x1, y1, x2, y2 = box.xyxy[0].cpu().tolist()
                    dets_xyxy.append([x1, y1, x2, y2])
                    dets_conf.append(conf)

        # Build DeepSort detections list
        detections = []
        for (x1, y1, x2, y2), conf in zip(dets_xyxy, dets_conf):
            # DeepSort expects: ([left, top, width, height], confidence, detection_class)
            left = x1
            top = y1
            width = x2 - x1
            height = y2 - y1
            detections.append(([left, top, width, height], conf, 'person'))

        # Update DeepSort tracks
        tracks = self.deepsort.update_tracks(detections, frame=frame)
        
        now = time.time()
        new_ids = set()
        trigger_beep = False
        log_msg = None

        # Loop through tracks
        for track in tracks:
            if not track.is_confirmed():
                continue
            
            tid = int(track.track_id)
            l, t, w_box, h_box = track.to_ltwh()
            x1, y1, x2, y2 = int(l), int(t), int(l + w_box), int(t + h_box)
            
            # Simple size filtering (must be larger than 0.5% of frame)
            if (w_box * h_box) / frame_area < 0.005:
                continue
                
            new_ids.add(tid)
            
            # Manage time tracking
            if tid not in self.person_times:
                self.person_times[tid] = {"first_seen": now, "last_seen": now}
                log_msg = f"Person ID {tid} entered the frame."
                print(log_msg)
            else:
                self.person_times[tid]["last_seen"] = now

        # Beep notification trigger
        for tid in new_ids:
            first_seen = self.person_times[tid]["first_seen"]
            duration = now - first_seen
            
            # Check if duration meets delay, and not yet beeped
            if (duration >= self.beep_delay and tid not in self.beeped_ids):
                trigger_beep = True
                self.beeped_ids.add(tid)
                
                # Try server-side playback (with cooldown)
                if now - self.last_beep_time >= self.global_beep_cooldown:
                    self.play_sound()
                    self.last_beep_time = now
                    
                log_msg = f"Person ID {tid} confirmed in frame for {int(duration)} seconds. Notification played!"
                print(log_msg)

        # Handle departures (IDs that were in person_times but not in current active tracks)
        left_ids = set(self.person_times.keys()) - new_ids
        for tid in left_ids:
            first = self.person_times[tid]["first_seen"]
            last = self.person_times[tid]["last_seen"]
            dur = last - first
            
            # Save to CSV if they were there for at least a minimum duration (e.g. 2 seconds)
            if dur >= 2.0:
                try:
                    with open(self.csv_file, 'a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            tid,
                            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(first)),
                            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last)),
                            round(dur, 2)
                        ])
                except Exception as e:
                    print(f"Failed to log departure to CSV: {e}")
                    
            # Clean up state
            log_msg = f"Person ID {tid} departed. (Total time: {round(dur, 1)}s)"
            print(log_msg)
            del self.person_times[tid]
            self.beeped_ids.discard(tid)

        # Draw bounding boxes and text
        annotated_frame = frame.copy()
        for track in tracks:
            if not track.is_confirmed():
                continue
            
            tid = int(track.track_id)
            if tid not in new_ids:
                continue
                
            l, t, w_box, h_box = track.to_ltwh()
            x1, y1, x2, y2 = int(l), int(t), int(l + w_box), int(t + h_box)
            
            # Draw rectangle (Emerald green color: (46, 204, 113) in BGR)
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (113, 204, 46), 2)
            
            # Add tag
            first_seen = self.person_times[tid]["first_seen"]
            duration = now - first_seen
            label = f"ID: {tid} ({int(duration)}s)"
            
            # Draw text background
            (label_width, label_height), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(annotated_frame, (x1, y1 - label_height - 10), (x1 + label_width, y1), (113, 204, 46), -1)
            cv2.putText(annotated_frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

        # Encode frame back to JPEG bytes
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        if not ret:
            return None, False, None
            
        return buffer.tobytes(), trigger_beep, log_msg
