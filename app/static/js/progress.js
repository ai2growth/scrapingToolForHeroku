// Helper Functions
function showError(message) {
    console.error('Error:', message);
    const errorMessage = document.getElementById('error-message');
    if (errorMessage) {
        errorMessage.textContent = message;
        errorMessage.style.display = 'block';
        setTimeout(() => (errorMessage.style.display = 'none'), 5000);
    }
}

function showNotification(message, type = 'success') {
    console.log('Notification:', message);
    const resultsMessage = document.getElementById('resultsMessage');
    if (resultsMessage) {
        resultsMessage.className = `alert alert-${type}`;
        resultsMessage.textContent = message;
        resultsMessage.style.display = 'block';
        setTimeout(() => (resultsMessage.style.display = 'none'), 8000);
    }
}

function verifySocketConnection() {
    if (!socket || !socket.connected) {
        console.warn('Socket is not connected');
        showError('Not connected to server. Please refresh the page.');
        return false;
    }
    console.log('Socket is connected, ID:', socket.id);
    return true;
}

function resetUI() {
    console.log('Resetting UI to default state...');
    const progressBar = document.querySelector('#overall-progress .progress-bar');
    const scrapeProgressBar = document.querySelector('#scraping-progress .progress-bar');

    if (progressBar) {
        progressBar.style.width = '0%';
        progressBar.textContent = '0%';
        progressBar.classList.remove('bg-success', 'bg-danger');
    }

    if (scrapeProgressBar) {
        scrapeProgressBar.style.width = '0%';
        scrapeProgressBar.textContent = '0%';
        scrapeProgressBar.classList.remove('bg-success', 'bg-danger');
    }

    const currentOperation = document.getElementById('current-operation');
    const progressText = document.getElementById('progress-text');
    if (currentOperation) currentOperation.textContent = '';
    if (progressText) progressText.textContent = '';

    const warningElement = document.getElementById('scrape-limit-warning');
    if (warningElement) {
        warningElement.remove();
    }

    const overallProgress = document.getElementById('overall-progress');
    const scrapingProgress = document.getElementById('scraping-progress');
    if (overallProgress) overallProgress.style.display = 'none';
    if (scrapingProgress) scrapingProgress.style.display = 'none';
}

// Global Variables
let socket;
let progressCheckInterval;
let lastUpdate = Date.now();


function startProgressMonitoring() {
    console.log('Starting progress monitoring...');
    progressCheckInterval = setInterval(() => {
        const timeSinceLastUpdate = Date.now() - lastUpdate;
        if (timeSinceLastUpdate > 30000) { // 30 seconds
            console.warn('No progress updates received for 30 seconds');
            showNotification('Processing may be stuck. Please check the console for details.', 'warning');
            stopProgressMonitoring();
        }
    }, 5000);
}

function stopProgressMonitoring() {
    if (progressCheckInterval) {
        clearInterval(progressCheckInterval);
        console.log('Progress monitoring stopped');
    }
}

function updateProgressTimestamp() {
    lastUpdate = Date.now();
}

function initializeApp() {
    console.log('Starting app initialization...');

    // 1. Element References
    const uploadForm = document.getElementById('uploadForm');
    const fileInput = document.getElementById('file-input');
    const uploadButton = document.getElementById('upload-button');
    const configSection = document.getElementById('config-section');
    const processForm = document.getElementById('processForm');
    const processButton = document.getElementById('process-button');
    const numAdditionalColumns = document.getElementById('num-additional-columns');
    const additionalColumnsContainer = document.getElementById('additional-columns-container');

    console.log('Elements found:', {
        uploadForm: !!uploadForm,
        fileInput: !!fileInput,
        uploadButton: !!uploadButton,
        configSection: !!configSection,
        processForm: !!processForm,
        processButton: !!processButton,
        numAdditionalColumns: !!numAdditionalColumns
    });

    try {
        const serverUrl = window.socketConfig?.serverUrl || window.location.origin;
        const options = {
            ...(window.socketConfig?.options || {}),
            autoConnect: false,
            transports: ['websocket', 'polling'],
            reconnection: true,
            reconnectionAttempts: 5,
            reconnectionDelay: 1000,
            timeout: 20000,
            path: '/socket.io',
            namespace: '/',
            forceNew: true  // Add this line
        };

        // Add connection timeout
        const connectionTimeout = setTimeout(() => {
            if (!socket || !socket.connected) {
                showError('Failed to connect to server. Please refresh the page.');
            }
        }, 5000);

        socket = io(serverUrl, options);

        socket.on('connect', () => {
            clearTimeout(connectionTimeout);
            console.log('Socket connected successfully:', socket.id);
            const errorMessage = document.getElementById('error-message');
            if (errorMessage) {
                errorMessage.style.display = 'none';
            }
        });  
        console.log('Attempting socket connection to:', serverUrl, 'with options:', options);
        
        // Initialize socket with server URL and options
        socket = io(serverUrl, options);
    
        // Add event handlers before connecting
        socket.on('connect', () => {
            console.log('Socket connected successfully:', socket.id);
            const errorMessage = document.getElementById('error-message');
            if (errorMessage) {
                errorMessage.style.display = 'none';
            }
        });
    
        socket.on('connection_confirmed', (data) => {
            console.log('Server confirmed connection:', data);
        });
    
        socket.on('connect_error', (error) => {
            console.warn('Socket connection error:', error);
            // Only show error after multiple attempts
            if (socket.reconnectionAttempts > 2) {
                showError('Connection issues. Trying to reconnect...');
            }
        });
    
        socket.on('disconnect', (reason) => {
            console.log('Socket disconnected:', reason);
            if (reason === 'io server disconnect') {
                socket.connect();
            }
        });
    
        // Now connect
        socket.connect();
    
        console.log('Socket.IO initialization attempted');
    } catch (error) {
        console.error('Socket.IO initialization error:', error);
    }
    function startProgressMonitoring() {
        console.log('Starting progress monitoring...');
        stopProgressMonitoring(); // Clear any existing interval
        
        let noUpdateCount = 0;
        progressCheckInterval = setInterval(() => {
            const timeSinceLastUpdate = Date.now() - lastUpdate;
            if (timeSinceLastUpdate > 30000) { // 30 seconds
                noUpdateCount++;
                console.warn(`No progress updates received for ${noUpdateCount} intervals`);
                
                if (noUpdateCount >= 3) { // After 3 intervals without updates
                    showError('Processing appears to be stuck. Please try again.');
                    stopProgressMonitoring();
                    resetUI();
                    if (processButton) {
                        processButton.disabled = false;
                        processButton.innerHTML = 'Start Processing';
                    }
                } else {
                    showNotification('Processing may be slow. Please wait...', 'warning');
                }
            } else {
                noUpdateCount = 0;
            }
        }, 10000); // Check every 10 seconds
    }
  
    function fetchScrapeCount() {
        if (!socket || !socket.connected) {
            console.warn('Socket not connected, retrying in 2 seconds...');
            setTimeout(fetchScrapeCount, 2000);
            return;
        }
    
        fetch('/get_scrape_count')
            .then(response => {
                if (response.status === 401) {
                    // User is not authenticated
                    const scrapeCountElement = document.querySelector('.navbar-nav .nav-link span');
                    if (scrapeCountElement) {
                        scrapeCountElement.textContent = 'Please login to view scrapes';
                    }
                    return null;
                }
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data) {  // Only update if we have data (user is authenticated)
                    const scrapeCountElement = document.querySelector('.navbar-nav .nav-link span');
                    if (scrapeCountElement) {
                        scrapeCountElement.textContent = `Scrapes: ${data.scrapes_used}/${data.scrape_limit}`;
                    }
                }
            })
            .catch(error => {
                console.error('Error fetching scrape count:', error);
                // Don't show error message if not authenticated
                if (error.message !== 'Network response was not ok') {
                    showError('Failed to fetch scrape count');
                }
            });
    }

    
    fetchScrapeCount();

    socket.on('scrape_count_updated', function(data) {
        console.log('Received scrape count update:', data);

        const scrapeCountElement = document.querySelector('.navbar-nav .nav-link span');
        if (scrapeCountElement) {
            scrapeCountElement.textContent = `Scrapes: ${data.scrapes_used}/${data.scrape_limit}`;

            if (data.scrapes_used >= data.scrape_limit * 0.9) {
                showNotification('Warning: You are approaching your scrape limit!', 'warning');

                let warningElement = document.getElementById('scrape-limit-warning');
                if (!warningElement) {
                    warningElement = document.createElement('div');
                    warningElement.id = 'scrape-limit-warning';
                    warningElement.className = 'alert alert-warning mt-2';
                    warningElement.textContent = `Warning: Only ${data.scrape_limit - data.scrapes_used} scrapes remaining!`;

                    const processingStatus = document.getElementById('processing-status');
                    if (processingStatus) {
                        processingStatus.appendChild(warningElement);
                    }
                }
            } else {
                const warningElement = document.getElementById('scrape-limit-warning');
                if (warningElement) {
                    warningElement.remove();
                }
            }
        } else {
            console.error('Scrape count element not found in navbar');
        }
    });

    socket.on('scraping_progress', function(data) {
        console.log('Scraping progress event received:', data);
        const progressBar = document.querySelector('#scraping-progress .progress-bar');
        const progressText = document.getElementById('progress-text');
        const progressDiv = document.getElementById('scraping-progress');

        progressDiv.style.display = 'block';
        const percentage = Math.round((data.current / data.total) * 100);
        progressBar.style.width = `${percentage}%`;
        progressBar.setAttribute('aria-valuenow', percentage);
        progressBar.textContent = `${percentage}%`;
        progressText.textContent = `Scraped: ${data.current} of ${data.total} websites`;
        updateProgressTimestamp();
    });

    socket.on('scraping_complete', function() {
        console.log('Scraping complete event received');
        const progressBar = document.querySelector('#scraping-progress .progress-bar');
        const progressText = document.getElementById('progress-text');

        progressBar.classList.remove('progress-bar-animated');
        progressText.textContent = 'Scraping complete! Analyzing with GPT...';
    });

    socket.on('scraping_error', function(data) {
        console.error('Scraping error event received:', data);
        const progressBar = document.querySelector('#scraping-progress .progress-bar');
        const progressText = document.getElementById('progress-text');

        progressText.textContent = `Error: ${data.message}`;
        progressBar.classList.remove('progress-bar-animated');
        progressBar.classList.add('bg-danger');
    });

    socket.on('processing_progress', function(data) {
        console.log('Processing progress event received:', data);
        updateProgressTimestamp();

        const progressBar = document.querySelector('#overall-progress .progress-bar');
        const progressText = document.getElementById('overall-progress-text');
        const operationStatus = document.getElementById('current-operation');
        const progressDiv = document.getElementById('overall-progress');

        if (!progressBar || !progressText || !operationStatus || !progressDiv) {
            console.error('Missing progress UI elements');
            return;
        }

        progressDiv.style.display = 'block';
        document.getElementById('operation-status').style.display = 'block';

        const percentage = Math.round((data.current / data.total) * 100);
        progressBar.style.transition = 'width 0.3s ease';
        progressBar.style.width = `${percentage}%`;
        progressBar.setAttribute('aria-valuenow', percentage);
        progressBar.textContent = `${percentage}%`;

        progressText.textContent = `Processing row ${data.current} of ${data.total}`;

        if (data.status === 'complete') {
            operationStatus.textContent = 'Processing complete! Preparing download...';
            progressBar.classList.remove('progress-bar-animated', 'progress-bar-striped');
            progressBar.classList.add('bg-success');
            showNotification('Processing complete! Your file will download automatically.', 'success');
            stopProgressMonitoring();
        }
    });

    socket.on('processing_error', function(data) {
        console.error('Processing error event received:', data);
        const operationStatus = document.getElementById('current-operation');
        const progressBar = document.querySelector('#overall-progress .progress-bar');

        operationStatus.textContent = `Error: ${data.message}`;
        progressBar.classList.remove('progress-bar-animated', 'progress-bar-striped');
        progressBar.classList.add('bg-danger');
        showError(data.message);
        stopProgressMonitoring();
    });


    socket.on('processing_complete', function(data) {
        console.log('Processing complete event received');
        try {
            if (data && data.csv_data) {
                console.log('CSV data received, initiating download...');
                
                // Create blob from CSV data
                const blob = new Blob([data.csv_data], { 
                    type: 'text/csv;charset=utf-8;' 
                });
                
                // Create download link
                const link = document.createElement('a');
                const url = window.URL.createObjectURL(blob);
                link.setAttribute('href', url);
                link.setAttribute('download', `analysis_results_${new Date().toISOString().slice(0,10)}.csv`);
                link.style.visibility = 'hidden';
                
                // Add to document, click, and remove
                document.body.appendChild(link);
                console.log('Triggering download...');
                link.click();
                document.body.removeChild(link);
                window.URL.revokeObjectURL(url);
                
                // Reset UI
                if (processButton) {
                    processButton.disabled = false;
                    processButton.innerHTML = 'Start Processing';
                }
                
                showNotification('Processing complete! Your file is downloading.', 'success');
                console.log('Download process completed');
            } else {
                console.error('No CSV data in response:', data);
                showError('Processing completed but no data received');
            }
        } catch (error) {
            console.error('Error handling download:', error);
            showError('Error downloading file: ' + error.message);
        } finally {
            // Ensure UI is reset even if there's an error
            if (processButton) {
                processButton.disabled = false;
                processButton.innerHTML = 'Start Processing';
            }
            stopProgressMonitoring();
        }
    });
    processForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        console.log('Process form submitted');
    
        const apiKey = document.getElementById('api_key').value;
        const instructions = document.getElementById('instructions').value;
        const filePath = document.getElementById('file_path').value;
    
        // Collect additional columns data
        const additionalColumns = [];
        document.querySelectorAll('.additional-column').forEach(column => {
            const name = column.querySelector('.column-name').value;
            const instructions = column.querySelector('.column-instructions').value;
            if (name && instructions) {
                additionalColumns.push({ name, instructions });
            }
        });
    
        console.log('Additional columns:', additionalColumns); // Add this debug log
    
        if (!apiKey || !instructions || !filePath) {
            showError('Please complete all required fields');
            return;
        }
    
        try {
            processButton.disabled = true;
            processButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Processing...';
    
            const payload = {
                file_path: filePath,
                api_key: apiKey,
                instructions: instructions,
                gpt_model: document.getElementById('gpt_model').value,
                row_limit: parseInt(document.getElementById('row-limit').value) || null,
                additional_columns: additionalColumns  // Make sure this is being sent
            };
    
            console.log('Sending payload:', payload); // Add this debug log
    
            socket.emit('start_processing', payload);
    
        } catch (error) {
            console.error('Processing error:', error);
            showError(error.message || 'Processing failed');
            processButton.disabled = false;
            processButton.innerHTML = 'Start Processing';
        }
    });    
// Add this right after the processForm handler
uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    console.log('Upload form submitted');

    const formData = new FormData();
    const file = fileInput.files[0];

    if (!file) {
        showError('Please select a file');
        return;
    }

    console.log('File selected:', file.name);
    formData.append('file', file);

    try {
        uploadButton.disabled = true;
        uploadButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Uploading...';

        const response = await fetch('/upload', {
            method: 'POST',
            body: formData,
            credentials: 'include'  // Important for session handling
        });

        console.log('Upload response status:', response.status);

        if (response.redirected) {
            window.location.href = response.url;
            return;
        }

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Upload failed');
        }

        const data = await response.json();
        console.log('Upload response data:', data);

        if (data.file_path) {
            document.getElementById('file_path').value = data.file_path;
            showNotification('File uploaded successfully! Please configure your analysis settings.', 'success');
            configSection.style.display = 'block';
            processButton.disabled = false;
        }
    } catch (error) {
        console.error('Upload error:', error);
        showError(error.message || 'Failed to upload file');
    } finally {
        uploadButton.disabled = false;
        uploadButton.innerHTML = 'Upload & Configure';
    }
});

    // Add the additional columns handler
    numAdditionalColumns.addEventListener('change', () => {
        additionalColumnsContainer.innerHTML = '';
        const numColumns = parseInt(numAdditionalColumns.value);

        for (let i = 0; i < numColumns; i++) {
            const columnHtml = `
                <div class="additional-column mb-4 p-3 border rounded">
                    <h6 class="mb-3">Additional Column ${i + 1}</h6>
                    <div class="mb-3">
                        <label class="form-label">Column Name</label>
                        <input type="text" class="form-control column-name" placeholder="Enter column name" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Analysis Instructions</label>
                        <textarea class="form-control column-instructions" rows="3" placeholder="Enter specific instructions for this column" required></textarea>
                    </div>
                </div>
            `;
            additionalColumnsContainer.innerHTML += columnHtml;
        }
    });

    // Add file input change listener
    fileInput.addEventListener('change', (e) => {
        console.log('File input changed:', e.target.files[0]?.name);
    });

    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
        resetUI();
        if (socket.connected) {
            socket.disconnect();
        }
    });

} // Close initializeApp function

// Initialize everything when the DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        console.log('DOM Content Loaded - Starting initialization');
        initializeApp();
    });
} else {
    console.log('DOM already loaded - Starting initialization immediately');
    initializeApp();
}
