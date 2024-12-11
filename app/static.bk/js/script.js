document.getElementById('start-processing').addEventListener('click', async () => {
    const apiKey = document.getElementById('api-key').value;
    const selectedColumns = Array.from(document.querySelectorAll('#column-checkboxes input:checked')).map(
        checkbox => checkbox.value
    );
    const instructions = document.getElementById('instructions').value;
    const rowLimit = parseInt(document.getElementById('row-limit').value) || 0;

    if (!apiKey || !instructions) {
        alert('API Key and instructions are required.');
        return;
    }

    if (!selectedColumns.includes('websites') && !selectedColumns.includes('Websites')) {
        alert('A column named "Websites" or "websites" is required in your CSV.');
        return;
    }

    try {
        const response = await fetch('/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                api_key: apiKey,
                selected_columns: selectedColumns,
                instructions: instructions,
                row_limit: rowLimit,
                file_path: uploadedFilePath,
            }),
        });

        if (response.ok) {
            const data = await response.json();
            alert('Scraping task started successfully. Task ID: ' + data.task_id);
        } else {
            const error = await response.json();
            alert('Error: ' + (error.message || 'Processing failed.'));
        }
    } catch (err) {
        alert('Error: ' + err.message);
    }
});
