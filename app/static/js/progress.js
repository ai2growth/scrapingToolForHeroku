// progress.js

// ========================================
// Global Variables
// ========================================
let socket;
let progressTimeout;
let lastProgressUpdate = Date.now();

// Socket Reconnection Variables
const MAX_RECONNECTION_ATTEMPTS = 5;
let reconnectionAttempts = 0;
let isReconnecting = false;

// ========================================
// Helper Functions
// ========================================

/**
 * Capitalizes the first letter of a string.
 * @param {string} string - The string to capitalize.
 * @returns {string} - The capitalized string.
 */
function capitalizeFirstLetter(string) {
    return string.charAt(0).toUpperCase() + string.slice(1);
}

/**
 * Displays an error message to the user.
 * @param {string} message - The error message to display.
 */
function showError(message) {
    console.error('Error:', message);
    const alertContainer = document.getElementById('alert-container');
    if (alertContainer) {
        const alert = document.createElement('div');
        alert.className = 'alert alert-danger alert-dismissible fade show';
        alert.role = 'alert';
        alert.innerHTML = `
            <strong>Error:</strong> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        alertContainer.appendChild(alert);

        // Automatically dismiss after 5 seconds
        setTimeout(() => {
            alert.remove();
        }, 5000);
    } else {
        console.warn('Alert container not found.');
    }
}

/**
 * Displays a notification message to the user.
 * @param {string} message - The notification message.
 * @param {string} type - The type of alert ('success', 'info', etc.).
 */
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
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        alertContainer.appendChild(alert);

        // Automatically dismiss after 5 seconds
        setTimeout(() => {
            alert.remove();
        }, 5000);
    } else {
        console.warn('Alert container not found.');
    }
}

// ========================================
// Form Validation Functions
// ========================================

/**
 * Validates the process form data.
 * @param {FormData} formData - The form data to validate.
 * @returns {Object} - An object containing validation errors.
 */
function validateProcessForm(formData) {
    // Add form validation logging
    console.log('Validating form data:', {
        apiKey: !!formData.get('api_key'),
        instructions: !!formData.get('instructions'),
        filePath: !!formData.get('file_path'),
        gptModel: formData.get('gpt_model'),
        rowLimit: formData.get('row_limit')
    }); 

    const errors = {};
    
    // API Key validation
    const apiKey = formData.get('api_key');
    if (!apiKey?.trim()) {
        errors.api_key = 'API key is required';
        console.warn('Validation Error: API key is missing or empty.');
    }
    
    // Instructions validation
    const instructions = formData.get('instructions');
    if (!instructions?.trim()) {
        errors.instructions = 'Instructions are required';
        console.warn('Validation Error: Instructions are missing or empty.');
    }
    
    // File path validation
    const filePath = formData.get('file_path');
    if (!filePath) {
        errors.file_path = 'Please upload a file first';
        console.warn('Validation Error: File path is missing.');
    }
    
    // GPT Model validation
    const gptModel = formData.get('gpt_model');
    if (!gptModel) {
        errors.gpt_model = 'Please select a GPT model';
        console.warn('Validation Error: GPT model is not selected.');
    }
    
    // Row limit validation
    const rowLimitValue = formData.get('row_limit');
    const rowLimit = parseInt(rowLimitValue, 10);
    if (isNaN(rowLimit) || rowLimit < 1) {
        errors.row_limit = 'Please enter a valid number of rows';
        console.warn(`Validation Error: Invalid row limit value "${rowLimitValue}".`);
    }
    
    // Log the errors object if there are any validation errors
    if (Object.keys(errors).length > 0) {
        console.log('Form Validation Errors:', errors);
    } else {
        console.log('Form validation passed with no errors.');
    }
    
    return errors;
}

/**
 * Displays form validation errors on the UI.
 * @param {Object} errors - An object containing validation errors.
 */
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

/**
 * Clears all form validation errors from the UI.
 */
function clearFormErrors() {
    document.querySelectorAll('.is-invalid').forEach(input => {
        input.classList.remove('is-invalid');
    });
    document.querySelectorAll('.invalid-feedback').forEach(feedback => {
        feedback.remove();
    });
}

// ========================================
// Additional Columns Management Functions
// ========================================

/**
 * Generates HTML for an additional analysis column.
 * @param {number} index - The index of the column.
 * @returns {string} - The HTML string for the column.
 */
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

/**
 * Handles the addition of additional analysis columns based on user selection.
 * @param {Event} event - The change event.
 */
function handleAddAdditionalColumns(event) {
    const num = parseInt(event.target.value, 10);
    const container = document.getElementById('additional-columns-container');
    container.innerHTML = ''; // Clear existing columns

    for (let i = 1; i <= num; i++) {
        container.insertAdjacentHTML('beforeend', generateColumnHTML(i));
    }
}

/**
 * Handles the removal of an additional analysis column.
 * @param {Event} event - The click event.
 */
function handleRemoveColumn(event) {
    if (event.target.classList.contains('remove-column-button')) {
        const index = event.target.getAttribute('data-index');
        const columnDiv = document.getElementById(`additional-column-${index}`);
        if (columnDiv) {
            columnDiv.remove();
        }
    }
}

// ========================================
// Reset UI Function Enhancements
// ========================================

/**
 * Resets the UI to its initial state.
 */
function resetUI() {
    // Reset upload form
    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        uploadForm.reset();
    }

    // Reset file input
    const fileInput = document.getElementById('file-input');
    if (fileInput) {
        fileInput.value = '';
    }

    // Reset upload button
    const uploadButton = document.getElementById('upload-button');
    if (uploadButton) {
        uploadButton.disabled = false;
        uploadButton.innerHTML = `
            <span class="spinner-border spinner-border-sm d-none" role="status" aria-hidden="true"></span>
            Upload & Configure
        `;
    }

    // Hide configuration section
    const configSection = document.getElementById('config-section');
    if (configSection) {
        configSection.style.display = 'none';
    }

    // Clear file info
    const fileInfo = document.getElementById('resultsMessage');
    if (fileInfo) {
        fileInfo.innerHTML = '';
    }

    // Reset process button
    const processButton = document.getElementById('process-button');
    if (processButton) {
        processButton.disabled = false;
        processButton.textContent = 'Start Processing';
    }

    // Clear alerts
    const alertContainer = document.getElementById('alert-container');
    if (alertContainer) {
        alertContainer.innerHTML = '';
    }

    // Clear form errors
    clearFormErrors();

    // Hide progress elements
    const progressDiv = document.getElementById('overall-progress');
    const operationStatus = document.getElementById('operation-status');
    const progressTimestamp = document.getElementById('progress-timestamp');
    if (progressDiv) progressDiv.style.display = 'none';
    if (operationStatus) operationStatus.style.display = 'none';
    if (progressTimestamp) progressTimestamp.textContent = '';

    // Stop progress monitoring
    stopProgressMonitoring();
}

// ========================================
// Validate Form Function
// ========================================

/**
 * Validates the upload form before submission.
 * @returns {boolean} - True if the form is valid, false otherwise.
 */
function validateForm() {
    const fileInput = document.getElementById('file-input');
    if (!fileInput || !fileInput.files || !fileInput.files[0]) {
        showError('Please select a file to upload.');
        return false;
    }

    const file = fileInput.files[0];
    if (!file.name.toLowerCase().endsWith('.csv')) {
        showError('Please upload a CSV file.');
        return false;
    }

    return true;
}

// ========================================
// Socket Connection Verification Function
// ========================================

/**
 * Verifies if the Socket.IO connection is active.
 * @returns {boolean} - True if connected, false otherwise.
 */
function verifySocketConnection() {
    console.log('Socket state:', {
        exists: !!socket,
        connected: socket?.connected,
        id: socket?.id
    });
    
    if (socket && socket.connected) {
        return true;
    } else {
        showError('Socket connection lost. Please refresh the page.');
        return false;
    }
}

// ========================================
// Socket Status Indicator Functions
// ========================================

/**
 * Updates the socket status indicator in the UI.
 * @param {string} status - The current socket status.
 */
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

// ========================================
// Progress Monitoring Functions
// ========================================

/**
 * Starts monitoring the progress by checking for updates.
 */
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

/**
 * Stops monitoring the progress.
 */
function stopProgressMonitoring() {
    console.log('Stopping progress monitoring...');
    clearInterval(progressTimeout);
    progressTimeout = null;
    lastProgressUpdate = Date.now();
}

/**
 * Updates the progress timestamp display.
 */
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

// ========================================
// Handle Upload Function
// ========================================

/**
 * Handles the upload form submission.
 * @param {FormData} formData - The form data containing the file.
 * @param {File} file - The selected file.
 */
function handleUpload(formData, file) {
    const uploadButton = document.getElementById('upload-button');
    const uploadSpinner = uploadButton.querySelector('.spinner-border');

    // Show spinner
    uploadSpinner.classList.remove('d-none');
    uploadButton.disabled = true;
    uploadButton.innerHTML = `
        <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
        Uploading & Configure
    `;

    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            showError(data.error);
            return;
        }
        document.getElementById('file_path').value = data.file_path;

        const fileInfo = document.getElementById('resultsMessage');
        if (fileInfo) {
            fileInfo.innerHTML = `
                <div class="alert alert-info">
                    <strong>File loaded:</strong> ${data.row_count} rows
                    <br>
                    <small>Available columns: ${data.columns.join(', ')}</small>
                </div>
            `;
        }
        document.getElementById('config-section').style.display = 'block';
        showNotification('File uploaded successfully! Configure your analysis settings.', 'success');
    })
    .catch(error => {
        console.error('Upload error:', error);
        showError('Upload failed. Please try again.');
    })
    .finally(() => {
        // Hide spinner
        uploadSpinner.classList.add('d-none');
        uploadButton.disabled = false;
        uploadButton.innerHTML = `
            <span class="spinner-border spinner-border-sm d-none" role="status" aria-hidden="true"></span>
            Upload & Configure
        `;
    });
}

// ========================================
// Handle Process Function
// ========================================

/**
 * Handles the process form submission.
 * @param {FormData} formData - The form data containing processing parameters.
 */
function handleProcess(formData) {
    // Add validation check at the start
    const errors = validateProcessForm(formData);
    if (Object.keys(errors).length > 0) {
        showFormErrors(errors);
        return;
    }

    // Prepare payload
    const payload = {
        api_key: formData.get('api_key'),
        gpt_model: formData.get('gpt_model'),
        instructions: formData.get('instructions'),
        file_path: formData.get('file_path'),
        row_limit: parseInt(formData.get('row_limit'), 10) || null,
        additional_columns: []
    };

    // Add additional columns if any
    const numColumns = parseInt(document.getElementById('num-additional-columns').value, 10) || 0;
    for (let i = 1; i <= numColumns; i++) {
        const nameField = document.getElementById(`additional-column-${i}-name`);
        const instructionsField = document.getElementById(`additional-column-${i}-instructions`);
        
        if (nameField && instructionsField && nameField.value && instructionsField.value) {
            payload.additional_columns.push({
                name: nameField.value,
                instructions: instructionsField.value
            });
        }
    }

    console.log('Emitting start_processing with payload:', payload); // Debug log

    // Update UI to processing state
    const processButton = document.getElementById('process-button');
    processButton.disabled = true;
    processButton.textContent = 'Processing...';

    // Show progress elements
    const progressDiv = document.getElementById('overall-progress');
    const progressBar = progressDiv.querySelector('.progress-bar');
    const progressText = document.getElementById('overall-progress-text');
    const operationStatus = document.getElementById('current-operation');
    const progressTimestamp = document.getElementById('progress-timestamp');

    progressDiv.style.display = 'block';
    document.getElementById('operation-status').style.display = 'block';
    progressTimestamp.textContent = ''; // Clear previous timestamp

    progressBar.style.width = '0%';
    progressBar.textContent = '0%';
    progressText.textContent = 'Processing started...';
    operationStatus.textContent = 'Initializing...';

    // Emit the processing event with a callback for acknowledgment
    socket.emit('start_processing', payload, function(response) {
        console.log('Server acknowledged start_processing:', response);
        
        if (!response) {
            showError('No response from server');
            resetUI();
            return;
        }

        if (response.status === 'error') {
            showError(response.error || 'Failed to start processing');
            resetUI();
            return;
        }

        if (response.status !== 'ok') {
            showError('Unexpected server response');
            resetUI();
            return;
        }

        showNotification('Processing started successfully', 'success');
        startProgressMonitoring();
    });
}

// ========================================
// Initialize Application with Debug Enhancements
// ========================================

/**
 * Initializes the application, setting up event listeners and Socket.IO connections.
 */
function initializeApp() {
    console.log('Starting app initialization...');

    // Debug form elements
    const uploadForm = document.getElementById('uploadForm');
    const processForm = document.getElementById('processForm');
    console.log('Forms found:', {
        uploadForm: !!uploadForm,
        processForm: !!processForm
    });

    // Add event listeners with debug logging
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(event) {
            console.log('Upload form submitted');
            event.preventDefault();
            
            const formData = new FormData(uploadForm);
            const file = document.getElementById('file-input').files[0];
            console.log('File selected:', file?.name);

            // Handle file upload
            handleUpload(formData, file);
        });
    }

    if (processForm) {
        processForm.addEventListener('submit', function(event) {
            console.log('Process form submitted');
            event.preventDefault();

            if (!verifySocketConnection()) {
                console.log('Socket connection verification failed');
                return;
            }

            const formData = new FormData(processForm);
            console.log('Form data:', {
                apiKey: !!formData.get('api_key'),
                gptModel: formData.get('gpt_model'),
                instructions: !!formData.get('instructions'),
                filePath: formData.get('file_path'),
                rowLimit: formData.get('row_limit')
            });

            // Handle process form submission
            handleProcess(formData);
        });
    }

    // Debug Socket.IO connection
    try {
        console.log('Initializing Socket.IO connection...');
        const serverUrl = window.socketConfig?.serverUrl || window.location.origin;
        const options = {
            transports: ['websocket', 'polling'],
            path: '/socket.io'
        };
        socket = io(serverUrl, options);

        // Socket.IO Event Listeners
        socket.on('connect', () => {
            console.log('Socket connected:', socket.id);
            updateSocketStatus('Connected');
            showNotification('Connected to server.', 'success');
        });

        socket.on('connect_error', (error) => {
            console.error('Socket connection error:', error);
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

        socket.on('error', (error) => {
            console.error('Socket error:', error);
            showError('Socket error occurred');
        });

        socket.on('processing_error', function(data) {
            console.error('Processing error:', data);
            showError(data.error || 'Processing failed');
            resetUI();
        });

        socket.on('scrape_count_updated', function(data) {
            console.log('Scrape count updated:', data);
            const scrapeCountElement = document.querySelector('.navbar-nav .nav-link span#scrape-count');
            if (scrapeCountElement) {
                scrapeCountElement.textContent = `Scrapes: ${data.scrapes_used}/${data.scrape_limit}`;
            }
        });

    } catch (error) {
        console.error('Socket initialization error:', error);
        showError('An error occurred while initializing the connection.');
    }
}

// ========================================
// Handle Upload Function
// ========================================

/**
 * Handles the upload form submission.
 * @param {FormData} formData - The form data containing the file.
 * @param {File} file - The selected file.
 */
function handleUpload(formData, file) {
    const uploadButton = document.getElementById('upload-button');
    const uploadSpinner = uploadButton.querySelector('.spinner-border');

    // Show spinner
    uploadSpinner.classList.remove('d-none');
    uploadButton.disabled = true;
    uploadButton.innerHTML = `
        <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
        Uploading & Configure
    `;

    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            showError(data.error);
            return;
        }
        document.getElementById('file_path').value = data.file_path;

        const fileInfo = document.getElementById('resultsMessage');
        if (fileInfo) {
            fileInfo.innerHTML = `
                <div class="alert alert-info">
                    <strong>File loaded:</strong> ${data.row_count} rows
                    <br>
                    <small>Available columns: ${data.columns.join(', ')}</small>
                </div>
            `;
        }
        document.getElementById('config-section').style.display = 'block';
        showNotification('File uploaded successfully! Configure your analysis settings.', 'success');
    })
    .catch(error => {
        console.error('Upload error:', error);
        showError('Upload failed. Please try again.');
    })
    .finally(() => {
        // Hide spinner
        uploadSpinner.classList.add('d-none');
        uploadButton.disabled = false;
        uploadButton.innerHTML = `
            <span class="spinner-border spinner-border-sm d-none" role="status" aria-hidden="true"></span>
            Upload & Configure
        `;
    });
}

// ========================================
// Handle Process Function
// ========================================

/**
 * Handles the process form submission.
 * @param {FormData} formData - The form data containing processing parameters.
 */
function handleProcess(formData) {
    // Add validation check at the start
    const errors = validateProcessForm(formData);
    if (Object.keys(errors).length > 0) {
        showFormErrors(errors);
        return;
    }

    // Prepare payload
    const payload = {
        api_key: formData.get('api_key'),
        gpt_model: formData.get('gpt_model'),
        instructions: formData.get('instructions'),
        file_path: formData.get('file_path'),
        row_limit: parseInt(formData.get('row_limit'), 10) || null,
        additional_columns: []
    };

    // Add additional columns if any
    const numColumns = parseInt(document.getElementById('num-additional-columns').value, 10) || 0;
    for (let i = 1; i <= numColumns; i++) {
        const nameField = document.getElementById(`additional-column-${i}-name`);
        const instructionsField = document.getElementById(`additional-column-${i}-instructions`);
        
        if (nameField && instructionsField && nameField.value && instructionsField.value) {
            payload.additional_columns.push({
                name: nameField.value,
                instructions: instructionsField.value
            });
        }
    }

    console.log('Emitting start_processing with payload:', payload); // Debug log

    // Update UI to processing state
    const processButton = document.getElementById('process-button');
    processButton.disabled = true;
    processButton.textContent = 'Processing...';

    // Show progress elements
    const progressDiv = document.getElementById('overall-progress');
    const progressBar = progressDiv.querySelector('.progress-bar');
    const progressText = document.getElementById('overall-progress-text');
    const operationStatus = document.getElementById('current-operation');
    const progressTimestamp = document.getElementById('progress-timestamp');

    progressDiv.style.display = 'block';
    document.getElementById('operation-status').style.display = 'block';
    progressTimestamp.textContent = ''; // Clear previous timestamp

    progressBar.style.width = '0%';
    progressBar.textContent = '0%';
    progressText.textContent = 'Processing started...';
    operationStatus.textContent = 'Initializing...';

    // Emit the processing event with a callback for acknowledgment
    socket.emit('start_processing', payload, function(response) {
        console.log('Server acknowledged start_processing:', response);
        
        if (!response) {
            showError('No response from server');
            resetUI();
            return;
        }

        if (response.status === 'error') {
            showError(response.error || 'Failed to start processing');
            resetUI();
            return;
        }

        if (response.status !== 'ok') {
            showError('Unexpected server response');
            resetUI();
            return;
        }

        showNotification('Processing started successfully', 'success');
        startProgressMonitoring();
    });
}

// ========================================
// Event Listener to Initialize App on DOMContentLoaded
// ========================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing app...');
    initializeApp();
});
