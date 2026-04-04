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

    const languageSelect = document.getElementById('languageSelect'); // 🌍 NEW

    let currentAudio = null;
    let lastSpoken = "";
    let stopInProgress = false;
    let mediaStream = null;
    let sending = false;
    let frameTimer = null;

    const MAX_UPLOAD_WIDTH = 512;
    const MAX_UPLOAD_HEIGHT = 384;
    const MIN_FRAME_DELAY_MS = 100;
    const MAX_FRAME_DELAY_MS = 300;
    const DEFAULT_FRAME_DELAY_MS = 140;

    function scheduleNextFrame(delayMs = DEFAULT_FRAME_DELAY_MS) {
        if (frameTimer) clearTimeout(frameTimer);
        frameTimer = setTimeout(sendFrame, Math.max(0, delayMs));
    }

    function hideLivePrediction() {
        predictedText.innerText = "";
        predictionConfidence.innerText = "";
    }

    // 🌍 MULTILINGUAL SPEAK
    function speakText(text) {
        const lang = languageSelect ? languageSelect.value : "en";

        fetch('/text_to_speech', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, lang })
        })
        .then(res => res.json())
        .then(data => {
            if (data.audio_url) {
                if (currentAudio) {
                    currentAudio.pause();
                    currentAudio.currentTime = 0;
                }
                currentAudio = new Audio(data.audio_url);
                currentAudio.play().catch(() => {});
            }
        })
        .catch(err => console.log("TTS error:", err));
    }

    async function sendFrame() {
        if (sending || !cameraVideo.videoWidth) return;
        sending = true;

        const startedAt = performance.now();

        try {
            const scale = Math.min(
                MAX_UPLOAD_WIDTH / cameraVideo.videoWidth,
                MAX_UPLOAD_HEIGHT / cameraVideo.videoHeight,
                1
            );

            const w = Math.round(cameraVideo.videoWidth * scale);
            const h = Math.round(cameraVideo.videoHeight * scale);

            cameraCanvas.width = w;
            cameraCanvas.height = h;

            const ctx = cameraCanvas.getContext('2d');
            ctx.drawImage(cameraVideo, 0, 0, w, h);

            const dataUrl = cameraCanvas.toDataURL('image/jpeg', 0.7);

            const res = await fetch('/process_frame', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: dataUrl }),
            });

            const data = await res.json();

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

            const elapsed = performance.now() - startedAt;
            const nextDelay = Math.min(
                MAX_FRAME_DELAY_MS,
                Math.max(MIN_FRAME_DELAY_MS, Math.round(elapsed * 1.2))
            );

            if (mediaStream) {
                scheduleNextFrame(nextDelay);
            }
        }
    }

    // 🎥 START CAMERA
    startCameraButton.addEventListener('click', async () => {

        try {
            await fetch('/reset_capture_state', { method: 'POST' });
            await fetch('/reset_frame_state', { method: 'POST' });
        } catch {}

        try {
            mediaStream = await navigator.mediaDevices.getUserMedia({
                video: true,
                audio: false
            });
        } catch (err) {
            alert("Camera error: " + err.message);
            return;
        }

        cameraVideo.srcObject = mediaStream;

        cameraFeedContainer.style.display = 'block';
        startCameraButton.style.display = 'none';
        closeCameraButton.style.display = 'inline-flex';
        startCapture.style.display = 'inline-flex';
        stopCapture.style.display = 'inline-flex';

        cameraVideo.onloadeddata = () => sendFrame();
    });

    // ❌ CLOSE CAMERA
    closeCameraButton.addEventListener('click', () => {

        if (frameTimer) clearTimeout(frameTimer);

        if (mediaStream) {
            mediaStream.getTracks().forEach(t => t.stop());
            mediaStream = null;
        }

        cameraVideo.srcObject = null;
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

    // ▶ START CAPTURE
    startCapture.addEventListener('click', async () => {
        await fetch('/start_capture', { method: 'POST' });

        finalText.innerText = "Capturing...";
        startCapture.classList.add("capturing");

        startCapture.disabled = true;
        stopCapture.disabled = false;
    });

    // ⏹ STOP CAPTURE
    stopCapture.addEventListener('click', async () => {

        if (stopInProgress) return;

        stopInProgress = true;
        stopCapture.disabled = true;

        const res = await fetch('/stop_capture', { method: 'POST' });
        const data = await res.json();

        if (data.words) {
            finalText.innerText = `Final: ${data.words}`;
            speakText(data.words);
        }

        startCapture.classList.remove("capturing");

        startCapture.disabled = false;
        stopCapture.disabled = true;
        stopInProgress = false;
    });

});