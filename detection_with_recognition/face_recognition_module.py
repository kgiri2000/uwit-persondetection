"""
Face Recognition Module
Handles face detection and recognition using OpenCV
"""

import cv2
import numpy as np
from config import FACE_MATCH_THRESHOLD


class FaceRecognizer:
    def __init__(self):
        """Initialize face recognition system"""
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        self.face_data_db = {}  # {face_id: {'image': gray_face, 'histogram': hist}}
        self.next_face_id = 1
        
    def compute_face_histogram(self, face_img):
        """
        Compute color histogram for face comparison
        
        Args:
            face_img: Face image (BGR format)
            
        Returns:
            Normalized histogram array or None if invalid
        """
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
    
    def compare_faces(self, hist1, hist2):
        """
        Compare two face histograms using correlation
        
        Args:
            hist1: First histogram
            hist2: Second histogram
            
        Returns:
            Correlation score (0.0 to 1.0, higher is more similar)
        """
        if hist1 is None or hist2 is None:
            return 0
        
        correlation = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
        return correlation
    
    def recognize_face(self, frame, bbox):
        """
        Extract and recognize face from bounding box
        
        Args:
            frame: Full frame image
            bbox: Bounding box tuple (x1, y1, x2, y2)
            
        Returns:
            Face ID string (e.g., "F0001") or None if no face detected
        """
        x1, y1, x2, y2 = bbox
        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(frame.shape[1], x2), min(frame.shape[0], y2)
        
        # Extract person region
        person_img = frame[y1:y2, x1:x2]
        
        if person_img.size == 0:
            return None
        
        # Convert to grayscale for face detection
        gray = cv2.cvtColor(person_img, cv2.COLOR_BGR2GRAY)
        
        # Detect faces in person region
        faces = self.face_cascade.detectMultiScale(
            gray, 
            scaleFactor=1.1, 
            minNeighbors=5, 
            minSize=(30, 30)
        )
        
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
        face_hist = self.compute_face_histogram(face_img)
        
        if face_hist is None:
            return None
        
        # Compare with known faces
        best_match_id = None
        best_match_score = 0
        
        for face_id, face_info in self.face_data_db.items():
            score = self.compare_faces(face_info['histogram'], face_hist)
            if score > best_match_score:
                best_match_score = score
                best_match_id = face_id
        
        # If good match found (correlation > threshold)
        if best_match_score > FACE_MATCH_THRESHOLD:
            return best_match_id
        
        # New face - assign new ID
        face_id = f"F{self.next_face_id:04d}"
        self.next_face_id += 1
        
        # Store face data
        self.face_data_db[face_id] = {
            'image': cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY),
            'histogram': face_hist
        }
        
        return face_id
    
    def get_unique_count(self):
        """Get number of unique faces recognized"""
        return len(self.face_data_db)
    
    def get_face_image(self, face_id):
        """
        Get stored face image for a given face ID
        
        Args:
            face_id: Face ID string
            
        Returns:
            Grayscale face image or None
        """
        if face_id in self.face_data_db:
            return self.face_data_db[face_id]['image']
        return None