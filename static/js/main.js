document.addEventListener('DOMContentLoaded', () => {
    /* ----------------------------------------------------------------
       1. Theme Toggle Logic
       ---------------------------------------------------------------- */
    const themeToggleBtn = document.getElementById('theme-toggle');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)');
    
    // Load saved theme or specific default (light preference per user request)
    // If no saved theme, default to 'light' to match the "Soft/Lavish" requirement.
    const currentTheme = localStorage.getItem('theme') || 'light';
    
    // Function to set theme
    const setTheme = (theme) => {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        updateIcon(theme);
    };

    // Update Icon (Sun/Moon)
    const updateIcon = (theme) => {
        if (!themeToggleBtn) return;
        // Simple text emoji for now, can be replaced with SVG/Icon later
        // Sun = ☀️, Moon = 🌙
        themeToggleBtn.textContent = theme === 'dark' ? '☀️' : '🌙';
        themeToggleBtn.setAttribute('aria-label', `Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`);
    };

    // Initialize
    setTheme(currentTheme);

    // Toggle Event
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            const activeTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = activeTheme === 'dark' ? 'light' : 'dark';
            setTheme(newTheme);
        });
    }

    /* ----------------------------------------------------------------
       2. Dropdown Logic (Global Delegated)
       ---------------------------------------------------------------- */
    // Close all dropdowns except the one passed as argument
    const closeAllDropdowns = (exceptButton = null) => {
        const allDropdowns = document.querySelectorAll('.dropdown-toggle.active');
        allDropdowns.forEach(btn => {
            if (btn !== exceptButton) {
                btn.classList.remove('active');
                const menu = btn.nextElementSibling;
                if (menu && menu.classList.contains('dropdown-menu')) {
                    menu.classList.remove('show');
                    // Accessibility
                    btn.setAttribute('aria-expanded', 'false');
                }
            }
        });
    };

    // Delegated click listener for dropdowns
    document.addEventListener('click', (e) => {
        const toggleBtn = e.target.closest('.dropdown-toggle');
        
        // If clicked on a toggle button
        if (toggleBtn) {
            e.preventDefault();
            e.stopPropagation(); // Stop bubbling
            
            const isExpanded = toggleBtn.getAttribute('aria-expanded') === 'true';
            
            // Close others first
            closeAllDropdowns(toggleBtn);
            
            // Toggle Logic
            const menu = toggleBtn.nextElementSibling;
            if (menu && menu.classList.contains('dropdown-menu')) {
                toggleBtn.classList.toggle('active');
                menu.classList.toggle('show');
                toggleBtn.setAttribute('aria-expanded', !isExpanded);
            }
            return;
        }

        // If clicked outside of any dropdown, close all
        if (!e.target.closest('.dropdown-menu')) {
            closeAllDropdowns();
        }
    });

    /* ----------------------------------------------------------------
       3. Mobile Menu Logic (If applicable)
       ---------------------------------------------------------------- */
    const navToggle = document.querySelector('.navbar-toggler');
    const navMenu = document.querySelector('.nav-links');
    
    if (navToggle && navMenu) {
        navToggle.addEventListener('click', () => {
            navMenu.classList.toggle('active');
            const expanded = navToggle.getAttribute('aria-expanded') === 'true';
            navToggle.setAttribute('aria-expanded', !expanded);
        });
    }
});
