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

# HTML Template
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
                <div class="stat-label">Avg Duration (s)</div>
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
    """Serve main dashboard page"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/stats')
def stats():
    """Return current statistics as JSON"""
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


@app.route('/heatmap_feed')
def heatmap_feed():
    """Stream heatmap feed"""
    def generate():
        while True:
            if heatmap_generator is not None:
                heatmap_img = heatmap_generator.generate_image()
                if heatmap_img is not None:
                    ret, buffer = cv2.imencode('.jpg', heatmap_img)
                    if ret:
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                else:
                    # Generate blank heatmap if no data yet
                    blank = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(blank, "Waiting for activity data...", (150, 240),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                    ret, buffer = cv2.imencode('.jpg', blank)
                    if ret:
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            else:
                # No heatmap generator yet
                blank = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(blank, "Initializing heatmap...", (180, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                ret, buffer = cv2.imencode('.jpg', blank)
                if ret:
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.1)  # 10 FPS for heatmap
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


def update_dashboard_stats(stats):
    """
    Update dashboard statistics
    
    Args:
        stats: Dictionary with keys: live_count, unique_visitors, total_visits, avg_duration
    """
    global dashboard_stats
    dashboard_stats = stats


def update_latest_frame(frame):
    """
    Update the latest frame for video streaming
    
    Args:
        frame: OpenCV frame (numpy array)
    """
    global latest_frame
    with frame_lock:
        latest_frame = frame.copy()


def set_heatmap_generator(generator):
    """
    Set the heatmap generator instance
    
    Args:
        generator: HeatmapGenerator instance
    """
    global heatmap_generator
    heatmap_generator = generator


def start_dashboard():
    """Start Flask dashboard server"""
    app.run(host='0.0.0.0', port=DASHBOARD_PORT, debug=False, threaded=True, use_reloader=False)