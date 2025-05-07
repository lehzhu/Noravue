document.addEventListener('DOMContentLoaded', function() {
    // Constants
    const DEFER_OPTIONS = [
        { position: 'end', label: 'Move to end' }
    ];

    // State
    let screenshots = [];
    let currentIndex = 0;
    let isLoading = false;
    let hasShownOnboardingHint = false;
    // Action history for undo functionality
    let actionHistory = [];

    // Elements
    const carousel = document.getElementById('screenshot-carousel');
    const carouselInner = document.querySelector('.carousel-inner');
    const carouselHint = document.querySelector('.carousel-hint');
    const loadingIndicator = document.getElementById('loading-indicator');
    const screenshotCounter = document.getElementById('screenshot-counter');
    const deferDropdown = document.getElementById('defer-dropdown-menu');
    const noScreenshotsMessage = document.getElementById('no-screenshots-message');
    const allDoneMessage = document.getElementById('all-done-message');
    const uploadForm = document.getElementById('upload-form');
    const actionButtons = document.getElementById('action-buttons');
    
    // Initialize the application
    init();

    function init() {
        // Setup defer dropdown options
        setupDeferOptions();
        
        // Load screenshots
        loadScreenshots();
        
        // Setup event listeners
        setupEventListeners();
        
        // Setup keyboard navigation
        setupKeyboardNavigation();
        
        // Setup the Restore All Dismissed button
        setupRestoreAllButton();
    }
    
    // Set up Restore All button
    function setupRestoreAllButton() {
        // Get all buttons with the id restore-all-btn (there might be multiple instances)
        const restoreButtons = document.querySelectorAll('#restore-all-btn');
        
        restoreButtons.forEach(button => {
            button.addEventListener('click', function() {
                console.log('Restore all button clicked');
                // Show loading indicator
                isLoading = true;
                showLoadingIndicator();
                
                fetch('/api/restore-dismissed', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    console.log('Restore response:', data);
                    if (data.success) {
                        showMiniToast(`Restored ${data.count} screenshots`);
                        // Reload screenshots with a short delay
                        setTimeout(() => {
                            loadScreenshots();
                        }, 500);
                    } else {
                        showErrorMessage(data.message || 'Error restoring screenshots');
                    }
                    isLoading = false;
                    hideLoadingIndicator();
                })
                .catch(error => {
                    console.error('Error restoring screenshots:', error);
                    showErrorMessage('Failed to restore screenshots');
                    isLoading = false;
                    hideLoadingIndicator();
                });
            });
        });
    }
    
    function setupKeyboardNavigation() {
        document.addEventListener('keydown', function(e) {
            // Only process when the carousel is visible
            if (carousel.classList.contains('d-none')) return;
            
            if (e.key === 'ArrowLeft') {
                // Previous screenshot
                carousel.querySelector('.carousel-control-prev').click();
            } else if (e.key === 'ArrowRight') {
                // Next screenshot
                carousel.querySelector('.carousel-control-next').click();
            } else if (e.key === 'Escape') {
                // Do nothing but catch the key
                e.preventDefault();
            } else if (e.key.toLowerCase() === 'e') {
                // Dismiss screenshot (e for "exclude")
                dismissCurrentScreenshot();
                e.preventDefault();
            } else if (e.key.toLowerCase() === 'h') {
                // Defer screenshot (h for "hold")
                deferCurrentScreenshot('end');
                e.preventDefault();
            } else if (e.key.toLowerCase() === 'z') {
                // Undo last action
                undoLastAction();
                e.preventDefault();
            }
        });
    }

    function setupDeferOptions() {
        // Clear existing options
        deferDropdown.innerHTML = '';
        
        // Add defer options to dropdown
        DEFER_OPTIONS.forEach(option => {
            const link = document.createElement('a');
            link.classList.add('dropdown-item');
            link.href = '#';
            link.textContent = option.label;
            link.dataset.position = option.position;
            link.addEventListener('click', function(e) {
                e.preventDefault();
                deferCurrentScreenshot(option.position);
            });
            deferDropdown.appendChild(link);
        });
    }

    function setupEventListeners() {
        // Listen for dismiss button click
        document.getElementById('dismiss-btn').addEventListener('click', dismissCurrentScreenshot);
        
        // Listen for carousel events to update the counter
        carousel.addEventListener('slide.bs.carousel', function(e) {
            currentIndex = e.to;
            updateCounter();
        });

        // Listen for file upload form submission
        if (uploadForm) {
            uploadForm.addEventListener('submit', function(e) {
                e.preventDefault();
                uploadScreenshots();
            });
        }
        
        // Listen for undo button click
        const undoBtn = document.getElementById('undo-btn');
        if (undoBtn) {
            undoBtn.addEventListener('click', undoLastAction);
        }
        
        // Listen for clear all button click
        const clearAllBtn = document.getElementById('clear-all-btn');
        if (clearAllBtn) {
            clearAllBtn.addEventListener('click', confirmAndClearAll);
        }
        
        // Listen for cleanup session button click
        const cleanupSessionBtn = document.getElementById('cleanup-session-btn');
        if (cleanupSessionBtn) {
            cleanupSessionBtn.addEventListener('click', confirmAndCleanupSession);
        }
        
        // Note: Restore All button is handled in setupRestoreAllButton()
    }
    
    function uploadScreenshots() {
        const fileInput = document.getElementById('screenshot-upload');
        const uploadForm = document.getElementById('upload-form');
        const uploadCard = document.querySelector('.card');
        
        if (!fileInput.files || fileInput.files.length === 0) {
            showErrorMessage('Please select at least one image file to upload');
            return;
        }
        
        // Show loading indicator
        isLoading = true;
        showLoadingIndicator();
        
        // Create progress bar container
        const progressContainer = document.createElement('div');
        progressContainer.className = 'progress-container card shadow-sm mb-4 p-3';
        progressContainer.innerHTML = `
            <h5 class="mb-3">Processing Screenshots</h5>
            <div class="d-flex justify-content-between mb-1">
                <span>Uploading and processing...</span>
                <span class="progress-status">0%</span>
            </div>
            <div class="progress mb-2">
                <div class="progress-bar progress-bar-striped progress-bar-animated bg-warning" 
                     role="progressbar" style="width: 0%" 
                     aria-valuenow="0" aria-valuemin="0" aria-valuemax="100"></div>
            </div>
            <div class="d-flex justify-content-between small">
                <span>
                    <span class="processed-count">0</span> of <span class="total-count">0</span> processed
                </span>
                <span class="time-remaining text-muted"></span>
            </div>
        `;
        
        // Add to the page
        document.querySelector('.container').insertBefore(progressContainer, uploadCard.nextSibling);
        
        // Get progress elements
        const progressBar = progressContainer.querySelector('.progress-bar');
        const progressStatus = progressContainer.querySelector('.progress-status');
        const processedCount = progressContainer.querySelector('.processed-count');
        const totalCount = progressContainer.querySelector('.total-count');
        const timeRemaining = progressContainer.querySelector('.time-remaining');
        
        // Create form data
        const formData = new FormData();
        for (let i = 0; i < fileInput.files.length; i++) {
            formData.append('screenshots[]', fileInput.files[i]);
        }
        
        // Record start time for time estimate
        const startTime = Date.now();
        
        // Send the files to the server
        fetch('/api/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            // Check if we got a timeout or server error
            if (!response.ok) {
                if (response.status === 504 || response.status === 408 || response.status >= 500) {
                    throw new Error('timeout');
                }
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                // Clear file input
                fileInput.value = '';
                
                // Hide the upload form
                if (uploadCard) {
                    uploadCard.style.display = 'none';
                }
                
                // Update total count
                totalCount.textContent = data.total_files;
                
                // Start polling for progress
                let pollInterval = setInterval(() => {
                    fetch('/api/upload/progress')
                        .then(response => response.json())
                        .then(progress => {
                            if (progress.total === 0) {
                                return; // No data yet
                            }
                            
                            // Update progress
                            const percent = Math.round((progress.processed / progress.total) * 100);
                            progressBar.style.width = `${percent}%`;
                            progressBar.setAttribute('aria-valuenow', percent);
                            progressStatus.textContent = `${percent}%`;
                            processedCount.textContent = progress.processed;
                            
                            // Calculate time remaining
                            if (progress.processed > 0) {
                                const elapsedTime = (Date.now() - startTime) / 1000; // in seconds
                                const timePerItem = elapsedTime / progress.processed;
                                const remainingItems = progress.total - progress.processed;
                                const remainingSeconds = Math.round(timePerItem * remainingItems);
                                
                                if (remainingSeconds > 0) {
                                    let timeText = '';
                                    if (remainingSeconds > 60) {
                                        timeText = `${Math.floor(remainingSeconds / 60)} min ${remainingSeconds % 60} sec remaining`;
                                    } else {
                                        timeText = `${remainingSeconds} seconds remaining`;
                                    }
                                    timeRemaining.textContent = timeText;
                                }
                            }
                            
                            // If completed
                            if (progress.completed) {
                                clearInterval(pollInterval);
                                
                                // Show success message
                                showMiniToast('Processing complete');
                                
                                console.log('Upload processing complete, reloading screenshots');
                                // Hide loading indicator
                                isLoading = false;
                                hideLoadingIndicator();
                                
                                // Remove progress bar after delay
                                setTimeout(() => {
                                    progressContainer.remove();
                                }, 2000);
                                
                                // Load screenshots with a small delay to ensure DB processing is complete
                                setTimeout(() => {
                                    loadScreenshots();
                                    console.log('Triggered loadScreenshots() after upload completion');
                                }, 1000);
                            }
                        })
                        .catch(error => {
                            console.error('Error checking progress:', error);
                        });
                }, 1000);
            } else {
                isLoading = false;
                hideLoadingIndicator();
                progressContainer.remove();
                
                showErrorMessage(data.message || 'Error uploading screenshots');
                if (data.warnings && data.warnings.length > 0) {
                    console.error('Upload warnings:', data.warnings);
                }
            }
        })
        .catch(error => {
            console.error('Error uploading screenshots:', error);
            isLoading = false;
            hideLoadingIndicator();
            progressContainer.remove();
            
            // Check if it was a timeout error
            if (error.message === 'timeout') {
                // Show specialized message for timeouts with option to refresh
                const errorContainer = document.createElement('div');
                errorContainer.className = 'alert alert-warning alert-dismissible fade show';
                errorContainer.innerHTML = `
                    <strong>Processing timeout!</strong> 
                    <p>Your screenshots are being processed in the background. This may take a few minutes for large batches.</p>
                    <p>You can <button class="btn btn-sm btn-outline-warning" onclick="window.location.reload()">Refresh the page</button> in a minute to see your uploads.</p>
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                `;
                
                // Add to the page
                document.querySelector('.container').insertBefore(errorContainer, document.querySelector('.container').firstChild);
                
                // Auto-refresh after 60 seconds
                setTimeout(() => {
                    window.location.reload();
                }, 60000);
            } else {
                showErrorMessage('Failed to upload screenshots. Please try again.');
            }
        });
    }

    function loadScreenshots() {
        console.log('loadScreenshots() called');
        isLoading = true;
        showLoadingIndicator();
        
        fetch('/api/screenshots')
            .then(response => {
                console.log('API response status:', response.status);
                return response.json();
            })
            .then(data => {
                console.log('Received screenshots:', data.length);
                
                screenshots = data.filter(screenshot => {
                    // Filter out deferred screenshots
                    if (screenshot.deferred_until) {
                        const deferredUntil = new Date(screenshot.deferred_until);
                        if (deferredUntil > new Date()) {
                            return false;
                        }
                    }
                    return true;
                });
                
                console.log('After filtering, screenshots count:', screenshots.length);
                
                renderScreenshots();
                isLoading = false;
                hideLoadingIndicator();
                updateCounter();
            })
            .catch(error => {
                console.error('Error loading screenshots:', error);
                isLoading = false;
                hideLoadingIndicator();
                showErrorMessage('Failed to load screenshots. Please try again.');
            });
    }

    function renderScreenshots() {
        console.log('renderScreenshots called');
        // Clear existing screenshots
        carouselInner.innerHTML = '';
        
        // Get the Clear All button
        const clearAllBtn = document.getElementById('clear-all-btn');
        
        if (screenshots.length === 0) {
            console.log('No screenshots to display');
            // Only show the "All Done" message if we previously had screenshots
            // and have now dismissed them all
            fetch('/api/has-dismissed-screenshots')
                .then(response => response.json())
                .then(data => {
                    console.log('Dismissed screenshots check:', data);
                    // Only show "All Done" if we have dismissed items AND
                    // we previously displayed screenshots (handled some items)
                    const hadPreviousActivity = localStorage.getItem('hadScreenshots') === 'true';
                    console.log('Had previous activity:', hadPreviousActivity);
                    
                    if (data.has_dismissed && hadPreviousActivity) {
                        // Show the "All Done" message if there are dismissed screenshots but none active
                        console.log('Showing "All Done" message');
                        showAllDoneMessage();
                    } else {
                        // Show the "No Screenshots" message if there are no screenshots at all
                        // or it's the first time loading the app
                        console.log('Showing "No Screenshots" message');
                        showNoScreenshotsMessage();
                    }
                })
                .catch(error => {
                    console.error('Error checking for dismissed screenshots:', error);
                    // Fallback to showing the generic no screenshots message
                    showNoScreenshotsMessage();
                });
            
            // Hide carousel hint and action buttons if they exist
            if (carouselHint) {
                carouselHint.classList.add('d-none');
            }
            if (actionButtons) {
                actionButtons.classList.add('d-none');
            }
            // Hide Clear All button
            if (clearAllBtn) {
                clearAllBtn.classList.add('d-none');
            }
            return;
        }
        
        // Show Clear All button when we have screenshots
        if (clearAllBtn) {
            clearAllBtn.classList.remove('d-none');
        }
        
        // If we have screenshots, remember that for next time
        localStorage.setItem('hadScreenshots', 'true');
        
        hideAllMessages();
        
        // Show action buttons when we have screenshots
        if (actionButtons) {
            actionButtons.classList.remove('d-none');
        }
        
        // Show carousel hint if it exists and we have screenshots
        if (carouselHint && screenshots.length > 0) {
            // Track the number of times the hint has been shown
            if (!localStorage.getItem('hintShownCount')) {
                localStorage.setItem('hintShownCount', '0');
            }
            
            let hintCount = parseInt(localStorage.getItem('hintShownCount'), 10);
            
            // Only show the hint for the first two uses
            if (hintCount < 2) {
                carouselHint.classList.remove('d-none');
                
                // Hide the hint after 10 seconds
                setTimeout(() => {
                    carouselHint.classList.add('d-none');
                }, 10000);
                
                // Increment the count
                localStorage.setItem('hintShownCount', (hintCount + 1).toString());
            }
            
            // Add keydown listener but don't show hint after first two uses
            document.addEventListener('keydown', function showHintOnKeyPress(e) {
                if (['e', 'E', 'h', 'H', 'z', 'Z'].includes(e.key)) {
                    let hintCount = parseInt(localStorage.getItem('hintShownCount'), 10);
                    
                    // Only show the hint for the first two uses
                    if (hintCount < 2) {
                        // Show the hint again
                        carouselHint.classList.remove('d-none');
                        
                        // Hide after a few seconds
                        clearTimeout(window.hintTimeout);
                        window.hintTimeout = setTimeout(() => {
                            carouselHint.classList.add('d-none');
                        }, 3000);
                    }
                }
            });
        }
        
        // Add each screenshot to the carousel
        screenshots.forEach((screenshot, index) => {
            const item = document.createElement('div');
            item.classList.add('carousel-item');
            if (index === 0) {
                item.classList.add('active');
            }
            
            item.dataset.id = screenshot.id;
            
            // Format date
            const createdDate = new Date(screenshot.created_at);
            const formattedDate = createdDate.toLocaleDateString() + ' ' + 
                                createdDate.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            
            // Calculate priority class
            let priorityClass = 'bg-info';
            if (screenshot.priority_score > 0.7) {
                priorityClass = 'bg-danger';
            } else if (screenshot.priority_score > 0.4) {
                priorityClass = 'bg-warning text-dark';
            }
            
            // Create content
            item.innerHTML = `
                <div class="screenshot-card">
                    <div class="screenshot-info mb-3">
                        <div>
                            <span class="badge ${priorityClass}">Priority: ${screenshot.priority_score.toFixed(2)}</span>
                            <small class="text-muted ms-2">${formattedDate}</small>
                        </div>
                        <span class="screenshot-filename">${screenshot.filename}</span>
                    </div>
                    <div class="screenshot-image-container large">
                        <img src="/${screenshot.path}" class="screenshot-image" alt="${screenshot.filename}" style="width: auto; max-width: 100%;">
                    </div>
                    <div class="text-details-toggle mt-2">
                        <button class="btn btn-sm btn-light text-toggle-btn" type="button">
                            <i data-feather="chevron-down" class="text-icon"></i> 
                            <span>Show extracted text</span>
                        </button>
                    </div>
                    <div class="screenshot-text collapse">
                        <div class="d-flex justify-content-between align-items-center mb-2 pt-2">
                            <h5 class="mb-0">Extracted Text:</h5>
                            <small class="text-muted">Scroll to view more</small>
                        </div>
                        <div class="text-content">${screenshot.text_content || 'No text extracted'}</div>
                    </div>
                </div>
            `;
            
            // Add event listener to the text toggle button after the item is added to the DOM
            setTimeout(() => {
                const toggleBtn = item.querySelector('.text-toggle-btn');
                const textSection = item.querySelector('.screenshot-text');
                const toggleIcon = item.querySelector('.text-icon');
                const toggleText = toggleBtn.querySelector('span');
                
                toggleBtn.addEventListener('click', function() {
                    const isCollapsed = textSection.classList.contains('collapse');
                    
                    if (isCollapsed) {
                        // Show section
                        textSection.classList.remove('collapse');
                        textSection.classList.add('show');
                        toggleIcon.setAttribute('data-feather', 'chevron-up');
                        toggleText.textContent = 'Hide extracted text';
                    } else {
                        // Hide section 
                        textSection.classList.add('collapse');
                        textSection.classList.remove('show');
                        toggleIcon.setAttribute('data-feather', 'chevron-down');
                        toggleText.textContent = 'Show extracted text';
                    }
                    
                    // Re-initialize feather icons
                    feather.replace();
                });
            }, 0);
            
            carouselInner.appendChild(item);
        });
        
        // Initialize the Bootstrap carousel
        new bootstrap.Carousel(carousel, {
            interval: false, // Don't auto-rotate
            keyboard: true,
            wrap: true
        });
    }

    function updateCounter() {
        if (screenshots.length === 0) {
            screenshotCounter.textContent = 'No screenshots';
            return;
        }
        
        screenshotCounter.textContent = `${screenshots.length} remaining`;
    }

    function getCurrentScreenshotId() {
        const activeItem = document.querySelector('.carousel-item.active');
        return activeItem ? parseInt(activeItem.dataset.id, 10) : null;
    }

    // Helper function to smooth transition between carousel items
    function smoothCarouselTransition() {
        if (carousel) {
            const carouselInner = document.querySelector('.carousel-inner');
            carouselInner.classList.add('transitioning');
            
            setTimeout(() => {
                carouselInner.classList.remove('transitioning');
            }, 500);
            
            const carouselInstance = bootstrap.Carousel.getInstance(carousel);
            carouselInstance.next();
        }
    }
    
    function dismissCurrentScreenshot() {
        const screenshotId = getCurrentScreenshotId();
        if (!screenshotId) return;
        
        // Find the current screenshot before it's removed
        const screenshot = screenshots.find(s => s.id === screenshotId);
        if (!screenshot) return;
        
        fetch(`/api/screenshots/${screenshotId}/dismiss`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Show mini toast notification
                showMiniToast('Dismissed');
                
                // Save to action history for undo
                actionHistory.push({
                    type: 'dismiss',
                    screenshotId: screenshotId,
                    screenshot: JSON.parse(JSON.stringify(screenshot))
                });
                
                // Remove from local array
                screenshots = screenshots.filter(s => s.id !== screenshotId);
                
                // Move to next or reload if this was the last one
                if (screenshots.length === 0) {
                    loadScreenshots();
                } else {
                    // Move to the next item automatically
                    if (carousel) {
                        const carouselInstance = bootstrap.Carousel.getInstance(carousel);
                        carouselInstance.next();
                    }
                    
                    // Update counter
                    setTimeout(updateCounter, 50);
                }
            }
        })
        .catch(error => {
            console.error('Error dismissing screenshot:', error);
            showErrorMessage('Failed to dismiss screenshot');
        });
    }

    // Track the last time Hold was used (to prevent rapid firing)
    let lastHoldTime = 0;
    const HOLD_DELAY = 2000; // 2 second buffer delay
    
    function deferCurrentScreenshot(position) {
        const screenshotId = getCurrentScreenshotId();
        if (!screenshotId) return;
        
        // Check if this was triggered from keyboard
        const now = Date.now();
        const isFromKeyboard = position === 'end' && (now - lastHoldTime < 100); 
        
        // If triggered from keyboard, apply the buffer delay
        if (isFromKeyboard) {
            // Check if enough time has passed
            if (now - lastHoldTime < HOLD_DELAY) {
                console.log('Hold action ignored - too soon after previous hold');
                return; // Skip if it's too soon
            }
        }
        
        // Update the last hold time
        lastHoldTime = now;
        
        // If position is 'end', we'll handle it locally by moving the item to the end of the array
        if (position === 'end') {
            // Find the current screenshot
            const currentScreenshot = screenshots.find(s => s.id === screenshotId);
            if (!currentScreenshot) return;
            
            // Save the current index for undo
            const currentIndex = screenshots.findIndex(s => s.id === screenshotId);
            
            // Add to action history for undo
            actionHistory.push({
                type: 'defer',
                screenshotId: screenshotId,
                screenshot: JSON.parse(JSON.stringify(currentScreenshot)),
                originalIndex: currentIndex
            });
            
            // Remove it from its current position
            screenshots = screenshots.filter(s => s.id !== screenshotId);
            
            // Add it to the end
            screenshots.push(currentScreenshot);
            
            // Show mini toast notification
            showMiniToast('Moved to end of queue');
            
            // Move to next item
            if (carousel) {
                const carouselInstance = bootstrap.Carousel.getInstance(carousel);
                carouselInstance.next();
                
                // Re-render the carousel to reflect the new order
                setTimeout(() => {
                    renderScreenshots();
                    updateCounter();
                }, 50);
            }
            
            return;
        }
        
        // For other types of deferrals (which we don't have anymore, but kept for flexibility)
        fetch(`/api/screenshots/${screenshotId}/defer`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ defer_hours: 1 }) // Default to 1 hour if needed
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Get the defer option label
                const option = DEFER_OPTIONS.find(o => o.position === position);
                const label = option ? option.label : 'Deferred';
                
                // Show mini toast notification
                showMiniToast(label);
                
                // Remove from local array
                screenshots = screenshots.filter(s => s.id !== screenshotId);
                
                // Move to next or reload if this was the last one
                if (screenshots.length === 0) {
                    loadScreenshots();
                } else {
                    // Move to the next item automatically
                    if (carousel) {
                        const carouselInstance = bootstrap.Carousel.getInstance(carousel);
                        carouselInstance.next();
                    }
                    
                    // Update counter
                    setTimeout(updateCounter, 50);
                }
            }
        })
        .catch(error => {
            console.error('Error deferring screenshot:', error);
            showErrorMessage('Failed to defer screenshot');
        });
    }
    
    function showMiniToast(message) {
        // Create a mini toast that appears briefly
        const miniToast = document.createElement('div');
        miniToast.classList.add('mini-toast');
        miniToast.innerHTML = `<div class="mini-toast-content">${message}</div>`;
        document.body.appendChild(miniToast);
        
        // Show and then hide
        setTimeout(() => {
            miniToast.classList.add('mini-toast-visible');
            setTimeout(() => {
                miniToast.classList.remove('mini-toast-visible');
                setTimeout(() => miniToast.remove(), 300);
            }, 1200);
        }, 10);
    }

    function rescanScreenshots() {
        isLoading = true;
        showLoadingIndicator();
        
        fetch('/api/rescan', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showToast(data.message);
                // Reload screenshots
                loadScreenshots();
            } else {
                showErrorMessage(data.message || 'Rescan failed');
                isLoading = false;
                hideLoadingIndicator();
            }
        })
        .catch(error => {
            console.error('Error rescanning screenshots:', error);
            showErrorMessage('Failed to rescan for new screenshots');
            isLoading = false;
            hideLoadingIndicator();
        });
    }

    // UI Helpers
    function showLoadingIndicator() {
        loadingIndicator.classList.remove('d-none');
    }

    function hideLoadingIndicator() {
        loadingIndicator.classList.add('d-none');
    }

    function showNoScreenshotsMessage() {
        noScreenshotsMessage.classList.remove('d-none');
        carousel.classList.add('d-none');
    }

    function hideNoScreenshotsMessage() {
        noScreenshotsMessage.classList.add('d-none');
        carousel.classList.remove('d-none');
    }
    
    function showAllDoneMessage() {
        allDoneMessage.classList.remove('d-none');
        carousel.classList.add('d-none');
    }
    
    function hideAllDoneMessage() {
        allDoneMessage.classList.add('d-none');
    }
    
    function hideAllMessages() {
        hideNoScreenshotsMessage();
        hideAllDoneMessage();
    }

    function showToast(message) {
        const toastContainer = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.classList.add('toast', 'shadow-lg');
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        
        toast.innerHTML = `
            <div class="toast-header bg-success bg-opacity-10">
                <i data-feather="check-circle" class="text-success me-2"></i>
                <strong class="me-auto text-success">Success</strong>
                <small>Just now</small>
                <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        `;
        
        toastContainer.appendChild(toast);
        
        const bsToast = new bootstrap.Toast(toast, {
            delay: 3000,
            autohide: true
        });
        
        bsToast.show();
        
        // Initialize feather icons for the new toast
        feather.replace();
        
        // Remove from DOM after hidden
        toast.addEventListener('hidden.bs.toast', function() {
            toast.remove();
        });
    }

    function showErrorMessage(message) {
        const toastContainer = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.classList.add('toast', 'shadow-lg');
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        
        toast.innerHTML = `
            <div class="toast-header bg-danger bg-opacity-10">
                <i data-feather="alert-circle" class="text-danger me-2"></i>
                <strong class="me-auto text-danger">Error</strong>
                <small>Just now</small>
                <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        `;
        
        toastContainer.appendChild(toast);
        
        const bsToast = new bootstrap.Toast(toast, {
            delay: 5000,
            autohide: true
        });
        
        bsToast.show();
        
        // Initialize feather icons for the new toast
        feather.replace();
        
        // Remove from DOM after hidden
        toast.addEventListener('hidden.bs.toast', function() {
            toast.remove();
        });
    }
    
    /**
     * Undo the last action performed on a screenshot
     */
    function undoLastAction() {
        if (actionHistory.length === 0) {
            showMiniToast('Nothing to undo');
            return;
        }
        
        // Get the last action
        const lastAction = actionHistory.pop();
        
        if (lastAction.type === 'dismiss') {
            // Restore a dismissed screenshot
            fetch(`/api/screenshots/${lastAction.screenshotId}/restore`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Add the screenshot back to our local array
                    screenshots.push(lastAction.screenshot);
                    
                    // Re-render the carousel
                    renderScreenshots();
                    
                    // Show mini toast notification
                    showMiniToast('Undid dismiss');
                    
                    // Update counter
                    updateCounter();
                } else {
                    showErrorMessage('Failed to undo dismiss action');
                }
            })
            .catch(error => {
                console.error('Error undoing dismiss:', error);
                showErrorMessage('Failed to undo dismiss action');
            });
        } else if (lastAction.type === 'defer') {
            // For defer actions, we just need to reposition the item in our local array
            const screenshot = screenshots.find(s => s.id === lastAction.screenshotId);
            
            // If the screenshot is still in our array, restore its position
            if (screenshot) {
                // Remove it from its current position
                screenshots = screenshots.filter(s => s.id !== lastAction.screenshotId);
                
                // Insert at original position (or as close as possible with remaining items)
                const targetIndex = Math.min(lastAction.originalIndex, screenshots.length);
                screenshots.splice(targetIndex, 0, screenshot);
                
                // Re-render the carousel
                renderScreenshots();
                
                // Show mini toast notification
                showMiniToast('Undid move to end');
                
                // If carousel is initialized, try to select the undone screenshot
                if (carousel) {
                    // Find the index of the screenshot in the current carousel
                    const newIndex = screenshots.findIndex(s => s.id === lastAction.screenshotId);
                    if (newIndex >= 0) {
                        const carouselInstance = bootstrap.Carousel.getInstance(carousel);
                        carouselInstance.to(newIndex);
                    }
                }
            } else {
                // The screenshot might have been dismissed or is no longer present
                showMiniToast('Cannot undo move (item no longer present)');
            }
        }
    }
    
    /**
     * Confirm and then clear all screenshots with a dialog
     */
    function confirmAndClearAll() {
        if (screenshots.length === 0) {
            showMiniToast('No screenshots to clear');
            return;
        }
        
        if (confirm(`Are you sure you want to dismiss all ${screenshots.length} screenshots?`)) {
            // Call the API to dismiss all screenshots
            fetch('/api/dismiss-all', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Show toast notification
                    showToast(data.message || `Dismissed all screenshots`);
                    
                    // Clear our local array
                    screenshots = [];
                    
                    // Reload screenshots (which will show the "all done" message)
                    loadScreenshots();
                } else {
                    showErrorMessage(data.message || 'Failed to dismiss all screenshots');
                }
            })
            .catch(error => {
                console.error('Error dismissing all screenshots:', error);
                showErrorMessage('Failed to dismiss all screenshots');
            });
        }
    }
    
    /**
     * Restore all dismissed screenshots
     */
    function restoreAllDismissed() {
        // Call the API to restore all dismissed screenshots
        fetch('/api/restore-dismissed', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Show toast notification
                showToast(data.message || `Restored all screenshots`);
                
                // Reload screenshots to show the restored items
                loadScreenshots();
            } else {
                showErrorMessage(data.message || 'Failed to restore dismissed screenshots');
            }
        })
        .catch(error => {
            console.error('Error restoring dismissed screenshots:', error);
            showErrorMessage('Failed to restore dismissed screenshots');
        });
    }
    
    /**
     * Confirm and then clean up the session data
     */
    function confirmAndCleanupSession() {
        if (confirm('Are you sure you want to clear all session data? This will remove all your screenshots and cannot be undone.')) {
            // Show loading indicator
            isLoading = true;
            showLoadingIndicator();
            
            // Call the API to clean up session data
            fetch('/api/cleanup-session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Show toast notification
                    showToast(data.message || 'Your session data has been cleared');
                    
                    // Reset states
                    screenshots = [];
                    currentIndex = 0;
                    localStorage.removeItem('hadScreenshots');
                    
                    // Force reload the page to reflect the cleared state
                    window.location.reload();
                } else {
                    showErrorMessage(data.message || 'Failed to clear session data');
                    isLoading = false;
                    hideLoadingIndicator();
                }
            })
            .catch(error => {
                console.error('Error cleaning up session:', error);
                showErrorMessage('Failed to clear session data');
                isLoading = false;
                hideLoadingIndicator();
            });
        }
    }
});
