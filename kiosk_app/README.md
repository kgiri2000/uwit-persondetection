# UWIT Kiosk Portal & Person Detection Intercom

A locally-hosted video intercom and visitor detection system designed for service windows. The application runs in **Docker** using **FastAPI** (Python) for the backend signaling/AI processing, and a **Vanilla HTML/CSS/JS** WebRTC mesh interface for real-time video/audio conferencing.

---

## Tech Stack & Tools Used

### Backend & AI Server
- **Python 3.10 & FastAPI**: Fast, asynchronous web framework hosting the static assets, WebRTC signaling WebSockets, and frame detection socket.
- **Uvicorn**: High-performance ASGI web server.
- **Ultralytics YOLOv8**: Real-time object detection model (`yolov8n.pt`) configured to detect persons.
- **DeepSort Realtime**: Deep learning multi-object tracking library used to track person IDs across frames.
- **Pygame**: Handles server-side audio playback attempts.

### Frontend Client
- **HTML5 & CSS3**: High-fidelity, custom glassmorphic dark-theme design utilizing the Google Font **Outfit** and flexible responsive grids.
- **JavaScript (ES6)**:
  - **Navigator MediaDevices API**: Captures webcam and microphone input from the client's browser.
  - **WebRTC (RTCPeerConnection)**: Establishes low-latency, direct peer-to-peer audio and video streams between host and guests in a mesh network.
  - **HTML5 Canvas**: Captures frames from the host's video stream and encodes them to JPEG blobs for real-time WebSocket transmission to YOLO.
  - **HTML5 Audio**: Plays the client-side chiming alert when visitors are confirmed.

### Infrastructure
- **Docker & Docker Compose**: Containerizes the Python ML dependencies (PyTorch, OpenCV system libraries) and isolates the web environment for easy network deployment.

---

## ⚙️ How It Works

### 1. Security & Role Selection
Access to the intercom portal is protected by a hardcoded credential:
- **Default Password**: `UWIT2026`

When opening the web portal, enter the password and select one of two roles:
- **Host (Kiosk)**: Positioned at the service window. Displays the local camera feed overlayed with YOLO green detection boxes and tracks visitor sessions.
- **Guest (Employee)**: Employee computers on the same network. Receives notifications and joins calls with the kiosk.

### 2. Visitor Detection & Alerting (Host-Side)
- The **Host Kiosk** camera captures frames in the browser.
- JavaScript extracts these frames at **10 FPS** and streams them to the FastAPI server via WebSockets.
- The server's `DetectionEngine` decodes each frame, runs YOLOv8 person detection, and registers tracking IDs through DeepSort.
- If a person is tracked in the frame continuously for **5 seconds**:
  - The server sends a WebSocket trigger `play_beep` to the Host browser.
  - The Host Kiosk browser plays `notification.wav` out of the kiosk speakers to alert desk employees nearby.
  - An entry is logged to the dashboard console and printed on screen.
- When the visitor leaves the camera view, the system calculates the duration of their visit and logs it to `visitor_log.csv`.

### 3. Video Calling (Intercom)
- When a **Guest (Employee)** joins, they connect to the WebRTC signaling WebSocket.
- The new guest automatically initiates an RTCPeerConnection to the **Host (Kiosk)**.
- Once negotiated, the Guest sees the Host Kiosk camera feed in **full screen** (to view the service desk window).
- The Guest's microphone and webcam are streamed back to the **Host Kiosk**, appearing in a smaller floating grid so the customer standing at the window can see and talk to the employee.

---

## Setup & Execution Instructions

You can run the application either using **Docker Compose** or **manually on your host system**.

### ⚙️ Configuration (.env) Setup
Before starting the application, you must create a `.env` file. A template `.env.example` is provided:
```bash
cp .env.example .env
```
Inside `.env`, you can customize:
- `PORTAL_PASSWORD`: Set the password for portal access (default: `UWIT2026`).
- `DETECTION_WIDTH` & `DETECTION_HEIGHT`: Increase or decrease these values to change the video resolution sent from the client to the detection engine (e.g., `400` x `300` for low-latency speed, or `640` x `480` for higher quality).
- `YOLO_IMGSZ`: The neural network inference size (e.g., `320` for super-fast CPU tracking, or `640` for full resolution).

### Option A: Running with Docker (Recommended)
1. Start the container:
   ```bash
   cd /home/kgiri/uwit-persondetection/kiosk_app
   docker compose up --build -d
   ```
2. View container logs:
   ```bash
   docker compose logs -f
   ```
3. Stop the container:
   ```bash
   docker compose down
   ```

---

### Option B: Running Manually on Host System

#### 1. System Dependencies (Linux only)
If running on Linux, make sure you have the required graphic and audio libraries:
```bash
sudo apt update && sudo apt install -y libgl1 libglib2.0-0 libasound2
```

#### 2. Create Virtual Environment
Create and activate a Python virtual environment to avoid package conflicts:
```bash
cd /home/kgiri/uwit-persondetection/kiosk_app
python3 -m venv venv
source venv/bin/activate
```

#### 3. Install Python Dependencies
Install the required packages from `requirements.txt`:
```bash
pip install -r requirements.txt
```

#### 4. Run the Server
Launch the FastAPI application with Uvicorn:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

### Step 2: Accessing the Application
- **Kiosk Machine (Host)**: Open your browser and go to `http://localhost:8000`.
- **Workstations (Guests)**: Open your browser and go to `http://<server-ip>:8000` (e.g. `http://192.168.1.125:8000`).

---

## Crucial Network Camera Configuration (WebRTC)

WebRTC security rules require a **Secure Context** (HTTPS or localhost) to access camera and microphone devices. If you access the server via a local network IP address (e.g. `http://192.168.1.125:8000`), the browser will **block** camera permissions.

### Local Network Insecure Origin Solution:
On any workstation or kiosk device accessing via the network IP:
1. Open Google Chrome.
2. Navigate to: `chrome://flags/#unsafely-treat-insecure-origin-as-secure`
3. Locate the flag and select **Enabled**.
4. In the text field, enter the IP and port of the host computer, prefixed with `http://` (e.g., `http://192.168.1.125:8000`).
5. Click **Relaunch** at the bottom of Chrome.
The browser will now permit camera and microphone access.

---

## Managing Log Exports
Visitor logs are recorded inside the container and synchronized with the host machine. You can find the CSV file containing visitor sessions in the local project directory:
- Path: `kiosk_app/visitor_log.csv`
- Format: `Person_ID, First_Seen, Last_Seen, Duration_sec`

Alternatively, you can download the log file directly from the Web UI sidebar using the **Export CSV** button.

---

## Project Structure
```
kiosk_app/
│
├── Dockerfile             # Package configuration & system library setup
├── docker-compose.yml     # Port forwarding & persistent CSV logging
├── requirements.txt       # Python ML & Web packages
│
├── main.py                # FastAPI server, WebSockets, & WebRTC signaling
├── detection_engine.py    # YOLOv8 & DeepSort tracking and sound logic
├── yolov8n.pt             # Pre-trained YOLOv8 model weights
├── visitor_log.csv        # Log of visitor sessions (generated automatically)
│
└── static/
    ├── index.html         # Main dashboard layout (Role selection modal)
    ├── notification.wav   # Notification chime
    │
    ├── css/
    │   └── style.css      # Premium dark glassmorphic styling
    └── js/
        └── app.js         # WebRTC mesh calling & WebSocket video transfer
```
