// App state variables
let pollInterval = null;
let currentRunId = null;
let processedLogCount = 0;

// Nodes list in order of sequential flow
const NODE_FLOW = ['extract', 'complexity', 'detect', 'suggest_improvements'];

// Initialize App
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initFormControls();
    initLineNumbers();
    initDemoSetup();
    initAuth();
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
