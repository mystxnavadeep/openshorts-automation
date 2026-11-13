/**
 * OpenShorts Automation Dashboard
 * Communicates ONLY with local/Tailscale backend API.
 * Never handles GitHub tokens or Gemini API keys directly in frontend.
 */

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const form = document.getElementById('processForm');
    const videoUrlInput = document.getElementById('videoUrl');
    const pasteBtn = document.getElementById('pasteBtn');
    const urlFeedback = document.getElementById('urlFeedback');
    const submitBtn = document.getElementById('submitBtn');
    const submitBtnText = document.getElementById('submitBtnText');
    const submissionAlert = document.getElementById('submissionAlert');

    const tailscaleBadge = document.getElementById('tailscaleBadge');
    const tailscaleText = document.getElementById('tailscaleText');
    const githubBadge = document.getElementById('githubBadge');
    const githubText = document.getElementById('githubText');
    const repoLink = document.getElementById('repoLink');

    const activeRunContainer = document.getElementById('activeRunContainer');
    const activeRunTitle = document.getElementById('activeRunTitle');
    const activeRunBadge = document.getElementById('activeRunBadge');
    const runGithubLink = document.getElementById('runGithubLink');
    const runGdriveLink = document.getElementById('runGdriveLink');
    const runArtifactLink = document.getElementById('runArtifactLink');

    const runsList = document.getElementById('runsList');
    const refreshRunsBtn = document.getElementById('refreshRunsBtn');

    let pollInterval = null;
    let monitoredRunId = null;

    // 1. Initialize System & Health Status
    async function initSystem() {
        try {
            const configResp = await fetch('/api/config');
            if (configResp.ok) {
                const config = await configResp.json();
                if (config.github_owner && config.github_repo) {
                    repoLink.href = `https://github.com/${config.github_owner}/${config.github_repo}`;
                    repoLink.textContent = `${config.github_owner}/${config.github_repo}`;
                }
            }

            const healthResp = await fetch('/api/health');
            if (healthResp.ok) {
                const health = await healthResp.json();
                
                // Tailscale status
                if (health.tailscale && health.tailscale.active) {
                    tailscaleBadge.className = 'status-badge online';
                    tailscaleText.textContent = `Tailscale: ${health.tailscale.ip}`;
                } else {
                    tailscaleBadge.className = 'status-badge checking';
                    tailscaleText.textContent = 'Tailnet / Local';
                }

                // GitHub API status
                if (health.github && health.github.authenticated) {
                    githubBadge.className = 'status-badge online';
                    githubText.textContent = 'GitHub: Connected';
                } else {
                    githubBadge.className = 'status-badge offline';
                    githubText.textContent = 'GitHub: Token Required';
                }
            }
        } catch (err) {
            console.warn('Health check failed:', err);
            tailscaleBadge.className = 'status-badge offline';
            tailscaleText.textContent = 'Backend Offline';
        }
    }

    // 2. Clipboard Paste Handler
    if (pasteBtn && navigator.clipboard) {
        pasteBtn.addEventListener('click', async () => {
            try {
                const text = await navigator.clipboard.readText();
                if (text) {
                    videoUrlInput.value = text.trim();
                    validateUrl(text.trim());
                }
            } catch (e) {
                console.log('Clipboard permission not granted or unavailable:', e);
            }
        });
    }

    // 3. YouTube URL Live Validation
    videoUrlInput.addEventListener('input', (e) => {
        validateUrl(e.target.value.trim());
    });

    function validateUrl(url) {
        if (!url) {
            urlFeedback.textContent = 'Enter any standard YouTube video URL';
            urlFeedback.style.color = 'var(--text-muted)';
            return false;
        }

        const ytRegex = /^(https?:\/\/)?(www\.|m\.)?(youtube\.com\/(watch\?.*v=|shorts\/|embed\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})/;
        const match = url.match(ytRegex);

        if (match) {
            const videoId = match[5];
            urlFeedback.textContent = `✓ Valid YouTube Video (ID: ${videoId})`;
            urlFeedback.style.color = 'var(--accent-green)';
            return true;
        } else {
            urlFeedback.textContent = '⚠️ Invalid URL. Must be a single YouTube video or Shorts link.';
            urlFeedback.style.color = 'var(--accent-amber)';
            return false;
        }
    }

    // 4. Submit Job Form
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const url = videoUrlInput.value.trim();
        if (!validateUrl(url)) {
            showAlert('Please enter a valid YouTube video URL before submitting.', 'error');
            return;
        }

        const payload = {
            url: url,
            output_format: document.getElementById('outputFormat').value,
            gemini_model: document.getElementById('geminiModel') ? document.getElementById('geminiModel').value : 'gemini-3.1-flash-lite',
            whisper_model: document.getElementById('whisperModel') ? document.getElementById('whisperModel').value : 'base',
            workers: document.getElementById('workers') ? document.getElementById('workers').value : '1',
            auto_hook: document.getElementById('autoHook').checked,
            gdrive_folder: document.getElementById('gdriveFolder').value.trim() || 'OpenShorts'
        };

        // UI Loading State
        submitBtn.disabled = true;
        submitBtnText.textContent = 'Dispatching to GitHub Actions...';
        hideAlert();

        try {
            const resp = await fetch('/api/process', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await resp.json();

            if (!resp.ok) {
                throw new Error(data.detail || 'Failed to dispatch workflow');
            }

            showAlert(`✅ Workflow successfully triggered for video ${data.video_id}! Processing has started on GitHub Actions runner.`, 'success');

            // Reset URL field
            videoUrlInput.value = '';
            urlFeedback.textContent = 'Job submitted! Waiting for runner...';

            // Start polling for workflow status
            startWorkflowMonitor();
        } catch (err) {
            showAlert(`❌ Error: ${err.message}`, 'error');
        } finally {
            submitBtn.disabled = false;
            submitBtnText.textContent = 'Dispatch GitHub Actions Workflow';
        }
    });

    function showAlert(msg, type) {
        submissionAlert.textContent = msg;
        submissionAlert.className = `alert ${type}`;
        submissionAlert.classList.remove('hidden');
    }

    function hideAlert() {
        submissionAlert.classList.add('hidden');
    }

    // 5. Workflow Run Tracking & Polling
    async function fetchWorkflowRuns() {
        try {
            const resp = await fetch('/api/workflows');
            if (!resp.ok) return;
            const data = await resp.json();
            const runs = data.runs || [];
            renderRunsList(runs);

            // If we have an active or recent run, track it
            if (runs.length > 0) {
                const latestRun = runs[0];
                if (latestRun.status !== 'completed' || monitoredRunId === latestRun.id) {
                    trackRun(latestRun.id);
                }
            }
        } catch (e) {
            console.warn('Error fetching workflow runs:', e);
        }
    }

    async function trackRun(runId) {
        monitoredRunId = runId;
        try {
            const resp = await fetch(`/api/workflows/${runId}`);
            if (!resp.ok) return;
            const run = await resp.json();

            activeRunContainer.classList.remove('hidden');
            activeRunTitle.textContent = run.display_title || `Workflow Run #${run.run_number}`;
            
            // Status badge
            const status = run.status;
            const conclusion = run.conclusion;
            
            if (status === 'completed') {
                if (conclusion === 'success') {
                    activeRunBadge.className = 'run-badge completed';
                    activeRunBadge.textContent = '✅ Completed';
                    updatePipelineStep('step-upload', 'done');
                } else {
                    activeRunBadge.className = 'run-badge failed';
                    activeRunBadge.textContent = `❌ ${conclusion || 'Failed'}`;
                }
            } else if (status === 'in_progress') {
                activeRunBadge.className = 'run-badge in_progress';
                activeRunBadge.textContent = '⚙️ Running';
            } else {
                activeRunBadge.className = 'run-badge queued';
                activeRunBadge.textContent = '⏳ Queued';
                updatePipelineStep('step-queued', 'active');
            }

            // GitHub link
            runGithubLink.href = run.html_url;

            // Google Drive Link
            const gdriveFolder = document.getElementById('gdriveFolder').value.trim() || 'OpenShorts';
            runGdriveLink.href = `https://drive.google.com/drive/search?q=${encodeURIComponent(gdriveFolder)}`;
            runGdriveLink.classList.remove('hidden');

            // Artifacts
            if (run.artifacts && run.artifacts.length > 0) {
                const art = run.artifacts[0];
                runArtifactLink.href = run.html_url; // Direct user to run page to download artifact securely
                runArtifactLink.textContent = `📦 Download ${art.name} (${Math.round(art.size_in_bytes / 1024 / 1024 * 10) / 10} MB)`;
                runArtifactLink.classList.remove('hidden');
            } else {
                runArtifactLink.classList.add('hidden');
            }

            // Inspect job steps to update pipeline tracker
            if (run.jobs && run.jobs.length > 0) {
                const steps = run.jobs[0].steps || [];
                updateStepsFromJob(steps);
            }

        } catch (e) {
            console.warn('Error tracking run:', e);
        }
    }

    function updateStepsFromJob(steps) {
        const stepMap = {
            'Download YouTube Video': 'step-download',
            'AI Transcription & Moment Analysis': 'step-transcribe',
            'Generate Viral Shorts': 'step-render',
            'Upload to Google Drive': 'step-upload'
        };

        steps.forEach(s => {
            for (const [key, elementId] of Object.entries(stepMap)) {
                if (s.name.includes(key)) {
                    if (s.conclusion === 'success') {
                        updatePipelineStep(elementId, 'done');
                    } else if (s.status === 'in_progress') {
                        updatePipelineStep(elementId, 'active');
                    }
                }
            }
        });
    }

    function updatePipelineStep(stepId, state) {
        const el = document.getElementById(stepId);
        if (!el) return;
        el.classList.remove('active', 'done');
        if (state) {
            el.classList.add(state);
        }
    }

    function renderRunsList(runs) {
        if (!runs || runs.length === 0) {
            runsList.innerHTML = '<div class="loading-spinner">No workflow executions found yet.</div>';
            return;
        }

        runsList.innerHTML = runs.map(r => {
            const dateStr = new Date(r.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            const badgeClass = r.status === 'completed' 
                ? (r.conclusion === 'success' ? 'completed' : 'failed') 
                : (r.status === 'in_progress' ? 'in_progress' : 'queued');
            
            const badgeLabel = r.status === 'completed' 
                ? (r.conclusion === 'success' ? 'Success' : 'Failed') 
                : (r.status === 'in_progress' ? 'Running' : 'Queued');

            return `
                <div class="run-item" onclick="window.open('${r.html_url}', '_blank')">
                    <div class="run-item-left">
                        <div class="run-item-title">#${r.run_number} - ${r.display_title || 'Video Processing'}</div>
                        <div class="run-item-meta">${dateStr} • Event: ${r.event}</div>
                    </div>
                    <div class="run-item-right">
                        <span class="run-badge ${badgeClass}">${badgeLabel}</span>
                    </div>
                </div>
            `;
        }).join('');
    }

    function startWorkflowMonitor() {
        if (pollInterval) clearInterval(pollInterval);
        fetchWorkflowRuns();
        pollInterval = setInterval(fetchWorkflowRuns, 5000);
    }

    if (refreshRunsBtn) {
        refreshRunsBtn.addEventListener('click', () => {
            fetchWorkflowRuns();
        });
    }

    // Boot
    initSystem();
    fetchWorkflowRuns();
    // Auto-refresh runs list every 15s in background
    setInterval(fetchWorkflowRuns, 15000);
});
