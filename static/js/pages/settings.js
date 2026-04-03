document.addEventListener('DOMContentLoaded', () => {
    // API KEY passed from backend
    // const apiKey = window.googleTranslateApiKey; // Defined in template block if needed

    const saveSettingsButtons = document.querySelectorAll('#saveSettingsBtn');
    const languageSelect = document.getElementById('languageSelect');
    const themeSelect = document.getElementById('themeSelect');
    const cameraSelect = document.getElementById('cameraSelect');
    
    // Elements to translate on page loaded
    const translatableElements = document.querySelectorAll('[data-translate]');

    // Load Settings
    const loadSettings = () => {
        const savedTheme = localStorage.getItem('theme');
        const savedLanguage = localStorage.getItem('language');
        const savedCameraQuality = localStorage.getItem('cameraQuality');

        if (savedTheme && themeSelect) {
            themeSelect.value = savedTheme;
            // Theme application is handled by main.js globally via data-theme
        }
        if (savedLanguage && languageSelect) {
            languageSelect.value = savedLanguage;
            translatePage(savedLanguage);
        }
        if (savedCameraQuality && cameraSelect) {
            cameraSelect.value = savedCameraQuality;
        }
    };

    // Save Settings
    const saveSettings = () => {
        const selectedLanguage = languageSelect ? languageSelect.value : 'en';
        const selectedTheme = themeSelect ? themeSelect.value : 'light';
        const cameraQuality = cameraSelect ? cameraSelect.value : '';

        // Update Global Theme
        document.documentElement.setAttribute('data-theme', selectedTheme);
        localStorage.setItem('theme', selectedTheme);
        localStorage.setItem('language', selectedLanguage);
        localStorage.setItem('cameraQuality', cameraQuality);

        // Notify user visibly or simple translation update
        translatePage(selectedLanguage);
    };

    // Event Listeners
    if (saveSettingsButtons.length > 0) {
        saveSettingsButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                // If this is a submit button, form submission might happen.
                // Depending on requirement, we can stop propagation if backend isn't used for settings.
                // Assuming backend IS used because of form POST in template.
                // We will just sync local storage here.
                saveSettings();
            });
        });
    }

    // Translation Logic (Placeholder reused from original code)
    async function translatePage(targetLanguage) {
        if (!window.googleTranslateApiKey) {
            // console.warn('GOOGLE_TRANSLATE_API_KEY is not set.');
            return; 
        }
        if (!targetLanguage || targetLanguage === 'en') return;

        const elementsToTranslate = Array.from(translatableElements).map(el => el.textContent);

        /* 
           NOTE: Real translation calls cost money/quota. 
           Should be careful calling this on every page load or save.
           For now, maintaining the existing logic structure.
        */
       
       /*
        const translations = await Promise.all(elementsToTranslate.map(text => {
            return fetch(...)
        }));
       */
    }

    // Initialize
    loadSettings();
});
