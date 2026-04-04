document.addEventListener('DOMContentLoaded', () => {
    const startCameraButton = document.getElementById('startCameraButton');
    const closeCameraButton = document.getElementById('closeCameraButton');
    const cameraFeedContainer = document.getElementById('cameraFeedContainer');
    const cameraVideo = document.getElementById('cameraVideo');
    const cameraCanvas = document.getElementById('cameraCanvas');
    const annotatedFeed = document.getElementById('annotatedFeed');

    const predictedText = document.getElementById('predictedText');
    const predictionConfidence = document.getElementById('predictionConfidence');
    const finalText = document.getElementById('finalText');

    const startCapture = document.getElementById('startCapture');
    const stopCapture = document.getElementById('stopCapture');

    let frameInterval = null;
    let currentAudio = null;
    let lastSpoken = "";
    let stopInProgress = false;
    let mediaStream = null;
    let sending = false;

    function hideLivePrediction() {
        predictedText.innerText = "";
        predictionConfidence.innerText = "";
    }

    function speakText(text) {
        fetch('/text_to_speech', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text }),
        })
            .then((res) => res.json())
            .then((data) => {
                if (data.audio_url) {
                    if (currentAudio) {
                        currentAudio.pause();
                        currentAudio.currentTime = 0;
                    }
                    currentAudio = new Audio(data.audio_url);
                    currentAudio.play();
                }
            })
            .catch(() => {});
    }

    async function sendFrame() {
        if (sending || !cameraVideo.videoWidth) return;
        sending = true;

        try {
            cameraCanvas.width = cameraVideo.videoWidth;
            cameraCanvas.height = cameraVideo.videoHeight;
            const ctx = cameraCanvas.getContext('2d');
            ctx.drawImage(cameraVideo, 0, 0);
            const dataUrl = cameraCanvas.toDataURL('image/jpeg', 0.7);

            const res = await fetch('/process_frame', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: dataUrl }),
            });
            const data = await res.json();

            // Show annotated frame with landmarks
            if (data.annotated_frame) {
                annotatedFeed.src = data.annotated_frame;
                annotatedFeed.style.display = 'block';
            }

            const text = (data.text || '').trim();
            const confidence = Number(data.confidence || 0);
            const state = data.state || 'idle';

            if (!text) {
                hideLivePrediction();
            } else {
                predictedText.innerText = `Live: ${text}`;
                predictionConfidence.innerText = `Confidence: ${Math.round(confidence * 100)}%`;

                if (state === 'predicted' && text !== lastSpoken) {
                    speakText(text);
                    lastSpoken = text;
                }
            }
        } catch {
            hideLivePrediction();
        } finally {
            sending = false;
        }
    }

    startCameraButton.addEventListener('click', async () => {
        try {
            await fetch('/reset_capture_state', { method: 'POST' });
            await fetch('/reset_frame_state', { method: 'POST' });
        } catch {}

        try {
            mediaStream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
                audio: false,
            });
        } catch (err) {
            alert('Camera permission denied or not available: ' + err.message);
            return;
        }

        cameraVideo.srcObject = mediaStream;
        cameraFeedContainer.style.display = 'block';
        finalText.innerText = '';

        startCameraButton.style.display = 'none';
        closeCameraButton.style.display = 'inline-flex';
        startCapture.style.display = 'inline-flex';
        stopCapture.style.display = 'inline-flex';

        // Wait for video to actually start playing before sending frames
        cameraVideo.onloadeddata = () => {
            frameInterval = setInterval(sendFrame, 200);
        };
    });

    closeCameraButton.addEventListener('click', () => {
        if (frameInterval) {
            clearInterval(frameInterval);
            frameInterval = null;
        }

        if (mediaStream) {
            mediaStream.getTracks().forEach(track => track.stop());
            mediaStream = null;
        }
        cameraVideo.srcObject = null;
        annotatedFeed.src = '';
        annotatedFeed.style.display = 'none';
        cameraFeedContainer.style.display = 'none';

        startCameraButton.style.display = 'inline-flex';
        closeCameraButton.style.display = 'none';
        startCapture.style.display = 'none';
        stopCapture.style.display = 'none';

        if (currentAudio) {
            currentAudio.pause();
            currentAudio.currentTime = 0;
        }

        hideLivePrediction();
        finalText.innerText = '';
        lastSpoken = '';
    });

    startCapture.addEventListener('click', async () => {
        await fetch('/start_capture', { method: 'POST' });

        finalText.innerText = 'Capturing...';
        startCapture.classList.add('capturing');

        startCapture.disabled = true;
        stopCapture.disabled = false;
    });

    stopCapture.addEventListener('click', async () => {
        if (stopInProgress) {
            return;
        }
        stopInProgress = true;
        stopCapture.disabled = true;

        const res = await fetch('/stop_capture', { method: 'POST' });
        const data = await res.json();

        if (data.words && data.words.trim() !== '') {
            finalText.innerText = `Final: ${data.words}`;
            speakText(data.words);
        } else {
            finalText.innerText = '';
        }

        startCapture.classList.remove('capturing');

        startCapture.disabled = false;
        stopCapture.disabled = true;
        stopInProgress = false;
    });
});
