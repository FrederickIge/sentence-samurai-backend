const API_BASE = window.location.origin;
let selectedFiles = [];
let currentJobId = null;

document.addEventListener('DOMContentLoaded', () => {
    setupFileUpload();
    checkHealth();
});

async function checkHealth() {
    const statusEl = document.getElementById('serverStatus');
    try {
        const response = await fetch(`${API_BASE}/`);
        const data = await response.json();
        statusEl.textContent = 'Server Online';
        statusEl.className = 'status-badge status-healthy';
        document.getElementById('endpointUrl').textContent = API_BASE;
    } catch (error) {
        statusEl.textContent = 'Server Offline';
        statusEl.className = 'status-badge status-error';
    }
}

function setupFileUpload() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    uploadArea.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = '#4facfe';
    });
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.style.borderColor = 'rgba(255, 255, 255, 0.2)';
    });
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = 'rgba(255, 255, 255, 0.2)';
        handleFiles(e.dataTransfer.files);
    });
    fileInput.addEventListener('change', (e) => handleFiles(e.target.files));
}

function handleFiles(files) {
    selectedFiles = Array.from(files).filter(f => f.type.startsWith('image/'));
    updateFileList();
    document.getElementById('processBtn').disabled = selectedFiles.length === 0;
}

function updateFileList() {
    const fileList = document.getElementById('fileList');
    fileList.innerHTML = selectedFiles.map((file, index) => `
        <div class="file-item">
            <span>${file.name}</span>
            <button onclick="selectedFiles.splice(${index}, 1); updateFileList();" style="background:none;border:none;color:#888;cursor:pointer;">Remove</button>
        </div>
    `).join('');
}

async function processManga() {
    const title = document.getElementById('mangaTitle').value || null;
    const formData = new FormData();
    selectedFiles.forEach(file => formData.append('files', file));
    if (title) formData.append('title', title);

    const progressContainer = document.getElementById('progressContainer');
    const progressText = document.getElementById('progressText');
    const resultArea = document.getElementById('resultArea');
    const processBtn = document.getElementById('processBtn');

    progressContainer.classList.remove('hidden');
    progressText.classList.remove('hidden');
    resultArea.classList.add('hidden');
    processBtn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/process-manga`, {
            method: 'POST',
            body: formData
        });
        const { job_id } = await response.json();
        currentJobId = job_id;
        await pollJobStatus(job_id);
    } catch (error) {
        console.error('Processing error:', error);
        progressContainer.classList.add('hidden');
        progressText.classList.add('hidden');
        processBtn.disabled = false;
        alert('Failed to process manga: ' + error.message);
    }
}

async function pollJobStatus(jobId) {
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    const progressContainer = document.getElementById('progressContainer');
    const resultArea = document.getElementById('resultArea');
    const processBtn = document.getElementById('processBtn');

    const interval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/job/${jobId}`);
            const data = await response.json();
            progressFill.style.width = data.progress + '%';
            progressText.textContent = `Processing... ${data.progress}%`;

            if (data.status === 'completed') {
                clearInterval(interval);
                showResults(jobId);
            } else if (data.status === 'failed') {
                clearInterval(interval);
                progressContainer.classList.add('hidden');
                progressText.classList.add('hidden');
                processBtn.disabled = false;
                alert('Processing failed: ' + (data.error || 'Unknown error'));
            }
        } catch (error) {
            clearInterval(interval);
            console.error('Polling error:', error);
        }
    }, 1000);
}

function showResults(jobId) {
    document.getElementById('progressContainer').classList.add('hidden');
    document.getElementById('progressText').classList.add('hidden');
    document.getElementById('resultArea').classList.remove('hidden');
    document.getElementById('processBtn').disabled = false;
    document.getElementById('viewHtmlLink').href = `${API_BASE}/html/${jobId}`;
    document.getElementById('downloadLink').href = `${API_BASE}/download/${jobId}`;
    document.getElementById('previewCard').classList.remove('hidden');
    document.getElementById('previewFrame').src = `${API_BASE}/html/${jobId}`;
}
