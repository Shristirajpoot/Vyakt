document.addEventListener('DOMContentLoaded', () => {
    const startCameraButton = document.getElementById('startCameraButton');
    const closeCameraButton = document.getElementById('closeCameraButton');
    const cameraFeedContainer = document.getElementById('cameraFeedContainer');
    const cameraFeed = document.getElementById('cameraFeed');
    
    // URL passed from template to global or data attribute
    // const videoFeedUrl = ... (handled via data attribute on button)
    
    if (startCameraButton) {
        startCameraButton.addEventListener('click', () => {
            const feedUrl = startCameraButton.getAttribute('data-feed-url');
            
            if (cameraFeedContainer) cameraFeedContainer.style.display = 'block';
            if (cameraFeed) cameraFeed.src = feedUrl;
            
            startCameraButton.style.display = 'none';
            if (closeCameraButton) closeCameraButton.style.display = 'inline-flex';
            
            // Scroll to camera
            cameraFeedContainer.scrollIntoView({behavior: "smooth"});
        });
    }

    if (closeCameraButton) {
        closeCameraButton.addEventListener('click', () => {
            if (cameraFeedContainer) cameraFeedContainer.style.display = 'none';
            if (cameraFeed) cameraFeed.src = ""; // Stop feed
            
            closeCameraButton.style.display = 'none';
            if (startCameraButton) startCameraButton.style.display = 'inline-flex';
        });
    }
});
