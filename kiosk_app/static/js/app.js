// UWIT Kiosk Application JS

// State Management
let localStream = null;
let signalingSocket = null;
let detectionSocket = null;
let myPeerId = null;
let myRole = null;
let myName = null;

const peerConnections = {}; // { peerId: RTCPeerConnection }
const peerRoles = {};        // { peerId: role }
const peerNames = {};        // { peerId: name }
let isSoundEnabled = true;
let detectionInterval = null;
const detectionFps = 10;
const iceServers = [
    { urls: 'stun:stun.l.google.com:19302' },
    { urls: 'stun:stun1.l.google.com:19302' }
];

// Configuration variables loaded from server
let detectionWidth = 400;
let detectionHeight = 300;

async function fetchConfig() {
    try {
        const res = await fetch('/api/config');
        const data = await res.json();
        detectionWidth = data.detectionWidth || 400;
        detectionHeight = data.detectionHeight || 300;
        console.log(`Frame transmission size: ${detectionWidth}x${detectionHeight}`);
    } catch (err) {
        console.error("Failed to load resolution configuration, using default 400x300:", err);
    }
}
fetchConfig();

// DOM Elements
const roleModal = document.getElementById('role-modal');
const appContainer = document.getElementById('app-container');
const btnSelectHost = document.getElementById('btn-select-host');
const btnSelectGuest = document.getElementById('btn-select-guest');
const guestNameInput = document.getElementById('guest-name');
const btnToggleSound = document.getElementById('btn-toggle-sound');
const btnToggleDetection = document.getElementById('btn-toggle-detection');
const soundIcon = document.getElementById('sound-icon');
const btnDisconnect = document.getElementById('btn-disconnect');
const timeDisplay = document.getElementById('time-display');
const localVideo = document.getElementById('local-video');
const detectionFeed = document.getElementById('detection-feed');
const remoteHostsGrid = document.getElementById('remote-hosts-grid');
const videoPlaceholder = document.getElementById('video-placeholder');
const placeholderText = document.getElementById('placeholder-text');
const videoStatusMsg = document.getElementById('video-status-msg');
const roleBadge = document.getElementById('role-badge');
const selfMiniVideo = document.getElementById('self-mini-video');
const btnToggleCam = document.getElementById('btn-toggle-cam');
const btnToggleMic = document.getElementById('btn-toggle-mic');

// Initialize time display
setInterval(() => {
    const now = new Date();
    timeDisplay.textContent = now.toLocaleTimeString();
}, 1000);

// Log to UI Console
function logToConsole(message, type = 'system') {
    const consoleElem = document.getElementById('log-console');
    if (consoleElem) {
        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;
        const timestamp = new Date().toLocaleTimeString();
        entry.textContent = `[${timestamp}] ${message}`;
        consoleElem.appendChild(entry);
        consoleElem.scrollTop = consoleElem.scrollHeight;
    }
}

// Play notification sound
function playBeep() {
    if (!isSoundEnabled) return;
    const player = document.getElementById('beep-player');
    if (player) {
        player.play().catch(err => {
            console.log("Audio playback blocked by browser security. Click on the page to enable.", err);
            logToConsole("Browser blocked beep audio. Click anywhere to activate audio.", "system");
        });
    }
}

// Portal Password validation (asynchronous API verification)
async function validatePassword() {
    const passwordInput = document.getElementById('portal-password');
    const passwordError = document.getElementById('password-error');
    
    try {
        const response = await fetch('/api/verify-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password: passwordInput.value })
        });
        const data = await response.json();
        if (data.valid) {
            passwordError.classList.add('hidden');
            return true;
        }
    } catch (err) {
        console.error("Password verification error:", err);
    }
    
    passwordError.classList.remove('hidden');
    passwordInput.focus();
    return false;
}

// Event Listeners for Role Selection
btnSelectHost.addEventListener('click', async () => {
    const valid = await validatePassword();
    if (!valid) return;
    myRole = 'host';
    myName = 'Kiosk Screen';
    initMediaAndConnect();
});

btnSelectGuest.addEventListener('click', async () => {
    const valid = await validatePassword();
    if (!valid) return;
    const name = guestNameInput.value.trim();
    if (!name) {
        alert("Please enter your name to connect.");
        return;
    }
    myRole = 'guest';
    myName = name;
    initMediaAndConnect();
});

// Setup camera & WebSocket connections
async function initMediaAndConnect() {
    logToConsole(`Initializing media devices as ${myRole.toUpperCase()} (${myName})...`, "system");
    
    // Request camera and microphone access
    try {
        localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        logToConsole("Camera and microphone accessed successfully.", "system");
    } catch (err) {
        logToConsole("Dual camera/mic permission failed. Trying video only...", "system");
        try {
            localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
            logToConsole("Camera accessed successfully (video only).", "system");
        } catch (err2) {
            logToConsole("Video access failed. Trying audio only...", "system");
            try {
                localStream = await navigator.mediaDevices.getUserMedia({ video: false, audio: true });
                logToConsole("Microphone accessed successfully (audio only).", "system");
            } catch (err3) {
                logToConsole("No media devices available. Joining in view-only mode.", "system");
                localStream = new MediaStream();
            }
        }
    }

    // Set up self video preview
    if (localStream.getVideoTracks().length > 0) {
        selfMiniVideo.srcObject = localStream;
    } else {
        // Show a placeholder in self-video card
        document.getElementById('self-card').style.background = '#1f2937';
    }

    // Hide Modal & Show Workspace
    roleModal.classList.add('hidden');
    appContainer.classList.remove('hidden');
    
    // Update header badges
    roleBadge.textContent = myRole;
    roleBadge.className = `role-badge ${myRole}`;
    videoStatusMsg.textContent = `Camera: Active | Role: ${myRole.toUpperCase()}`;

    // Establish WebSocket connections
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const hostPort = window.location.host;
    
    // Connect to WebRTC signaling server
    const signalingUrl = `${protocol}//${hostPort}/ws/signaling?role=${myRole}&name=${encodeURIComponent(myName)}`;
    signalingSocket = new WebSocket(signalingUrl);
    setupSignalingWebSocket();

    // If host, start WebSocket for server-side YOLO person detection
    if (myRole === 'host') {
        const selfCard = document.getElementById('self-card');
        if (selfCard) {
            selfCard.style.display = 'none';
        }
        if (btnToggleDetection) {
            btnToggleDetection.style.display = 'inline-block';
        }
        const detectUrl = `${protocol}//${hostPort}/ws/detect`;
        detectionSocket = new WebSocket(detectUrl);
        setupDetectionWebSocket();
        
        // Host needs local-video element running in background to capture frames
        localVideo.srcObject = localStream;
        localVideo.muted = true;
        localVideo.play();
    } else {
        // Guest shows main placeholder initially
        placeholderText.textContent = "Waiting for Host Kiosk to connect...";
        const selfCard = document.getElementById('self-card');
        if (selfCard) {
            selfCard.style.display = 'block';
        }
    }
}

// -------------------------------------------------------------
// Person Detection WebSocket (Host Kiosk Only)
// -------------------------------------------------------------
function setupDetectionWebSocket() {
    detectionSocket.onopen = () => {
        logToConsole("Connected to server-side YOLO detection engine.", "system");
        startFrameTransmission();
    };

    detectionSocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        // Display annotated frame
        if (data.frame) {
            detectionFeed.src = "data:image/jpeg;base64," + data.frame;
            if (isDetectionEnabled) {
                detectionFeed.classList.remove('video-inactive');
                detectionFeed.classList.add('video-active');
                localVideo.classList.remove('video-active');
                localVideo.classList.add('video-inactive');
            }
            videoPlaceholder.classList.add('hidden');
        }

        // Update floating overlay status log
        updateVideoOverlay(data.log, data.play_beep);

        // Trigger beep sound locally if commanded by YOLO engine
        if (data.play_beep) {
            logToConsole("NEW PERSON DETECTED AT WINDOW! Sounding chime...", "alert");
            playBeep();
        }

        // Log messages
        if (data.log) {
            logToConsole(data.log, "tracking");
        }
    };

    detectionSocket.onclose = () => {
        logToConsole("Disconnected from YOLO detection engine.", "system");
        stopFrameTransmission();
        
        // Fallback to raw local video
        detectionFeed.classList.remove('video-active');
        detectionFeed.classList.add('video-inactive');
        localVideo.classList.remove('video-inactive');
        localVideo.classList.add('video-active');
    };

    detectionSocket.onerror = (err) => {
        console.error("YOLO detection socket error:", err);
    };
}

let isDetectionEnabled = true;

function startFrameTransmission() {
    if (!isDetectionEnabled) return;
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    
    detectionInterval = setInterval(() => {
        if (localVideo && localVideo.readyState === localVideo.HAVE_ENOUGH_DATA) {
            // Resize to configured resolution for fast network transfer
            canvas.width = detectionWidth;
            canvas.height = detectionHeight;
            ctx.drawImage(localVideo, 0, 0, canvas.width, canvas.height);
            
            canvas.toBlob((blob) => {
                if (detectionSocket && detectionSocket.readyState === WebSocket.OPEN) {
                    detectionSocket.send(blob);
                }
            }, 'image/jpeg', 0.6); // 0.6 compression maintains high FPS & good detections
        }
    }, 1000 / detectionFps);
}

function stopFrameTransmission() {
    if (detectionInterval) {
        clearInterval(detectionInterval);
        detectionInterval = null;
    }
}

// -------------------------------------------------------------
// WebRTC Signaling & Mesh Conferencing
// -------------------------------------------------------------
function setupSignalingWebSocket() {
    signalingSocket.onopen = () => {
        logToConsole("Connected to signaling network.", "system");
    };

    signalingSocket.onmessage = async (event) => {
        const message = JSON.parse(event.data);
        
        switch (message.type) {
            case 'init':
                myPeerId = message.peerId;
                // If role was corrected (e.g. host already exists, so forced to guest)
                if (myRole !== message.role) {
                    myRole = message.role;
                    roleBadge.textContent = myRole;
                    roleBadge.className = `role-badge ${myRole}`;
                    logToConsole(`Server reassigned role to: ${myRole.toUpperCase()} (Host limit reached).`, "system");
                    
                    if (myRole === 'guest') {
                        // Clean up detection socket if it was opened
                        if (detectionSocket) {
                            detectionSocket.close();
                        }
                        stopFrameTransmission();
                        detectionFeed.classList.remove('video-active');
                        detectionFeed.classList.add('video-inactive');
                        localVideo.classList.remove('video-active');
                        localVideo.classList.add('video-inactive');
                        videoPlaceholder.classList.remove('hidden');
                        placeholderText.textContent = "Waiting for Host Kiosk to connect...";
                        
                        const selfCard = document.getElementById('self-card');
                        if (selfCard) {
                            selfCard.style.display = 'block';
                        }
                    }
                }
                logToConsole(`Registered on network with peer ID: ${myPeerId}`, "connect");
                
                // Establish connection with existing active peers
                message.activePeers.forEach(peer => {
                    peerRoles[peer.peerId] = peer.role;
                    peerNames[peer.peerId] = peer.name;
                    
                    // Skip host-to-host connections
                    if (myRole === 'host' && peer.role === 'host') {
                        logToConsole(`Skipping connection to another Host Kiosk: ${peer.name}`, "system");
                        return;
                    }
                    
                    // As the new joiner, we initiate connection to all existing peers
                    initiatePeerConnection(peer.peerId, peer.role, peer.name);
                });
                break;
                
            case 'peer-joined':
                peerRoles[message.peerId] = message.role;
                peerNames[message.peerId] = message.name;
                logToConsole(`Participant joined: ${message.name} (${message.role.toUpperCase()})`, "connect");
                // We just prepare; the new joiner will send us an WebRTC Offer
                break;
                
            case 'offer':
                // Skip host-to-host connections
                if (myRole === 'host' && peerRoles[message.senderId] === 'host') {
                    break;
                }
                logToConsole(`Received WebRTC connection request from ${peerNames[message.senderId]}...`, "system");
                handleOffer(message.senderId, message.sdp);
                break;
                
            case 'answer':
                logToConsole(`WebRTC connection accepted by ${peerNames[message.senderId]}.`, "system");
                handleAnswer(message.senderId, message.sdp);
                break;
                
            case 'ice-candidate':
                handleIceCandidate(message.senderId, message.candidate);
                break;
                
            case 'peer-left':
                const leaverName = peerNames[message.peerId] || "Participant";
                logToConsole(`${leaverName} left the room.`, "system");
                closePeerConnection(message.peerId);
                break;
        }
    };

    signalingSocket.onclose = () => {
        logToConsole("Disconnected from signaling server.", "system");
        // Clean up all connections
        Object.keys(peerConnections).forEach(pid => closePeerConnection(pid));
    };

    signalingSocket.onerror = (err) => {
        console.error("Signaling socket error:", err);
    };
}

// Initiate outgoing connection (Offer)
async function initiatePeerConnection(peerId, role, name) {
    logToConsole(`Initiating connection to ${name} (${role.toUpperCase()})...`, "system");
    const pc = createRTCPeerConnection(peerId, role, name);
    
    try {
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        
        signalingSocket.send(JSON.stringify({
            type: 'offer',
            targetId: peerId,
            sdp: offer
        }));
    } catch (err) {
        console.error("Error creating WebRTC offer:", err);
    }
}

// Handle incoming connection request (Offer)
async function handleOffer(senderId, sdp) {
    const role = peerRoles[senderId] || 'guest';
    const name = peerNames[senderId] || 'Guest';
    
    const pc = createRTCPeerConnection(senderId, role, name);
    
    try {
        await pc.setRemoteDescription(new RTCSessionDescription(sdp));
        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);
        
        signalingSocket.send(JSON.stringify({
            type: 'answer',
            targetId: senderId,
            sdp: answer
        }));
    } catch (err) {
        console.error("Error answering WebRTC offer:", err);
    }
}

// Handle answer response
async function handleAnswer(senderId, sdp) {
    const pc = peerConnections[senderId];
    if (pc) {
        try {
            await pc.setRemoteDescription(new RTCSessionDescription(sdp));
        } catch (err) {
            console.error("Error setting remote description:", err);
        }
    }
}

// Handle incoming ICE candidate
async function handleIceCandidate(senderId, candidate) {
    const pc = peerConnections[senderId];
    if (pc) {
        try {
            await pc.addIceCandidate(new RTCIceCandidate(candidate));
        } catch (err) {
            console.error("Error adding ICE candidate:", err);
        }
    }
}

// Create core RTCPeerConnection object
function createRTCPeerConnection(peerId, role, name) {
    const pc = new RTCPeerConnection({ iceServers });
    peerConnections[peerId] = pc;
    
    // Add local media tracks to connection
    if (localStream) {
        localStream.getTracks().forEach(track => {
            pc.addTrack(track, localStream);
        });
    }

    // ICE Candidate handler
    pc.onicecandidate = (event) => {
        if (event.candidate && signalingSocket && signalingSocket.readyState === WebSocket.OPEN) {
            signalingSocket.send(JSON.stringify({
                type: 'ice-candidate',
                targetId: peerId,
                candidate: event.candidate
            }));
        }
    };

    // Incoming track handler
    pc.ontrack = (event) => {
        const remoteStream = event.streams[0];
        
        if (role === 'host') {
            // Guest viewing Host kiosk
            if (myRole === 'guest') {
                logToConsole(`Rendering Host kiosk (${name}) feed on main screen.`, "connect");
                let videoEl = document.getElementById(`remote-host-${peerId}`);
                if (!videoEl) {
                    videoEl = document.createElement('video');
                    videoEl.id = `remote-host-${peerId}`;
                    videoEl.className = 'remote-host-video';
                    videoEl.autoplay = true;
                    videoEl.playsinline = true;
                    if (remoteHostsGrid) {
                        remoteHostsGrid.appendChild(videoEl);
                    }
                }
                videoEl.srcObject = remoteStream;
                videoPlaceholder.classList.add('hidden');
            }
        } else {
            // Host viewing Guest employee (or guests viewing each other)
            logToConsole(`Rendering guest ${name} feed in mini view.`, "connect");
            
            // Check if card already exists
            let peerCard = document.getElementById(`peer-card-${peerId}`);
            if (!peerCard) {
                peerCard = document.createElement('div');
                peerCard.className = 'peer-video-card';
                peerCard.id = `peer-card-${peerId}`;
                
                const video = document.createElement('video');
                video.className = 'peer-mini-video';
                video.autoplay = true;
                video.playsinline = true;
                video.srcObject = remoteStream;
                
                const label = document.createElement('span');
                label.className = 'peer-label';
                label.textContent = name;
                
                peerCard.appendChild(video);
                peerCard.appendChild(label);
                document.getElementById('peers-grid').appendChild(peerCard);
            }
        }
    };

    pc.onconnectionstatechange = () => {
        logToConsole(`Connection state with ${name}: ${pc.connectionState}`, "system");
        if (pc.connectionState === 'failed' || pc.connectionState === 'disconnected') {
            closePeerConnection(peerId);
        }
    };

    return pc;
}

// Clean up peer connection
function closePeerConnection(peerId) {
    const pc = peerConnections[peerId];
    if (pc) {
        pc.close();
        delete peerConnections[peerId];
    }
    
    // Remove UI element
    const peerCard = document.getElementById(`peer-card-${peerId}`);
    if (peerCard) {
        peerCard.remove();
    }

    // Reset main view if Host disconnected
    if (peerRoles[peerId] === 'host') {
        const videoEl = document.getElementById(`remote-host-${peerId}`);
        if (videoEl) {
            videoEl.srcObject = null;
            videoEl.remove();
        }
        
        // If no more hosts are connected, show placeholder
        const remainingHosts = document.querySelectorAll('.remote-host-video');
        if (remainingHosts.length === 0) {
            videoPlaceholder.classList.remove('hidden');
            placeholderText.textContent = "Host Kiosk disconnected. Waiting for reconnect...";
        }
    }
    
    delete peerRoles[peerId];
    delete peerNames[peerId];
}

// -------------------------------------------------------------
// Interactive Controls & Actions
// -------------------------------------------------------------

// Sound Toggle (Mute Speaker beep)
btnToggleSound.addEventListener('click', () => {
    isSoundEnabled = !isSoundEnabled;
    if (isSoundEnabled) {
        soundIcon.textContent = "🔊";
        logToConsole("Sound notification alerts enabled.", "system");
    } else {
        soundIcon.textContent = "🔇";
        logToConsole("Sound notification alerts muted.", "system");
    }
});

// Camera and Mic toggles
btnToggleCam.addEventListener('click', () => {
    if (localStream) {
        const videoTrack = localStream.getVideoTracks()[0];
        if (videoTrack) {
            videoTrack.enabled = !videoTrack.enabled;
            btnToggleCam.classList.toggle('active', videoTrack.enabled);
            logToConsole(`Local camera turned ${videoTrack.enabled ? 'ON' : 'OFF'}.`, "system");
        }
    }
});

btnToggleMic.addEventListener('click', () => {
    if (localStream) {
        const audioTrack = localStream.getAudioTracks()[0];
        if (audioTrack) {
            audioTrack.enabled = !audioTrack.enabled;
            btnToggleMic.classList.toggle('active', audioTrack.enabled);
            logToConsole(`Local microphone turned ${audioTrack.enabled ? 'ON' : 'OFF'}.`, "system");
        }
    }
});

// Disconnect
btnDisconnect.addEventListener('click', () => {
    if (confirm("Disconnect from room?")) {
        window.location.reload();
    }
});

// Floating video overlay status update logic
function updateVideoOverlay(logMsg, alertActive) {
    const overlay = document.getElementById('video-overlay-log');
    const text = document.getElementById('video-overlay-text');
    const dot = document.getElementById('video-overlay-status-dot');
    if (!overlay || !text || !dot) return;

    if (alertActive) {
        overlay.className = "video-overlay-log alert-active";
        text.textContent = "🚨 VISIT ALARM: Person Present!";
        dot.style.boxShadow = "0 0 8px #ef4444";
        dot.style.backgroundColor = "#ef4444";
    } else if (logMsg && logMsg.includes("entered")) {
        overlay.className = "video-overlay-log detected";
        text.textContent = "👤 Visitor Detected";
        dot.style.boxShadow = "0 0 8px #f59e0b";
        dot.style.backgroundColor = "#f59e0b";
    } else if (logMsg && logMsg.includes("confirmed")) {
        overlay.className = "video-overlay-log detected";
        text.textContent = "👤 Occupant Tracking Active";
        dot.style.boxShadow = "0 0 8px #f59e0b";
        dot.style.backgroundColor = "#f59e0b";
    } else if (logMsg && logMsg.includes("departed")) {
        overlay.className = "video-overlay-log clear";
        text.textContent = "🟢 Service Window Clear";
        dot.style.boxShadow = "0 0 6px var(--color-primary)";
        dot.style.backgroundColor = "var(--color-primary)";
    }
}

// Toggle Sidebar
const btnToggleSidebar = document.getElementById('btn-toggle-sidebar');
const appSidebar = document.querySelector('.app-sidebar');
btnToggleSidebar.addEventListener('click', () => {
    appSidebar.classList.toggle('collapsed');
    const isCollapsed = appSidebar.classList.contains('collapsed');
    btnToggleSidebar.textContent = isCollapsed ? 'Show Console' : 'Hide Console';
});

// Toggle Detection Button
if (btnToggleDetection) {
    btnToggleDetection.addEventListener('click', () => {
        isDetectionEnabled = !isDetectionEnabled;
        btnToggleDetection.classList.toggle('active', isDetectionEnabled);
        
        if (isDetectionEnabled) {
            btnToggleDetection.textContent = "Detection: ON";
            logToConsole("YOLO Person Detection enabled.", "system");
            
            // Swap active layers
            localVideo.classList.remove('video-active');
            localVideo.classList.add('video-inactive');
            detectionFeed.classList.remove('video-inactive');
            detectionFeed.classList.add('video-active');
            
            startFrameTransmission();
        } else {
            btnToggleDetection.textContent = "Detection: OFF";
            logToConsole("YOLO Person Detection disabled.", "system");
            
            // Stop sending frames, swap active layers
            stopFrameTransmission();
            detectionFeed.classList.remove('video-active');
            detectionFeed.classList.add('video-inactive');
            localVideo.classList.remove('video-inactive');
            localVideo.classList.add('video-active');
            
            // Set floating overlay status to inactive/paused
            const overlay = document.getElementById('video-overlay-log');
            const text = document.getElementById('video-overlay-text');
            const dot = document.getElementById('video-overlay-status-dot');
            if (overlay && text && dot) {
                overlay.className = "video-overlay-log clear";
                text.textContent = "⚪ Person Detection Paused";
                dot.style.boxShadow = "none";
                dot.style.backgroundColor = "#9ca3af";
            }
        }
    });
}
