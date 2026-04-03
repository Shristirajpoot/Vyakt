document.addEventListener('DOMContentLoaded', () => {
    /* ----------------------------------------------------------------
       Feature Accordion Logic
       ---------------------------------------------------------------- */
    const featureItems = document.querySelectorAll('.feature-item');

    featureItems.forEach(item => {
        item.addEventListener('click', function(e) {
            // Did we click a video link? Don't toggle accordion
            if (e.target.tagName === 'A' || e.target.tagName === 'BUTTON' || e.target.closest('video') || e.target.closest('iframe')) {
                return;
            }

            // Toggle active class on clicked item
            this.classList.toggle('active');

            // Find content within this item
            const content = this.querySelector('.feature-content');
            if (content) {
                content.classList.toggle('active');
            }
            
            // Interaction: Pause other videos when opening a new one?
            // Optional: Close other feature items (Accordion behavior)
            // Uncomment below for strict accordion
            /*
            featureItems.forEach(otherItem => {
                if (otherItem !== item) {
                    otherItem.classList.remove('active');
                    const otherContent = otherItem.querySelector('.feature-content');
                    if (otherContent) otherContent.classList.remove('active');
                    // Pause videos in others
                    const video = otherItem.querySelector('video');
                    if(video) video.pause();
                }
            });
            */
            
            // Auto-play video on open (if strict gesture interaction is desired)
            if (this.classList.contains('active')) {
                const video = this.querySelector('video');
                if (video) {
                    video.play().catch(e => console.log('Autoplay prevented by browser'));
                }
            } else {
                const video = this.querySelector('video');
                if (video) video.pause();
            }
        });
    });

    /* ----------------------------------------------------------------
       API Key Passing (Safe usage)
       ---------------------------------------------------------------- */
    // window.googleTranslateApiKey was set in the HTML via script tag if needed,
    // or we can fetch it here if we attach it to a data attribute.
    // Ideally, keep sensitive keys out of client-side code unless public.
    // For now, retaining the placeholder logic.
});
