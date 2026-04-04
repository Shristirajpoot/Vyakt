document.addEventListener('DOMContentLoaded', () => {
    const startCameraButton = document.getElementById('startCameraButton');
    const closeCameraButton = document.getElementById('closeCameraButton');
    const cameraFeedContainer = document.getElementById('cameraFeedContainer');
    const cameraFeed = document.getElementById('cameraFeed');

    const predictedText = document.getElementById('predictedText');
    const predictionConfidence = document.getElementById('predictionConfidence');
    const finalText = document.getElementById('finalText');

    const startCapture = document.getElementById('startCapture');
    const stopCapture = document.getElementById('stopCapture');

    let predictionInterval;
    let currentAudio = null;
    let lastSpoken = "";

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

    startCameraButton.addEventListener('click', () => {
        const feedUrl = startCameraButton.getAttribute('data-feed-url');

        cameraFeedContainer.style.display = 'block';
        cameraFeed.src = feedUrl;

        startCameraButton.style.display = 'none';
        closeCameraButton.style.display = 'inline-flex';

        startCapture.style.display = 'inline-flex';
        stopCapture.style.display = 'inline-flex';

        predictionInterval = setInterval(async () => {
            try {
                const res = await fetch('/get_prediction');
                const data = await res.json();

                const text = (data.text || '').trim();
                const confidence = Number(data.confidence || 0);
                const state = data.state || 'idle';

                if (!text) {
                    hideLivePrediction();
                    return;
                }

                predictedText.innerText = `Live: ${text}`;
                predictionConfidence.innerText = `Confidence: ${Math.round(confidence * 100)}%`;

                if (state === 'predicted' && text !== lastSpoken) {
                    speakText(text);
                    lastSpoken = text;
                }
            } catch {
                hideLivePrediction();
            }
        }, 500);
    });

    closeCameraButton.addEventListener('click', () => {
        cameraFeed.src = '';
        cameraFeedContainer.style.display = 'none';

        startCameraButton.style.display = 'inline-flex';
        closeCameraButton.style.display = 'none';

        startCapture.style.display = 'none';
        stopCapture.style.display = 'none';

        clearInterval(predictionInterval);

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
    });
});
