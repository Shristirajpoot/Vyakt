document.addEventListener("DOMContentLoaded", () => {

  const micBtn = document.getElementById("micBtn");
  const textInput = document.querySelector('input[name="sen"]');
  const languageSelect = document.getElementById("languageSelect");

  const videoPlayer = document.getElementById("signVideo");
  const currentWordDisplay = document.getElementById("currentWordDisplay");
  const finalSentenceEl = document.getElementById("finalSentence");

  let mediaRecorder;
  let audioChunks = [];
  let currentAudio = null;
  let fullSentenceSpoken = false;

// reset on page load
fullSentenceSpoken = false;

  // =========================
  // 🌍 LANGUAGE SAVE
  // =========================
  if (languageSelect) {
    const savedLang = localStorage.getItem("lang");
    if (savedLang) languageSelect.value = savedLang;

    languageSelect.addEventListener("change", () => {
      localStorage.setItem("lang", languageSelect.value);
    });
  }

  // =========================
  // 🎤 MIC INPUT
  // =========================
  if (micBtn && textInput) {
    micBtn.addEventListener("click", async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = e => audioChunks.push(e.data);

        mediaRecorder.onstop = async () => {
          const audioBlob = new Blob(audioChunks, { type: "audio/webm" });

          const formData = new FormData();
          formData.append("audio", audioBlob, "speech.webm");

          const lang = languageSelect ? languageSelect.value : "en";
          formData.append("lang", lang);

          const res = await fetch("/speech_to_text", {
            method: "POST",
            body: formData
          });

          const data = await res.json();
          if (data.text) textInput.value = data.text;
        };

        mediaRecorder.start();
        micBtn.innerText = "⏹️ Recording...";

        setTimeout(() => {
          mediaRecorder.stop();
          micBtn.innerText = "🎤";
        }, 3000);

      } catch {
        alert("Mic error");
      }
    });
  }

  // =========================
  // 🔊 FINAL SENTENCE VOICE
  // =========================
  function speakFinal(sentence) {

    if (!sentence || fullSentenceSpoken) return;

    fullSentenceSpoken = true;

    const lang = languageSelect ? languageSelect.value : "en";

    fetch("/text_to_speech", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        text: sentence,
        lang: lang
      })
    })
    .then(res => res.json())
    .then(data => {
      if (data.audio_url) {

        if (currentAudio) {
          currentAudio.pause();
          currentAudio.currentTime = 0;
        }

        currentAudio = new Audio(data.audio_url);
        currentAudio.play();
      }
    });
  }

  // =========================
  // 🎬 VIDEO PLAY
  // =========================
  if (videoPlayer) {

    const playlist = [];

    document.querySelectorAll(".word-badge").forEach(el => {
      const word = el.innerText.trim();
      playlist.push({
        word: word,
        url: `/static/assets/${word}.mp4`
      });
    });

    let index = 0;

    function playNext() {

      if (index < playlist.length) {

        const item = playlist[index];

        videoPlayer.src = item.url;
        currentWordDisplay.textContent = `Signing: "${item.word}"`;

        videoPlayer.play().catch(() => {});
        index++;

      } else {
        // ✅ After full animation → speak sentence
        if (finalSentenceEl) {
          const sentence = finalSentenceEl.innerText.trim();
          speakFinal(sentence);
        }
      }
    }

    videoPlayer.addEventListener("ended", playNext);
    videoPlayer.addEventListener("error", playNext);

    if (playlist.length > 0) playNext();
  }

});