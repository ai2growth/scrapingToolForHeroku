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

    // 2. Socket.IO Setup
    socket = io();  // Assign to global variable
    console.log('Socket.IO initialized');

    socket.on('connect_error', (error) => {
        console.error('Socket connection error:', error);
        showError('Connection error. Please refresh the page.');
    });

    socket.on('disconnect', (reason) => {
        console.log('Socket disconnected:', reason);
        if (reason === 'io server disconnect') {
            socket.connect();
        }
    });

    function fetchScrapeCount() {
        if (!socket || !socket.connected) {
            console.warn('Socket not connected, retrying in 2 seconds...');
            setTimeout(fetchScrapeCount, 2000);
            return;
        }

        fetch('/get_scrape_count')
            .then(response => response.json())
            .then(data => {
                const scrapeCountElement = document.querySelector('.navbar-nav .nav-link span');
                if (scrapeCountElement) {
                    scrapeCountElement.textContent = `Scrapes: ${data.scrapes_used}/${data.scrape_limit}`;
                }
            })
            .catch(error => {
                console.error('Error fetching scrape count:', error);
                showError('Failed to fetch scrape count');
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
    
    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        console.log('Upload form submitted');
    
        if (!fileInput.files[0]) {
            showError('Please select a file');
            return;
        }
    
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
    
        try {
            uploadButton.disabled = true;
            uploadButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Uploading...';
    
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
    
            if (response.status === 302) {
                console.warn('Redirect detected. Navigating to login page...');
                window.location.href = '/auth/login';
                return;
            }
    
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Upload failed');
            }
    
            const data = await response.json();
            if (data.file_path) {
                document.getElementById('file_path').value = data.file_path;
                showNotification('File uploaded successfully! Please configure your analysis settings.', 'success');
                configSection.style.display = 'block';
                processButton.disabled = false;
            }
        } catch (error) {
            console.error('Upload error:', error);
            showError(error.message || 'An unexpected error occurred during upload');
        } finally {
            uploadButton.disabled = false;
            uploadButton.innerHTML = 'Upload & Configure';
        }
    });
    
    processForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        if (!verifySocketConnection()) {
            showError('Not connected to server. Please refresh the page.');
            return;
        }

        const apiKey = document.getElementById('api_key').value;
        const instructions = document.getElementById('instructions').value;

        if (!apiKey || !instructions) {
            showError('Please complete all required fields');
            return;
        }

        processButton.disabled = true;
        processButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Processing...';

        startProgressMonitoring();

        try {
            const payload = {
                file_path: document.getElementById('file_path').value,
                api_key: apiKey,
                instructions: instructions,
                gpt_model: document.getElementById('gpt_model').value,
                row_limit: parseInt(document.getElementById('row-limit').value) || null,
                additional_columns: []
            };

            document.querySelectorAll('.additional-column').forEach(column => {
                const name = column.querySelector('.column-name').value;
                const instructions = column.querySelector('.column-instructions').value;
                if (name && instructions) {
                    payload.additional_columns.push({ name, instructions });
                }
            });
            const response = await fetch('/process', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error(await response.text());
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `analysis_results_${new Date().toISOString().slice(0, 10)}.csv`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            showNotification('Processing complete! File downloaded.', 'success');
        } catch (error) {
            console.error('Processing error:', error);
            showError(error.message);
        } finally {
            processButton.disabled = false;
            processButton.innerHTML = 'Start Processing';
            stopProgressMonitoring();
            setTimeout(resetUI, 5000);
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
