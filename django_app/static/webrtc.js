const CONFIG = {
    iceServers: [
        { urls: ['stun:stun.l.google.com:19302'] },
        { urls: ['stun:stun1.l.google.com:19302'] },
        { urls: ['stun:stun2.l.google.com:19302'] },
        { urls: ['stun:stun3.l.google.com:19302'] },
        { urls: ['stun:stun4.l.google.com:19302'] },
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

let localStream = null;
let socket = null;
let peerConnections = {};
let dataChannels = {};
let remoteStreams = {};

let currentUser = {
    id: null,
    username: null,
};

let roomState = {
    roomId: null,
    sessionType: 'group',
    peers: [],
    isAdmin: false,
};

let stats = {
    videoResolution: '1280x720',
    networkLatency: 0,
    packetsSent: 0,
    packetsReceived: 0,
};

async function initializeConference() {
    try {
        const roomId = document.getElementById('roomId')?.textContent ||
                      new URLSearchParams(window.location.search).get('room_id') ||
                      'default-room';

        const userId = window.USER_ID || 1;
        const username = window.USERNAME || 'Anonymous';

        currentUser.id = parseInt(userId);
        currentUser.username = username;
        roomState.roomId = roomId;
        roomState.isAdmin = window.IS_ADMIN || false;
        roomState.sessionType = window.ROOM_SESSION_TYPE || 'group';

        document.getElementById('roomId').textContent = roomId;
        document.getElementById('userName').textContent = username;

        await initializeSocket();
        await getLocalStream();
        createLocalVideoElement();

        document.getElementById('loadingBox').style.display = 'none';
        document.getElementById('mainContent').style.display = 'block';

        updateConnectionStatus('Connected');

        // Show "Next" button for random match rooms
        const nextBtn = document.getElementById('nextMatchBtn');
        if (nextBtn && roomId && roomId.startsWith && roomId.startsWith('1v1-')) {
            nextBtn.style.display = 'inline-flex';
        }

        logger('Video conference initialized successfully');
    } catch (error) {
        showError(`Initialization failed: ${error.message}`);
        logger(`Initialization error: ${error}`, 'error');
    }
}

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

            socket.on('auth_failed', (data) => {
                showError(`Authentication failed: ${data.message}`);
                logger(`Auth failed: ${data.message}`, 'error');
            });

            socket.on('room_joined', handleRoomJoined);
            socket.on('peer_joined', handlePeerJoined);
            socket.on('peer_disconnected', handlePeerDisconnected);
            socket.on('room_ended', handleRoomEnded);

            socket.on('webrtc_signal', handleWebRTCSignal);
            socket.on('room_peers', handleRoomPeers);

            socket.on('signal_error', (data) => {
                logger(`Signal error: ${data.message}`, 'error');
            });

        } catch (error) {
            reject(error);
        }
    });
}

async function getLocalStream() {
    try {
        const constraints = {
            audio: CONFIG.audioConstraints,
            video: CONFIG.videoConstraints,
        };

        if (roomState.isAdmin) {
            logger('Admin mode: getting media stream (tracks will be disabled)');
        }

        localStream = await navigator.mediaDevices.getUserMedia(constraints);

        if (roomState.isAdmin) {
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

function handleRoomJoined(data) {
    logger(`Room joined: ${data.room_id} with ${data.existing_peers.length} existing peers`);

    roomState.peers = data.existing_peers || [];
    updatePeerCount();

    data.existing_peers.forEach(peer => {
        createPeerConnection(peer.user_id, peer.username, true);
    });
}

function handlePeerJoined(data) {
    logger(`Peer joined: ${data.username} (ID: ${data.user_id})`);

    if (!roomState.peers.find(p => p.user_id === data.user_id)) {
        roomState.peers.push({
            user_id: data.user_id,
            username: data.username
        });
    }

    updatePeerCount();
    createPeerConnection(data.user_id, data.username, false);
}

function handlePeerDisconnected(data) {
    logger(`Peer disconnected: ${data.username} (ID: ${data.user_id})`);

    roomState.peers = roomState.peers.filter(p => p.user_id !== data.user_id);
    updatePeerCount();

    if (data.user_id in peerConnections) {
        peerConnections[data.user_id].close();
        delete peerConnections[data.user_id];
    }

    removeVideoElement(data.user_id);
}

function handleRoomEnded(data) {
    logger(`Room ended: ${data.message}`, 'warning');
    showError(`Room ended: ${data.message}`);

    Object.values(peerConnections).forEach(pc => pc.close());
    peerConnections = {};

    if (localStream) {
        localStream.getTracks().forEach(track => track.stop());
    }

    setTimeout(() => {
        window.location.href = '/video/join/';
    }, 3000);
}

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

function handleRoomPeers(data) {
    logger(`Room peers: ${data.peers.length} peers in room`);
}

function createPeerConnection(peerId, peerUsername, shouldCreateOffer) {
    logger(`Creating peer connection with user ${peerUsername} (ID: ${peerId}), shouldCreateOffer: ${shouldCreateOffer}`);

    if (peerId in peerConnections) {
        logger(`Peer connection already exists for ${peerId}`);
        return peerConnections[peerId];
    }

    const peerConnection = new RTCPeerConnection({
        iceServers: CONFIG.iceServers
    });

    localStream.getTracks().forEach(track => {
        peerConnection.addTrack(track, localStream);
    });

    peerConnection.ontrack = (event) => {
        logger(`Received remote track from ${peerId}: ${event.track.kind}`);

        if (!remoteStreams[peerId]) {
            remoteStreams[peerId] = new MediaStream();
            createRemoteVideoElement(peerId, peerUsername, remoteStreams[peerId]);
        }

        remoteStreams[peerId].addTrack(event.track);
    };

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

    peerConnection.oniceconnectionstatechange = () => {
        logger(`ICE connection state change for ${peerId}: ${peerConnection.iceConnectionState}`);
    };

    peerConnection.onsignalingstatechange = () => {
        logger(`Signaling state change for ${peerId}: ${peerConnection.signalingState}`);
    };

    peerConnections[peerId] = peerConnection;

    if (shouldCreateOffer) {
        createOffer(peerId, peerConnection);
    }

    return peerConnection;
}

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

async function handleAnswer(peerConnection, peerId, answer) {
    try {
        logger(`Handling answer from ${peerId}`);
        await peerConnection.setRemoteDescription(new RTCSessionDescription(answer));
        logger(`Remote description (answer) set for ${peerId}`);
    } catch (error) {
        logger(`Error handling answer from ${peerId}: ${error}`, 'error');
    }
}

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

function createRemoteVideoElement(peerId, peerUsername, mediaStream) {
    const videoGrid = document.getElementById('videoGrid');

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

function toggleMicrophone() {
    if (!localStream) return;

    const audioTracks = localStream.getAudioTracks();
    const isEnabled = audioTracks[0]?.enabled || false;

    audioTracks.forEach(track => {
        track.enabled = !isEnabled;
    });

    const btn = document.getElementById('micToggle');
    btn.classList.toggle('active');
    btn.innerHTML = isEnabled ? 'Microphone' : 'Microphone (Off)';

    logger(`Microphone ${isEnabled ? 'disabled' : 'enabled'}`);
}

function toggleCamera() {
    if (!localStream) return;

    const videoTracks = localStream.getVideoTracks();
    const isEnabled = videoTracks[0]?.enabled || false;

    videoTracks.forEach(track => {
        track.enabled = !isEnabled;
    });

    const btn = document.getElementById('videoToggle');
    btn.classList.toggle('active');
    btn.innerHTML = isEnabled ? 'Camera' : 'Camera (Off)';

    logger(`Camera ${isEnabled ? 'disabled' : 'enabled'}`);
}

async function changeResolution() {
    const resolutions = [
        { width: 1280, height: 720 },
        { width: 640, height: 480 },
        { width: 1920, height: 1080 },
    ];

    try {
        localStream.getTracks().forEach(track => track.stop());

        const currentResIdx = resolutions.findIndex(r =>
            r.width === parseInt(stats.videoResolution.split('x')[0])
        );
        const nextResIdx = (currentResIdx + 1) % resolutions.length;
        const newResolution = resolutions[nextResIdx];

        const constraints = {
            audio: CONFIG.audioConstraints,
            video: {
                ...newResolution,
                frameRate: { ideal: 30, max: 60 }
            },
        };

        localStream = await navigator.mediaDevices.getUserMedia(constraints);

        if (roomState.isAdmin) {
            localStream.getTracks().forEach(track => {
                track.enabled = false;
            });
        }

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

function endCall() {
    if (confirm('Are you sure you want to end this call?')) {
        socket.emit('end_room', {
            room_id: roomState.roomId,
            initiator_user_id: currentUser.id
        });

        Object.values(peerConnections).forEach(pc => pc.close());
        peerConnections = {};

        if (localStream) {
            localStream.getTracks().forEach(track => track.stop());
        }

        window.location.href = '/video/join/';
    }
}

function nextMatch() {
    if (confirm('Find a new match?')) {
        // Clean up current connection
        Object.values(peerConnections).forEach(pc => pc.close());
        peerConnections = {};
        if (localStream) {
            localStream.getTracks().forEach(track => track.stop());
        }
        // Go to random match page to find next
        window.location.href = '/video/random-match/';
    }
}

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

function updatePeerCount() {
    document.getElementById('peerCount').textContent = roomState.peers.length;
}

function updateConnectionStatus(status) {
    document.getElementById('connectionStatus').textContent = status;
}

async function monitorStats() {
    setInterval(async () => {
        try {
            for (const [peerId, pc] of Object.entries(peerConnections)) {
                const stats = await pc.getStats();
                stats.forEach(report => {
                    if (report.type === 'inbound-rtp' && report.kind === 'video') {
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

function showError(message) {
    const errorBox = document.getElementById('errorBox');
    errorBox.textContent = message;
    errorBox.classList.add('show');

    setTimeout(() => {
        errorBox.classList.remove('show');
    }, 5000);
}

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

document.addEventListener('DOMContentLoaded', async () => {
    await initializeConference();
    monitorStats();
    logger('Page loaded and ready');
});

window.addEventListener('beforeunload', () => {
    Object.values(peerConnections).forEach(pc => pc.close());

    if (localStream) {
        localStream.getTracks().forEach(track => track.stop());
    }

    if (socket) {
        socket.disconnect();
    }
});
