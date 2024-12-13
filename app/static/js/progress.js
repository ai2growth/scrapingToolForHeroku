// Global Variables
let socket;
let progressTimeout;
let lastProgressUpdate = Date.now();

// Socket Reconnection Variables
const MAX_RECONNECTION_ATTEMPTS = 5;
let reconnectionAttempts = 0;
let isReconnecting = false;

// Helper Functions
function showError(message) {
    console.error('Error:', message);
    const alertContainer = document.getElementById('alert-container');
    if (alertContainer) {
        const alert = document.createElement('div');
        alert.className = 'alert alert-danger alert-dismissible fade show';
        alert.role = 'alert';
        alert.innerHTML = `
            <strong>Error:</strong> ${message}
            <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                <span aria-hidden="true">&times;</span>
            </button>
        `;
        alertContainer.appendChild(alert);

        // Automatically dismiss after 5 seconds
        setTimeout(() => {
            $(alert).alert('close');
        }, 5000);
    } else {
        console.warn('Alert container not found.');
    }
}

function showNotification(message, type = 'success') {
    console.log(`${type}: ${message}`);
    const alertContainer = document.getElementById('alert-container');
    if (alertContainer) {
        const alert = document.createElement('div');
        const alertType = `alert-${type}`;
        alert.className = `alert ${alertType} alert-dismissible fade show`;
        alert.role = 'alert';
        alert.innerHTML = `
            <strong>${capitalizeFirstLetter(type)}:</strong> ${message}
            <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                <span aria-hidden="true">&times;</span>
            </button>
        `;
        alertContainer.appendChild(alert);

        // Automatically dismiss after 5 seconds
        setTimeout(() => {
            $(alert).alert('close');
        }, 5000);
    } else {
        console.warn('Alert container not found.');
    }
}

function capitalizeFirstLetter(string) {
    return string.charAt(0).toUpperCase() + string.slice(1);
}

// Form Validation Functions
function validateProcessForm(formData) {
    const errors = {};
    
    // API Key validation
    const apiKey = formData.get('api_key');
    if (!apiKey?.trim()) {
        errors.api_key = 'API key is required';
    }
    
    // Instructions validation
    const instructions = formData.get('instructions');
    if (!instructions?.trim()) {
        errors.instructions = 'Instructions are required';
    }
    
    // File path validation
    const filePath = formData.get('file_path');
    if (!filePath) {
        errors.file_path = 'Please upload a file first';
    }
    
    // GPT Model validation
    const gptModel = formData.get('gpt_model');
    if (!gptModel) {
        errors.gpt_model = 'Please select a GPT model';
    }
    
    // Row limit validation
    const rowLimit = parseInt(formData.get('row_limit'), 10);
    if (isNaN(rowLimit) || rowLimit < 1) {
        errors.row_limit = 'Please enter a valid number of rows';
    }
    
    return errors;
}

function showFormErrors(errors) {
    // Clear previous errors
    clearFormErrors();
    
    // Show new errors
    Object.entries(errors).forEach(([field, message]) => {
        const input = document.getElementById(field);
        if (input) {
            input.classList.add('is-invalid');
            const feedback = document.createElement('div');
            feedback.className = 'invalid-feedback';
            feedback.textContent = message;
            input.parentNode.appendChild(feedback);
        }
    });
}

function clearFormErrors() {
    document.querySelectorAll('.is-invalid').forEach(input => {
        input.classList.remove('is-invalid');
    });
    document.querySelectorAll('.invalid-feedback').forEach(feedback => {
        feedback.remove();
    });
}

// Additional Columns Management Functions
function generateColumnHTML(index) {
    return `
        <div class="form-row align-items-center mb-3" id="additional-column-${index}">
            <div class="col-md-5">
                <label for="additional-column-${index}-name">Column ${index} Name</label>
                <input type="text" class="form-control" id="additional-column-${index}-name" name="additionalColumn${index}Name" required>
            </div>
            <div class="col-md-5">
                <label for="additional-column-${index}-instructions">Column ${index} Instructions</label>
                <input type="text" class="form-control" id="additional-column-${index}-instructions" name="additionalColumn${index}Instructions" required>
            </div>
            <div class="col-md-2 d-flex align-items-end">
                <button type="button" class="btn btn-danger remove-column-button" data-index="${index}" aria-label="Remove Column ${index}">Remove</button>
            </div>
        </div>
    `;
}

function handleAddAdditionalColumns(event) {
    const num = parseInt(event.target.value, 10);
    const container = document.getElementById('additional-columns-container');
    container.innerHTML = ''; // Clear existing columns

    for (let i = 1; i <= num; i++) {
        container.insertAdjacentHTML('beforeend', generateColumnHTML(i));
    }
}

function handleRemoveColumn(event) {
    if (event.target.classList.contains('remove-column-button')) {
        const index = event.target.getAttribute('data-index');
        const columnDiv = document.getElementById(`additional-column-${index}`);
        if (columnDiv) {
            columnDiv.remove();
        }
    }
}

// Reset UI Function Enhancements
function resetUI() {
    const progressBar = document.querySelector('#overall-progress .progress-bar');
    const progressText = document.getElementById('overall-progress-text');
    const operationStatus = document.getElementById('current-operation');

    if (progressBar) {
        progressBar.style.width = '0%';
        progressBar.textContent = '0%';
        progressBar.classList.remove('bg-success', 'bg-danger');
    }

    if (progressText) {
        progressText.textContent = '';
    }

    if (operationStatus) {
        operationStatus.textContent = '';
    }

    const processButton = document.getElementById('process-button');
    if (processButton) {
        processButton.disabled = false;
        processButton.textContent = 'Start Processing';
    }

    const overallProgress = document.getElementById('overall-progress');
    const operationStatusDiv = document.getElementById('operation-status');
    if (overallProgress) overallProgress.style.display = 'none';
    if (operationStatusDiv) operationStatusDiv.style.display = 'none';

    // Clear all form inputs
    const processForm = document.getElementById('processForm');
    if (processForm) {
        processForm.reset();
    }

    // Reset file input
    const fileInput = document.getElementById('file-input');
    if (fileInput) {
        fileInput.value = '';
    }

    // Clear additional columns
    const additionalColumnsContainer = document.getElementById('additional-columns-container');
    if (additionalColumnsContainer) {
        additionalColumnsContainer.innerHTML = '';
    }

    // Clear any existing alerts
    const alertContainer = document.getElementById('alert-container');
    if (alertContainer) {
        alertContainer.innerHTML = '';
    }

    // Clear Socket Status Indicator
    updateSocketStatus('Disconnected');

    stopProgressMonitoring();
}

// Socket Connection Verification Function
function verifySocketConnection() {
    if (socket && socket.connected) {
        return true;
    } else {
        showError('Socket is not connected. Please check your connection.');
        return false;
    }
}

// Socket Status Indicator Functions
function updateSocketStatus(status) {
    const statusIndicator = document.querySelector('#socket-status .status-indicator');
    const statusText = document.querySelector('#socket-status .status-text');

    if (statusIndicator && statusText) {
        statusText.textContent = status;
        statusIndicator.className = 'status-indicator'; // Reset classes

        switch (status) {
            case 'Connected':
                statusIndicator.classList.add('connected');
                break;
            case 'Disconnected':
                statusIndicator.classList.add('disconnected');
                break;
            case 'Reconnecting...':
            case 'Reconnecting... (n)':
                statusIndicator.classList.add('reconnecting');
                break;
            default:
                statusIndicator.classList.add('unknown');
        }
    }
}

// Progress Monitoring Functions
function startProgressMonitoring() {
    console.log('Starting progress monitoring...');
    progressTimeout = setInterval(() => {
        const now = Date.now();
        if (now - lastProgressUpdate > 10000) { // 10 seconds without update
            showError('No progress updates received. The process might be stuck.');
            stopProgressMonitoring();
        }
    }, 5000); // Check every 5 seconds
}

function stopProgressMonitoring() {
    console.log('Stopping progress monitoring...');
    clearInterval(progressTimeout);
    lastProgressUpdate = Date.now();
}

function updateProgressTimestamp() {
    lastProgressUpdate = Date.now();
    const timestampElement = document.getElementById('progress-timestamp');
    if (timestampElement) {
        const now = new Date();
        timestampElement.textContent = `Last update: ${now.toLocaleTimeString()}`;
    } else {
        console.warn('Progress timestamp element not found.');
    }
}

// Initialize the application when the DOM is fully loaded
function initializeApp() {
    console.log('Starting app initialization...');

    // Element References
    const uploadForm = document.getElementById('uploadForm');
    const fileInput = document.getElementById('file-input');
    const uploadButton = document.getElementById('upload-button');
    const processForm = document.getElementById('processForm');
    const processButton = document.getElementById('process-button');
    const numAdditionalColumns = document.getElementById('num-additional-columns');
    const additionalColumnsContainer = document.getElementById('additional-columns-container');

    console.log('Elements found:', {
        uploadForm: !!uploadForm,
        fileInput: !!fileInput,
        uploadButton: !!uploadButton,
        processForm: !!processForm,
        processButton: !!processButton,
        numAdditionalColumns: !!numAdditionalColumns,
        additionalColumnsContainer: !!additionalColumnsContainer
    });

    try {
        const serverUrl = window.socketConfig?.serverUrl || window.location.origin;
        const options = {
            autoConnect: false,
            transports: ['websocket', 'polling'],
            reconnection: true,
            reconnectionAttempts: MAX_RECONNECTION_ATTEMPTS,
            reconnectionDelay: 1000,
            timeout: 20000,
            path: '/socket.io',
            namespace: '/',
            forceNew: true
        };

        // Global socket initialization
        socket = io(serverUrl, options);

        // Set a timeout to check for connection issues
        const connectionTimeout = setTimeout(() => {
            if (!socket || !socket.connected) {
                showError('Failed to connect to server. Please refresh the page.');
                updateSocketStatus('Disconnected');
            }
        }, 5000);

        // Event listeners for Socket.IO
        socket.on('connect', () => {
            clearTimeout(connectionTimeout);
            console.log('Socket connected successfully:', socket.id);
            showNotification('Connected to server.', 'success');
            reconnectionAttempts = 0;
            isReconnecting = false;
            updateSocketStatus('Connected');
        });

        socket.on('connect_error', (error) => {
            console.warn('Socket connection error:', error);
            showError('Unable to connect to the server. Please try again later.');
            if (reconnectionAttempts < MAX_RECONNECTION_ATTEMPTS && !isReconnecting) {
                isReconnecting = true;
                showNotification('Attempting to reconnect...', 'warning');
                updateSocketStatus('Reconnecting...');
            }
        });

        socket.on('reconnect_attempt', () => {
            reconnectionAttempts += 1;
            showNotification(`Reconnection attempt ${reconnectionAttempts} of ${MAX_RECONNECTION_ATTEMPTS}...`, 'warning');
            updateSocketStatus(`Reconnecting... (${reconnectionAttempts})`);
        });

        socket.on('reconnect_failed', () => {
            showError('Failed to reconnect to the server. Please refresh the page.');
            isReconnecting = false;
            updateSocketStatus('Disconnected');
        });

        socket.on('disconnect', (reason) => {
            console.log('Socket disconnected:', reason);
            showError('Disconnected from server.');
            if (reason === 'io server disconnect') {
                // The disconnection was initiated by the server, need to reconnect manually
                socket.connect();
            }
            // Cleanup existing processes if any
            resetUI();
            updateSocketStatus('Disconnected');
        });

        // Processing event handlers
        socket.on('processing_progress', function(data) {
            console.log('Processing progress:', data);
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
            progressBar.style.width = `${percentage}%`;
            progressBar.textContent = `${percentage}%`;
            progressText.textContent = `Processing row ${data.current} of ${data.total}`;
            operationStatus.textContent = data.current === 1 ? 'Starting process...' : `Processing row ${data.current}`;
        });

        socket.on('processing_complete', function(data) {
            console.log('Processing complete:', data);
            if (data && data.csv_data) {
                const blob = new Blob([data.csv_data], { type: 'text/csv' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `analysis_results_${new Date().toISOString().slice(0,10)}.csv`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                
                showNotification('Processing complete! Your file is downloading.', 'success');
            }
            resetUI();
        });

        socket.on('processing_error', function(data) {
            console.error('Processing error:', data);
            showError(data.error || 'Processing failed');
            resetUI();
        });

        socket.on('scrape_count_updated', function(data) {
            console.log('Scrape count updated:', data);
            const scrapeCountElement = document.querySelector('.navbar-nav .nav-link span');
            if (scrapeCountElement) {
                scrapeCountElement.textContent = `Scrapes: ${data.scrapes_used}/${data.scrape_limit}`;
            }
        });

        // Connect to the server
        socket.connect();

        // Form Handlers

        // Upload Form Submission Handler
        if (uploadForm && fileInput && uploadButton) {
            uploadForm.addEventListener('submit', function(event) {
                event.preventDefault();
                // No need to verify socket connection since using fetch
                const file = fileInput.files[0];
                if (!file) {
                    showError('Please select a file to upload.');
                    return;
                }

                // Validate file type and size if necessary
                const allowedTypes = ['text/csv', 'application/vnd.ms-excel'];
                if (!allowedTypes.includes(file.type)) {
                    showError('Invalid file type. Please upload a CSV file.');
                    return;
                }

                if (file.size > 5 * 1024 * 1024) { // 5MB limit
                    showError('File size exceeds 5MB limit.');
                    return;
                }

                uploadButton.disabled = true;
                uploadButton.textContent = 'Uploading...';

                const formData = new FormData();
                formData.append('file', file);

                fetch('/upload', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.file_path && data.columns && data.row_count) {
                        // Store file path
                        document.getElementById('file_path').value = data.file_path;
                        
                        // Update file info
                        document.getElementById('file-info').innerHTML = `
                            <div class="alert alert-info">
                                <strong>File loaded:</strong> ${data.row_count} rows
                                <br>
                                <small>Available columns: ${data.columns.join(', ')}</small>
                            </div>
                        `;
                        
                        // Show config section and enable process button
                        document.getElementById('config-section').style.display = 'block';
                        document.getElementById('process-button').disabled = false;
                        
                        showNotification('File uploaded successfully! Configure your analysis settings.', 'success');
                    } else {
                        throw new Error(data.error || 'Invalid server response');
                    }
                    uploadButton.disabled = false;
                    uploadButton.textContent = 'Upload';
                })
                .catch(error => {
                    console.error('Upload error:', error);
                    showError(error.message || 'An error occurred during file upload.');
                    uploadButton.disabled = false;
                    uploadButton.textContent = 'Upload';
                });
            });
        }

        // Process Form Submission Handler
        if (processForm && processButton) {
            processForm.addEventListener('submit', function(event) {
                event.preventDefault();
                if (!verifySocketConnection()) {
                    return;
                }

                // Gather form data
                const formData = new FormData(processForm);
                const apiKey = formData.get('api_key'); // Assuming 'api_key' is the field name
                const instructions = formData.get('instructions'); // Assuming 'instructions' is the field name
                const filePath = formData.get('file_path'); // Assuming 'file_path' is the hidden input field
                const gptModel = formData.get('gpt_model'); // New field
                const rowLimit = parseInt(formData.get('row_limit'), 10); // New field
                const numColumns = parseInt(numAdditionalColumns.value, 10) || 0;
                const additionalColumns = [];

                for (let i = 1; i <= numColumns; i++) {
                    const columnName = formData.get(`additionalColumn${i}Name`);
                    const columnInstructions = formData.get(`additionalColumn${i}Instructions`);
                    if (columnName && columnInstructions) {
                        additionalColumns.push({ name: columnName, instructions: columnInstructions });
                    } else {
                        showError(`Please fill in all fields for Additional Column ${i}.`);
                        return;
                    }
                }

                // Validate necessary fields
                const errors = validateProcessForm(formData);
                if (Object.keys(errors).length > 0) {
                    showFormErrors(errors);
                    return;
                }

                processButton.disabled = true;
                processButton.textContent = 'Processing...';

                // Initialize progress bar
                const progressDiv = document.getElementById('overall-progress');
                const progressBar = progressDiv.querySelector('.progress-bar');
                const progressText = document.getElementById('overall-progress-text');
                const operationStatus = document.getElementById('current-operation');

                progressDiv.style.display = 'block';
                document.getElementById('operation-status').style.display = 'block';

                progressBar.style.width = '0%';
                progressBar.textContent = '0%';
                progressText.textContent = 'Processing started...';
                operationStatus.textContent = 'Initializing...';

                // Emit processing event with proper payload
                socket.emit('start_processing', { 
                    api_model: gptModel, // Matching Python backend field
                    row_limit: rowLimit, 
                    api_key: apiKey, 
                    instructions: instructions, 
                    file_path: filePath, 
                    additional_columns: additionalColumns 
                }, (response) => {
                    if (response.status !== 'ok') {
                        showError(response.error || 'Processing failed to start.');
                        resetUI();
                    } else {
                        showNotification('Processing started.', 'info');
                        startProgressMonitoring();
                    }
                });
            });
        }

        // Additional Columns Handler
        if (numAdditionalColumns && additionalColumnsContainer) {
            numAdditionalColumns.addEventListener('change', handleAddAdditionalColumns);
            additionalColumnsContainer.addEventListener('click', handleRemoveColumn);
        }

    } catch (error) {
        console.error('Error initializing the app:', error);
        showError('An unexpected error occurred during initialization.');
    }

    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
        if (socket && socket.connected) {
            socket.disconnect();
        }
    });
}

// Initialize the application when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', initializeApp);
