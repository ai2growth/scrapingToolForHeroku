// Initialize Socket.IO connection
const socket = io();

// Get progress elements
const progressBar = document.querySelector('#scraping-progress .progress-bar');
const progressText = document.getElementById('progress-text');
const progressDiv = document.getElementById('scraping-progress');

// Listen for scraping progress events
socket.on('scraping_progress', function(data) {
    // Show progress div if hidden
    progressDiv.style.display = 'block';
    
    // Update progress bar
    const percentage = Math.round((data.current / data.total) * 100);
    progressBar.style.width = `${percentage}%`;
    progressBar.setAttribute('aria-valuenow', percentage);
    progressBar.textContent = `${percentage}%`;
    
    // Update text
    progressText.textContent = `Scraped: ${data.current} of ${data.total} websites`;
});

// Listen for completion
socket.on('scraping_complete', function() {
    progressBar.classList.remove('progress-bar-animated');
    progressText.textContent = 'Scraping complete! Analyzing with GPT...';
});

// Listen for errors
socket.on('scraping_error', function(data) {
    progressText.textContent = `Error: ${data.message}`;
    progressBar.classList.remove('progress-bar-animated');
    progressBar.classList.add('bg-danger');
});

// Reset progress when starting new process
function resetProgress() {
    progressDiv.style.display = 'none';
    progressBar.style.width = '0%';
    progressBar.setAttribute('aria-valuenow', 0);
    progressBar.textContent = '0%';
    progressBar.classList.add('progress-bar-animated');
    progressBar.classList.remove('bg-danger');
    progressText.textContent = 'Starting...';
}