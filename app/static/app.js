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
    const versionsBtn = document.getElementById('nav-item-versions');
    if (versionsBtn) versionsBtn.style.display = 'none';
    const chatBtn = document.getElementById('nav-item-chat');
    if (chatBtn) chatBtn.style.display = 'none';

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
            } else if (targetView === 'view-versions') {
                loadProjectVersions(activeProjectId);
            } else if (targetView === 'view-chat') {
                loadProjectChat(activeProjectId);
            } else if (targetView === 'view-pull-requests') {
                loadProjectPullRequests(activeProjectId);
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
            const prBtn = document.getElementById('nav-item-pull-requests');
            if (prBtn) prBtn.style.display = 'none';
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
        
        const versionsBtn = document.getElementById('nav-item-versions');
        if (versionsBtn) versionsBtn.style.display = 'block';
        const chatBtn = document.getElementById('nav-item-chat');
        if (chatBtn) chatBtn.style.display = 'block';
        const prBtn = document.getElementById('nav-item-pull-requests');
        if (prBtn) prBtn.style.display = 'block';

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

function startAnalysisPolling(analysisId) {
    const progressContainer = document.getElementById('analysis-progress-container');
    const progressLabel = document.getElementById('analysis-progress-label');
    const progressPct = document.getElementById('analysis-progress-pct');
    const btn = document.getElementById('btn-start-project-analysis');
    const reportCard = document.getElementById('project-report-card');

    if (btn) btn.disabled = true;
    if (reportCard) reportCard.style.display = 'none';
    if (progressContainer) progressContainer.style.display = 'block';

    if (progressLabel) progressLabel.textContent = 'Reviewing codebase...';
    if (progressPct) progressPct.textContent = '10%';

    // Initialize timeline indicators as pending
    document.querySelectorAll('.pipeline-step').forEach(step => {
        step.className = 'pipeline-step pending';
        const durEl = step.querySelector('.step-duration');
        if (durEl) durEl.textContent = '--';
    });

    if (analysisPollInterval) clearInterval(analysisPollInterval);

    analysisPollInterval = setInterval(async () => {
        try {
            const statusRes = await authorizedFetch(`/analysis/${analysisId}`);
            if (!statusRes.ok) return;

            const run = await statusRes.json();

            // Update Timeline UI
            if (run.pipeline_stages) {
                try {
                    const stages = typeof run.pipeline_stages === 'string'
                        ? JSON.parse(run.pipeline_stages)
                        : run.pipeline_stages;

                    const stageIds = {
                        "Load Intelligence": "step-load-intel",
                        "Prioritize Files": "step-prioritize-files",
                        "Module Reviews": "step-module-reviews",
                        "Merge Results": "step-merge-results",
                        "Validate Findings": "step-validate-findings",
                        "Generate Report": "step-generate-report"
                    };

                    let completedCount = 0;
                    stages.forEach(s => {
                        const stepId = stageIds[s.stage];
                        if (!stepId) return;

                        const stepEl = document.getElementById(stepId);
                        if (stepEl) {
                            stepEl.className = `pipeline-step ${s.status}`;
                            const durEl = stepEl.querySelector('.step-duration');
                            if (durEl) {
                                durEl.textContent = s.status === 'completed'
                                    ? `${s.duration.toFixed(3)}s`
                                    : (s.status === 'running' ? 'running...' : '--');
                            }
                        }
                        if (s.status === 'completed') {
                            completedCount++;
                        }
                    });

                    const progressPercent = Math.round((completedCount / stages.length) * 100);
                    if (progressPct) progressPct.textContent = `${progressPercent}%`;
                } catch (e) {
                    console.error("Error parsing stages:", e);
                }
            }

            if (run.status === 'running') {
                if (progressLabel) progressLabel.textContent = 'Executing modular reviews...';
            } else if (run.status === 'completed') {
                clearInterval(analysisPollInterval);
                if (progressLabel) progressLabel.textContent = 'Analysis Completed!';
                if (progressPct) progressPct.textContent = '100%';

                await loadProjectReport(analysisId);
                await selectProject(activeProjectId);

                setTimeout(() => {
                    if (progressContainer) progressContainer.style.display = 'none';
                    if (btn) btn.disabled = false;
                }, 2000);
            } else if (run.status === 'failed') {
                clearInterval(analysisPollInterval);
                alert('AI Review run encountered an error or timed out.');
                if (progressContainer) progressContainer.style.display = 'none';
                if (btn) btn.disabled = false;
            }
        } catch (err) {
            console.error('Error polling status:', err);
        }
    }, 1500);
}

async function startProjectAnalysis() {
    if (!activeProjectId) return;

    const apiKey = document.getElementById('project-analysis-key').value;
    const btn = document.getElementById('btn-start-project-analysis');
    const progressContainer = document.getElementById('analysis-progress-container');

    btn.disabled = true;
    progressContainer.style.display = 'block';

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
        startAnalysisPolling(analysis.id);

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
        let runData = null;
        if (runRes.ok) {
            runData = await runRes.json();
            modelUsed = runData.model_used || "mock-simulator";
            durationStr = runData.duration !== null ? `${runData.duration.toFixed(3)}s` : "0.000s";
        }

        renderProjectReport(report, modelUsed, durationStr, runData);
    } catch (err) {
        console.error('Failed to load project report:', err);
    }
}

function renderProjectReport(report, modelUsed = "--", durationStr = "--", run = null) {
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

    // Render Pipeline Telemetry details (v1.5)
    if (run) {
        document.getElementById('telemetry-coverage').textContent = run.coverage_percentage !== null ? `${run.coverage_percentage}%` : '--';
        document.getElementById('telemetry-files-reviewed').textContent = `${run.files_reviewed || 0} / ${run.total_files || 0}`;
        document.getElementById('telemetry-ai-calls').textContent = run.ai_calls !== null ? run.ai_calls : '0';
        document.getElementById('telemetry-confidence').textContent = run.overall_confidence !== null ? `${Math.round(run.overall_confidence * 100)}%` : '--';
        
        // Modules Reviewed
        const modulesListEl = document.getElementById('telemetry-modules-list');
        modulesListEl.innerHTML = '';
        if (run.modules_reviewed) {
            try {
                const modules = typeof run.modules_reviewed === 'string' ? JSON.parse(run.modules_reviewed) : run.modules_reviewed;
                if (modules && modules.length > 0) {
                    modules.forEach(m => {
                        const badge = document.createElement('span');
                        badge.className = 'pill outline';
                        badge.style.fontSize = '11px';
                        badge.style.borderColor = 'rgba(139,92,246,0.3)';
                        badge.style.color = 'var(--accent-purple)';
                        badge.textContent = m;
                        modulesListEl.appendChild(badge);
                    });
                } else {
                    modulesListEl.innerHTML = '<span style="color: var(--text-muted);">None</span>';
                }
            } catch (e) {
                console.error("Error rendering modules reviewed:", e);
            }
        } else {
            modulesListEl.innerHTML = '<span style="color: var(--text-muted);">None</span>';
        }
        
        // Skipped Files List
        const skippedCountEl = document.getElementById('telemetry-skipped-count');
        const skippedSection = document.getElementById('telemetry-skipped-section');
        const skippedListEl = document.getElementById('telemetry-skipped-list');
        
        skippedListEl.innerHTML = '';
        if (run.skipped_reasons_json) {
            try {
                const skipped = typeof run.skipped_reasons_json === 'string' ? JSON.parse(run.skipped_reasons_json) : run.skipped_reasons_json;
                const fileNames = Object.keys(skipped || {});
                skippedCountEl.textContent = fileNames.length;
                if (fileNames.length > 0) {
                    skippedSection.style.display = 'flex';
                    fileNames.forEach(fn => {
                        const div = document.createElement('div');
                        div.style.display = 'flex';
                        div.style.justifyContent = 'space-between';
                        div.style.marginBottom = '4px';
                        div.style.borderBottom = '1px solid rgba(255,255,255,0.02)';
                        div.style.paddingBottom = '2px';
                        div.innerHTML = `<span style="color: var(--text-muted); text-align: left; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 70%;">${escapeHtml(fn)}</span> <span class="pill outline" style="font-size: 10px; color: #fca5a5; border-color: rgba(239, 68, 68, 0.2);">${escapeHtml(skipped[fn])}</span>`;
                        skippedListEl.appendChild(div);
                    });
                } else {
                    skippedSection.style.display = 'none';
                }
            } catch (e) {
                console.error("Error rendering skipped list:", e);
                skippedSection.style.display = 'none';
            }
        } else {
            skippedSection.style.display = 'none';
        }
    } else {
        // Fallback if run object is not supplied (e.g. from static config loading)
        document.getElementById('telemetry-coverage').textContent = '--';
        document.getElementById('telemetry-files-reviewed').textContent = '--';
        document.getElementById('telemetry-ai-calls').textContent = '--';
        document.getElementById('telemetry-confidence').textContent = '--';
        document.getElementById('telemetry-modules-list').innerHTML = '--';
        document.getElementById('telemetry-skipped-section').style.display = 'none';
    }

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
        tbody.innerHTML = '<tr class="empty-row"><td colspan="6">No issues detected by the AI Review Engine. Excellent!</td></tr>';
    } else {
        issues.forEach(issue => {
            const tr = document.createElement('tr');
            const severityClass = `badge-severity-${(issue.severity || 'low').toLowerCase()}`;
            const fileWithLine = issue.line ? `${issue.file}#L${issue.line}` : issue.file;
            const issueTitle = issue.title || `${issue.category} finding in ${issue.file}`;
            const issueExplanation = issue.explanation || issue.description || '';
            
            tr.innerHTML = `
                <td><span class="pill outline" style="font-size: 11px;">${escapeHtml(issue.category)}</span></td>
                <td><span class="${severityClass}">${escapeHtml(issue.severity)}</span></td>
                <td style="font-family: var(--font-mono); font-size: 12px; color: var(--text-bright); word-break: break-all;">${escapeHtml(fileWithLine)}</td>
                <td>
                    <div style="font-weight: 600; color: var(--text-bright); margin-bottom: 4px;">${escapeHtml(issueTitle)}</div>
                    <div style="font-size: 12px; color: var(--text-muted); line-height: 1.4; margin-bottom: 6px;">${escapeHtml(issueExplanation)}</div>
                    ${issue.evidence ? `<div style="font-family: var(--font-mono); font-size: 11px; padding: 6px 10px; background: rgba(0,0,0,0.2); border-left: 3px solid var(--accent-purple); border-radius: 4px; color: #e9d5ff; overflow-x: auto; white-space: pre-wrap; word-break: break-all;">${escapeHtml(issue.evidence)}</div>` : ''}
                </td>
                <td style="font-size: 12px; color: var(--accent-teal); line-height: 1.4;">${escapeHtml(issue.recommendation)}</td>
            `;

            // Action cell with Apply Fix button
            const tdAction = document.createElement('td');
            const fixBtn = document.createElement('button');
            fixBtn.className = 'btn btn-primary btn-sm';
            fixBtn.style.margin = '0';
            fixBtn.style.padding = '4px 8px';
            fixBtn.style.fontSize = '12px';
            fixBtn.textContent = 'Apply Fix';
            fixBtn.addEventListener('click', async () => {
                const originalText = fixBtn.textContent;
                fixBtn.disabled = true;
                fixBtn.textContent = 'Fixing...';
                
                try {
                    const apiKey = document.getElementById('project-analysis-key').value;
                    const res = await authorizedFetch(`/projects/${activeProjectId}/versions/apply-fix`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            issue: issue,
                            api_key: apiKey || null
                        })
                    });
                    
                    if (res.ok) {
                        const newVer = await res.json();
                        alert(`Successfully applied fix for ${issue.category} finding in '${issue.file}'. Version ${newVer.version_number} has been created and code is being analyzed.`);
                        
                        // Switch view to Projects page to show timeline progress
                        const navProjectsBtn = document.querySelector('.nav-item[data-view="view-projects"]');
                        if (navProjectsBtn) navProjectsBtn.click();
                        
                        // Start polling progress for the new analysis run!
                        if (newVer.source_analysis_id) {
                            startAnalysisPolling(newVer.source_analysis_id);
                        }
                    } else {
                        const data = await res.json();
                        alert(data.detail || 'Failed to apply fix.');
                        fixBtn.disabled = false;
                        fixBtn.textContent = originalText;
                    }
                } catch (err) {
                    alert('Fix application error: ' + err.message);
                    fixBtn.disabled = false;
                    fixBtn.textContent = originalText;
                }
            });
            tdAction.appendChild(fixBtn);
            tr.appendChild(tdAction);

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

/* ==========================================================================
   PROJECT VERSIONING & WORKSPACE MANAGEMENT
   ========================================================================== */

let versionList = [];

async function loadProjectVersions(projectId) {
    if (!projectId) return;

    try {
        const res = await authorizedFetch(`/projects/${projectId}/versions`);
        if (!res.ok) return;

        versionList = await res.json();
        
        // 1. Populate current head version labels
        if (versionList.length > 0) {
            const head = versionList[0]; // ordered desc
            document.getElementById('head-version-badge').textContent = `v${head.version_number}`;
            document.getElementById('current-ver-name').textContent = `Version ${head.version_number}`;
            document.getElementById('current-ver-date').textContent = new Date(head.created_at).toLocaleString();
            document.getElementById('current-ver-summary').textContent = head.summary || 'Initial baseline';
        }

        // 2. Populate comparison selector dropdowns
        const compare1 = document.getElementById('compare-ver-1');
        const compare2 = document.getElementById('compare-ver-2');
        compare1.innerHTML = '';
        compare2.innerHTML = '';

        versionList.forEach((v, index) => {
            const opt1 = document.createElement('option');
            opt1.value = v.id;
            opt1.textContent = `v${v.version_number} - ${v.summary ? v.summary.substring(0, 40) : 'Snapshot'}`;
            if (index === versionList.length - 1) opt1.selected = true;
            compare1.appendChild(opt1);

            const opt2 = document.createElement('option');
            opt2.value = v.id;
            opt2.textContent = `v${v.version_number} - ${v.summary ? v.summary.substring(0, 40) : 'Snapshot'}`;
            if (index === 0) opt2.selected = true;
            compare2.appendChild(opt2);
        });

        // 3. Render Snapshots History Table
        const tbody = document.getElementById('versions-history-tbody');
        tbody.innerHTML = '';

        versionList.forEach(v => {
            const tr = document.createElement('tr');
            
            // Format applied fixes
            let fixesStr = 'None';
            if (v.applied_fixes) {
                try {
                    const fixes = JSON.parse(v.applied_fixes);
                    if (fixes.length > 0) {
                        fixesStr = fixes.map(f => {
                            if (f.restored_from) return `Restored v${f.restored_from}`;
                            return `${f.category || 'Fix'} in ${f.file || 'code'}`;
                        }).join(', ');
                    }
                } catch (e) {}
            }

            tr.innerHTML = `
                <td style="font-weight: 700; color: var(--accent-purple);">v${v.version_number}</td>
                <td style="font-size: 13px;">${escapeHtml(v.summary || 'Baseline snapshot.')}</td>
                <td style="font-size: 12px; color: var(--text-muted);">${escapeHtml(fixesStr)}</td>
                <td style="font-size: 12px; color: var(--text-main); white-space: nowrap;">${new Date(v.created_at).toLocaleString()}</td>
            `;

            // Actions Cell
            const tdActions = document.createElement('td');
            tdActions.style.whiteSpace = 'nowrap';

            // Download Button
            const dlBtn = document.createElement('button');
            dlBtn.className = 'btn btn-secondary btn-sm';
            dlBtn.style.margin = '0 4px 0 0';
            dlBtn.textContent = '📥 Download';
            dlBtn.addEventListener('click', () => {
                window.location.href = `/projects/${projectId}/versions/${v.id}/download`;
            });
            tdActions.appendChild(dlBtn);

            // Restore Button
            if (v.id !== versionList[0].id) {
                const rstBtn = document.createElement('button');
                rstBtn.className = 'btn btn-secondary btn-sm';
                rstBtn.style.margin = '0';
                rstBtn.textContent = '⏪ Restore';
                rstBtn.addEventListener('click', async () => {
                    const confirmRestore = confirm(`Are you sure you want to restore the codebase back to Version ${v.version_number}? This will create a new immutable version in the workspace history.`);
                    if (!confirmRestore) return;

                    rstBtn.disabled = true;
                    rstBtn.textContent = 'Restoring...';

                    try {
                        const res = await authorizedFetch(`/projects/${projectId}/versions/${v.id}/restore`, {
                            method: 'POST'
                        });

                        if (res.ok) {
                            const newVer = await res.json();
                            alert(`Project successfully restored to Version ${v.version_number}. Version ${newVer.version_number} is created.`);
                            
                            // Load project pane & start polling progress
                            const navProjectsBtn = document.querySelector('.nav-item[data-view="view-projects"]');
                            if (navProjectsBtn) navProjectsBtn.click();
                            
                            if (newVer.source_analysis_id) {
                                startAnalysisPolling(newVer.source_analysis_id);
                            }
                        } else {
                            const data = await res.json();
                            alert(data.detail || 'Failed to restore version.');
                            rstBtn.disabled = false;
                            rstBtn.textContent = '⏪ Restore';
                        }
                    } catch (err) {
                        alert('Restore error: ' + err.message);
                        rstBtn.disabled = false;
                        rstBtn.textContent = '⏪ Restore';
                    }
                });
                tdActions.appendChild(rstBtn);
            }

            tr.appendChild(tdActions);
            tbody.appendChild(tr);
        });

        // 4. Render Workspace Evolution Timeline
        const timelineContainer = document.getElementById('evolution-timeline-container');
        timelineContainer.innerHTML = '';

        // Iterate in chronological order
        const chronVersions = [...versionList].reverse();
        chronVersions.forEach((v, index) => {
            const isHead = index === chronVersions.length - 1;
            const node = document.createElement('div');
            node.className = 'timeline-node';
            node.style.position = 'relative';
            node.style.paddingBottom = '16px';

            const dotStyle = isHead 
                ? 'background: var(--accent-purple); box-shadow: 0 0 10px var(--accent-purple); width: 12px; height: 12px; left: -25px;'
                : 'background: var(--accent-teal); box-shadow: 0 0 6px var(--accent-teal); width: 8px; height: 8px; left: -23px;';

            let icon = '📁';
            let label = 'Project Created';
            
            if (v.version_number > 1) {
                if (v.applied_fixes.includes('restored_from')) {
                    icon = '⏪';
                    label = 'Restore';
                } else if (v.applied_fixes && JSON.parse(v.applied_fixes).length > 0) {
                    icon = '🛠️';
                    label = 'Fix Applied';
                } else {
                    icon = '🔄';
                    label = 'Analysis Sync';
                }
            }

            node.innerHTML = `
                <div style="position: absolute; top: 4px; border-radius: 50%; ${dotStyle} transition: all 0.3s;"></div>
                <div style="font-weight: 700; font-size: 14px; color: var(--text-bright); display: flex; align-items: center; gap: 8px;">
                    <span>${icon}</span>
                    <span>${label} (v${v.version_number})</span>
                    ${isHead ? '<span class="pill outline" style="font-size: 10px; color: var(--accent-purple); border-color: rgba(139,92,246,0.3); padding: 1px 6px;">Latest</span>' : ''}
                </div>
                <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">${new Date(v.created_at).toLocaleString()}</div>
                <div style="font-size: 13px; color: var(--text-main); line-height: 1.4;">${escapeHtml(v.summary || 'Codebase snapshot enqueued.')}</div>
            `;
            timelineContainer.appendChild(node);
        });

    } catch (err) {
        console.error('Failed to load project versions:', err);
    }
}

async function runVersionsComparison() {
    if (!activeProjectId) return;

    const v1Id = document.getElementById('compare-ver-1').value;
    const v2Id = document.getElementById('compare-ver-2').value;

    if (!v1Id || !v2Id) {
        alert('Please select both older (base) and newer (target) versions.');
        return;
    }

    const btn = document.getElementById('btn-run-compare');
    btn.disabled = true;
    btn.textContent = 'Comparing...';

    try {
        const res = await authorizedFetch(`/projects/${activeProjectId}/versions/compare/details?v1_id=${v1Id}&v2_id=${v2Id}`);
        if (!res.ok) {
            const data = await res.json();
            alert(data.detail || 'Comparison failed.');
            return;
        }

        const comparison = await res.json();

        // 1. Populate stats cards
        document.getElementById('compare-stat-files').textContent = comparison.files_changed_count;
        document.getElementById('compare-stat-added').textContent = `+${comparison.lines_added}`;
        document.getElementById('compare-stat-removed').textContent = `-${comparison.lines_removed}`;

        // 2. Populate fixed issues list
        const fixedList = document.getElementById('compare-fixed-issues');
        fixedList.innerHTML = '';
        if (comparison.issues_fixed && comparison.issues_fixed.length > 0) {
            comparison.issues_fixed.forEach(iss => {
                const li = document.createElement('li');
                li.style.marginBottom = '4px';
                li.innerHTML = `<strong style="color: var(--accent-green);">Fixed:</strong> ${escapeHtml(iss.category)} issue in <code>${escapeHtml(iss.file)}#L${iss.line}</code>: ${escapeHtml(iss.explanation || iss.description)}`;
                fixedList.appendChild(li);
            });
        } else {
            fixedList.innerHTML = '<li style="color: var(--text-muted);">No issues resolved in this comparison delta.</li>';
        }

        // 3. Populate remaining issues list
        const remainingList = document.getElementById('compare-remaining-issues');
        remainingList.innerHTML = '';
        if (comparison.remaining_issues && comparison.remaining_issues.length > 0) {
            comparison.remaining_issues.forEach(iss => {
                const li = document.createElement('li');
                li.style.marginBottom = '4px';
                li.innerHTML = `<strong style="color: var(--accent-orange);">Remaining:</strong> ${escapeHtml(iss.category)} finding in <code>${escapeHtml(iss.file)}#L${iss.line}</code>`;
                remainingList.appendChild(li);
            });
        } else {
            remainingList.innerHTML = '<li style="color: var(--accent-green); font-weight: 500;">🎉 Codebase has zero remaining warnings!</li>';
        }

        // 4. Handle Code Diff Dropdown
        const fileSelector = document.getElementById('compare-diff-file-selector');
        fileSelector.innerHTML = '';

        const diffFiles = Object.keys(comparison.diffs || {});
        if (diffFiles.length > 0) {
            diffFiles.forEach(fn => {
                const opt = document.createElement('option');
                opt.value = fn;
                opt.textContent = fn;
                fileSelector.appendChild(opt);
            });

            fileSelector.onchange = () => {
                renderGitDiff(comparison.diffs[fileSelector.value]);
            };

            renderGitDiff(comparison.diffs[diffFiles[0]]);
            
            document.getElementById('compare-diff-viewer').style.display = 'flex';
        } else {
            document.getElementById('compare-diff-viewer').style.display = 'none';
        }

        // Switch panel visibility
        document.getElementById('compare-placeholder').style.display = 'none';
        document.getElementById('compare-stats-card').style.display = 'block';

    } catch (err) {
        alert('Comparison error: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Compare';
    }
}

function renderGitDiff(diffText) {
    const diffContainer = document.getElementById('compare-diff-content');
    if (!diffText) {
        diffContainer.innerHTML = '<span style="color: var(--text-muted);">No modifications in this file.</span>';
        return;
    }

    const lines = diffText.split('\n');
    let highlightedHTML = '';

    lines.forEach(line => {
        let lineClass = '';
        if (line.startsWith('+') && !line.startsWith('+++')) {
            lineClass = 'style="background: rgba(16, 185, 129, 0.15); color: #34d399; display: block; width: 100%;"';
        } else if (line.startsWith('-') && !line.startsWith('---')) {
            lineClass = 'style="background: rgba(239, 68, 68, 0.15); color: #fca5a5; display: block; width: 100%;"';
        } else if (line.startsWith('@@')) {
            lineClass = 'style="color: var(--accent-purple); font-weight: 600; display: block;"';
        }
        highlightedHTML += `<div ${lineClass}>${escapeHtml(line)}</div>`;
    });

    diffContainer.innerHTML = highlightedHTML;
}

// Bind comparison button click handler
document.addEventListener('DOMContentLoaded', () => {
    const runCompareBtn = document.getElementById('btn-run-compare');
    if (runCompareBtn) {
        runCompareBtn.addEventListener('click', runVersionsComparison);
    }

    // Chat view bindings
    const chatForm = document.getElementById('chat-input-form');
    if (chatForm) {
        chatForm.addEventListener('submit', handleChatSubmit);
    }

    const clearChatBtn = document.getElementById('btn-clear-chat');
    if (clearChatBtn) {
        clearChatBtn.addEventListener('click', clearProjectChat);
    }

    // Suggested tags click events
    const tagExplain = document.getElementById('suggest-tag-explain');
    if (tagExplain) tagExplain.addEventListener('click', () => selectSuggestedChat('Explain this project'));
    const tagAuth = document.getElementById('suggest-tag-auth');
    if (tagAuth) tagAuth.addEventListener('click', () => selectSuggestedChat('Explain authentication flow'));
    const tagRefactor = document.getElementById('suggest-tag-refactor');
    if (tagRefactor) tagRefactor.addEventListener('click', () => selectSuggestedChat('Suggest refactoring'));
    const tagReadme = document.getElementById('suggest-tag-readme');
    if (tagReadme) tagReadme.addEventListener('click', () => selectSuggestedChat('Generate README'));
});

// AI Project Chat Logic
let activeChatMessages = [];

async function loadProjectChat(projectId) {
    const messagesContainer = document.getElementById('chat-messages-container');
    if (!messagesContainer) return;
    
    messagesContainer.innerHTML = '<div style="color: var(--text-muted); font-style: italic; padding: 20px; text-align: center;">Loading chat history...</div>';
    
    try {
        const res = await authorizedFetch(`/projects/${projectId}/chat/history`);
        if (!res.ok) {
            messagesContainer.innerHTML = '<div style="color: var(--text-muted); font-style: italic; padding: 20px; text-align: center;">Failed to load chat history.</div>';
            return;
        }
        
        const history = await res.json();
        activeChatMessages = history;
        messagesContainer.innerHTML = '';
        
        if (history.length === 0) {
            messagesContainer.innerHTML = '<div style="color: var(--text-muted); font-style: italic; padding: 20px; text-align: center;" id="chat-empty-notice">Ask a question to start the conversation!</div>';
            resetCitationsInspector();
            return;
        }
        
        history.forEach(msg => {
            renderChatMessage(msg);
        });
        
        // Highlight active citations for the last message
        const lastMsg = history[history.length - 1];
        if (lastMsg) {
            updateCitationsInspector(lastMsg);
        }
        
        scrollChatToBottom();
    } catch (err) {
        console.error('Failed to load chat:', err);
        messagesContainer.innerHTML = '<div style="color: var(--text-muted); font-style: italic; padding: 20px; text-align: center;">Connection error.</div>';
    }
}

function scrollChatToBottom() {
    const messagesContainer = document.getElementById('chat-messages-container');
    if (messagesContainer) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
}

function renderChatMessage(msg) {
    const messagesContainer = document.getElementById('chat-messages-container');
    if (!messagesContainer) return;
    
    // Remove empty notice if exists
    const notice = document.getElementById('chat-empty-notice');
    if (notice) notice.remove();
    
    const bubble = document.createElement('div');
    bubble.className = `chat-msg ${msg.role}`;
    bubble.id = `chat-msg-${msg.id}`;
    
    const roleSpan = document.createElement('span');
    roleSpan.className = 'chat-msg-role';
    roleSpan.textContent = msg.role === 'user' ? 'User' : 'Assistant';
    bubble.appendChild(roleSpan);
    
    const contentDiv = document.createElement('div');
    contentDiv.innerHTML = formatMarkdown(msg.content);
    bubble.appendChild(contentDiv);
    
    if (msg.role === 'assistant') {
        const inspectBtn = document.createElement('div');
        inspectBtn.className = 'chat-msg-inspect';
        inspectBtn.innerHTML = '🔍 Inspect References';
        inspectBtn.addEventListener('click', () => {
            // Remove active inspection class from other messages
            document.querySelectorAll('.chat-msg.assistant').forEach(el => el.classList.remove('active-inspect'));
            bubble.classList.add('active-inspect');
            updateCitationsInspector(msg);
        });
        bubble.appendChild(inspectBtn);
    }
    
    messagesContainer.appendChild(bubble);
    scrollChatToBottom();
}

function resetCitationsInspector() {
    document.getElementById('inspector-version').textContent = 'No version cited';
    document.getElementById('inspector-files').innerHTML = '<span style="color: var(--text-muted); font-style: italic; font-size: 11px;">No files cited</span>';
    document.getElementById('inspector-classes').innerHTML = '<span style="color: var(--text-muted); font-style: italic; font-size: 11px;">No classes cited</span>';
    document.getElementById('inspector-functions').innerHTML = '<span style="color: var(--text-muted); font-style: italic; font-size: 11px;">No functions cited</span>';
    document.getElementById('inspector-reports').innerHTML = '<span style="color: var(--text-muted); font-style: italic; font-size: 11px;">No reports cited</span>';
}

function updateCitationsInspector(msg) {
    resetCitationsInspector();
    
    if (msg.referenced_version) {
        document.getElementById('inspector-version').textContent = `v${msg.referenced_version}`;
    }
    
    if (msg.referenced_files && msg.referenced_files.length > 0) {
        const container = document.getElementById('inspector-files');
        container.innerHTML = '';
        msg.referenced_files.forEach(f => {
            container.innerHTML += `<div style="margin-bottom: 4px;"><span class="pill outline" style="color: var(--accent-emerald); border-color: rgba(16,185,129,0.3); font-size: 11px; padding: 2px 6px; font-family: var(--font-mono); font-weight: 500; display: inline-block;">📄 ${f}</span></div>`;
        });
    }
    
    if (msg.referenced_classes && msg.referenced_classes.length > 0) {
        const container = document.getElementById('inspector-classes');
        container.innerHTML = '';
        msg.referenced_classes.forEach(c => {
            container.innerHTML += `<span class="pill outline" style="color: var(--accent-purple); border-color: rgba(139,92,246,0.3); font-size: 11px; padding: 2px 6px; font-weight: 500;">🏷️ ${c}</span>`;
        });
    }
    
    if (msg.referenced_functions && msg.referenced_functions.length > 0) {
        const container = document.getElementById('inspector-functions');
        container.innerHTML = '';
        msg.referenced_functions.forEach(fn => {
            container.innerHTML += `<span class="pill outline" style="color: var(--text-bright); border-color: rgba(255,255,255,0.08); font-size: 11px; padding: 2px 6px; font-family: var(--font-mono); font-weight: 500;">⚙️ ${fn}</span>`;
        });
    }
    
    if (msg.referenced_reports && msg.referenced_reports.length > 0) {
        const container = document.getElementById('inspector-reports');
        container.innerHTML = '';
        msg.referenced_reports.forEach(r => {
            container.innerHTML += `<span class="pill outline" style="color: #f59e0b; border-color: rgba(245,158,11,0.3); font-size: 11px; padding: 2px 6px; font-weight: 500;">📊 Report #${r}</span>`;
        });
    }
}

async function clearProjectChat() {
    if (!confirm('Are you sure you want to clear this project chat history?')) return;
    
    try {
        const res = await authorizedFetch(`/projects/${activeProjectId}/chat/history`, {
            method: 'DELETE'
        });
        if (res.ok) {
            loadProjectChat(activeProjectId);
        } else {
            alert('Failed to clear history.');
        }
    } catch (err) {
        alert('Connection error: ' + err.message);
    }
}

async function handleChatSubmit(e) {
    if (e) e.preventDefault();
    
    const input = document.getElementById('chat-input-text');
    if (!input || !input.value.trim()) return;
    
    const text = input.value.trim();
    input.value = '';
    
    // Render user message immediately
    const tempUserMsg = { id: Date.now(), role: 'user', content: text };
    renderChatMessage(tempUserMsg);
    
    // Add assistant placeholder message
    const messagesContainer = document.getElementById('chat-messages-container');
    const tempBubbleId = 'assistant-stream-temp';
    let tempBubble = document.getElementById(tempBubbleId);
    if (!tempBubble) {
        tempBubble = document.createElement('div');
        tempBubble.className = 'chat-msg assistant';
        tempBubble.id = tempBubbleId;
        
        const roleSpan = document.createElement('span');
        roleSpan.className = 'chat-msg-role';
        roleSpan.textContent = 'Assistant';
        tempBubble.appendChild(roleSpan);
        
        const contentDiv = document.createElement('div');
        contentDiv.id = 'assistant-stream-temp-content';
        contentDiv.innerHTML = '<span style="color: var(--text-muted); font-style: italic;">Connecting...</span>';
        tempBubble.appendChild(contentDiv);
        
        messagesContainer.appendChild(tempBubble);
    }
    
    scrollChatToBottom();
    
    // Show typing indicator
    const typing = document.getElementById('chat-typing-indicator');
    if (typing) typing.style.display = 'flex';
    
    try {
        const apiKey = localStorage.getItem('gemini_api_key') || '';
        const res = await fetch(`/projects/${activeProjectId}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: JSON.stringify({ message: text, api_key: apiKey })
        });
        
        if (!res.ok) {
            const errBody = await res.json();
            document.getElementById('assistant-stream-temp-content').innerHTML = `<span style="color: var(--text-error);">Error: ${errBody.detail || 'Failed to generate response'}</span>`;
            if (typing) typing.style.display = 'none';
            return;
        }
        
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let assistantText = '';
        const contentDiv = document.getElementById('assistant-stream-temp-content');
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const dataText = line.substring(6).trim();
                    if (dataText === '[DONE]') {
                        break;
                    }
                    try {
                        const parsedObj = JSON.parse(dataText);
                        if (parsedObj.text) {
                            assistantText += parsedObj.text;
                            contentDiv.innerHTML = formatMarkdown(assistantText);
                            // Highlight Prism code blocks if any
                            Prism.highlightAllUnder(contentDiv);
                            scrollChatToBottom();
                        }
                    } catch (err) {
                        // ignore parsing partial chunk
                    }
                }
            }
        }
        
        // Hide typing indicator
        if (typing) typing.style.display = 'none';
        
        // Remove temporary stream bubble and load history to display citations/inspect buttons properly
        tempBubble.remove();
        await loadProjectChat(activeProjectId);
        
    } catch (err) {
        console.error('Chat stream exception:', err);
        tempBubble.innerHTML = `<span style="color: var(--text-error);">Stream error: ${err.message}</span>`;
        if (typing) typing.style.display = 'none';
    }
}

function selectSuggestedChat(text) {
    const input = document.getElementById('chat-input-text');
    if (input) {
        input.value = text;
        // Trigger chat submission
        const chatForm = document.getElementById('chat-input-form');
        if (chatForm) {
            // Dispatch submit event
            const event = new Event('submit', { cancelable: true });
            chatForm.dispatchEvent(event);
        }
    }
}

function formatMarkdown(text) {
    // Escape HTML to prevent XSS
    let escaped = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
        
    // Replace code blocks: ```python ... ```
    escaped = escaped.replace(/```(python|bash|javascript|json|html|css)?\n([\s\S]*?)```/g, (match, lang, code) => {
        const language = lang || 'python';
        return `<pre class="language-${language}"><code class="language-${language}">${code.trim()}</code></pre>`;
    });
    
    // Replace inline code blocks: `code`
    escaped = escaped.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
    
    // Replace headings: #, ##, ###
    escaped = escaped.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    escaped = escaped.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    escaped = escaped.replace(/^# (.*$)/gim, '<h1>$1</h1>');
    
    // Replace bullet lists
    escaped = escaped.replace(/^\s*-\s+(.*$)/gim, '<li>$1</li>');
    // Wrap consecutive <li> in <ul>
    escaped = escaped.replace(/(<li>.*<\/li>)/g, '<ul>$1</ul>');
    // Clean up duplicate overlapping tags
    escaped = escaped.replace(/<\/ul>\s*<ul>/g, '');
    
    // Replace bold text: **text**
    escaped = escaped.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    
    // Replace lines with paragraph
    const lines = escaped.split('\n');
    const processedLines = lines.map(line => {
        if (line.trim().startsWith('<h') || line.trim().startsWith('<pre') || line.trim().startsWith('</pre') || line.trim().startsWith('<code') || line.trim().startsWith('</code') || line.trim().startsWith('<ul>') || line.trim().startsWith('</ul>') || line.trim().startsWith('<li>') || line.trim().startsWith('</li>')) {
            return line;
        }
        return line.trim() ? `<p>${line}</p>` : '';
    });
    
    return processedLines.join('\n');
}

/* ==========================================================================
   PULL REQUEST REVIEW DASHBOARD LOGIC
   ========================================================================== */

let activePRId = null;
let activePRFindings = [];
let prPollInterval = null;

async function loadProjectPullRequests(projectId) {
    const listContainer = document.getElementById('pr-list-container');
    if (!listContainer) return;

    listContainer.innerHTML = '<div style="color: var(--text-muted); font-style: italic; padding: 20px; text-align: center;">Loading Pull Requests...</div>';
    document.getElementById('pr-details-panel').classList.add('hidden');
    activePRId = null;

    try {
        const res = await authorizedFetch(`/projects/${projectId}/pull-requests`);
        if (!res.ok) {
            listContainer.innerHTML = '<div style="color: var(--text-error); font-style: italic; padding: 20px; text-align: center;">Failed to load Pull Requests.</div>';
            return;
        }

        const prs = await res.json();
        listContainer.innerHTML = '';

        if (prs.length === 0) {
            listContainer.innerHTML = `
                <div class="empty-state" style="padding: 20px 10px;">
                    <span style="font-size: 24px;">💻</span>
                    <p style="margin-top: 10px; font-size: 13px;">No Pull Requests reviewed yet</p>
                </div>`;
            return;
        }

        prs.forEach(pr => {
            const card = document.createElement('div');
            card.className = `project-card pr-card ${activePRId === pr.id ? 'active' : ''}`;
            card.id = `pr-card-${pr.id}`;
            card.style.padding = '12px';
            card.style.borderRadius = '8px';
            card.style.border = '1px solid rgba(255,255,255,0.06)';
            card.style.background = 'rgba(255,255,255,0.02)';
            card.style.cursor = 'pointer';
            card.style.display = 'flex';
            card.style.flexDirection = 'column';
            card.style.gap = '6px';

            const statusClass = pr.status === 'open' ? 'badge-severity-low' : 'badge-severity-medium';
            
            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;">
                    <h3 style="font-size: 13px; font-weight: 600; color: var(--text-bright); margin: 0; word-break: break-all;">#${pr.github_pr_number} ${escapeHtml(pr.title)}</h3>
                    <span class="pill outline" style="font-size: 9px; padding: 1px 4px;">${pr.status}</span>
                </div>
                <div style="font-size: 11px; color: var(--text-muted);">By @${escapeHtml(pr.author)}</div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">
                    <span style="font-size: 10px; font-family: var(--font-mono); color: var(--text-muted);">${escapeHtml(pr.base_branch)} &larr; ${escapeHtml(pr.head_branch)}</span>
                    <span class="badge" style="font-size: 11px; font-weight: bold; background: rgba(139,92,246,0.1); color: var(--accent-purple); padding: 2px 6px; border-radius: 4px;">Score: ${pr.analyses && pr.analyses.length > 0 && pr.analyses[0].score !== null ? pr.analyses[0].score + '%' : '--'}</span>
                </div>
            `;

            card.addEventListener('click', () => {
                document.querySelectorAll('.pr-card').forEach(c => c.classList.remove('active'));
                card.classList.add('active');
                selectPullRequest(pr);
            });

            listContainer.appendChild(card);
        });

        // Auto-select first PR if active
        if (!activePRId && prs.length > 0) {
            listContainer.firstElementChild.click();
        }

    } catch (err) {
        console.error('Failed to load project PRs:', err);
        listContainer.innerHTML = '<div style="color: var(--text-error); font-style: italic; padding: 20px; text-align: center;">Connection error.</div>';
    }
}

async function selectPullRequest(pr) {
    activePRId = pr.id;
    const panel = document.getElementById('pr-details-panel');
    panel.classList.remove('hidden');

    // Headers
    document.getElementById('pr-details-status').textContent = pr.status;
    document.getElementById('pr-details-title').textContent = pr.title;
    document.getElementById('pr-details-meta').textContent = `PR #${pr.github_pr_number} by @${pr.author} | base: ${pr.base_branch} &larr; head: ${pr.head_branch}`;

    // Overview details loading
    document.getElementById('pr-score-badge').textContent = '--%';
    document.getElementById('pr-executive-summary').textContent = 'Loading review summary...';
    document.getElementById('pr-risk-pill').textContent = 'loading...';
    document.getElementById('pr-risk-pill').className = 'pill';
    document.getElementById('pr-meta-files').textContent = pr.files_changed;
    document.getElementById('pr-meta-commits').textContent = pr.commits;

    // Reset components
    document.getElementById('pr-files-tab-container').innerHTML = '';
    document.getElementById('pr-diff-code-panel').innerHTML = '<span style="color: var(--text-muted); font-style: italic;">Select a modified file to view diff patch</span>';
    document.getElementById('pr-findings-container').innerHTML = '';
    document.getElementById('pr-fixes-container').innerHTML = '';
    document.getElementById('pr-timeline-container').innerHTML = '';

    // File Tabs rendering from JSON metadata
    if (pr.pr_files_json) {
        try {
            const files = JSON.parse(pr.pr_files_json);
            const container = document.getElementById('pr-files-tab-container');
            container.innerHTML = '';

            files.forEach((f, idx) => {
                const item = document.createElement('div');
                item.className = 'file-tab-item';
                item.style.padding = '8px 12px';
                item.style.borderBottom = '1px solid rgba(255,255,255,0.04)';
                item.style.cursor = 'pointer';
                item.style.fontSize = '12px';
                item.style.color = 'var(--text-main)';
                item.style.fontFamily = 'var(--font-mono)';
                item.style.display = 'flex';
                item.style.justifyContent = 'space-between';
                item.style.alignItems = 'center';

                item.innerHTML = `
                    <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 80%;" title="${escapeHtml(f.filename)}">📄 ${escapeHtml(f.filename.split('/').pop())}</span>
                    <span style="font-size: 10px; color: var(--accent-emerald);">+${f.additions} -${f.deletions}</span>
                `;

                item.addEventListener('click', () => {
                    document.querySelectorAll('.file-tab-item').forEach(el => {
                        el.style.background = '';
                        el.style.color = '';
                    });
                    item.style.background = 'rgba(139,92,246,0.15)';
                    item.style.color = '#fff';
                    renderPRDiff(f.patch || 'No patch information available.');
                });

                container.appendChild(item);

                // Auto click first tab
                if (idx === 0) item.click();
            });
        } catch (e) {
            console.error('Failed to render file tabs:', e);
        }
    }

    // Load actual Review execution details
    if (pr.latest_analysis_id) {
        await loadPRAnalysisRunData(pr.latest_analysis_id);
    } else {
        document.getElementById('pr-executive-summary').textContent = 'No review runs executed yet for this Pull Request. Click "Review Again" to run.';
    }

    // Render historical Analysis Runs timeline
    if (pr.analyses && pr.analyses.length > 0) {
        const timeline = document.getElementById('pr-timeline-container');
        timeline.innerHTML = '';

        pr.analyses.forEach(run => {
            const node = document.createElement('div');
            node.className = 'timeline-run-item';
            node.style.cursor = 'pointer';
            node.style.padding = '6px 10px';
            node.style.borderRadius = '6px';
            node.style.border = '1px solid rgba(255,255,255,0.04)';
            node.style.background = 'rgba(255,255,255,0.01)';
            node.style.display = 'flex';
            node.style.justifyContent = 'space-between';
            node.style.alignItems = 'center';
            node.style.fontSize = '12px';

            const activeMark = run.id === pr.latest_analysis_id ? 'border-color: var(--accent-purple); background: rgba(139,92,246,0.05);' : '';
            node.setAttribute('style', `cursor: pointer; padding: 6px 10px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.04); background: rgba(255,255,255,0.01); display: flex; justify-content: space-between; align-items: center; font-size: 12px; margin-bottom: 4px; ${activeMark}`);

            node.innerHTML = `
                <div>
                    <strong>Run #${run.id}</strong> <span style="color: var(--text-muted); font-size: 11px; margin-left: 6px;">${new Date(run.created_at).toLocaleString()}</span>
                </div>
                <div style="display: flex; gap: 8px; align-items: center;">
                    <span class="pill outline" style="font-size: 10px;">${run.status}</span>
                    <strong style="color: var(--accent-purple);">${run.score !== null ? run.score + '%' : '--'}</strong>
                </div>
            `;

            node.addEventListener('click', async () => {
                document.querySelectorAll('.timeline-run-item').forEach(el => {
                    el.style.borderColor = '';
                    el.style.background = '';
                });
                node.style.borderColor = 'var(--accent-purple)';
                node.style.background = 'rgba(139,92,246,0.05)';
                await loadPRAnalysisRunData(run.id);
            });

            timeline.appendChild(node);
        });
    }
}

async function loadPRAnalysisRunData(analysisId) {
    try {
        // Fetch summary
        const summaryRes = await authorizedFetch(`/pull-requests/${activePRId}/summary`);
        if (summaryRes.ok) {
            const summary = await summaryRes.json();
            document.getElementById('pr-score-badge').textContent = `${summary.score}%`;
            document.getElementById('pr-executive-summary').textContent = summary.summary;
            
            // Risk pill styling
            const pill = document.getElementById('pr-risk-pill');
            pill.textContent = summary.risk_assessment.toUpperCase();
            
            let pillClass = 'badge-severity-low';
            if (summary.risk_assessment === 'critical') pillClass = 'badge-severity-critical';
            else if (summary.risk_assessment === 'high') pillClass = 'badge-severity-high';
            else if (summary.risk_assessment === 'medium') pillClass = 'badge-severity-medium';
            pill.className = `pill ${pillClass}`;
        }

        // Fetch findings
        const findingsRes = await authorizedFetch(`/pull-requests/${activePRId}/findings`);
        if (findingsRes.ok) {
            activePRFindings = await findingsRes.json();
            renderPRFindings('all');
        }
    } catch (err) {
        console.error('Failed to load analysis run data:', err);
    }
}

function renderPRDiff(patchText) {
    const panel = document.getElementById('pr-diff-code-panel');
    if (!patchText || patchText === 'No patch information available.') {
        panel.innerHTML = '<span style="color: var(--text-muted); font-style: italic;">No patch information available for this file.</span>';
        return;
    }

    const lines = patchText.split('\n');
    let output = '';

    lines.forEach(line => {
        let style = '';
        if (line.startsWith('+') && !line.startsWith('+++')) {
            style = 'background: rgba(16, 185, 129, 0.12); color: #34d399; font-weight: 500; display: block;';
        } else if (line.startsWith('-') && !line.startsWith('---')) {
            style = 'background: rgba(239, 68, 68, 0.12); color: #fca5a5; display: block; text-decoration: line-through;';
        } else if (line.startsWith('@@')) {
            style = 'color: var(--accent-purple); font-weight: 600; display: block;';
        }
        output += `<div style="${style}">${escapeHtml(line)}</div>`;
    });

    panel.innerHTML = output;
}

function renderPRFindings(filter) {
    const container = document.getElementById('pr-findings-container');
    const fixesContainer = document.getElementById('pr-fixes-container');
    
    container.innerHTML = '';
    fixesContainer.innerHTML = '';

    const filtered = activePRFindings.filter(f => {
        if (filter === 'all') return true;
        return f.severity.toLowerCase() === filter;
    });

    if (filtered.length === 0) {
        container.innerHTML = `<div style="color: var(--text-muted); font-style: italic; font-size: 13px; text-align: center; padding: 15px;">No ${filter} findings found in this Pull Request run.</div>`;
        return;
    }

    filtered.forEach(issue => {
        const div = document.createElement('div');
        div.style.padding = '12px';
        div.style.borderRadius = '8px';
        div.style.border = '1px solid rgba(255,255,255,0.06)';
        div.style.background = 'rgba(255,255,255,0.01)';
        div.style.display = 'flex';
        div.style.flexDirection = 'column';
        div.style.gap = '6px';
        
        const severityClass = `badge-severity-${(issue.severity || 'low').toLowerCase()}`;
        const fileLine = issue.line ? `${issue.file}#L${issue.line}` : issue.file;

        div.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span class="${severityClass}" style="font-size: 10px; padding: 2px 6px; border-radius: 4px; text-transform: uppercase;">${issue.severity}</span>
                <span style="font-family: var(--font-mono); font-size: 11px; color: var(--text-muted);">${escapeHtml(fileLine)}</span>
            </div>
            <div style="font-size: 13px; font-weight: 600; color: var(--text-bright);">${escapeHtml(issue.category)} finding</div>
            <p style="font-size: 12px; color: var(--text-muted); line-height: 1.4; margin: 0;">${escapeHtml(issue.explanation)}</p>
            ${issue.evidence ? `<pre style="margin: 4px 0 0 0; padding: 6px 10px; background: rgba(0,0,0,0.25); border-radius: 4px; border-left: 2px solid var(--accent-purple); font-size: 11px; color: #d8b4fe; overflow-x: auto;"><code>${escapeHtml(issue.evidence)}</code></pre>` : ''}
            <div style="font-size: 12px; color: var(--accent-teal); margin-top: 4px;"><strong>Recommendation:</strong> ${escapeHtml(issue.recommendation)}</div>
        `;

        container.appendChild(div);

        // Add fix widget if it's a critical/high security issue with evidence
        if (issue.severity === 'critical' || issue.severity === 'high') {
            const fixWidget = document.createElement('div');
            fixWidget.style.padding = '12px';
            fixWidget.style.borderRadius = '8px';
            fixWidget.style.border = '1px solid rgba(139,92,246,0.2)';
            fixWidget.style.background = 'rgba(139,92,246,0.03)';
            fixWidget.style.display = 'flex';
            fixWidget.style.flexDirection = 'column';
            fixWidget.style.gap = '8px';

            fixWidget.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <strong style="font-size: 12px; color: var(--accent-purple);">Suggested Secure Fix for ${escapeHtml(issue.file)}</strong>
                    <span style="font-size: 11px; color: var(--text-muted); font-family: var(--font-mono);">Severity: ${issue.severity}</span>
                </div>
                <div style="font-size: 12px; color: var(--text-main); font-family: var(--font-mono); font-style: italic; background: rgba(0,0,0,0.2); padding: 8px; border-radius: 4px;">
                    ${escapeHtml(issue.recommendation)}
                </div>
            `;

            const fixBtn = document.createElement('button');
            fixBtn.className = 'btn btn-primary btn-sm';
            fixBtn.style.margin = '4px 0 0 0';
            fixBtn.style.alignSelf = 'flex-start';
            fixBtn.textContent = 'Apply AI Fix Patch';
            
            fixBtn.addEventListener('click', async () => {
                const originalText = fixBtn.textContent;
                fixBtn.disabled = true;
                fixBtn.textContent = 'Applying Patch...';
                
                try {
                    const apiKey = localStorage.getItem('gemini_api_key') || '';
                    const res = await authorizedFetch(`/projects/${activeProjectId}/versions/apply-fix`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            issue: issue,
                            api_key: apiKey || null
                        })
                    });
                    
                    if (res.ok) {
                        const newVer = await res.json();
                        alert(`Successfully applied fix for ${issue.category} finding in '${issue.file}'. New Version ${newVer.version_number} has been created.`);
                        
                        // Reload timeline
                        loadProjectPullRequests(activeProjectId);
                    } else {
                        const data = await res.json();
                        alert(data.detail || 'Failed to apply patch.');
                        fixBtn.disabled = false;
                        fixBtn.textContent = originalText;
                    }
                } catch (err) {
                    alert('Patch error: ' + err.message);
                    fixBtn.disabled = false;
                    fixBtn.textContent = originalText;
                }
            });

            fixWidget.appendChild(fixBtn);
            fixesContainer.appendChild(fixWidget);
        }
    });

    // Handle placeholder for Suggested fixes
    if (fixesContainer.innerHTML === '') {
        fixesContainer.innerHTML = '<div style="color: var(--text-muted); font-style: italic; font-size: 13px; text-align: center; padding: 10px;">No secure code patches recommended for this PR.</div>';
    }
}

// Bind filters click handlers
document.addEventListener('DOMContentLoaded', () => {
    const filters = document.querySelectorAll('#pr-findings-filters span');
    filters.forEach(span => {
        span.addEventListener('click', () => {
            filters.forEach(s => s.classList.remove('active'));
            span.classList.add('active');
            renderPRFindings(span.getAttribute('data-filter'));
        });
    });

    // Form submit review trigger listener
    const triggerForm = document.getElementById('pr-review-trigger-form');
    if (triggerForm) {
        triggerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!activeProjectId) return;

            const inputNum = document.getElementById('pr-trigger-number');
            const prNum = parseInt(inputNum.value);
            if (!prNum) return;

            const submitBtn = triggerForm.querySelector('button[type="submit"]');
            const originalText = submitBtn.textContent;
            submitBtn.disabled = true;
            submitBtn.textContent = 'Triggering...';

            try {
                const res = await authorizedFetch(`/projects/${activeProjectId}/pull-requests/review`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ pull_request_number: prNum })
                });

                if (res.ok) {
                    const pr = await res.json();
                    inputNum.value = '';
                    alert(`PR #${prNum} review successfully enqueued! Checking changed files...`);
                    
                    // Trigger polling progress bar simulation
                    startPRAnalysisPolling(pr.id);
                } else {
                    const data = await res.json();
                    alert(data.detail || 'Failed to trigger review.');
                }
            } catch (err) {
                alert('Review trigger error: ' + err.message);
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
            }
        });
    }

    // Refresh action trigger
    const refreshBtn = document.getElementById('btn-pr-refresh');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', async () => {
            if (!activePRId) return;

            const originalText = refreshBtn.textContent;
            refreshBtn.disabled = true;
            refreshBtn.textContent = 'Syncing...';

            try {
                const res = await authorizedFetch(`/pull-requests/${activePRId}/refresh`, {
                    method: 'POST'
                });

                if (res.ok) {
                    const updated = await res.json();
                    alert('Pull Request metadata refreshed successfully!');
                    selectPullRequest(updated);
                } else {
                    alert('Failed to refresh metadata.');
                }
            } catch (err) {
                alert('Refresh error: ' + err.message);
            } finally {
                refreshBtn.disabled = false;
                refreshBtn.textContent = originalText;
            }
        });
    }

    // Review again trigger
    const reviewAgainBtn = document.getElementById('btn-pr-review-again');
    if (reviewAgainBtn) {
        reviewAgainBtn.addEventListener('click', async () => {
            if (!activePRId) return;

            const originalText = reviewAgainBtn.textContent;
            reviewAgainBtn.disabled = true;
            reviewAgainBtn.textContent = 'Starting...';

            try {
                const res = await authorizedFetch(`/pull-requests/${activePRId}/review-again`, {
                    method: 'POST'
                });

                if (res.ok) {
                    const updated = await res.json();
                    alert('Re-review analysis triggered successfully! Queueing modified files...');
                    startPRAnalysisPolling(updated.id);
                } else {
                    alert('Failed to re-review.');
                }
            } catch (err) {
                alert('Re-review error: ' + err.message);
            } finally {
                reviewAgainBtn.disabled = false;
                reviewAgainBtn.textContent = originalText;
            }
        });
    }
});

// Polls active Pull Request Analysis progress
function startPRAnalysisPolling(prId) {
    if (prPollInterval) clearInterval(prPollInterval);
    
    // Switch UI sidebar view automatically to show PR dashboard
    const navPrBtn = document.getElementById('nav-item-pull-requests');
    if (navPrBtn) navPrBtn.click();

    prPollInterval = setInterval(async () => {
        try {
            const res = await authorizedFetch(`/pull-requests/${prId}`);
            if (!res.ok) {
                clearInterval(prPollInterval);
                return;
            }

            const pr = await res.json();
            
            // Check status of latest analysis
            if (pr.latest_analysis_id) {
                const runRes = await authorizedFetch(`/analysis/${pr.latest_analysis_id}`);
                if (runRes.ok) {
                    const run = await runRes.json();
                    if (run.status === 'completed' || run.status === 'failed') {
                        clearInterval(prPollInterval);
                        
                        // Reload PR pane content
                        loadProjectPullRequests(activeProjectId);
                        selectPullRequest(pr);
                        
                        if (run.status === 'completed') {
                            alert('PR review pipeline analysis completed successfully!');
                        } else {
                            alert('PR review pipeline analysis execution failed.');
                        }
                    }
                }
            }
        } catch (err) {
            console.error('Polling PR error:', err);
            clearInterval(prPollInterval);
        }
    }, 1500);
}

