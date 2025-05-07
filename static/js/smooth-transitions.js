/**
 * Helper functions for smooth transitions between carousel items
 */

// Add this function to the global scope
window.applyCarouselTransition = function() {
    const carouselInner = document.querySelector('.carousel-inner');
    if (carouselInner) {
        carouselInner.classList.add('transitioning');
        
        setTimeout(() => {
            carouselInner.classList.remove('transitioning');
        }, 600);
    }
};

// Extend Bootstrap's Carousel to apply transitions
document.addEventListener('DOMContentLoaded', function() {
    // Get the carousel
    const carousel = document.getElementById('screenshot-carousel');
    if (!carousel) return;
    
    // Wait for Bootstrap to initialize
    setTimeout(() => {
        // Get the Bootstrap carousel instance
        const carouselInstance = bootstrap.Carousel.getInstance(carousel);
        if (!carouselInstance) return;
        
        // Store the original next method
        const originalNext = carouselInstance.next;
        
        // Override the next method
        carouselInstance.next = function() {
            // Apply the transition class
            window.applyCarouselTransition();
            
            // Call the original method
            originalNext.call(this);
        };
    }, 500);
    
    // Apply transitions when dismiss or defer buttons are clicked
    document.getElementById('dismiss-btn')?.addEventListener('click', function() {
        window.applyCarouselTransition();
    });
    
    // Handle keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        if (e.key.toLowerCase() === 'e' || e.key.toLowerCase() === 'h') {
            window.applyCarouselTransition();
        }
    });
});