"""
Dashboard Module
Flask-based web dashboard for live statistics and video feeds
"""

import cv2
import numpy as np
import time
import json
import threading
from flask import Flask, Response, render_template_string
from config import DASHBOARD_PORT
from heatmap_module import HeatmapGenerator

# Create Flask app
app = Flask(__name__)

# Global variables for dashboard
dashboard_stats = {
    'live_count': 0,
    'unique_visitors': 0,
    'total_visits': 0,
    'avg_duration': 0
}

latest_frame = None
frame_lock = threading.Lock()
heatmap_generator = None

# Updated HTML Template — heatmap removed, camera feed full width, stats overlay added
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Visitor Detection Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <style>
        body {
            margin: 0;
            padding: 0;
            background: #111;
            font-family: Arial, sans-serif;
            color: white;
        }
        .video-container {
            position: relative;
            width: 100%;
            max-width: 1500px;
            margin: 0 auto;
        }
        #camera-feed {
            width: 100%;
            border-radius: 10px;
            display: block;
        }
        .overlay-stats {
            position: absolute;
            top: 15px;
            left: 20px;
            background: rgba(0,0,0,0.55);
            padding: 12px 18px;
            border-radius: 10px;
            font-size: 22px;
            letter-spacing: 1px;
        }
        .pulse {
            display: inline-block;
            width: 10px;
            height: 10px;
            background: #4CAF50;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: .3; }
        }
    </style>

    <script>
        // Update stats every second
        function updateStats() {
            fetch('/stats')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('live-count').textContent = data.live_count;
                    document.getElementById('total-visits').textContent = data.total_visits;
                });
        }

        setInterval(updateStats, 1000);

        // Refresh camera feed without page reload
        setInterval(() => {
            document.getElementById('camera-feed').src = '/video_feed?' + new Date().getTime();
        }, 100);
    </script>
</head>

<body>
    <div class="video-container">
        <div class="overlay-stats">
            <span class="pulse"></span>
            Live: <span id="live-count">0</span>  
            &nbsp;&nbsp;|&nbsp;&nbsp;  
            Total Visits: <span id="total-visits">0</span>
        </div>

        <img id="camera-feed" src="/video_feed" alt="Camera Feed">
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
    """Stream live video feed"""
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




def update_dashboard_stats(stats):
    global dashboard_stats
    dashboard_stats = stats


def update_latest_frame(frame):
    global latest_frame
    with frame_lock:
        latest_frame = frame.copy()


def set_heatmap_generator(generator):
    global heatmap_generator
    heatmap_generator = generator


def start_dashboard():
    app.run(host='0.0.0.0', port=DASHBOARD_PORT, debug=False, threaded=True, use_reloader=False)
