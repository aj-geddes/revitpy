/**
 * RevitPy Documentation - Main JavaScript
 * Handles interactive features, copy buttons, mobile navigation, and code tabs
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all features
    initMobileNav();
    initCodeTabs();
    initCopyButtons();
    initSmoothScrolling();
    initTOCHighlighting();
    initExternalLinks();
});

/**
 * Mobile Navigation
 * Handles hamburger menu toggle for mobile devices
 */
function initMobileNav() {
    const navToggle = document.querySelector('.nav-toggle');
    const mobileNav = document.querySelector('.mobile-nav');

    if (!navToggle || !mobileNav) return;

    navToggle.addEventListener('click', function() {
        const isExpanded = navToggle.getAttribute('aria-expanded') === 'true';

        navToggle.setAttribute('aria-expanded', !isExpanded);
        navToggle.classList.toggle('active');
        mobileNav.classList.toggle('active');

        // Prevent body scroll when menu is open
        document.body.style.overflow = isExpanded ? '' : 'hidden';
    });

    // Close menu when clicking a link
    mobileNav.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', () => {
            navToggle.setAttribute('aria-expanded', 'false');
            navToggle.classList.remove('active');
            mobileNav.classList.remove('active');
            document.body.style.overflow = '';
        });
    });

    // Close menu on escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && mobileNav.classList.contains('active')) {
            navToggle.click();
        }
    });
}

/**
 * Code Tabs
 * Handles tab switching for code examples on homepage
 */
function initCodeTabs() {
    const tabContainers = document.querySelectorAll('.code-tabs');

    tabContainers.forEach(container => {
        const tabs = container.querySelectorAll('.code-tab');
        const parent = container.parentElement;
        const panels = parent.querySelectorAll('.code-panel');

        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const targetId = tab.getAttribute('data-tab');

                // Update active tab
                tabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');

                // Update active panel
                panels.forEach(panel => {
                    if (panel.id === targetId) {
                        panel.classList.add('active');
                    } else {
                        panel.classList.remove('active');
                    }
                });
            });
        });
    });
}

/**
 * Copy Buttons
 * Adds copy functionality to all code blocks
 */
function initCopyButtons() {
    // Handle pre-existing copy buttons (from HTML)
    document.querySelectorAll('.copy-button').forEach(button => {
        if (!button.hasAttribute('data-initialized')) {
            const codeBlock = button.closest('.code-block');
            if (codeBlock) {
                const code = codeBlock.querySelector('code');
                if (code) {
                    setupCopyButton(button, code);
                }
            }
            button.setAttribute('data-initialized', 'true');
        }
    });

    // Add copy buttons to code blocks without them
    document.querySelectorAll('pre code').forEach(code => {
        const pre = code.parentElement;

        // Skip if already has a copy button
        if (pre.querySelector('.copy-button')) return;

        // Create wrapper if needed
        if (!pre.classList.contains('code-block')) {
            pre.classList.add('code-block');
        }

        const button = document.createElement('button');
        button.className = 'copy-button';
        button.textContent = 'Copy';
        button.setAttribute('aria-label', 'Copy code to clipboard');

        setupCopyButton(button, code);
        pre.appendChild(button);
    });
}

/**
 * Setup individual copy button
 */
function setupCopyButton(button, code) {
    button.addEventListener('click', async () => {
        const text = code.textContent;

        try {
            await navigator.clipboard.writeText(text);
            button.textContent = 'Copied!';
            button.classList.add('copied');

            setTimeout(() => {
                button.textContent = 'Copy';
                button.classList.remove('copied');
            }, 2000);
        } catch (err) {
            // Fallback for older browsers
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();

            try {
                document.execCommand('copy');
                button.textContent = 'Copied!';
                button.classList.add('copied');

                setTimeout(() => {
                    button.textContent = 'Copy';
                    button.classList.remove('copied');
                }, 2000);
            } catch (e) {
                button.textContent = 'Failed';
                setTimeout(() => {
                    button.textContent = 'Copy';
                }, 2000);
            }

            document.body.removeChild(textarea);
        }
    });
}

/**
 * Smooth Scrolling
 * Handles smooth scroll for anchor links
 */
function initSmoothScrolling() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            if (href === '#') return;

            const target = document.querySelector(href);
            if (target) {
                e.preventDefault();

                const headerHeight = document.querySelector('.site-header')?.offsetHeight || 0;
                const targetPosition = target.getBoundingClientRect().top + window.pageYOffset - headerHeight - 20;

                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });

                // Update URL without jumping
                history.pushState(null, null, href);
            }
        });
    });
}

/**
 * TOC Highlighting
 * Highlights current section in table of contents
 */
function initTOCHighlighting() {
    const toc = document.querySelector('.sidebar-menu, .toc-list');
    if (!toc) return;

    const headings = document.querySelectorAll('h2[id], h3[id], h4[id]');
    const tocLinks = toc.querySelectorAll('a[href^="#"]');

    if (headings.length === 0 || tocLinks.length === 0) return;

    const observerOptions = {
        rootMargin: '-80px 0px -60% 0px',
        threshold: 0
    };

    const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const id = entry.target.getAttribute('id');

                tocLinks.forEach(link => {
                    const href = link.getAttribute('href');
                    if (href === `#${id}`) {
                        link.classList.add('active');
                    } else {
                        link.classList.remove('active');
                    }
                });
            }
        });
    }, observerOptions);

    headings.forEach(heading => observer.observe(heading));
}

/**
 * External Links
 * Opens external links in new tab with proper security attributes
 */
function initExternalLinks() {
    document.querySelectorAll('a[href^="http"]').forEach(link => {
        const url = new URL(link.href);

        if (url.hostname !== window.location.hostname) {
            link.setAttribute('target', '_blank');
            link.setAttribute('rel', 'noopener noreferrer');
        }
    });
}

/**
 * Utility: Debounce function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func.apply(this, args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Dark Mode Toggle (optional)
 * Call this if you add a manual dark mode toggle button
 */
function initDarkMode() {
    const toggle = document.querySelector('.dark-mode-toggle');
    if (!toggle) return;

    // Check for saved preference or system preference
    const savedTheme = localStorage.getItem('theme');
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const currentTheme = savedTheme || (systemPrefersDark ? 'dark' : 'light');

    document.documentElement.setAttribute('data-theme', currentTheme);

    toggle.addEventListener('click', () => {
        const theme = document.documentElement.getAttribute('data-theme');
        const newTheme = theme === 'light' ? 'dark' : 'light';

        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
    });

    // Listen for system theme changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        if (!localStorage.getItem('theme')) {
            document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light');
        }
    });
}
