/**
 * WebRTC Video Conference Client
 *
 * Implements a full mesh WebRTC architecture for multi-peer video conferencing.
 * Features:
 * - Support for 1v1 and group video sessions
 * - Dynamic peer connection management
 * - ICE candidate handling
 * - Audio/video track management
 * - Bandwidth optimization
 */

// ============================================================================
// Configuration
// ============================================================================

const CONFIG = {
    iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' },
        { urls: 'stun:stun2.l.google.com:19302' },
        { urls: 'stun:stun3.l.google.com:19302' },
        { urls: 'stun:stun4.l.google.com:19302' },
        // Add TURN servers here for production reliability
        // { 
        //     urls: 'turn:your-turn-server.com:3478', 
        //     username: 'username', 
        //     credential: 'password' 
        // },
    ],
    videoConstraints: {
        width: { ideal: 1280 },
        height: { ideal: 720 },
        frameRate: { ideal: 30, max: 60 }
    },
    audioConstraints: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
    }
};

// ============================================================================
// Global State
// ============================================================================

let localStream = null;
let socket = null;
let peerConnections = {}; // {userId: RTCPeerConnection}
let dataChannels = {}; // {userId: RTCDataChannel}
let remoteStreams = {}; // {userId: MediaStream}

let currentUser = {
    id: null,
    username: null,
};

let roomState = {
    roomId: null,
    sessionType: 'group',
    peers: [], // List of peer objects {userId, username}
    isAdmin: false,
};

// Statistics
let stats = {
    videoResolution: '1280x720',
    networkLatency: 0,
    packetsSent: 0,
    packetsReceived: 0,
};

// ============================================================================
// Initialization
// ============================================================================

/**
 * Initialize the video conference client
 */
async function initializeConference() {
    try {
        // Extract room details from page metadata
        const roomId = document.getElementById('roomId')?.textContent || 
                      new URLSearchParams(window.location.search).get('room_id') ||
                      'default-room';
        
        const userId = document.querySelector('[data-user-id]')?.dataset.userId ||
                      window.USER_ID || 1;
        
        const username = document.querySelector('[data-username]')?.dataset.username ||
                        window.USERNAME || 'Anonymous';

        currentUser.id = parseInt(userId);
        currentUser.username = username;
        roomState.roomId = roomId;
        roomState.isAdmin = window.IS_ADMIN || false;

        // Update UI
        document.getElementById('roomId').textContent = roomId;
        document.getElementById('userName').textContent = username;

        // Initialize Socket.IO connection
        await initializeSocket();

        // Get local media stream
        await getLocalStream();

        // Create local video element
        createLocalVideoElement();

        // Show main content
        document.getElementById('loadingBox').style.display = 'none';
        document.getElementById('mainContent').style.display = 'block';

        // Update connection status
        updateConnectionStatus('Connected');

        logger('Video conference initialized successfully');
    } catch (error) {
        showError(`Initialization failed: ${error.message}`);
        logger(`Initialization error: ${error}`, 'error');
    }
}

/**
 * Initialize Socket.IO connection
 */
function initializeSocket() {
    return new Promise((resolve, reject) => {
        try {
            const socketUrl = window.SOCKET_SERVER_URL || 'http://localhost:5000';

            socket = io(socketUrl, {
                reconnection: true,
                reconnectionDelay: 1000,
                reconnectionDelayMax: 5000,
                reconnectionAttempts: 5,
            });

            socket.on('connect', () => {
                logger(`Connected to signaling server: ${socket.id}`);
                updateConnectionStatus('Connected');

                // Join room
                socket.emit('join_room', {
                    user_id: currentUser.id,
                    room_id: roomState.roomId,
                    username: currentUser.username,
                    session_type: roomState.sessionType,
                });

                resolve();
            });

            socket.on('disconnect', () => {
                logger('Disconnected from signaling server', 'warning');
                updateConnectionStatus('Disconnected');
            });

            socket.on('error', (error) => {
                logger(`Socket error: ${error}`, 'error');
                showError(`Connection error: ${error}`);
            });

            socket.on('connection_response', (data) => {
                logger(`Server response: ${data.data}`);
            });

            // Handle authentication failures
            socket.on('auth_failed', (data) => {
                showError(`Authentication failed: ${data.message}`);
                logger(`Auth failed: ${data.message}`, 'error');
            });

            // Handle room events
            socket.on('room_joined', handleRoomJoined);
            socket.on('peer_joined', handlePeerJoined);
            socket.on('peer_disconnected', handlePeerDisconnected);
            socket.on('room_ended', handleRoomEnded);

            // Handle WebRTC signals
            socket.on('webrtc_signal', handleWebRTCSignal);
            socket.on('room_peers', handleRoomPeers);

            // Handle errors
            socket.on('signal_error', (data) => {
                logger(`Signal error: ${data.message}`, 'error');
            });

        } catch (error) {
            reject(error);
        }
    });
}

/**
 * Get local media stream (audio and video)
 */
async function getLocalStream() {
    try {
        // For admin monitoring mode, get media but disable tracks
        const constraints = {
            audio: CONFIG.audioConstraints,
            video: CONFIG.videoConstraints,
        };

        if (roomState.isAdmin) {
            logger('Admin mode: getting media stream (tracks will be disabled)');
        }

        localStream = await navigator.mediaDevices.getUserMedia(constraints);

        if (roomState.isAdmin) {
            // Disable all tracks for silent monitoring
            localStream.getTracks().forEach(track => {
                track.enabled = false;
            });
            logger('Admin monitoring: all local tracks disabled');
        }

        logger(`Local stream obtained: ${localStream.getTracks().length} tracks`);
        updateVideoResolution();

        return localStream;
    } catch (error) {
        throw new Error(`Failed to get local media: ${error.message}`);
    }
}

// ============================================================================
// Socket Event Handlers
// ============================================================================

/**
 * Handle room joined event
 */
function handleRoomJoined(data) {
    logger(`Room joined: ${data.room_id} with ${data.existing_peers.length} existing peers`);

    roomState.peers = data.existing_peers || [];
    updatePeerCount();

    // For each existing peer, initiate connection (as offerer)
    data.existing_peers.forEach(peer => {
        createPeerConnection(peer.user_id, peer.username, true);
    });
}

/**
 * Handle peer joined event
 */
function handlePeerJoined(data) {
    logger(`Peer joined: ${data.username} (ID: ${data.user_id})`);

    // Add to peers list
    if (!roomState.peers.find(p => p.user_id === data.user_id)) {
        roomState.peers.push({
            user_id: data.user_id,
            username: data.username
        });
    }

    updatePeerCount();

    // Create connection with new peer (as answerer)
    createPeerConnection(data.user_id, data.username, false);
}

/**
 * Handle peer disconnected event
 */
function handlePeerDisconnected(data) {
    logger(`Peer disconnected: ${data.username} (ID: ${data.user_id})`);

    // Remove from peers list
    roomState.peers = roomState.peers.filter(p => p.user_id !== data.user_id);
    updatePeerCount();

    // Close peer connection
    if (data.user_id in peerConnections) {
        peerConnections[data.user_id].close();
        delete peerConnections[data.user_id];
    }

    // Remove video element
    removeVideoElement(data.user_id);
}

/**
 * Handle room ended event
 */
function handleRoomEnded(data) {
    logger(`Room ended: ${data.message}`, 'warning');
    showError(`Room ended: ${data.message}`);

    // Close all connections
    Object.values(peerConnections).forEach(pc => pc.close());
    peerConnections = {};

    // Stop local stream
    if (localStream) {
        localStream.getTracks().forEach(track => track.stop());
    }

    // Redirect or show end screen
    setTimeout(() => {
        window.location.href = '/video/join/';
    }, 3000);
}

/**
 * Handle WebRTC signaling events
 */
function handleWebRTCSignal(data) {
    const { from_user_id, type, payload } = data;

    logger(`Received WebRTC signal: ${type} from user ${from_user_id}`);

    if (!(from_user_id in peerConnections)) {
        logger(`No peer connection for user ${from_user_id}, creating one...`);
        const peerInfo = roomState.peers.find(p => p.user_id === from_user_id);
        if (peerInfo) {
            createPeerConnection(from_user_id, peerInfo.username, false);
        } else {
            logger(`Peer ${from_user_id} not found in peers list`, 'error');
            return;
        }
    }

    const peerConnection = peerConnections[from_user_id];

    switch (type) {
        case 'offer':
            handleOffer(peerConnection, from_user_id, payload);
            break;
        case 'answer':
            handleAnswer(peerConnection, from_user_id, payload);
            break;
        case 'candidate':
            handleCandidate(peerConnection, from_user_id, payload);
            break;
        default:
            logger(`Unknown signal type: ${type}`, 'error');
    }
}

/**
 * Handle room peers list
 */
function handleRoomPeers(data) {
    logger(`Room peers: ${data.peers.length} peers in room`);
    // Can be used to sync state if needed
}

// ============================================================================
// Peer Connection Management
// ============================================================================

/**
 * Create a new RTCPeerConnection for a peer
 */
function createPeerConnection(peerId, peerUsername, shouldCreateOffer) {
    logger(`Creating peer connection with user ${peerUsername} (ID: ${peerId}), shouldCreateOffer: ${shouldCreateOffer}`);

    if (peerId in peerConnections) {
        logger(`Peer connection already exists for ${peerId}`);
        return peerConnections[peerId];
    }

    const peerConnection = new RTCPeerConnection({
        iceServers: CONFIG.iceServers
    });

    // Add local stream tracks
    localStream.getTracks().forEach(track => {
        peerConnection.addTrack(track, localStream);
    });

    // Handle remote stream
    peerConnection.ontrack = (event) => {
        logger(`Received remote track from ${peerId}: ${event.track.kind}`);

        if (!remoteStreams[peerId]) {
            remoteStreams[peerId] = new MediaStream();
            createRemoteVideoElement(peerId, peerUsername, remoteStreams[peerId]);
        }

        remoteStreams[peerId].addTrack(event.track);
    };

    // Handle ICE candidates
    peerConnection.onicecandidate = (event) => {
        if (event.candidate) {
            logger(`ICE candidate generated for ${peerId}`);

            socket.emit('webrtc_signal', {
                from_user_id: currentUser.id,
                to_user_id: peerId,
                room_id: roomState.roomId,
                type: 'candidate',
                payload: event.candidate
            });
        }
    };

    // Handle connection state changes
    peerConnection.onconnectionstatechange = () => {
        logger(`Connection state change for ${peerId}: ${peerConnection.connectionState}`);

        if (peerConnection.connectionState === 'disconnected' ||
            peerConnection.connectionState === 'failed' ||
            peerConnection.connectionState === 'closed') {
            logger(`Connection lost with ${peerId}`, 'warning');
            handlePeerDisconnected({
                user_id: peerId,
                username: peerUsername
            });
        }
    };

    // Handle ICE connection state changes
    peerConnection.oniceconnectionstatechange = () => {
        logger(`ICE connection state change for ${peerId}: ${peerConnection.iceConnectionState}`);
    };

    peerConnection.onsignalingstatechange = () => {
        logger(`Signaling state change for ${peerId}: ${peerConnection.signalingState}`);
    };

    // Store connection
    peerConnections[peerId] = peerConnection;

    // Create offer if needed
    if (shouldCreateOffer) {
        createOffer(peerId, peerConnection);
    }

    return peerConnection;
}

/**
 * Create and send an offer to a peer
 */
async function createOffer(peerId, peerConnection) {
    try {
        logger(`Creating offer for peer ${peerId}`);

        const offer = await peerConnection.createOffer({
            offerToReceiveAudio: true,
            offerToReceiveVideo: true,
        });

        await peerConnection.setLocalDescription(offer);
        logger(`Offer created and set as local description for ${peerId}`);

        socket.emit('webrtc_signal', {
            from_user_id: currentUser.id,
            to_user_id: peerId,
            room_id: roomState.roomId,
            type: 'offer',
            payload: offer
        });
    } catch (error) {
        logger(`Error creating offer for ${peerId}: ${error}`, 'error');
    }
}

/**
 * Handle received offer
 */
async function handleOffer(peerConnection, peerId, offer) {
    try {
        logger(`Handling offer from ${peerId}`);

        await peerConnection.setRemoteDescription(new RTCSessionDescription(offer));
        logger(`Remote description (offer) set for ${peerId}`);

        const answer = await peerConnection.createAnswer();
        await peerConnection.setLocalDescription(answer);
        logger(`Answer created and set as local description for ${peerId}`);

        socket.emit('webrtc_signal', {
            from_user_id: currentUser.id,
            to_user_id: peerId,
            room_id: roomState.roomId,
            type: 'answer',
            payload: answer
        });
    } catch (error) {
        logger(`Error handling offer from ${peerId}: ${error}`, 'error');
    }
}

/**
 * Handle received answer
 */
async function handleAnswer(peerConnection, peerId, answer) {
    try {
        logger(`Handling answer from ${peerId}`);
        await peerConnection.setRemoteDescription(new RTCSessionDescription(answer));
        logger(`Remote description (answer) set for ${peerId}`);
    } catch (error) {
        logger(`Error handling answer from ${peerId}: ${error}`, 'error');
    }
}

/**
 * Handle received ICE candidate
 */
async function handleCandidate(peerConnection, peerId, candidate) {
    try {
        if (candidate.candidate) {
            await peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
            logger(`ICE candidate added for ${peerId}`);
        }
    } catch (error) {
        logger(`Error adding ICE candidate from ${peerId}: ${error}`, 'error');
    }
}

// ============================================================================
// Video Element Management
// ============================================================================

/**
 * Create and display local video element
 */
function createLocalVideoElement() {
    const videoGrid = document.getElementById('videoGrid');
    const videoWrapper = document.createElement('div');
    videoWrapper.className = 'video-wrapper local-video';
    videoWrapper.id = `video-local`;

    const video = document.createElement('video');
    video.id = 'localVideo';
    video.autoplay = true;
    video.muted = true;
    video.playsInline = true;

    const label = document.createElement('div');
    label.className = 'video-label';
    label.innerHTML = `<div class="status-badge"></div><span>${currentUser.username} (You)</span>`;

    videoWrapper.appendChild(video);
    videoWrapper.appendChild(label);
    videoGrid.appendChild(videoWrapper);

    video.srcObject = localStream;
    logger('Local video element created');
}

/**
 * Create and display remote video element
 */
function createRemoteVideoElement(peerId, peerUsername, mediaStream) {
    const videoGrid = document.getElementById('videoGrid');

    // Check if element already exists
    if (document.getElementById(`video-${peerId}`)) {
        return;
    }

    const videoWrapper = document.createElement('div');
    videoWrapper.className = 'video-wrapper remote-video';
    videoWrapper.id = `video-${peerId}`;

    const video = document.createElement('video');
    video.id = `remoteVideo-${peerId}`;
    video.autoplay = true;
    video.playsInline = true;

    const label = document.createElement('div');
    label.className = 'video-label';
    label.innerHTML = `<div class="status-badge"></div><span>${peerUsername}</span>`;

    videoWrapper.appendChild(video);
    videoWrapper.appendChild(label);
    videoGrid.appendChild(videoWrapper);

    video.srcObject = mediaStream;
    logger(`Remote video element created for ${peerUsername}`);
}

/**
 * Remove a video element
 */
function removeVideoElement(peerId) {
    const element = document.getElementById(`video-${peerId}`);
    if (element) {
        element.remove();
        logger(`Video element removed for peer ${peerId}`);
    }

    if (remoteStreams[peerId]) {
        remoteStreams[peerId].getTracks().forEach(track => track.stop());
        delete remoteStreams[peerId];
    }
}

// ============================================================================
// Control Functions
// ============================================================================

/**
 * Toggle microphone
 */
function toggleMicrophone() {
    if (!localStream) return;

    const audioTracks = localStream.getAudioTracks();
    const isEnabled = audioTracks[0]?.enabled || false;

    audioTracks.forEach(track => {
        track.enabled = !isEnabled;
    });

    const btn = document.getElementById('micToggle');
    btn.classList.toggle('active');
    btn.innerHTML = isEnabled ? '🎤 Microphone' : '🔇 Microphone (Off)';

    logger(`Microphone ${isEnabled ? 'disabled' : 'enabled'}`);
}

/**
 * Toggle camera
 */
function toggleCamera() {
    if (!localStream) return;

    const videoTracks = localStream.getVideoTracks();
    const isEnabled = videoTracks[0]?.enabled || false;

    videoTracks.forEach(track => {
        track.enabled = !isEnabled;
    });

    const btn = document.getElementById('videoToggle');
    btn.classList.toggle('active');
    btn.innerHTML = isEnabled ? '📷 Camera' : '📷 Camera (Off)';

    logger(`Camera ${isEnabled ? 'disabled' : 'enabled'}`);
}

/**
 * Change video resolution
 */
async function changeResolution() {
    // Cycle through resolutions
    const resolutions = [
        { width: 1280, height: 720 },
        { width: 640, height: 480 },
        { width: 1920, height: 1080 },
    ];

    try {
        // Stop current stream
        localStream.getTracks().forEach(track => track.stop());

        // Rotate to next resolution
        const currentResIdx = resolutions.findIndex(r =>
            r.width === parseInt(stats.videoResolution.split('x')[0])
        );
        const nextResIdx = (currentResIdx + 1) % resolutions.length;
        const newResolution = resolutions[nextResIdx];

        // Get new stream
        const constraints = {
            audio: CONFIG.audioConstraints,
            video: {
                ...newResolution,
                frameRate: { ideal: 30, max: 60 }
            },
        };

        localStream = await navigator.mediaDevices.getUserMedia(constraints);

        // Disable tracks if admin
        if (roomState.isAdmin) {
            localStream.getTracks().forEach(track => {
                track.enabled = false;
            });
        }

        // Update all peer connections with new tracks
        localStream.getVideoTracks().forEach(track => {
            Object.values(peerConnections).forEach(pc => {
                const sender = pc.getSenders().find(s => s.track?.kind === 'video');
                if (sender) {
                    sender.replaceTrack(track);
                }
            });
        });

        const localVideo = document.getElementById('localVideo');
        if (localVideo) {
            localVideo.srcObject = localStream;
        }

        updateVideoResolution();
        logger(`Resolution changed to ${newResolution.width}x${newResolution.height}`);
    } catch (error) {
        logger(`Error changing resolution: ${error}`, 'error');
        showError(`Failed to change resolution: ${error.message}`);
    }
}

/**
 * End the call
 */
function endCall() {
    if (confirm('Are you sure you want to end this call?')) {
        // Emit end_room event if user is initiator
        socket.emit('end_room', {
            room_id: roomState.roomId,
            initiator_user_id: currentUser.id
        });

        // Close all connections
        Object.values(peerConnections).forEach(pc => pc.close());
        peerConnections = {};

        // Stop local stream
        if (localStream) {
            localStream.getTracks().forEach(track => track.stop());
        }

        // Redirect
        window.location.href = '/video/join/';
    }
}

// ============================================================================
// Statistics and Monitoring
// ============================================================================

/**
 * Update video resolution display
 */
async function updateVideoResolution() {
    try {
        const videoTracks = localStream?.getVideoTracks();
        if (videoTracks && videoTracks.length > 0) {
            const settings = videoTracks[0].getSettings();
            stats.videoResolution = `${settings.width}x${settings.height}`;
            document.getElementById('videoResolution').textContent = stats.videoResolution;
        }
    } catch (error) {
        logger(`Error updating resolution: ${error}`, 'error');
    }
}

/**
 * Update peer count
 */
function updatePeerCount() {
    document.getElementById('peerCount').textContent = roomState.peers.length;
}

/**
 * Update connection status
 */
function updateConnectionStatus(status) {
    document.getElementById('connectionStatus').textContent = status;
}

/**
 * Monitor connection stats
 */
async function monitorStats() {
    setInterval(async () => {
        try {
            for (const [peerId, pc] of Object.entries(peerConnections)) {
                const stats = await pc.getStats();
                stats.forEach(report => {
                    if (report.type === 'inbound-rtp' && report.kind === 'video') {
                        // Update network latency
                        if (report.jitter !== undefined) {
                            stats.networkLatency = Math.round(report.jitter * 1000);
                            document.getElementById('networkLatency').textContent =
                                `${stats.networkLatency}ms`;
                        }
                    }
                });
            }
        } catch (error) {
            // Stats monitoring error - non-critical
        }
    }, 5000);
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Show error message
 */
function showError(message) {
    const errorBox = document.getElementById('errorBox');
    errorBox.textContent = message;
    errorBox.classList.add('show');

    setTimeout(() => {
        errorBox.classList.remove('show');
    }, 5000);
}

/**
 * Logger function
 */
function logger(message, level = 'info') {
    const timestamp = new Date().toLocaleTimeString();
    const prefix = `[${timestamp}] [${level.toUpperCase()}]`;

    switch (level) {
        case 'error':
            console.error(`${prefix} ${message}`);
            break;
        case 'warning':
            console.warn(`${prefix} ${message}`);
            break;
        case 'info':
        default:
            console.log(`${prefix} ${message}`);
    }
}

// ============================================================================
// Page Load
// ============================================================================

document.addEventListener('DOMContentLoaded', async () => {
    // Initialize conference
    await initializeConference();

    // Start monitoring stats
    monitorStats();

    logger('Page loaded and ready');
});

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    // Close all peer connections
    Object.values(peerConnections).forEach(pc => pc.close());

    // Stop local stream
    if (localStream) {
        localStream.getTracks().forEach(track => track.stop());
    }

    // Disconnect socket
    if (socket) {
        socket.disconnect();
    }
});
