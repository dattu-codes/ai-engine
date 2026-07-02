// App state variables
let pollInterval = null;
let currentRunId = null;
let processedLogCount = 0;

// Nodes list in order of sequential flow
const NODE_FLOW = ['extract', 'complexity', 'detect', 'suggest_improvements'];

// Initialize App
document.addEventListener('DOMContentLoaded', () => {
    initSidebar();
    initTabs();
    initFormControls();
    initLineNumbers();
    initDemoSetup();
    initAuth();
    initProjectsTab();
});

// Tab Navigation logic
function initTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');
            
            // Toggle active button
            tabButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            // Toggle active pane
            const panes = document.querySelectorAll('.tab-pane');
            panes.forEach(pane => {
                if (pane.id === targetTab) {
                    pane.classList.add('active');
                } else {
                    pane.classList.remove('active');
                }
            });
        });
    });
}

// Form Controls listeners
function initFormControls() {
    // Threshold slider
    const thresholdSlider = document.getElementById('threshold');
    const thresholdVal = document.getElementById('threshold-val');
    thresholdSlider.addEventListener('input', (e) => {
        thresholdVal.textContent = `${e.target.value}%`;
    });

    // Toggle API Key visibility
    const apiKeyInput = document.getElementById('api-key');
    const toggleKeyBtn = document.getElementById('toggle-key-visibility');
    toggleKeyBtn.addEventListener('click', () => {
        const type = apiKeyInput.getAttribute('type') === 'password' ? 'text' : 'password';
        apiKeyInput.setAttribute('type', type);
        toggleKeyBtn.textContent = type === 'password' ? '👁️' : '🔒';
    });

    // Execute Button
    const runBtn = document.getElementById('btn-run');
    runBtn.addEventListener('click', executeWorkflow);

    // Copy refactored code
    const copyBtn = document.getElementById('btn-copy');
    copyBtn.addEventListener('click', () => {
        const codeText = document.getElementById('refactored-code-block').innerText;
        if (codeText && !codeText.startsWith('# Refactored')) {
            navigator.clipboard.writeText(codeText);
            const originalText = copyBtn.textContent;
            copyBtn.textContent = 'Copied!';
            copyBtn.style.background = 'var(--accent-green)';
            setTimeout(() => {
                copyBtn.textContent = originalText;
                copyBtn.style.background = '';
            }, 1500);
        }
    });
}

// Line Numbers Sync for Editor
function initLineNumbers() {
    const textarea = document.getElementById('code-input');
    const lineNumbers = document.getElementById('line-numbers');
    
    function updateLines() {
        const lines = textarea.value.split('\n');
        let numbersHTML = '';
        for (let i = 1; i <= lines.length; i++) {
            numbersHTML += `<div>${i}</div>`;
        }
        lineNumbers.innerHTML = numbersHTML;
    }
    
    textarea.addEventListener('input', updateLines);
    textarea.addEventListener('scroll', () => {
        lineNumbers.scrollTop = textarea.scrollTop;
    });
    
    updateLines();
}

// Setup Demo / Status checks
function initDemoSetup() {
    const apiKeyInput = document.getElementById('api-key');
    const statusText = document.getElementById('status-text');
    const statusIndicator = document.querySelector('.status-indicator');

    function updateStatusLabel() {
        if (apiKeyInput.value.trim() !== '') {
            statusText.textContent = 'SYSTEM ONLINE (LIVE API MODE)';
            statusText.style.color = '#fff';
            statusIndicator.className = 'status-indicator online';
        } else {
            statusText.textContent = 'SYSTEM ONLINE (DEMO MODE)';
            statusText.style.color = '';
            statusIndicator.className = 'status-indicator online';
        }
    }
    
    apiKeyInput.addEventListener('input', updateStatusLabel);
    updateStatusLabel();
}

// Console Logging helper
function appendLog(message, type = 'system', time = null) {
    const consoleLogs = document.getElementById('console-logs');
    const displayTime = time || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true }).toLowerCase();
    const line = document.createElement('div');
    line.className = `console-line ${type}`;
    line.innerHTML = `<span style="color: #64748b;">[${displayTime}]</span> ${message}`;
    consoleLogs.appendChild(line);
    consoleLogs.scrollTop = consoleLogs.scrollHeight;
}

// Visualizer Reset helper
function resetGraphVisualizer() {
    NODE_FLOW.forEach(nodeId => {
        const container = document.getElementById(`node-${nodeId}`);
        container.className = 'node-container';
        container.querySelector('.node-status-badge').textContent = 'Idle';
    });
    
    for (let i = 1; i <= 3; i++) {
        document.getElementById(`arrow-${i}`).className = 'pipeline-arrow';
    }
    
    document.getElementById('loop-indicator').style.display = 'none';
}

// Update Visualizer Active/Completed Nodes
function updateGraphState(activeNodeIndex, completedNodesSet) {
    NODE_FLOW.forEach((nodeId, idx) => {
        const container = document.getElementById(`node-${nodeId}`);
        const badge = container.querySelector('.node-status-badge');
        
        if (completedNodesSet.has(nodeId)) {
            container.className = 'node-container completed';
            badge.textContent = 'Done';
            
            // Color connection arrow
            if (idx < NODE_FLOW.length - 1) {
                document.getElementById(`arrow-${idx + 1}`).className = 'pipeline-arrow completed';
            }
        } else if (idx === activeNodeIndex) {
            container.className = 'node-container running';
            badge.textContent = 'Running';
            
            // Set connection arrow pulsing
            if (idx < NODE_FLOW.length - 1) {
                document.getElementById(`arrow-${idx + 1}`).className = 'pipeline-arrow running';
            }
        } else {
            container.className = 'node-container';
            badge.textContent = 'Idle';
        }
    });
}

// Main execution flow
async  function executeWorkflow() {
    const code = document.getElementById('code-input').value;
    const apiKey = document.getElementById('api-key').value;
    const threshold = document.getElementById('threshold').value;
    const model = document.getElementById('model').value;
    const runBtn = document.getElementById('btn-run');
    
    if (!code.trim()) {
        alert('Please provide some Python code to analyze.');
        return;
    }

    // Set UI to running state
    runBtn.disabled = true;
    runBtn.querySelector('.btn-text').textContent = 'Running Pipeline...';
    processedLogCount = 0;
    
    // Clear old result states
    resetGraphVisualizer();
    document.getElementById('bugs-tbody').innerHTML = `
        <tr class="empty-row">
            <td colspan="4">Scanning codebase structure... Please wait.</td>
        </tr>`;
    document.getElementById('val-quality').textContent = '--';
    document.getElementById('val-complexity').textContent = '--';
    document.getElementById('val-funcs').textContent = '--';
    document.getElementById('bar-quality').style.width = '0%';
    document.getElementById('badge-bugs').textContent = '0';
    document.getElementById('badge-bugs').classList.remove('red-glow');
    document.getElementById('summary-text').textContent = 'Engine processing workflow graph...';
    document.getElementById('functions-list-container').style.display = 'none';
    document.getElementById('functions-list').innerHTML = '';
    document.getElementById('improvements-list').innerHTML = '<li class="placeholder-li">Reviewing suggestions...</li>';
    document.getElementById('refactored-code-block').textContent = '# Refactoring output will appear here...';
    Prism.highlightElement(document.getElementById('refactored-code-block'));
    
    // Clear logs
    const consoleLogs = document.getElementById('console-logs');
    consoleLogs.innerHTML = '';
    appendLog('Starting workflow initialization...', 'system');

    try {
        // 1. Create Graph preset
        const createRes = await authorizedFetch('/graph/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ preset: 'code_review' })
        });
        
        if (!createRes.ok) throw new Error('Failed to initialize workflow graph template on backend.');
        const { graph_id } = await createRes.json();
        appendLog(`Workflow Graph registered. ID: ${graph_id.slice(0, 8)}...`, 'success');

        // 2. Start Graph Run
        const runRes = await authorizedFetch('/graph/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                graph_id,
                initial_state: {
                    code,
                    api_key: apiKey,
                    threshold: parseInt(threshold),
                    model
                }
            })
        });
        
        if (!runRes.ok) throw new Error('Failed to allocate executor for workflow run.');
        const { run_id } = await runRes.json();
        currentRunId = run_id;
        appendLog(`Workflow Runner active. Run ID: ${run_id.slice(0, 8)}...`, 'success');
        
        // Mark first node running
        updateGraphState(0, new Set());
        
        // 3. Start Polling
        if (pollInterval) clearInterval(pollInterval);
        pollInterval = setInterval(() => pollState(run_id), 800);
        
    } catch (err) {
        appendLog(`Initialization error: ${err.message}`, 'error');
        runBtn.disabled = false;
        runBtn.querySelector('.btn-text').textContent = 'Execute Workflow';
        document.getElementById('bugs-tbody').innerHTML = `
            <tr class="empty-row">
                <td colspan="4" style="color: var(--accent-red)">Failed to start workflow: ${err.message}</td>
            </tr>`;
    }
}

// Poll state endpoint
async function pollState(runId) {
    try {
        const res = await authorizedFetch(`/graph/state/${runId}`);
        if (!res.ok) throw new Error('State fetch rejected by backend.');
        const data = await res.json();
        
        // 1. Process new console logs
        if (data.logs && data.logs.length > processedLogCount) {
            for (let i = processedLogCount; i < data.logs.length; i++) {
                const log = data.logs[i];
                processStepLog(log);
            }
            processedLogCount = data.logs.length;
        }

        // 2. Determine current node indexing
        const completedNodes = new Set();
        let activeNodeIndex = 0;
        
        if (data.logs && data.logs.length > 0) {
            data.logs.forEach(log => {
                if (log.node) {
                    completedNodes.add(log.node);
                }
            });
            
            // If we completed suggest_improvements but we loop back:
            const lastLog = data.logs[data.logs.length - 1];
            if (lastLog.node === 'suggest_improvements' && lastLog.action && lastLog.action.includes('Looping back')) {
                // Loop back visually
                completedNodes.clear();
                activeNodeIndex = 0; // restart at extract
                document.getElementById('loop-indicator').style.display = 'flex';
            } else {
                // Find next node that hasn't run yet
                const lastCompleted = data.logs[data.logs.length - 1].node;
                const flowIndex = NODE_FLOW.indexOf(lastCompleted);
                if (flowIndex !== -1 && flowIndex < NODE_FLOW.length - 1) {
                    activeNodeIndex = flowIndex + 1;
                } else {
                    activeNodeIndex = -1; // all done
                }
            }
        }
        
        // Update nodes visualizer classes
        updateGraphState(activeNodeIndex, completedNodes);

        // 3. Handle run termination
        if (data.status === 'completed' || data.status === 'error' || data.status === 'max_steps_exceeded') {
            clearInterval(pollInterval);
            finalizeWorkflow(data);
        }
        
    } catch (err) {
        appendLog(`Polling connection error: ${err.message}`, 'error');
    }
}

// Process individual step logging in console
function processStepLog(log) {
    if (!log.node) return;
    
    const t = log.timestamp;
    
    // Inject step start logging on first and subsequent passes
    if (log.node === 'extract') {
        appendLog('Executing Step 1: Extract Functions...', 'node', t);
    }
    
    if (log.message) {
        appendLog(log.message, 'success', t);
    }
    
    if (log.node === 'extract') {
        appendLog(`Summary generated: "${log.summary}"`, 'system', t);
        appendLog('Executing Step 2: Complexity Analysis...', 'node', t);
    } else if (log.node === 'complexity') {
        appendLog(`Complexity Details: ${log.explanation}`, 'system', t);
        appendLog('Executing Step 3: Issue Detection...', 'node', t);
    } else if (log.node === 'detect') {
        appendLog(`Scanned and identified ${log.issues ? log.issues.length : 0} items.`, 'system', t);
        appendLog('Executing Step 4: Quality Assessment & Refactoring...', 'node', t);
    } else if (log.node === 'suggest_improvements') {
        if (log.improvements && log.improvements.length > 0) {
            appendLog(`Generated changes: ${log.improvements.join(' | ')}`, 'system', t);
        }
        
        // Chronological self-healing loop warning
        if (log.action && log.action.includes('Looping back')) {
            document.getElementById('loop-indicator').style.display = 'flex';
            appendLog('🔄 SELF-HEALING LOOP: Target quality not met. Code modified and re-routed through analysis pipeline.', 'warning', t);
        }
    }
}

// Finalize and populate tabs
function finalizeWorkflow(runData) {
    const runBtn = document.getElementById('btn-run');
    runBtn.disabled = false;
    runBtn.querySelector('.btn-text').textContent = 'Execute Workflow';
    
    const state = runData.state;
    
    if (runData.status === 'error') {
        appendLog(`Workflow terminated with ERROR: ${runData.logs[runData.logs.length - 1]?.error || 'Unknown execution fault'}`, 'error');
        // Mark last running node as error
        const activeNode = document.querySelector('.node-container.running');
        if (activeNode) {
            activeNode.className = 'node-container error';
            activeNode.querySelector('.node-status-badge').textContent = 'Error';
        }
        return;
    }
    
    appendLog('Workflow pipeline completed successfully.', 'success');
    
    // 1. Populate Summary
    const quality = state.quality_score !== undefined ? state.quality_score : 100;
    document.getElementById('val-quality').textContent = `${quality}%`;
    const qBar = document.getElementById('bar-quality');
    qBar.style.width = `${quality}%`;
    
    // Set bar color based on quality
    if (quality >= 80) {
        qBar.style.background = 'linear-gradient(90deg, var(--accent-purple), var(--accent-green))';
    } else if (quality >= 60) {
        qBar.style.background = 'linear-gradient(90deg, var(--accent-orange), var(--accent-purple))';
    } else {
        qBar.style.background = 'linear-gradient(90deg, var(--accent-red), var(--accent-orange))';
    }

    const comp = state.complexity?.complexity_score !== undefined ? state.complexity.complexity_score : '--';
    document.getElementById('val-complexity').textContent = `${comp}/100`;
    
    const funcs = state.functions ? state.functions.length : 0;
    document.getElementById('val-funcs').textContent = funcs;
    
    document.getElementById('summary-text').textContent = state.summary || 'Code analysis report complete.';
    
    // Function Pills list
    if (state.functions && state.functions.length > 0) {
        const funcsContainer = document.getElementById('functions-list-container');
        const funcsUl = document.getElementById('functions-list');
        funcsUl.innerHTML = '';
        state.functions.forEach(f => {
            const li = document.createElement('li');
            li.title = `Arguments: (${f.args.join(', ')})\nDocstring: ${f.docstring || 'None'}`;
            li.textContent = `${f.name}(${f.args.join(', ')})`;
            funcsUl.appendChild(li);
        });
        funcsContainer.style.display = 'block';
    }
    
    // 2. Populate Bugs List
    const bugsBody = document.getElementById('bugs-tbody');
    const bugsCount = state.issues ? state.issues.length : 0;
    const badgeBugs = document.getElementById('badge-bugs');
    badgeBugs.textContent = bugsCount;
    
    if (bugsCount > 0) {
        badgeBugs.classList.add('red-glow');
        bugsBody.innerHTML = '';
        state.issues.forEach(iss => {
            const tr = document.createElement('tr');
            
            const severityClass = (iss.severity || 'low').toLowerCase();
            tr.innerHTML = `
                <td class="type-cell">${iss.type || 'Style'}</td>
                <td><span class="pill ${severityClass}">${iss.severity || 'Low'}</span></td>
                <td>${iss.description}</td>
                <td class="loc-cell">${iss.location || 'Unknown'}</td>
            `;
            bugsBody.appendChild(tr);
        });
    } else {
        badgeBugs.classList.remove('red-glow');
        bugsBody.innerHTML = `
            <tr class="empty-row">
                <td colspan="4" style="color: var(--accent-green); font-style: normal; font-weight: 500;">
                    🎉 Excellent! Code scans detected no bugs, warnings, or stylistic violations.
                </td>
            </tr>`;
    }
    
    // 3. Populate Refactored Code and Improvements
    const refCode = state.code || '';
    const refBlock = document.getElementById('refactored-code-block');
    refBlock.textContent = refCode;
    Prism.highlightElement(refBlock);
    
    const impsList = document.getElementById('improvements-list');
    impsList.innerHTML = '';
    const improvements = state.improvements || ['Code structure validated against targets.'];
    improvements.forEach(imp => {
        const li = document.createElement('li');
        li.textContent = imp;
        impsList.appendChild(li);
    });
}

/* ==========================================================================
   AUTHENTICATION LOGIC & UTILITIES
   ========================================================================== */

let activeAuthTab = 'login'; // 'login' or 'signup'

function initAuth() {
    const tabLogin = document.getElementById('tab-login-btn');
    const tabSignup = document.getElementById('tab-signup-btn');
    const signupRoleGroup = document.getElementById('signup-role-group');
    const authSubmitBtn = document.getElementById('btn-auth-submit');
    const authForm = document.getElementById('auth-form');
    const logoutBtn = document.getElementById('btn-logout');

    // Tab toggling
    tabLogin.addEventListener('click', () => {
        activeAuthTab = 'login';
        tabLogin.classList.add('active');
        tabSignup.classList.remove('active');
        signupRoleGroup.style.display = 'none';
        authSubmitBtn.textContent = 'Login';
        clearAuthError();
    });

    tabSignup.addEventListener('click', () => {
        activeAuthTab = 'signup';
        tabSignup.classList.add('active');
        tabLogin.classList.remove('active');
        signupRoleGroup.style.display = 'block';
        authSubmitBtn.textContent = 'Sign Up';
        clearAuthError();
    });

    // Form Submission
    authForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('auth-username').value.trim();
        const password = document.getElementById('auth-password').value;
        const role = document.getElementById('auth-role').value;

        clearAuthError();

        if (activeAuthTab === 'login') {
            await handleLogin(username, password);
        } else {
            await handleSignup(username, password, role);
        }
    });

    // Logout Action
    logoutBtn.addEventListener('click', handleLogout);

    // Initial session verification
    checkUserSession();
}

function clearAuthError() {
    const errorMsg = document.getElementById('auth-error-msg');
    errorMsg.style.display = 'none';
    errorMsg.textContent = '';
}

function showAuthError(message) {
    const errorMsg = document.getElementById('auth-error-msg');
    errorMsg.style.display = 'block';
    errorMsg.textContent = message;
}

async function handleLogin(username, password) {
    try {
        const res = await fetch('/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        const data = await res.json();
        if (res.ok) {
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('refresh_token', data.refresh_token);
            await checkUserSession();
            
            // Reset input values
            document.getElementById('auth-username').value = '';
            document.getElementById('auth-password').value = '';
        } else {
            showAuthError(data.detail || 'Login failed. Please check credentials.');
        }
    } catch (e) {
        showAuthError('Connection error: Failed to reach backend server.');
    }
}

async function handleSignup(username, password, role) {
    try {
        const res = await fetch('/auth/signup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, role })
        });

        const data = await res.json();
        if (res.ok) {
            // Success: Switch to login tab and auto-fill username
            activeAuthTab = 'login';
            document.getElementById('tab-login-btn').click();
            document.getElementById('auth-username').value = username;
            document.getElementById('auth-password').value = '';
            showAuthError('Signup successful! Please enter your password to log in.');
            document.getElementById('auth-error-msg').style.background = 'rgba(16, 185, 129, 0.08)';
            document.getElementById('auth-error-msg').style.borderColor = 'var(--accent-green)';
            document.getElementById('auth-error-msg').style.color = '#a7f3d0';
        } else {
            showAuthError(data.detail || 'Signup failed.');
        }
    } catch (e) {
        showAuthError('Connection error: Failed to reach backend server.');
    }
}

async function handleLogout() {
    const refreshToken = localStorage.getItem('refresh_token');
    
    // Clear tokens immediately on frontend
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    
    // Reset UI
    document.getElementById('auth-overlay').classList.remove('hidden');
    document.getElementById('header-auth').style.display = 'none';

    if (refreshToken) {
        try {
            await fetch('/auth/logout', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: refreshToken })
            });
        } catch (e) {
            console.error('Logout request failed on backend:', e);
        }
    }
}

async function checkUserSession() {
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
        showLoginOverlay();
        return;
    }

    try {
        const res = await fetch('/auth/profile', {
            headers: { 'Authorization': `Bearer ${accessToken}` }
        });

        if (res.ok) {
            const user = await res.json();
            
            // Set header authentication state
            document.getElementById('user-display-name').textContent = user.username;
            document.getElementById('user-display-role').textContent = user.role.toUpperCase();
            
            // Adjust visual system indicators if needed
            document.getElementById('header-auth').style.display = 'flex';
            document.getElementById('auth-overlay').classList.add('hidden');
            
            // Auto-load projects on login
            loadProjects();
        } else if (res.status === 401) {
            // Attempt rotation
            const refreshed = await attemptTokenRefresh();
            if (refreshed) {
                await checkUserSession();
            } else {
                showLoginOverlay();
            }
        } else {
            showLoginOverlay();
        }
    } catch (e) {
        showLoginOverlay();
        showAuthError('Connection lost: Unable to check credentials session.');
    }
}

function showLoginOverlay() {
    document.getElementById('auth-overlay').classList.remove('hidden');
    document.getElementById('header-auth').style.display = 'none';
}

// Custom authenticated fetch utility
async function authorizedFetch(url, options = {}) {
    let accessToken = localStorage.getItem('access_token');
    
    if (!options.headers) {
        options.headers = {};
    }
    if (accessToken) {
        options.headers['Authorization'] = `Bearer ${accessToken}`;
    }

    let response = await fetch(url, options);

    if (response.status === 401 && localStorage.getItem('refresh_token')) {
        const refreshed = await attemptTokenRefresh();
        if (refreshed) {
            // Retry
            options.headers['Authorization'] = `Bearer ${localStorage.getItem('access_token')}`;
            response = await fetch(url, options);
        } else {
            showLoginOverlay();
            throw new Error('Session expired. Please log in again.');
        }
    }

    return response;
}

async function attemptTokenRefresh() {
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) return false;

    try {
        const res = await fetch('/auth/refresh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken })
        });

        if (res.ok) {
            const data = await res.json();
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('refresh_token', data.refresh_token);
            return true;
        }
    } catch (e) {
        console.error('Session token refresh failed:', e);
    }
    
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    return false;
}

/* ==========================================================================
   SIDEBAR & PROJECT COMPONENT LOGIC
   ========================================================================== */

let activeProjectId = null;
let selectedZipFile = null;

function initSidebar() {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const targetView = item.getAttribute('data-view');
            
            navItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            
            const panes = document.querySelectorAll('.view-pane');
            panes.forEach(pane => {
                if (pane.id === targetView) {
                    pane.classList.add('active');
                } else {
                    pane.classList.remove('active');
                }
            });

            if (targetView === 'view-projects') {
                loadProjects();
            }
        });
    });
}

function initProjectsTab() {
    // Project Modal bindings
    const btnCreateModal = document.getElementById('btn-create-project-modal');
    const btnModalCancel = document.getElementById('btn-project-modal-cancel');
    const projectModal = document.getElementById('project-modal');
    const projectCreateForm = document.getElementById('project-create-form');

    btnCreateModal.addEventListener('click', () => {
        projectModal.classList.remove('hidden');
        document.getElementById('project-modal-name').value = '';
        const repoInput = document.getElementById('project-modal-repo-url');
        if (repoInput) repoInput.value = '';
    });

    btnModalCancel.addEventListener('click', () => {
        projectModal.classList.add('hidden');
    });

    projectCreateForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('project-modal-name').value.trim();
        const repoInput = document.getElementById('project-modal-repo-url');
        const repoUrl = repoInput ? repoInput.value.trim() : '';
        if (!name) return;

        const submitBtn = projectCreateForm.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.textContent = repoUrl ? 'Cloning & Ingesting...' : 'Creating...';

        try {
            const res = await authorizedFetch('/projects', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, repo_url: repoUrl || null })
            });

            if (res.ok) {
                projectModal.classList.add('hidden');
                loadProjects();
            } else {
                const data = await res.json();
                alert(data.detail || 'Failed to create project.');
            }
        } catch (err) {
            alert('Error creating project: ' + err.message);
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    });

    // Project Actions: Rename & Delete
    document.getElementById('btn-rename-project').addEventListener('click', renameActiveProject);
    document.getElementById('btn-delete-project').addEventListener('click', deleteActiveProject);

    // Sync Repository click handler
    const btnSyncRepo = document.getElementById('btn-sync-repository');
    if (btnSyncRepo) {
        btnSyncRepo.addEventListener('click', async () => {
            if (!activeProjectId) return;

            const originalHtml = btnSyncRepo.innerHTML;
            btnSyncRepo.disabled = true;
            btnSyncRepo.innerHTML = '🔄 Syncing...';

            try {
                const res = await authorizedFetch(`/projects/${activeProjectId}/sync`, {
                    method: 'POST'
                });

                const data = await res.json();
                if (res.ok) {
                    alert(data.message || 'Repository sync completed.');
                    await selectProject(activeProjectId);
                } else {
                    alert(data.detail || 'Failed to synchronize repository.');
                }
            } catch (err) {
                alert('Sync error: ' + err.message);
            } finally {
                btnSyncRepo.disabled = false;
                btnSyncRepo.innerHTML = originalHtml;
            }
        });
    }

    // Ingestion tabs inside project page
    const ingestionTabBtns = document.querySelectorAll('.ingestion-tabs .tab-btn');
    ingestionTabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');
            ingestionTabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            const panes = btn.closest('.card').querySelectorAll('.tab-pane');
            panes.forEach(pane => {
                if (pane.id === targetTab) {
                    pane.classList.add('active');
                } else {
                    pane.classList.remove('active');
                }
            });
        });
    });

    // Run AI Review click binding
    document.getElementById('btn-start-project-analysis').addEventListener('click', startProjectAnalysis);

    // Ingest Paste Code Form
    document.getElementById('form-ingest-paste').addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!activeProjectId) return;

        const filename = document.getElementById('paste-filename').value.trim();
        const content = document.getElementById('paste-content').value;

        const formData = new FormData();
        formData.append('pasted_filename', filename);
        formData.append('pasted_content', content);

        try {
            const res = await authorizedFetch(`/projects/${activeProjectId}/upload`, {
                method: 'POST',
                body: formData
            });

            if (res.ok) {
                document.getElementById('paste-filename').value = '';
                document.getElementById('paste-content').value = '';
                alert('Source code ingested successfully!');
                selectProject(activeProjectId);
            } else {
                const data = await res.json();
                alert(data.detail || 'Failed to ingest pasted code.');
            }
        } catch (err) {
            alert('Ingestion error: ' + err.message);
        }
    });

    // Ingest ZIP Drag & Drop + Browse
    const zipDropZone = document.getElementById('zip-drop-zone');
    const zipFileInput = document.getElementById('zip-file-input');
    const zipSelectedName = document.getElementById('zip-file-selected-name');
    const btnIngestZip = document.getElementById('btn-ingest-zip');

    zipDropZone.addEventListener('click', () => zipFileInput.click());
    
    zipDropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zipDropZone.classList.add('dragover');
    });

    zipDropZone.addEventListener('dragleave', () => {
        zipDropZone.classList.remove('dragover');
    });

    zipDropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        zipDropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            handleZipFileSelection(e.dataTransfer.files[0]);
        }
    });

    zipFileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleZipFileSelection(e.target.files[0]);
        }
    });

    function handleZipFileSelection(file) {
        if (!file.name.endsWith('.zip')) {
            alert('Please select a valid .zip archive.');
            return;
        }
        selectedZipFile = file;
        zipSelectedName.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
        zipSelectedName.style.display = 'block';
        btnIngestZip.disabled = false;
    }

    document.getElementById('form-ingest-zip').addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!activeProjectId || !selectedZipFile) return;

        btnIngestZip.disabled = true;
        btnIngestZip.textContent = 'Processing ZIP...';

        const formData = new FormData();
        formData.append('file', selectedZipFile);

        try {
            const res = await authorizedFetch(`/projects/${activeProjectId}/upload`, {
                method: 'POST',
                body: formData
            });

            if (res.ok) {
                alert('ZIP archive successfully parsed and metadata indexed!');
                selectedZipFile = null;
                zipFileInput.value = '';
                zipSelectedName.style.display = 'none';
                btnIngestZip.textContent = 'Ingest ZIP';
                btnIngestZip.disabled = true;
                selectProject(activeProjectId);
            } else {
                const data = await res.json();
                alert(data.detail || 'Failed to ingest ZIP file.');
                btnIngestZip.disabled = false;
                btnIngestZip.textContent = 'Ingest ZIP';
            }
        } catch (err) {
            alert('Ingestion error: ' + err.message);
            btnIngestZip.disabled = false;
            btnIngestZip.textContent = 'Ingest ZIP';
        }
    });

    // Link Git Repository Form
    document.getElementById('form-ingest-git').addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!activeProjectId) return;

        const repoUrl = document.getElementById('git-repo-url').value.trim();
        const submitBtn = e.target.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Cloning & Ingesting...';

        try {
            const res = await authorizedFetch(`/projects/${activeProjectId}/repository`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ repo_url: repoUrl })
            });

            if (res.ok) {
                document.getElementById('git-repo-url').value = '';
                alert('GitHub repository linked and ingested successfully!');
                selectProject(activeProjectId);
            } else {
                const data = await res.json();
                alert(data.detail || 'Failed to link repository.');
            }
        } catch (err) {
            alert('Link error: ' + err.message);
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    });
}

async function loadProjects() {
    try {
        const res = await authorizedFetch('/projects');
        if (!res.ok) return;

        const projects = await res.json();
        const container = document.getElementById('projects-list-container');
        
        if (projects.length === 0) {
            container.innerHTML = '<p class="placeholder-text" style="padding: 0 16px;">No projects registered. Click "+ New" to begin.</p>';
            document.getElementById('active-project-details').style.display = 'none';
            activeProjectId = null;
            return;
        }

        container.innerHTML = '';
        projects.forEach(p => {
            const card = document.createElement('div');
            card.className = `project-card ${activeProjectId === p.id ? 'active' : ''}`;
            card.innerHTML = `
                <h3>${escapeHtml(p.name)}</h3>
                <p>Created: ${new Date(p.created_at).toLocaleDateString()}</p>
            `;
            card.addEventListener('click', () => {
                document.querySelectorAll('.project-card').forEach(c => c.classList.remove('active'));
                card.classList.add('active');
                selectProject(p.id);
            });
            container.appendChild(card);
        });

        // Auto-select first project if none is active
        if (!activeProjectId && projects.length > 0) {
            container.firstElementChild.click();
        }
    } catch (err) {
        console.error('Failed to load projects list:', err);
    }
}

async function selectProject(id) {
    activeProjectId = id;
    try {
        const res = await authorizedFetch(`/projects/${id}`);
        if (!res.ok) return;

        const details = await res.json();
        
        // Update detail headers
        document.getElementById('detail-project-name').textContent = details.name;
        document.getElementById('detail-project-lang').textContent = details.languages.join(', ') || 'None Detected';
        document.getElementById('detail-project-files').textContent = details.total_files;
        
        // Handle GitHub Integration card
        const githubCard = document.getElementById('project-github-card');
        if (details.repo_url) {
            githubCard.style.display = 'block';
            const urlLink = document.getElementById('github-info-url');
            urlLink.href = details.repo_url;
            urlLink.textContent = `${details.repo_owner}/${details.repo_name}`;
            document.getElementById('github-info-branch').textContent = details.current_branch || '--';
            document.getElementById('github-info-default-branch').textContent = details.default_branch || '--';
            document.getElementById('github-info-sync-time').textContent = details.last_sync_time ? new Date(details.last_sync_time).toLocaleString() : '--';
            document.getElementById('github-info-commit-sha').textContent = details.last_commit_sha ? details.last_commit_sha.slice(0, 7) : '--';
            document.getElementById('github-info-commit-msg').textContent = details.last_commit_message || '--';
        } else {
            githubCard.style.display = 'none';
        }

        // Handle Code Intelligence Card
        const intelCard = document.getElementById('project-intelligence-card');
        if (details.total_files > 0 && details.has_intelligence) {
            intelCard.style.display = 'block';
            document.getElementById('intel-project-type').textContent = details.project_type || 'None';
            document.getElementById('intel-framework').textContent = details.framework || 'None';
            document.getElementById('intel-architecture').textContent = details.architecture || 'None';
            document.getElementById('intel-entry-point').textContent = details.entry_point || 'None';
            document.getElementById('intel-total-lines').textContent = details.total_lines || '0';

            // Languages Distribution
            const langBar = document.getElementById('intel-languages-bar');
            const langLegend = document.getElementById('intel-languages-legend');
            langBar.innerHTML = '';
            langLegend.innerHTML = '';
            
            if (details.languages_distribution) {
                try {
                    const dist = JSON.parse(details.languages_distribution);
                    const colors = {
                        'Python': '#3572A5',
                        'Java': '#b07219',
                        'JavaScript': '#f1e05a',
                        'TypeScript': '#3178c6',
                        'HTML': '#e34c26',
                        'CSS': '#563d7c',
                        'Unknown': '#64748b'
                    };
                    
                    Object.entries(dist).forEach(([lang, pct]) => {
                        const color = colors[lang] || '#' + Math.floor(Math.random()*16777215).toString(16);
                        
                        // Segment in bar
                        const segment = document.createElement('div');
                        segment.style.width = `${pct}%`;
                        segment.style.backgroundColor = color;
                        segment.style.height = '100%';
                        segment.title = `${lang}: ${pct}%`;
                        langBar.appendChild(segment);
                        
                        // Item in legend
                        const legendItem = document.createElement('div');
                        legendItem.style.display = 'flex';
                        legendItem.style.alignItems = 'center';
                        legendItem.style.gap = '6px';
                        legendItem.innerHTML = `
                            <span style="width: 8px; height: 8px; border-radius: 50%; background-color: ${color}; display: inline-block;"></span>
                            <strong>${lang}</strong> <span>${pct}%</span>
                        `;
                        langLegend.appendChild(legendItem);
                    });
                } catch (e) {
                    console.error('Failed to parse languages_distribution:', e);
                }
            }

            // Dependencies
            const depCount = document.getElementById('intel-dep-count');
            const depList = document.getElementById('intel-dependencies-list');
            depList.innerHTML = '';
            
            if (details.dependencies_json) {
                try {
                    const deps = JSON.parse(details.dependencies_json);
                    depCount.textContent = `${deps.length} package${deps.length === 1 ? '' : 's'}`;
                    
                    if (deps.length === 0) {
                        depList.innerHTML = '<span class="placeholder-text" style="font-size: 12px; color: var(--text-muted);">No dependencies detected.</span>';
                    } else {
                        deps.forEach(dep => {
                            const badge = document.createElement('span');
                            badge.className = 'pill';
                            badge.style.background = 'rgba(255,255,255,0.04)';
                            badge.style.border = '1px solid rgba(255,255,255,0.08)';
                            badge.style.fontSize = '12px';
                            badge.style.padding = '2px 8px';
                            badge.style.borderRadius = '10px';
                            badge.style.color = 'var(--text-main)';
                            badge.innerHTML = `<strong style="color: var(--accent-teal);">${escapeHtml(dep.name)}</strong> <span style="color: var(--text-muted); font-size: 11px;">${escapeHtml(dep.version)}</span>`;
                            depList.appendChild(badge);
                        });
                    }
                } catch (e) {
                    console.error('Failed to parse dependencies_json:', e);
                    depList.innerHTML = '<span class="placeholder-text" style="font-size: 12px; color: var(--text-muted);">No dependencies detected.</span>';
                }
            } else {
                depCount.textContent = '0 packages';
                depList.innerHTML = '<span class="placeholder-text" style="font-size: 12px; color: var(--text-muted);">No dependencies detected.</span>';
            }
        } else {
            intelCard.style.display = 'none';
        }

        if (details.last_analysis) {
            document.getElementById('detail-project-last-run').textContent = new Date(details.last_analysis.created_at).toLocaleString();
            
            // Check if it's a real AI Review analysis (has model_used)
            const isAnalyzed = !!details.last_analysis.model_used;
            const statusEl = document.getElementById('detail-project-status');
            statusEl.className = 'stat-value';

            if (isAnalyzed) {
                // Reset subtab state
                switchReportTab('ai');
                
                document.getElementById('detail-project-status').textContent = details.last_analysis.status.toUpperCase();
                if (details.last_analysis.status === 'completed') {
                    statusEl.style.color = 'var(--accent-green)';
                    loadProjectReport(details.last_analysis.id);
                } else if (details.last_analysis.status === 'failed') {
                    statusEl.style.color = 'var(--accent-red)';
                    document.getElementById('project-report-card').style.display = 'none';
                } else {
                    statusEl.style.color = 'var(--accent-orange)';
                    document.getElementById('project-report-card').style.display = 'none';
                }
            } else {
                // Ingested but not analyzed yet
                document.getElementById('detail-project-status').textContent = 'UNANALYZED';
                statusEl.style.color = '';
                document.getElementById('project-report-card').style.display = 'none';
            }
        } else {
            document.getElementById('detail-project-last-run').textContent = '--';
            document.getElementById('detail-project-status').textContent = 'UNANALYZED';
            document.getElementById('detail-project-status').style.color = '';
            document.getElementById('project-report-card').style.display = 'none';
        }

        document.getElementById('active-project-details').style.display = 'flex';

        // Load files list
        await loadProjectFiles(id);
    } catch (err) {
        console.error('Failed to select project details:', err);
    }
}

async function loadProjectFiles(id) {
    try {
        const res = await authorizedFetch(`/projects/${id}/files`);
        const tbody = document.getElementById('project-files-tbody');

        if (!res.ok) {
            tbody.innerHTML = '<tr class="empty-row"><td colspan="4">Failed to load files list.</td></tr>';
            return;
        }

        const files = await res.json();
        if (files.length === 0) {
            tbody.innerHTML = '<tr class="empty-row"><td colspan="4">No source files parsed. Ingest code to display files.</td></tr>';
            return;
        }

        tbody.innerHTML = '';
        files.forEach(f => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="font-family: var(--font-mono); font-size: 13px; color: var(--text-bright);">${escapeHtml(f.filename)}</td>
                <td><span class="pill outline">${escapeHtml(f.extension)}</span></td>
                <td>${f.size}</td>
                <td><span class="pill" style="background: rgba(139,92,246,0.1); border: 1px solid rgba(139,92,246,0.2); color: var(--accent-purple);">${escapeHtml(f.language)}</span></td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error('Failed to load project files list:', err);
    }
}

async function renameActiveProject() {
    if (!activeProjectId) return;

    const newName = prompt('Enter a new name for this project:');
    if (!newName || !newName.trim()) return;

    try {
        const res = await authorizedFetch(`/projects/${activeProjectId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: newName.trim() })
        });

        if (res.ok) {
            loadProjects();
            selectProject(activeProjectId);
        } else {
            const data = await res.json();
            alert(data.detail || 'Failed to rename project.');
        }
    } catch (err) {
        alert('Rename error: ' + err.message);
    }
}

async function deleteActiveProject() {
    if (!activeProjectId) return;

    const confirmDelete = confirm('Are you sure you want to permanently delete this project? This will delete all files and reports.');
    if (!confirmDelete) return;

    try {
        const res = await authorizedFetch(`/projects/${activeProjectId}`, {
            method: 'DELETE'
        });

        if (res.ok) {
            activeProjectId = null;
            loadProjects();
        } else {
            alert('Failed to delete project.');
        }
    } catch (err) {
        alert('Delete error: ' + err.message);
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, function(m) { return map[m]; });
}

/* ==========================================================================
   AI REVIEW RUN & REPORT RENDERING FUNCTIONS
   ========================================================================== */

let analysisPollInterval = null;

async function startProjectAnalysis() {
    if (!activeProjectId) return;

    const apiKey = document.getElementById('project-analysis-key').value;
    const btn = document.getElementById('btn-start-project-analysis');
    const progressContainer = document.getElementById('analysis-progress-container');
    const progressLabel = document.getElementById('analysis-progress-label');
    const progressPct = document.getElementById('analysis-progress-pct');
    const progressBar = document.getElementById('analysis-progress-bar');
    const reportCard = document.getElementById('project-report-card');

    btn.disabled = true;
    reportCard.style.display = 'none';
    progressContainer.style.display = 'block';
    
    progressLabel.textContent = 'Enqueuing run...';
    progressPct.textContent = '10%';
    progressBar.style.width = '10%';

    try {
        const res = await authorizedFetch(`/analysis/${activeProjectId}/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: apiKey || null })
        });

        if (!res.ok) {
            const data = await res.json();
            alert(data.detail || 'Failed to start analysis.');
            progressContainer.style.display = 'none';
            btn.disabled = false;
            return;
        }

        const analysis = await res.json();
        const analysisId = analysis.id;

        // Poll analysis run status
        progressLabel.textContent = 'Reviewing codebase...';
        progressPct.textContent = '30%';
        progressBar.style.width = '30%';

        if (analysisPollInterval) clearInterval(analysisPollInterval);
        
        analysisPollInterval = setInterval(async () => {
            try {
                const statusRes = await authorizedFetch(`/analysis/${analysisId}`);
                if (!statusRes.ok) return;

                const run = await statusRes.json();
                if (run.status === 'running') {
                    progressLabel.textContent = 'AI is writing the report...';
                    progressPct.textContent = '65%';
                    progressBar.style.width = '65%';
                } else if (run.status === 'completed') {
                    clearInterval(analysisPollInterval);
                    progressLabel.textContent = 'Analysis Completed!';
                    progressPct.textContent = '100%';
                    progressBar.style.width = '100%';

                    // Load the report details
                    await loadProjectReport(analysisId);
                    
                    // Refresh project stats (updates status badge & last run time)
                    await selectProject(activeProjectId);

                    setTimeout(() => {
                        progressContainer.style.display = 'none';
                        btn.disabled = false;
                    }, 2000);
                } else if (run.status === 'failed') {
                    clearInterval(analysisPollInterval);
                    alert('AI Review run encountered an error or timed out.');
                    progressContainer.style.display = 'none';
                    btn.disabled = false;
                }
            } catch (err) {
                console.error('Error polling status:', err);
            }
        }, 1500);

    } catch (err) {
        alert('Error starting review: ' + err.message);
        progressContainer.style.display = 'none';
        btn.disabled = false;
    }
}

async function loadProjectReport(analysisId) {
    try {
        const res = await authorizedFetch(`/analysis/${analysisId}/report`);
        if (!res.ok) return;

        const report = await res.json();
        
        // Query the analysis details to read model_used and duration
        const runRes = await authorizedFetch(`/analysis/${analysisId}`);
        let modelUsed = "mock-simulator";
        let durationStr = "0.00s";
        if (runRes.ok) {
            const run = await runRes.json();
            modelUsed = run.model_used || "mock-simulator";
            durationStr = run.duration !== null ? `${run.duration.toFixed(3)}s` : "0.000s";
        }

        renderProjectReport(report, modelUsed, durationStr);
    } catch (err) {
        console.error('Failed to load project report:', err);
    }
}

function renderProjectReport(report, modelUsed = "--", durationStr = "--") {
    let data;
    try {
        data = typeof report.details_json === 'string' 
            ? jsonParseSafe(report.details_json) 
            : report.details_json;
    } catch (err) {
        data = report;
    }

    if (!data) return;

    // Render metadata labels
    document.getElementById('report-meta-engine').textContent = modelUsed;
    document.getElementById('report-meta-duration').textContent = durationStr;

    // Set score and badge color
    const scoreBadge = document.getElementById('report-score-badge');
    scoreBadge.textContent = `${data.score || 0}/100`;
    
    // Set Executive Summary
    document.getElementById('report-summary-text').textContent = data.summary || 'No summary text available.';

    // Populate lists helper
    const populateList = (elementId, items) => {
        const el = document.getElementById(elementId);
        el.innerHTML = '';
        if (items && items.length > 0) {
            items.forEach(item => {
                const li = document.createElement('li');
                li.textContent = item;
                el.appendChild(li);
            });
        } else {
            el.innerHTML = '<li style="color: var(--text-muted);">None noted.</li>';
        }
    };

    populateList('report-strengths-list', data.strengths);
    populateList('report-weaknesses-list', data.weaknesses);
    populateList('report-recommendations-list', data.recommendations);

    // Populate Issues table
    const tbody = document.getElementById('report-issues-tbody');
    tbody.innerHTML = '';
    const issues = data.issues || [];

    if (issues.length === 0) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="5">No issues detected by the AI Review Engine. Excellent!</td></tr>';
    } else {
        issues.forEach(issue => {
            const tr = document.createElement('tr');
            const severityClass = `badge-severity-${(issue.severity || 'low').toLowerCase()}`;
            tr.innerHTML = `
                <td><span class="pill outline" style="font-size: 11px;">${escapeHtml(issue.category)}</span></td>
                <td><span class="${severityClass}">${escapeHtml(issue.severity)}</span></td>
                <td style="font-family: var(--font-mono); font-size: 12px; color: var(--text-bright);">${escapeHtml(issue.file)}</td>
                <td>
                    <div style="font-weight: 600; color: var(--text-bright); margin-bottom: 4px;">${escapeHtml(issue.title)}</div>
                    <div style="font-size: 12px; color: var(--text-muted); line-height: 1.4;">${escapeHtml(issue.description)}</div>
                </td>
                <td style="font-size: 12px; color: var(--accent-teal); line-height: 1.4;">${escapeHtml(issue.recommendation)}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    // Render static code analyzer metrics if available
    if (data.analyzers) {
        const analyzers = data.analyzers;
        const summary = analyzers.summary || {};

        // 1. Complexity Gauge
        const complexityVal = summary.avg_complexity || 1.0;
        document.getElementById('gauge-val-complexity').textContent = complexityVal;
        // Circumference of r=38 circle is 2*pi*38 ~ 238
        // Cap complexity mapping value at 15 for gauge visual reference
        const complexityDash = Math.min(238, Math.max(0, (complexityVal / 15) * 238));
        document.getElementById('gauge-fill-complexity').setAttribute('stroke-dasharray', `${complexityDash} 238`);
        
        const complRating = (summary.complexity_rating || 'LOW').toUpperCase();
        const complEl = document.getElementById('rating-complexity');
        complEl.textContent = complRating;
        complEl.className = 'rating-pill ' + (complRating === 'LOW' ? 'green' : complRating === 'MODERATE' ? 'orange' : 'red');

        // 2. Maintainability Gauge
        const miVal = summary.avg_maintainability || 100;
        document.getElementById('gauge-val-maintainability').textContent = `${Math.round(miVal)}%`;
        const miDash = Math.min(238, Math.max(0, (miVal / 100) * 238));
        document.getElementById('gauge-fill-maintainability').setAttribute('stroke-dasharray', `${miDash} 238`);

        const miRating = (summary.maintainability_rating || 'EXCELLENT').toUpperCase();
        const miEl = document.getElementById('rating-maintainability');
        miEl.textContent = miRating === 'NEEDS REFACTORING' ? 'REFACTOR' : miRating;
        miEl.className = 'rating-pill ' + (miRating === 'EXCELLENT' ? 'green' : miRating === 'MODERATE' ? 'orange' : 'red');

        // 3. Security Gauge
        const securityVal = summary.vulnerabilities_count || 0;
        document.getElementById('gauge-val-security').textContent = securityVal;
        const secDash = securityVal === 0 ? 0 : Math.min(238, (securityVal / 10) * 238);
        document.getElementById('gauge-fill-security').setAttribute('stroke-dasharray', `${secDash} 238`);

        const secRating = (summary.security_rating || 'SECURE').toUpperCase();
        const secEl = document.getElementById('rating-security');
        secEl.textContent = secRating;
        secEl.className = 'rating-pill ' + (secRating === 'SECURE' ? 'green' : secRating === 'LOW RISK' ? 'orange' : 'red');

        // 4. Populate Files Metrics Table
        const filesBody = document.getElementById('analyzer-files-tbody');
        filesBody.innerHTML = '';
        const files = analyzers.files || [];
        if (files.length === 0) {
            filesBody.innerHTML = '<tr class="empty-row"><td colspan="6">No files evaluated.</td></tr>';
        } else {
            files.forEach(f => {
                const tr = document.createElement('tr');
                const alertBadgeClass = f.vulnerabilities_count > 0 ? 'badge red-glow' : 'badge';
                tr.innerHTML = `
                    <td style="font-family: var(--font-mono); color: var(--text-bright);">${escapeHtml(f.file)}</td>
                    <td><span class="pill outline" style="font-size: 11px;">${escapeHtml(f.language)}</span></td>
                    <td style="font-family: var(--font-mono);">${f.loc}</td>
                    <td style="font-family: var(--font-mono);">${f.complexity}</td>
                    <td style="font-family: var(--font-mono); font-weight: 600; color: ${f.maintainability >= 80 ? 'var(--accent-green)' : f.maintainability >= 55 ? 'var(--accent-orange)' : 'var(--accent-red)'};">${f.maintainability}%</td>
                    <td><span class="${alertBadgeClass}">${f.vulnerabilities_count}</span></td>
                `;
                filesBody.appendChild(tr);
            });
        }

        // 5. Populate Static Vulnerability Alerts Table
        const vulnsBody = document.getElementById('analyzer-vulns-tbody');
        vulnsBody.innerHTML = '';
        const vulns = analyzers.vulnerabilities || [];
        if (vulns.length === 0) {
            vulnsBody.innerHTML = '<tr class="empty-row"><td colspan="5">No security warnings flagged. Good job!</td></tr>';
        } else {
            vulns.forEach(v => {
                const tr = document.createElement('tr');
                const sevClass = `badge-severity-${(v.severity || 'low').toLowerCase()}`;
                tr.innerHTML = `
                    <td><span class="pill outline" style="font-size: 11px;">${escapeHtml(v.category)}</span></td>
                    <td><span class="${sevClass}">${escapeHtml(v.severity)}</span></td>
                    <td style="font-family: var(--font-mono); font-size: 12px; color: var(--text-bright);">${escapeHtml(v.file)}:${v.line}</td>
                    <td>
                        <div style="font-weight: 600; color: var(--text-bright); margin-bottom: 4px;">${escapeHtml(v.title)}</div>
                        <div style="font-size: 12px; color: var(--text-muted); line-height: 1.4;">${escapeHtml(v.description)}</div>
                    </td>
                    <td style="font-size: 12px; color: var(--accent-teal); line-height: 1.4;">${escapeHtml(v.recommendation)}</td>
                `;
                vulnsBody.appendChild(tr);
            });
        }
    } else {
        // Reset/Empty Analyzer tabs
        document.getElementById('gauge-val-complexity').textContent = '--';
        document.getElementById('gauge-fill-complexity').setAttribute('stroke-dasharray', '0 238');
        document.getElementById('rating-complexity').textContent = '--';
        document.getElementById('rating-complexity').className = 'rating-pill';

        document.getElementById('gauge-val-maintainability').textContent = '--';
        document.getElementById('gauge-fill-maintainability').setAttribute('stroke-dasharray', '0 238');
        document.getElementById('rating-maintainability').textContent = '--';
        document.getElementById('rating-maintainability').className = 'rating-pill';

        document.getElementById('gauge-val-security').textContent = '--';
        document.getElementById('gauge-fill-security').setAttribute('stroke-dasharray', '0 238');
        document.getElementById('rating-security').textContent = '--';
        document.getElementById('rating-security').className = 'rating-pill';

        document.getElementById('analyzer-files-tbody').innerHTML = '<tr class="empty-row"><td colspan="6">No records.</td></tr>';
        document.getElementById('analyzer-vulns-tbody').innerHTML = '<tr class="empty-row"><td colspan="5">No security warnings flagged.</td></tr>';
    }

    document.getElementById('project-report-card').style.display = 'block';
}

function switchReportTab(tab) {
    const aiBtn = document.getElementById('btn-subtab-ai');
    const staticBtn = document.getElementById('btn-subtab-static');
    const aiPane = document.getElementById('report-subtab-ai');
    const staticPane = document.getElementById('report-subtab-static');

    if (!aiBtn || !staticBtn || !aiPane || !staticPane) return;

    if (tab === 'ai') {
        aiBtn.classList.add('active');
        staticBtn.classList.remove('active');
        aiPane.classList.add('active');
        staticPane.classList.remove('active');
    } else {
        staticBtn.classList.add('active');
        aiBtn.classList.remove('active');
        staticPane.classList.add('active');
        aiPane.classList.remove('active');
    }
}

function jsonParseSafe(str) {
    try {
        return JSON.parse(str);
    } catch (e) {
        return {};
    }
}
