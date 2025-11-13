"""
Heatmap Module
Generates activity heatmaps based on person positions
"""

import cv2
import numpy as np


class HeatmapGenerator:
    def __init__(self, grid_size=10):
        """
        Initialize heatmap generator
        
        Args:
            grid_size: Size of grid cells (lower = more detailed)
        """
        self.grid_size = grid_size
        self.heatmap_data = None
        
    def update(self, frame, tracks):
        """
        Update heatmap based on person positions
        
        Args:
            frame: Current video frame
            tracks: List of DeepSort tracks
        """
        if self.heatmap_data is None:
            self.heatmap_data = np.zeros(
                (frame.shape[0] // self.grid_size, frame.shape[1] // self.grid_size), 
                dtype=np.float32
            )
        
        for track in tracks:
            if not track.is_confirmed():
                continue
            
            l, t, w, h = track.to_ltwh()
            center_x = int((l + w/2) // self.grid_size)
            center_y = int((t + h/2) // self.grid_size)
            
            if (0 <= center_y < self.heatmap_data.shape[0] and 
                0 <= center_x < self.heatmap_data.shape[1]):
                self.heatmap_data[center_y, center_x] += 1
    
    def generate_image(self):
        """
        Generate heatmap visualization
        
        Returns:
            Colored heatmap image or None if no data
        """
        if self.heatmap_data is None:
            return None
        
        # Normalize heatmap
        normalized = cv2.normalize(self.heatmap_data, None, 0, 255, cv2.NORM_MINMAX)
        normalized = normalized.astype(np.uint8)
        
        # Apply colormap (blue = cold, red = hot)
        heatmap_colored = cv2.applyColorMap(normalized, cv2.COLORMAP_JET)
        
        # Resize to match original dimensions
        heatmap_resized = cv2.resize(
            heatmap_colored, 
            (self.heatmap_data.shape[1] * self.grid_size, 
             self.heatmap_data.shape[0] * self.grid_size)
        )
        
        return heatmap_resized
    
    def reset(self):
        """Reset heatmap data"""
        self.heatmap_data = None
    
    def get_hotspots(self, top_n=5):
        """
        Get top N hotspot locations
        
        Args:
            top_n: Number of top locations to return
            
        Returns:
            List of tuples (x, y, intensity)
        """
        if self.heatmap_data is None:
            return []
        
        # Flatten and get top indices
        flat = self.heatmap_data.flatten()
        top_indices = np.argsort(flat)[-top_n:][::-1]
        
        hotspots = []
        for idx in top_indices:
            y = idx // self.heatmap_data.shape[1]
            x = idx % self.heatmap_data.shape[1]
            intensity = self.heatmap_data[y, x]
            
            # Convert back to original coordinates
            x_orig = x * self.grid_size + self.grid_size // 2
            y_orig = y * self.grid_size + self.grid_size // 2
            
            hotspots.append((x_orig, y_orig, intensity))
        
        return hotspots