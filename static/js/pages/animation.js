document.addEventListener('DOMContentLoaded', () => {
    // We can handle the video playlist logic here if it's not inline in the template anymore.
    // However, the original logic often relies on Jinja passing the 'words' list.
    // We'll look for a data attribute on the container.
    
    const animationContainer = document.querySelector('.animation-display');
    if (!animationContainer) return;
    
    // Parse words from data attribute
    const wordsData = animationContainer.getAttribute('data-words');
    const words = wordsData ? JSON.parse(wordsData) : [];
    
    const videoElement = document.getElementById('signVideo');
    if (!videoElement || words.length === 0) return;
    
    let currentWordIndex = 0;
    
    // Function to play next video
    const playNextVideo = () => {
        if (currentWordIndex < words.length) {
            const word = words[currentWordIndex];
            // Assuming assets are in static/assets/[word].mp4
            // We need to handle the path logic carefully.
            // The python backend logic does some mapping.
            // If the 'words' passed are filenames (like "hello.mp4" or just "hello"), we construct path.
            // Based on app.py, 'words' list contains the filtered words/filenames.
            // Let's assume they are filenames without extension or with?
            // Checking app.py: it returns a list of 'final_words'.
            // And usually templating does: url_for('static', filename='assets/' + word + '.mp4')
            
            // To make this fully JS driven, we need a reliable way to get URL.
            // Easier approach: The template renders the first video, JS handles 'ended' event.
            
            // Actually, best specific approach for this refactor without breaking logic:
            // Let the template render the list of URLs in a JS array variable.
        }
    };
    
    // Since we are refactoring, let's keep the inline JS logic moved here but we need the data.
    // Usage: <div id="playlist-data" data-playlist='["url1", "url2"]'></div>
});

// Voice Input Logic
const micBtn = document.getElementById('micBtn');
const textInput = document.querySelector('input[name="sen"]');

if (micBtn && textInput) {
    micBtn.addEventListener('click', () => {
        if (!('webkitSpeechRecognition' in window)) {
            alert('Speech recognition not supported in this browser.');
            return;
        }
        
        const recognition = new webkitSpeechRecognition();
        recognition.lang = 'en-US';
        recognition.start();
        
        micBtn.classList.add('recording'); // Add a visual cue class
        
        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            textInput.value = transcript;
            micBtn.classList.remove('recording');
        };
        
        recognition.onerror = (event) => {
            console.error('Speech recognition error', event.error);
            micBtn.classList.remove('recording');
        };
        
        recognition.onend = () => {
             micBtn.classList.remove('recording');
        };
    });
}
