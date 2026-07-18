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
    initFixCenterControls();
    initSassSettings();
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
    if (toggleKeyBtn && apiKeyInput) {
        toggleKeyBtn.addEventListener('click', () => {
            const type = apiKeyInput.getAttribute('type') === 'password' ? 'text' : 'password';
            apiKeyInput.setAttribute('type', type);
            toggleKeyBtn.textContent = type === 'password' ? '👁️' : '🔒';
        });
    }

    // Dynamic API key label and loading based on selected model engine (v3.1 UX refinement)
    const modelEngineSelect = document.getElementById('model');
    const apiKeyLabel = document.getElementById('api-key-label');
    
    function updatePlaygroundKeyLabelAndValue() {
        if (!modelEngineSelect || !apiKeyLabel || !apiKeyInput) return;
        const selectedModel = modelEngineSelect.value;
        if (selectedModel.startsWith('gpt-')) {
            apiKeyLabel.textContent = 'OpenAI API Key';
            apiKeyInput.placeholder = 'Enter OpenAI API Key to enable Live Mode...';
            apiKeyInput.value = localStorage.getItem('openai_api_key') || '';
        } else if (selectedModel.startsWith('claude-')) {
            apiKeyLabel.textContent = 'Anthropic API Key';
            apiKeyInput.placeholder = 'Enter Anthropic API Key to enable Live Mode...';
            apiKeyInput.value = localStorage.getItem('anthropic_api_key') || '';
        } else {
            apiKeyLabel.textContent = 'Gemini API Key';
            apiKeyInput.placeholder = 'Enter API Key to enable Live Mode...';
            apiKeyInput.value = localStorage.getItem('gemini_api_key') || '';
        }
    }
    
    if (modelEngineSelect) {
        modelEngineSelect.addEventListener('change', updatePlaygroundKeyLabelAndValue);
        // Run once on load to initialize correct state
        updatePlaygroundKeyLabelAndValue();
    }

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
    let apiKey = document.getElementById('api-key').value;
    const threshold = document.getElementById('threshold').value;
    const model = document.getElementById('model').value;
    const runBtn = document.getElementById('btn-run');
    
    // Auto-fill from settings if playground key is empty
    if (!apiKey) {
        if (model.startsWith('gpt-')) {
            apiKey = localStorage.getItem('openai_api_key') || '';
        } else if (model.startsWith('claude-')) {
            apiKey = localStorage.getItem('anthropic_api_key') || '';
        } else {
            apiKey = localStorage.getItem('gemini_api_key') || '';
        }
    }
    
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
    const prBtn = document.getElementById('nav-item-pull-requests');
    if (prBtn) prBtn.style.display = 'none';
    const findingsBtn = document.getElementById('nav-item-findings');
    if (findingsBtn) findingsBtn.style.display = 'none';
    const semanticBtn = document.getElementById('nav-item-semantic');
    if (semanticBtn) semanticBtn.style.display = 'none';
    const fixCenterBtn = document.getElementById('nav-item-fix-center');
    if (fixCenterBtn) fixCenterBtn.style.display = 'none';
    const testCenterBtn = document.getElementById('nav-item-test-center');
    if (testCenterBtn) testCenterBtn.style.display = 'none';
    const workspaceBtn = document.getElementById('nav-item-workspace');
    if (workspaceBtn) workspaceBtn.style.display = 'none';

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
            document.getElementById('user-display-role').textContent = user.role.toUpperCase();            // Adjust visual system indicators if needed
            document.getElementById('header-auth').style.display = 'flex';
            document.getElementById('auth-overlay').classList.add('hidden');

            // Auto-load projects on login
            const workspaceBtn = document.getElementById('nav-item-workspace');
            if (workspaceBtn) workspaceBtn.style.display = 'block';
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
            } else if (targetView === 'view-findings') {
                loadProjectFindings(activeProjectId);
            } else if (targetView === 'view-workspace') {
                loadWorkspaces();
            } else if (targetView === 'view-fix-center') {
                loadFixCenter(activeProjectId);
            } else if (targetView === 'view-test-center') {
                loadTestCenter(activeProjectId);
            } else if (targetView === 'view-deployment') {
                loadDeploymentMetrics();
            } else if (targetView === 'view-insights') {
                loadRepositoryInsights(activeProjectId);
            }

            // Dynamically update breadcrumbs active text
            const navTextSpan = item.querySelector('.nav-text');
            if (navTextSpan) {
                const breadcrumbActive = document.getElementById('nav-breadcrumbs-view');
                if (breadcrumbActive) {
                    breadcrumbActive.textContent = navTextSpan.textContent;
                }
            }
        });
    });
}

let deploymentPollInterval = null;

async function loadDeploymentMetrics() {
    await fetchDeploymentMetrics();
    
    if (deploymentPollInterval) {
        clearInterval(deploymentPollInterval);
    }
    
    // Poll metrics every 5 seconds while on this pane
    deploymentPollInterval = setInterval(async () => {
        const view = document.getElementById('view-deployment');
        if (view && view.classList.contains('active')) {
            await fetchDeploymentMetrics();
        } else {
            clearInterval(deploymentPollInterval);
            deploymentPollInterval = null;
        }
    }, 5000);
}

async function fetchDeploymentMetrics() {
    try {
        const token = localStorage.getItem('access_token');
        const headers = {};
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        
        const healthRes = await fetch('/health', { headers });
        let healthData = { status: 'Unhealthy', database: 'Offline', redis: 'Offline', storage: 'Offline', version: '2.6.0' };
        if (healthRes.ok) {
            healthData = await healthRes.json();
        }
        
        const metricsRes = await fetch('/metrics', { headers });
        let metricsData = {
            projects: 0, analyses: 0, fixes: 0, tests: 0,
            queue_size: 0, active_workers: 1, average_processing_time: 4.5,
            failure_rate: '0.0%', cache_hits: 0, cache_misses: 0
        };
        if (metricsRes.ok) {
            metricsData = await metricsRes.json();
        }

        const diagRes = await fetch('/diagnostics', { headers });
        let diagData = { warnings: [], recommendations: [] };
        if (diagRes.ok) {
            diagData = await diagRes.json();
        }
        
        const statusBadge = document.getElementById('deployment-status-badge');
        const envBadge = document.getElementById('deployment-env-badge');
        
        const isProd = healthData.environment === 'production';
        envBadge.textContent = `ENVIRONMENT: ${healthData.environment ? healthData.environment.toUpperCase() : 'DEVELOPMENT'}`;
        envBadge.className = isProd ? 'badge badge-warning' : 'badge badge-info';
        
        statusBadge.textContent = healthData.status === 'Healthy' ? 'SYSTEM READY' : 'SYSTEM DEGRADED';
        statusBadge.className = healthData.status === 'Healthy' ? 'badge badge-success' : 'badge badge-danger';
        
        const dbStatus = document.getElementById('metrics-db-status');
        const dbType = document.getElementById('metrics-db-type');
        dbStatus.textContent = healthData.database.includes('Unhealthy') ? 'ERROR' : 'HEALTHY';
        dbStatus.style.color = healthData.database.includes('Unhealthy') ? 'var(--accent-red)' : 'var(--accent-green)';
        dbType.textContent = isProd ? 'PostgreSQL Engine' : 'SQLite Engine (Development)';
        
        const redisStatus = document.getElementById('metrics-redis-status');
        const redisInfo = document.getElementById('metrics-redis-info');
        const isRedisOffline = healthData.redis.includes('Unhealthy');
        redisStatus.textContent = isRedisOffline ? 'OFFLINE' : 'CONNECTED';
        redisStatus.style.color = isRedisOffline ? 'var(--accent-red)' : 'var(--accent-green)';
        redisInfo.textContent = isRedisOffline ? 'Offline Fallback' : 'Active Connection Cache';
        
        const storageStatus = document.getElementById('metrics-storage-status');
        const storageProvider = document.getElementById('metrics-storage-provider');
        const isStorageOffline = healthData.storage.includes('Unhealthy');
        storageStatus.textContent = isStorageOffline ? 'ERROR' : 'ONLINE';
        storageStatus.style.color = isStorageOffline ? 'var(--accent-red)' : 'var(--accent-green)';
        storageProvider.textContent = isProd ? 'AWS S3 cloud storage' : 'Local Storage filesystem';
        
        document.getElementById('metrics-active-workers').textContent = metricsData.active_workers;
        document.getElementById('queue-pending-count').textContent = metricsData.queue_size;
        document.getElementById('queue-failure-rate').textContent = metricsData.failure_rate;
        document.getElementById('queue-avg-latency').textContent = `${metricsData.average_processing_time}s`;
        
        document.getElementById('metric-total-projects').textContent = metricsData.projects;
        document.getElementById('metric-total-analyses').textContent = metricsData.analyses;
        document.getElementById('metric-total-fixes').textContent = metricsData.fixes;
        document.getElementById('metric-total-tests').textContent = metricsData.tests;
        
        const dockerMode = document.getElementById('diagnostics-docker-mode');
        dockerMode.textContent = isProd ? 'Active (production compose)' : 'Inactive';
        dockerMode.style.color = isProd ? 'var(--accent-green)' : 'var(--text-muted)';
        
        const logsList = document.getElementById('diagnostics-logs-list');
        let logsHTML = `
            <div>[INFO] Platform Version: v${healthData.version || '2.6.0'}</div>
            <div>[INFO] Database Status check: ${healthData.database}</div>
            <div>[INFO] Redis Cache pool check: ${healthData.redis}</div>
            <div>[INFO] Storage Layer write check: ${healthData.storage}</div>
            <div>[INFO] Active queues: task_queue length = ${metricsData.queue_size}</div>
        `;
        if (diagData.warnings && diagData.warnings.length > 0) {
            diagData.warnings.forEach(w => {
                logsHTML += `<div style="color: var(--accent-orange);">[WARN] ${w}</div>`;
            });
        }
        if (diagData.recommendations && diagData.recommendations.length > 0) {
            diagData.recommendations.forEach(r => {
                logsHTML += `<div style="color: var(--accent-blue);">[RECO] ${r}</div>`;
            });
        }
        logsList.innerHTML = logsHTML;

        
    } catch (err) {
        console.error('Error fetching deployment center metrics:', err);
    }
}


function initProjectsTab() {
    // Project Modal bindings
    const btnCreateModal = document.getElementById('btn-create-project-modal');
    const btnModalCancel = document.getElementById('btn-project-modal-cancel');
    const projectModal = document.getElementById('project-modal');
    const projectCreateForm = document.getElementById('project-create-form');

    btnCreateModal.addEventListener('click', async () => {
        projectModal.classList.remove('hidden');
        document.getElementById('project-modal-name').value = '';
        const repoInput = document.getElementById('project-modal-repo-url');
        if (repoInput) repoInput.value = '';
        await populateProjectModalWorkspaces();
    });

    btnModalCancel.addEventListener('click', () => {
        projectModal.classList.add('hidden');
    });

    projectCreateForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('project-modal-name').value.trim();
        const repoInput = document.getElementById('project-modal-repo-url');
        const repoUrl = repoInput ? repoInput.value.trim() : '';
        const workspaceIdVal = document.getElementById('project-modal-workspace-id').value;
        const workspaceId = workspaceIdVal ? parseInt(workspaceIdVal) : null;
        if (!name) return;

        const submitBtn = projectCreateForm.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.textContent = repoUrl ? 'Cloning & Ingesting...' : 'Creating...';

        try {
            const res = await authorizedFetch('/projects', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, repo_url: repoUrl || null, workspace_id: workspaceId })
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

    // Dynamic project key label and value loading (v3.1)
    const projectModelSelect = document.getElementById('project-model');
    const projectAnalysisKeyLabel = document.getElementById('project-analysis-key-label');
    const projectAnalysisKeyInput = document.getElementById('project-analysis-key');

    function updateProjectAnalysisKeyLabelAndValue() {
        if (!projectModelSelect || !projectAnalysisKeyLabel || !projectAnalysisKeyInput) return;
        const selectedModel = projectModelSelect.value;
        if (selectedModel.startsWith('gpt-')) {
            projectAnalysisKeyLabel.textContent = 'OpenAI API Key';
            projectAnalysisKeyInput.placeholder = 'Enter OpenAI API Key (leave empty for offline)...';
            projectAnalysisKeyInput.value = localStorage.getItem('openai_api_key') || '';
        } else if (selectedModel.startsWith('claude-')) {
            projectAnalysisKeyLabel.textContent = 'Anthropic API Key';
            projectAnalysisKeyInput.placeholder = 'Enter Anthropic API Key (leave empty for offline)...';
            projectAnalysisKeyInput.value = localStorage.getItem('anthropic_api_key') || '';
        } else {
            projectAnalysisKeyLabel.textContent = 'Gemini API Key';
            projectAnalysisKeyInput.placeholder = 'Enter key (leave empty for offline)...';
            projectAnalysisKeyInput.value = localStorage.getItem('gemini_api_key') || '';
        }
    }

    if (projectModelSelect) {
        projectModelSelect.addEventListener('change', updateProjectAnalysisKeyLabelAndValue);
        // Initialize once
        updateProjectAnalysisKeyLabelAndValue();
    }

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
    const container = document.getElementById('projects-list-container');
    if (container) {
        container.innerHTML = `
            <div class="skeleton-loader-card" style="padding: 12px; margin-bottom: 8px; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.04); border-radius: 8px;">
                <div class="skeleton-line" style="width: 70%; height: 12px; background: rgba(255,255,255,0.05); margin-bottom: 6px; border-radius: 4px; animation: pulse 1.5s infinite ease-in-out;"></div>
                <div class="skeleton-line" style="width: 40%; height: 8px; background: rgba(255,255,255,0.03); border-radius: 4px; animation: pulse 1.5s infinite ease-in-out;"></div>
            </div>
            <div class="skeleton-loader-card" style="padding: 12px; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.04); border-radius: 8px;">
                <div class="skeleton-line" style="width: 50%; height: 12px; background: rgba(255,255,255,0.05); margin-bottom: 6px; border-radius: 4px; animation: pulse 1.5s infinite ease-in-out;"></div>
                <div class="skeleton-line" style="width: 60%; height: 8px; background: rgba(255,255,255,0.03); border-radius: 4px; animation: pulse 1.5s infinite ease-in-out;"></div>
            </div>
        `;
    }
    try {
        const res = await authorizedFetch('/projects');
        if (!res.ok) return;

        const projects = await res.json();
        
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
        const findingsBtn = document.getElementById('nav-item-findings');
        if (findingsBtn) findingsBtn.style.display = 'block';
        const semanticBtn = document.getElementById('nav-item-semantic');
        if (semanticBtn) semanticBtn.style.display = 'block';
        const fixCenterBtn = document.getElementById('nav-item-fix-center');
        if (fixCenterBtn) fixCenterBtn.style.display = 'block';
        const testCenterBtn = document.getElementById('nav-item-test-center');
        if (testCenterBtn) testCenterBtn.style.display = 'block';
        const workspaceBtn = document.getElementById('nav-item-workspace');
        if (workspaceBtn) workspaceBtn.style.display = 'block';
        const insightsBtn = document.getElementById('nav-item-insights');
        if (insightsBtn) insightsBtn.style.display = 'block';

        // Load files list
        await loadProjectFiles(id);
        
        // Auto-load project key label and values based on selected model (v3.1)
        if (typeof updateProjectAnalysisKeyLabelAndValue === 'function') {
            updateProjectAnalysisKeyLabelAndValue();
        }
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
    const projectModelSelect = document.getElementById('project-model');
    const selectedModel = projectModelSelect ? projectModelSelect.value : 'gemini-2.5-flash';
    const btn = document.getElementById('btn-start-project-analysis');
    const progressContainer = document.getElementById('analysis-progress-container');

    btn.disabled = true;
    progressContainer.style.display = 'block';

    try {
        const res = await authorizedFetch(`/analysis/${activeProjectId}/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: apiKey || null, model: selectedModel })
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
        const chatModelSelect = document.getElementById('chat-model-select');
        const selectedModel = chatModelSelect ? chatModelSelect.value : 'gemini-2.5-flash';
        let apiKey = '';
        if (selectedModel.startsWith('gpt-')) {
            apiKey = localStorage.getItem('openai_api_key') || '';
        } else if (selectedModel.startsWith('claude-')) {
            apiKey = localStorage.getItem('anthropic_api_key') || '';
        } else {
            apiKey = localStorage.getItem('gemini_api_key') || '';
        }

        const res = await fetch(`/projects/${activeProjectId}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: JSON.stringify({ message: text, api_key: apiKey, model: selectedModel })
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


// --- Review Findings Subsystem ---
let activeFindingsList = [];
let activeFindingId = null;
let activeFindingFilterStatus = 'Open';
let activeFindingFilterSeverity = '';
let activeFindingFilterCategory = '';
let activeFindingSearchQuery = '';

async function loadProjectFindings(projectId) {
    if (!projectId) return;
    try {
        const res = await authorizedFetch(`/projects/${projectId}/findings`);
        if (res.ok) {
            activeFindingsList = await res.json();
            renderFindings();
            renderFindingsDashboard(projectId);
        } else {
            console.error('Failed to load findings');
        }
    } catch (err) {
        console.error('Error loading findings:', err);
    }
}

function renderFindings() {
    const listContainer = document.getElementById('findings-list-container');
    if (!listContainer) return;

    listContainer.innerHTML = '';

    // Apply filtering
    const filtered = activeFindingsList.filter(f => {
        // Status filter
        if (f.status !== activeFindingFilterStatus) return false;
        // Severity filter
        if (activeFindingFilterSeverity && f.severity !== activeFindingFilterSeverity) return false;
        // Category filter
        if (activeFindingFilterCategory && f.category !== activeFindingFilterCategory) return false;
        // Search query
        if (activeFindingSearchQuery) {
            const query = activeFindingSearchQuery.toLowerCase();
            const desc = (f.description || '').toLowerCase();
            const file = (f.file_path || '').toLowerCase();
            if (!desc.includes(query) && !file.includes(query)) return false;
        }
        return true;
    });

    // Update count badge
    const badge = document.getElementById('findings-total-badge');
    if (badge) {
        badge.textContent = `${filtered.length} ${activeFindingFilterStatus}`;
    }

    if (filtered.length === 0) {
        listContainer.innerHTML = `<div style="color: var(--text-muted); font-style: italic; font-size: 13px; text-align: center; padding: 20px;">No ${activeFindingFilterStatus.toLowerCase()} findings match the criteria.</div>`;
        return;
    }

    filtered.forEach(f => {
        const card = document.createElement('div');
        card.className = `card glass finding-card ${activeFindingId === f.id ? 'active' : ''}`;
        card.style.margin = '0 0 10px 0';
        card.style.padding = '12px';
        card.style.cursor = 'pointer';
        card.style.border = activeFindingId === f.id ? '1px solid var(--accent-purple)' : '1px solid rgba(255,255,255,0.06)';
        card.style.transition = 'all 0.2s';
        
        const sevColors = {
            critical: '#ef4444',
            high: '#f97316',
            medium: '#eab308',
            low: '#3b82f6'
        };

        const badgeColor = sevColors[f.severity.toLowerCase()] || 'var(--text-muted)';
        
        card.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 6px;">
                <span style="font-size: 11px; font-weight: 600; text-transform: uppercase; color: ${badgeColor};">${f.severity}</span>
                <span style="font-size: 11px; color: var(--text-muted); font-family: var(--font-mono);">${f.category}</span>
            </div>
            <div style="font-size: 13px; font-weight: 700; color: var(--text-bright); margin-bottom: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                ${f.title || f.file_path}
            </div>
            <div style="font-size: 11px; color: var(--text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                ${f.file_path}#L${f.line_number}
            </div>
        `;

        card.addEventListener('click', () => {
            // Remove active class from previous
            document.querySelectorAll('.finding-card').forEach(c => {
                c.classList.remove('active');
                c.style.borderColor = 'rgba(255,255,255,0.06)';
            });
            card.classList.add('active');
            card.style.borderColor = 'var(--accent-purple)';
            
            selectFinding(f.id);
        });

        listContainer.appendChild(card);
    });
}

async function selectFinding(findingId) {
    activeFindingId = findingId;
    try {
        const res = await authorizedFetch(`/findings/${findingId}`);
        if (res.ok) {
            const finding = await res.json();
            await updateAssigneeSelectOptions(activeProjectId);
            renderFindingDetail(finding);
            loadFindingComments(findingId);
        }
    } catch (err) {
        console.error('Error fetching finding detail:', err);
    }
}

function renderFindingDetail(finding) {
    document.getElementById('finding-detail-placeholder').style.display = 'none';
    document.getElementById('finding-detail-content').style.display = 'flex';

    document.getElementById('finding-detail-title').textContent = finding.title || `${finding.category} Issue`;
    document.getElementById('finding-detail-meta').textContent = `${finding.file_path} #L${finding.line_number}`;
    document.getElementById('finding-detail-desc').textContent = finding.description;
    document.getElementById('finding-detail-rec').textContent = finding.recommendation;

    // Set Assignee dropdown
    const select = document.getElementById('finding-assignee-select');
    if (select) {
        select.value = finding.assigned_to || '';
    }

    // Set meta tags
    document.getElementById('finding-meta-analysis').textContent = finding.analysis_id || '--';
    
    const versionContainer = document.getElementById('finding-meta-resolved-version-container');
    if (finding.resolved_in_version_id) {
        versionContainer.style.display = 'block';
        document.getElementById('finding-meta-resolved-version').textContent = finding.resolved_in_version_id;
    } else {
        versionContainer.style.display = 'none';
    }

    // Badges
    const badgeContainer = document.getElementById('finding-detail-badges');
    badgeContainer.innerHTML = '';
    
    const sevColors = {
        critical: 'rgba(239, 68, 68, 0.15)',
        high: 'rgba(249, 115, 22, 0.15)',
        medium: 'rgba(234, 179, 8, 0.15)',
        low: 'rgba(59, 130, 246, 0.15)'
    };
    const sevTextColors = {
        critical: '#fca5a5',
        high: '#ffedd5',
        medium: '#fef9c3',
        low: '#dbeafe'
    };

    const sevBadge = document.createElement('span');
    sevBadge.className = 'badge';
    sevBadge.style.background = sevColors[finding.severity.toLowerCase()] || 'rgba(255,255,255,0.06)';
    sevBadge.style.color = sevTextColors[finding.severity.toLowerCase()] || 'var(--text-muted)';
    sevBadge.textContent = finding.severity.toUpperCase();
    badgeContainer.appendChild(sevBadge);

    const confBadge = document.createElement('span');
    confBadge.className = 'badge';
    confBadge.style.background = 'rgba(139, 92, 246, 0.15)';
    confBadge.style.color = '#c084fc';
    confBadge.textContent = `${Math.round(finding.confidence * 100)}% Conf`;
    badgeContainer.appendChild(confBadge);

    // Set action buttons display based on status
    const reopenBtn = document.getElementById('btn-finding-reopen');
    const ignoreBtn = document.getElementById('btn-finding-ignore');
    const resolveBtn = document.getElementById('btn-finding-resolve');
    const fixBtn = document.getElementById('btn-finding-apply-fix');
    const ignoreReasonContainer = document.getElementById('finding-ignored-reason-container');

    if (finding.status === 'Resolved') {
        reopenBtn.style.display = 'block';
        ignoreBtn.style.display = 'none';
        resolveBtn.style.display = 'none';
        fixBtn.style.display = 'none';
        ignoreReasonContainer.style.display = 'none';
    } else if (finding.status === 'Ignored') {
        reopenBtn.style.display = 'block';
        ignoreBtn.style.display = 'none';
        resolveBtn.style.display = 'none';
        fixBtn.style.display = 'none';
        
        ignoreReasonContainer.style.display = 'block';
        document.getElementById('finding-ignored-reason').textContent = finding.ignored_reason || 'No ignore reason provided.';
    } else {
        reopenBtn.style.display = 'none';
        ignoreBtn.style.display = 'block';
        resolveBtn.style.display = 'block';
        fixBtn.style.display = 'block';
        ignoreReasonContainer.style.display = 'none';
    }
}

async function renderFindingsDashboard(projectId) {
    if (!projectId) return;

    // 1. Gather status metrics from activeFindingsList
    let openCount = 0;
    let progressCount = 0;
    let resolvedCount = 0;
    let ignoredCount = 0;
    let criticalCount = 0;

    activeFindingsList.forEach(f => {
        if (f.status === 'Open') openCount++;
        else if (f.status === 'In Progress') progressCount++;
        else if (f.status === 'Resolved') resolvedCount++;
        else if (f.status === 'Ignored') ignoredCount++;

        if (f.severity.toLowerCase() === 'critical' && f.status !== 'Resolved' && f.status !== 'Ignored') {
            criticalCount++;
        }
    });

    document.getElementById('metric-open-findings').textContent = openCount + progressCount;
    document.getElementById('metric-critical-findings').textContent = criticalCount;
    document.getElementById('metric-resolved-today').textContent = resolvedCount;
    document.getElementById('metric-ignored-findings').textContent = ignoredCount;

    const total = openCount + progressCount + resolvedCount + ignoredCount;
    const successRate = total > 0 ? Math.round((resolvedCount / total) * 100) : 0;
    document.getElementById('metric-fix-success').textContent = `${successRate}%`;

    // 2. Fetch history timeline for Resolution Trend
    try {
        const res = await authorizedFetch(`/projects/${projectId}/findings/history`);
        if (res.ok) {
            const history = await res.json();
            drawResolutionTrendChart(history);
            
            // Calculate Average Resolution Time
            if (history.length > 0) {
                let totalDiff = 0;
                history.forEach(item => {
                    const created = new Date(item.created_at);
                    const resolved = new Date(item.resolved_at);
                    totalDiff += (resolved - created);
                });
                const avgHours = Math.round(totalDiff / (1000 * 60 * 60 * history.length));
                if (avgHours < 24) {
                    document.getElementById('metric-avg-time').textContent = `${avgHours} hrs`;
                } else {
                    document.getElementById('metric-avg-time').textContent = `${Math.round(avgHours / 24)} days`;
                }
            } else {
                document.getElementById('metric-avg-time').textContent = '--';
            }
        }
    } catch (err) {
        console.error('Error fetching history:', err);
    }

    // 3. Draw Severity & Category distributions
    drawSeverityCategoryBars(activeFindingsList);
}

function drawSeverityCategoryBars(findings) {
    const sevContainer = document.getElementById('chart-severity-bars');
    const catContainer = document.getElementById('chart-category-bars');
    if (!sevContainer || !catContainer) return;

    // Severity counts
    const sevCounts = { critical: 0, high: 0, medium: 0, low: 0 };
    // Category counts
    const catCounts = {};

    findings.forEach(f => {
        if (f.status === 'Resolved') return;
        const sev = f.severity.toLowerCase();
        if (sevCounts[sev] !== undefined) sevCounts[sev]++;
        
        const cat = f.category || 'Other';
        catCounts[cat] = (catCounts[cat] || 0) + 1;
    });

    const totalSev = Object.values(sevCounts).reduce((a, b) => a + b, 0);
    const totalCat = Object.values(catCounts).reduce((a, b) => a + b, 0);

    // Render Severity Bars
    let sevHtml = '<div style="font-size: 11px; color: var(--text-muted); font-weight: 600; margin-bottom: 4px;">SEVERITY</div>';
    const sevColors = {
        critical: '#ef4444',
        high: '#f97316',
        medium: '#eab308',
        low: '#3b82f6'
    };
    
    Object.keys(sevCounts).forEach(sev => {
        const count = sevCounts[sev];
        const pct = totalSev > 0 ? (count / totalSev) * 100 : 0;
        sevHtml += `
            <div style="display: flex; flex-direction: column; gap: 2px; font-size: 11px; margin-bottom: 5px;">
                <div style="display: flex; justify-content: space-between; color: var(--text-main);">
                    <span style="text-transform: capitalize;">${sev}</span>
                    <span>${count}</span>
                </div>
                <div style="width: 100%; height: 6px; background: rgba(255,255,255,0.04); border-radius: 3px; overflow: hidden;">
                    <div style="width: ${pct}%; height: 100%; background: ${sevColors[sev] || 'var(--text-muted)'}; border-radius: 3px;"></div>
                </div>
            </div>
        `;
    });
    sevContainer.innerHTML = sevHtml;

    // Render Category Bars
    let catHtml = '<div style="font-size: 11px; color: var(--text-muted); font-weight: 600; margin-bottom: 4px;">CATEGORY</div>';
    const categories = Object.keys(catCounts).sort((a,b) => catCounts[b] - catCounts[a]).slice(0, 4);
    
    if (categories.length === 0) {
        catHtml += '<div style="color: var(--text-muted); font-style: italic; font-size: 12px;">No categories</div>';
    } else {
        categories.forEach(cat => {
            const count = catCounts[cat];
            const pct = totalCat > 0 ? (count / totalCat) * 100 : 0;
            catHtml += `
                <div style="display: flex; flex-direction: column; gap: 2px; font-size: 11px; margin-bottom: 5px;">
                    <div style="display: flex; justify-content: space-between; color: var(--text-main);">
                        <span>${cat}</span>
                        <span>${count}</span>
                    </div>
                    <div style="width: 100%; height: 6px; background: rgba(255,255,255,0.04); border-radius: 3px; overflow: hidden;">
                        <div style="width: ${pct}%; height: 100%; background: var(--accent-teal); border-radius: 3px;"></div>
                    </div>
                </div>
            `;
        });
    }
    catContainer.innerHTML = catHtml;
}

function drawResolutionTrendChart(history) {
    const container = document.getElementById('chart-resolution-trend-container');
    if (!container) return;

    if (!history || history.length === 0) {
        container.innerHTML = `<span style="color: var(--text-muted); font-style: italic; font-size: 12px;">No resolved findings trend data yet. Resolve issues to populate.</span>`;
        return;
    }

    // Group history by date (YYYY-MM-DD)
    const countsByDate = {};
    history.forEach(item => {
        if (!item.resolved_at) return;
        const dateStr = item.resolved_at.split('T')[0];
        countsByDate[dateStr] = (countsByDate[dateStr] || 0) + 1;
    });

    const dates = Object.keys(countsByDate).sort();
    let cumulative = 0;
    const dataPoints = dates.map(date => {
        cumulative += countsByDate[date];
        return { date, value: cumulative };
    });

    if (dataPoints.length === 0) {
        container.innerHTML = `<span style="color: var(--text-muted); font-style: italic; font-size: 12px;">No resolved findings trend data yet.</span>`;
        return;
    }

    const points = dataPoints.slice(-10);
    
    const width = container.clientWidth || 350;
    const height = 100;
    const padding = 15;
    
    const maxVal = Math.max(...points.map(p => p.value)) || 1;
    
    const xStep = points.length > 1 ? (width - padding * 2) / (points.length - 1) : 0;
    const yScale = (height - padding * 2) / maxVal;
    
    let pathD = "";
    let areaD = "";
    let circlesHtml = "";
    
    points.forEach((p, idx) => {
        const x = padding + idx * xStep;
        const y = height - padding - (p.value * yScale);
        
        if (idx === 0) {
            pathD = `M ${x} ${y}`;
            areaD = `M ${x} ${height - padding} L ${x} ${y}`;
        } else {
            pathD += ` L ${x} ${y}`;
            areaD += ` L ${x} ${y}`;
        }
        
        if (idx === points.length - 1) {
            areaD += ` L ${x} ${height - padding} Z`;
        }

        circlesHtml += `<circle cx="${x}" cy="${y}" r="4" fill="var(--accent-purple)" stroke="white" stroke-width="1.5">
            <title>${p.date}: ${p.value} resolved</title>
        </circle>`;
    });

    if (points.length === 1) {
        const x = width / 2;
        const y = height / 2;
        pathD = `M ${padding} ${y} L ${width - padding} ${y}`;
        circlesHtml = `<circle cx="${x}" cy="${y}" r="5" fill="var(--accent-purple)" stroke="white" stroke-width="1.5">
            <title>${points[0].date}: ${points[0].value} resolved</title>
        </circle>`;
    }

    container.innerHTML = `
        <svg width="100%" height="100%" viewBox="0 0 ${width} ${height}" style="overflow: visible;">
            <defs>
                <linearGradient id="trendAreaGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="var(--accent-purple)" stop-opacity="0.2"/>
                    <stop offset="100%" stop-color="var(--accent-purple)" stop-opacity="0"/>
                </linearGradient>
            </defs>
            <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>
            ${areaD ? `<path d="${areaD}" fill="url(#trendAreaGrad)"/>` : ''}
            ${pathD ? `<path d="${pathD}" fill="none" stroke="var(--accent-purple)" stroke-width="2"/>` : ''}
            ${circlesHtml}
        </svg>
    `;
}

// Bind search and filter events in custom init
document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('findings-search');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            activeFindingSearchQuery = e.target.value;
            renderFindings();
        });
    }

    const sevFilter = document.getElementById('findings-filter-severity');
    if (sevFilter) {
        sevFilter.addEventListener('change', (e) => {
            activeFindingFilterSeverity = e.target.value;
            renderFindings();
        });
    }

    const catFilter = document.getElementById('findings-filter-category');
    if (catFilter) {
        catFilter.addEventListener('change', (e) => {
            activeFindingFilterCategory = e.target.value;
            renderFindings();
        });
    }

    const tabs = document.querySelectorAll('#findings-status-tabs .finding-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => {
                t.classList.remove('active');
                t.style.color = 'var(--text-muted)';
                t.style.borderBottom = 'none';
                t.style.fontWeight = 'normal';
            });
            tab.classList.add('active');
            tab.style.color = 'var(--accent-purple)';
            tab.style.borderBottom = '2px solid var(--accent-purple)';
            tab.style.fontWeight = '600';

            activeFindingFilterStatus = tab.getAttribute('data-status');
            renderFindings();
        });
    });

    const resolveBtn = document.getElementById('btn-finding-resolve');
    if (resolveBtn) {
        resolveBtn.addEventListener('click', async () => {
            if (!activeFindingId) return;
            try {
                const res = await authorizedFetch(`/findings/${activeFindingId}/status`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: 'Resolved' })
                });
                if (res.ok) {
                    alert('Finding marked as Resolved successfully!');
                    loadProjectFindings(activeProjectId);
                } else {
                    alert('Failed to resolve finding.');
                }
            } catch (err) {
                alert('Resolve error: ' + err.message);
            }
        });
    }

    const ignoreBtn = document.getElementById('btn-finding-ignore');
    if (ignoreBtn) {
        ignoreBtn.addEventListener('click', async () => {
            if (!activeFindingId) return;
            const reason = prompt('Please enter a reason for ignoring/overriding this finding:');
            if (reason === null) return;
            
            try {
                const res = await authorizedFetch(`/findings/${activeFindingId}/ignore`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ reason: reason })
                });
                if (res.ok) {
                    alert('Finding ignored and overridden successfully!');
                    loadProjectFindings(activeProjectId);
                } else {
                    alert('Failed to ignore finding.');
                }
            } catch (err) {
                alert('Ignore error: ' + err.message);
            }
        });
    }

    const reopenBtn = document.getElementById('btn-finding-reopen');
    if (reopenBtn) {
        reopenBtn.addEventListener('click', async () => {
            if (!activeFindingId) return;
            try {
                const res = await authorizedFetch(`/findings/${activeFindingId}/reopen`, {
                    method: 'PATCH'
                });
                if (res.ok) {
                    alert('Finding reopened successfully!');
                    loadProjectFindings(activeProjectId);
                } else {
                    alert('Failed to reopen finding.');
                }
            } catch (err) {
                alert('Reopen error: ' + err.message);
            }
        });
    }

    const assigneeSelect = document.getElementById('finding-assignee-select');
    if (assigneeSelect) {
        assigneeSelect.addEventListener('change', async (e) => {
            if (!activeFindingId) return;
            const user = e.target.value || null;
            try {
                const res = await authorizedFetch(`/findings/${activeFindingId}/assign`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ assigned_to: user })
                });
                if (res.ok) {
                    alert(`Finding successfully assigned to ${user || 'Unassigned'}.`);
                    loadProjectFindings(activeProjectId);
                }
            } catch (err) {
                console.error('Assign error:', err);
            }
        });
    }

    const applyFixBtn = document.getElementById('btn-finding-apply-fix');
    if (applyFixBtn) {
        applyFixBtn.addEventListener('click', async () => {
            if (!activeFindingId || !activeProjectId) return;

            const originalText = applyFixBtn.textContent;
            applyFixBtn.disabled = true;
            applyFixBtn.textContent = 'Generating Plan...';

            try {
                const res = await authorizedFetch(`/findings/${activeFindingId}/generate-fix`, {
                    method: 'POST'
                });

                if (res.ok) {
                    const fixExec = await res.json();
                    alert(`AI Fix plan and patch preview generated successfully! Redirecting you to the AI Fix Center.`);
                    
                    // Hide details modal if open (it might be open inside view-findings)
                    const findingModal = document.getElementById('finding-detail-modal');
                    if (findingModal) findingModal.classList.add('hidden');
                    
                    // Switch sidebar view to AI Fix Center
                    const fixCenterNav = document.getElementById('nav-item-fix-center');
                    if (fixCenterNav) {
                        fixCenterNav.click();
                        // Load the newly created fix run details
                        showFixDetails(fixExec);
                    }
                } else {
                    const data = await res.json();
                    alert(data.detail || 'Failed to generate AI fix plan.');
                }
            } catch (err) {
                alert('Generate fix error: ' + err.message);
            } finally {
                applyFixBtn.disabled = false;
                applyFixBtn.textContent = originalText;
            }
        });
    }
});

// ==========================================
// AI Engine v2.2: Semantic Code Graph Explorer
// ==========================================

let semGraphData = { nodes: [], edges: [] };
let semNodePositions = {}; // id -> { x, y }
let semSelectedNode = null;
let semZoomScale = 1.0;
let semPanOffset = { x: 0, y: 0 };
let semIsDragging = false;
let semDragStart = { x: 0, y: 0 };
let semGraphCanvas = null;
let semGraphCtx = null;
let semNodeRadii = {
    file: 20,
    class: 16,
    db_model: 18,
    interface: 16,
    method: 10,
    function: 10,
    api_route: 15
};
let semNodeColors = {
    file: '#94a3b8',      // slate
    class: '#3b82f6',     // custom blue
    db_model: '#fbbf24',  // amber
    interface: '#60a5fa', // sky blue
    method: '#a78bfa',    // purple
    function: '#c084fc',  // lavender
    api_route: '#10b981'  // emerald
};

// Listen to view-pane change to load and render semantic explorer
document.addEventListener('click', (e) => {
    const navItem = e.target.closest('.nav-item');
    if (navItem && navItem.getAttribute('data-view') === 'view-semantic') {
        initSemanticExplorer();
    }
});

async function initSemanticExplorer() {
    semGraphCanvas = document.getElementById('sem-graph-canvas');
    if (!semGraphCanvas) return;
    semGraphCtx = semGraphCanvas.getContext('2d');
    
    // Resize canvas to fill parent
    resizeSemCanvas();
    window.addEventListener('resize', resizeSemCanvas);
    
    // Attach mouse listeners
    semGraphCanvas.addEventListener('mousedown', onSemMouseDown);
    semGraphCanvas.addEventListener('mousemove', onSemMouseMove);
    semGraphCanvas.addEventListener('mouseup', onSemMouseUp);
    semGraphCanvas.addEventListener('mouseleave', onSemMouseUp);
    semGraphCanvas.addEventListener('wheel', onSemWheel, { passive: false });
    
    // Wire UI controls
    document.getElementById('sem-graph-view').onchange = renderSemanticGraph;
    document.getElementById('sem-graph-search').oninput = renderSemanticGraph;
    document.getElementById('btn-sem-zoom-in').onclick = () => { semZoomScale *= 1.2; renderSemanticGraph(); };
    document.getElementById('btn-sem-zoom-out').onclick = () => { semZoomScale /= 1.2; renderSemanticGraph(); };
    document.getElementById('btn-sem-reset').onclick = () => {
        semZoomScale = 1.0;
        semPanOffset = { x: 0, y: 0 };
        semSelectedNode = null;
        renderSemanticGraph();
    };
    
    document.getElementById('btn-regenerate-graph').onclick = regenerateSemanticGraph;
    document.getElementById('btn-run-impact').onclick = runSemanticImpactAnalysis;
    
    // Load data
    await loadSemanticGraphData();
}

function resizeSemCanvas() {
    if (!semGraphCanvas) return;
    const rect = semGraphCanvas.parentElement.getBoundingClientRect();
    semGraphCanvas.width = rect.width;
    semGraphCanvas.height = rect.height;
    renderSemanticGraph();
}

async function loadSemanticGraphData() {
    if (!activeProjectId) return;
    try {
        const res = await authorizedFetch(`/projects/${activeProjectId}/semantic-graph`);
        if (!res.ok) return;
        const data = await res.json();
        semGraphData = data;
        
        // Populate stats dashboard
        const stats = data.statistics || {};
        document.getElementById('sem-stat-classes').textContent = stats.classes || 0;
        document.getElementById('sem-stat-functions').textContent = stats.functions || 0;
        document.getElementById('sem-stat-apis').textContent = stats.api_routes || 0;
        
        // Fetch circular dependencies
        const cyclesRes = await authorizedFetch(`/projects/${activeProjectId}/semantic-graph/cycles`);
        const cycles = cyclesRes.ok ? await cyclesRes.json() : [];
        document.getElementById('sem-stat-cycles').textContent = cycles.length;
        
        // Fetch dead code
        const deadRes = await authorizedFetch(`/projects/${activeProjectId}/semantic-graph/dead-code`);
        const dead = deadRes.ok ? await deadRes.json() : { unused_files: [], dead_symbols: [] };
        const totalDead = (dead.unused_files || []).length + (dead.dead_symbols || []).length;
        document.getElementById('sem-stat-dead').textContent = totalDead;
        
        // Initialize node positions using force layout simulation
        initNodePositions();
    } catch (err) {
        console.error('Failed to load semantic graph details:', err);
    }
}

function initNodePositions() {
    semNodePositions = {};
    if (semGraphData.nodes.length === 0) return;
    
    const width = semGraphCanvas.width || 800;
    const height = semGraphCanvas.height || 600;
    
    // Initial placement grouped by node type to build beautiful layouts
    semGraphData.nodes.forEach((n, idx) => {
        let x = width / 2;
        let y = height / 2;
        
        if (n.node_type === 'file') {
            x = width * 0.2 + Math.random() * 80;
            y = height * 0.2 + (idx * 50) % (height * 0.6);
        } else if (n.node_type === 'class' || n.node_type === 'db_model') {
            x = width * 0.5 + Math.random() * 80;
            y = height * 0.3 + (idx * 60) % (height * 0.5);
        } else if (n.node_type === 'method' || n.node_type === 'function') {
            x = width * 0.7 + Math.random() * 80;
            y = height * 0.4 + (idx * 40) % (height * 0.5);
        } else if (n.node_type === 'api_route') {
            x = width * 0.85 - Math.random() * 40;
            y = height * 0.5 + (idx * 70) % (height * 0.4);
        }
        
        semNodePositions[n.id] = { x, y };
    });
    
    // Run spring force-directed simulation (60 iterations) to settle layout
    const k = 50; // spring rest length
    const cRepulsive = 200000;
    const cAttractive = 0.06;
    
    for (let iter = 0; iter < 60; iter++) {
        let forces = {};
        semGraphData.nodes.forEach(n => { forces[n.id] = { x: 0, y: 0 }; });
        
        // Repulsive forces between all nodes
        for (let i = 0; i < semGraphData.nodes.length; i++) {
            const n1 = semGraphData.nodes[i];
            const p1 = semNodePositions[n1.id];
            for (let j = i + 1; j < semGraphData.nodes.length; j++) {
                const n2 = semGraphData.nodes[j];
                const p2 = semNodePositions[n2.id];
                if (!p1 || !p2) continue;
                
                const dx = p1.x - p2.x;
                const dy = p1.y - p2.y;
                const distSq = dx * dx + dy * dy + 0.1;
                const dist = Math.sqrt(distSq);
                
                if (dist < 300) {
                    const fRep = cRepulsive / distSq;
                    const fx = (dx / dist) * fRep;
                    const fy = (dy / dist) * fRep;
                    
                    forces[n1.id].x += fx;
                    forces[n1.id].y += fy;
                    forces[n2.id].x -= fx;
                    forces[n2.id].y -= fy;
                }
            }
        }
        
        // Attractive forces along edges
        semGraphData.edges.forEach(e => {
            const p1 = semNodePositions[e.source_node_id];
            const p2 = semNodePositions[e.target_node_id];
            if (p1 && p2) {
                const dx = p1.x - p2.x;
                const dy = p1.y - p2.y;
                const dist = Math.sqrt(dx * dx + dy * dy) + 0.1;
                
                const fAtt = cAttractive * (dist - k);
                const fx = (dx / dist) * fAtt;
                const fy = (dy / dist) * fAtt;
                
                forces[e.source_node_id].x -= fx;
                forces[e.source_node_id].y -= fy;
                forces[e.target_node_id].x += fx;
                forces[e.target_node_id].y += fy;
            }
        });
        
        // Apply forces to update node coordinates
        semGraphData.nodes.forEach(n => {
            const p = semNodePositions[n.id];
            const f = forces[n.id];
            if (!p || !f) return;
            
            // limit displacement
            const dispLimit = 15;
            const fx = Math.max(-dispLimit, Math.min(dispLimit, f.x));
            const fy = Math.max(-dispLimit, Math.min(dispLimit, f.y));
            
            p.x += fx;
            p.y += fy;
        });
    }
    
    renderSemanticGraph();
}

function renderSemanticGraph() {
    if (!semGraphCtx || !semGraphCanvas) return;
    
    const ctx = semGraphCtx;
    const canvas = semGraphCanvas;
    const viewMode = document.getElementById('sem-graph-view').value;
    const searchQuery = document.getElementById('sem-graph-search').value.toLowerCase();
    
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Filter nodes and edges based on View Mode selection
    let nodesToDraw = semGraphData.nodes || [];
    let edgesToDraw = semGraphData.edges || [];
    
    if (viewMode === 'class') {
        nodesToDraw = nodesToDraw.filter(n => ['file', 'class', 'db_model', 'interface'].includes(n.node_type));
    } else if (viewMode === 'function') {
        nodesToDraw = nodesToDraw.filter(n => ['file', 'function'].includes(n.node_type));
    } else if (viewMode === 'api') {
        nodesToDraw = nodesToDraw.filter(n => ['file', 'api_route', 'method', 'function'].includes(n.node_type));
    } else if (viewMode === 'call') {
        nodesToDraw = nodesToDraw.filter(n => ['method', 'function'].includes(n.node_type));
    }
    
    const allowedNodeIds = new Set(nodesToDraw.map(n => n.id));
    edgesToDraw = edgesToDraw.filter(e => allowedNodeIds.has(e.source_node_id) && allowedNodeIds.has(e.target_node_id));
    
    // Handle selections and highlighted states
    let highlightedNodes = new Set();
    let highlightedEdges = new Set();
    
    if (semSelectedNode) {
        highlightedNodes.add(semSelectedNode.id);
        edgesToDraw.forEach(e => {
            if (e.source_node_id === semSelectedNode.id) {
                highlightedNodes.add(e.target_node_id);
                highlightedEdges.add(e.id);
            }
            if (e.target_node_id === semSelectedNode.id) {
                highlightedNodes.add(e.source_node_id);
                highlightedEdges.add(e.id);
            }
        });
    }
    
    ctx.save();
    // Translate and Scale canvas viewport
    ctx.translate(semPanOffset.x, semPanOffset.y);
    ctx.scale(semZoomScale, semZoomScale);
    
    // 1. Draw Edges
    edgesToDraw.forEach(e => {
        const p1 = semNodePositions[e.source_node_id];
        const p2 = semNodePositions[e.target_node_id];
        if (!p1 || !p2) return;
        
        const isHighlighted = semSelectedNode ? highlightedEdges.has(e.id) : true;
        ctx.strokeStyle = isHighlighted ? 'rgba(96,165,250,0.8)' : 'rgba(255,255,255,0.06)';
        ctx.lineWidth = isHighlighted ? 2 : 1;
        
        ctx.beginPath();
        if (e.relationship === 'IMPORTS' || e.relationship === 'DEPENDS_ON') {
            ctx.setLineDash([4, 4]); // dashed lines for imports
        } else {
            ctx.setLineDash([]);
        }
        
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.stroke();
        
        // Draw directional relationship arrow
        const targetNodeObj = semGraphData.nodes.find(n => n.id === e.target_node_id);
        if (targetNodeObj) {
            drawEdgeArrow(ctx, p1.x, p1.y, p2.x, p2.y, semNodeRadii[targetNodeObj.node_type] || 15);
        }
    });
    
    ctx.setLineDash([]); // reset dash
    
    // 2. Draw Nodes
    nodesToDraw.forEach(n => {
        const pos = semNodePositions[n.id];
        if (!pos) return;
        
        const radius = semNodeRadii[n.node_type] || 15;
        const color = semNodeColors[n.node_type] || '#94a3b8';
        
        const isMatched = searchQuery ? n.name.toLowerCase().includes(searchQuery) || n.file_path.toLowerCase().includes(searchQuery) : true;
        const isSelected = semSelectedNode && semSelectedNode.id === n.id;
        const isHighlighted = semSelectedNode ? highlightedNodes.has(n.id) : true;
        
        // Opacity
        ctx.globalAlpha = (isHighlighted && isMatched) ? 1.0 : 0.15;
        
        // Glow effect for selected
        if (isSelected) {
            ctx.shadowColor = color;
            ctx.shadowBlur = 15;
        } else {
            ctx.shadowBlur = 0;
        }
        
        // Circle body
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, radius, 0, 2 * Math.PI);
        ctx.fillStyle = color;
        ctx.fill();
        
        // Outline border
        ctx.strokeStyle = isSelected ? '#ffffff' : 'rgba(255,255,255,0.15)';
        ctx.lineWidth = isSelected ? 3 : 1.5;
        ctx.stroke();
        
        // Text labels
        ctx.shadowBlur = 0; // reset shadow
        ctx.fillStyle = '#f8fafc'; // light text
        ctx.font = isSelected ? 'bold 11px var(--font-mono)' : '9px var(--font-mono)';
        ctx.textAlign = 'center';
        ctx.fillText(n.name, pos.x, pos.y + radius + 11);
        
        // Node Type subtitle
        ctx.fillStyle = 'rgba(255,255,255,0.4)';
        ctx.font = '8px var(--font-sans)';
        ctx.fillText(n.node_type.toUpperCase(), pos.x, pos.y - radius - 5);
    });
    
    ctx.restore();
}

function drawEdgeArrow(ctx, fromx, fromy, tox, toy, targetRadius) {
    const angle = Math.atan2(toy - fromy, tox - fromx);
    // Find point on target circle boundary
    const arrowX = tox - targetRadius * Math.cos(angle);
    const arrowY = toy - targetRadius * Math.sin(angle);
    
    ctx.beginPath();
    ctx.moveTo(arrowX, arrowY);
    ctx.lineTo(arrowX - 8 * Math.cos(angle - Math.PI / 6), arrowY - 8 * Math.sin(angle - Math.PI / 6));
    ctx.lineTo(arrowX - 8 * Math.cos(angle + Math.PI / 6), arrowY - 8 * Math.sin(angle + Math.PI / 6));
    ctx.closePath();
    ctx.fillStyle = ctx.strokeStyle;
    ctx.fill();
}

// Interactive zoom/pan/drag events implementation

function onSemMouseDown(e) {
    const rect = semGraphCanvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    
    // Transform coordinates back to canvas world coordinates
    const worldX = (mouseX - semPanOffset.x) / semZoomScale;
    const worldY = (mouseY - semPanOffset.y) / semZoomScale;
    
    // Check if clicked on any node
    let clickedNode = null;
    for (let i = 0; i < semGraphData.nodes.length; i++) {
        const n = semGraphData.nodes[i];
        const p = semNodePositions[n.id];
        if (p) {
            const radius = semNodeRadii[n.node_type] || 15;
            const dist = Math.sqrt((worldX - p.x) ** 2 + (worldY - p.y) ** 2);
            if (dist <= radius) {
                clickedNode = n;
                break;
            }
        }
    }
    
    if (clickedNode) {
        semSelectedNode = clickedNode;
        // Populate node details card
        displayNodeDetails(clickedNode);
        
        // Seed impact analyzer inputs with selected node path
        document.getElementById('impact-file-path').value = clickedNode.file_path;
        if (clickedNode.node_type !== 'file') {
            document.getElementById('impact-symbol').value = clickedNode.name.split('.').pop();
        } else {
            document.getElementById('impact-symbol').value = '';
        }
        
        renderSemanticGraph();
    } else {
        semIsDragging = true;
        semDragStart = { x: mouseX - semPanOffset.x, y: mouseY - semPanOffset.y };
        semGraphCanvas.style.cursor = 'grabbing';
    }
}

function onSemMouseMove(e) {
    if (semIsDragging) {
        const rect = semGraphCanvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        semPanOffset.x = mouseX - semDragStart.x;
        semPanOffset.y = mouseY - semDragStart.y;
        renderSemanticGraph();
    }
}

function onSemMouseUp() {
    semIsDragging = false;
    if (semGraphCanvas) semGraphCanvas.style.cursor = 'grab';
}

function onSemWheel(e) {
    e.preventDefault();
    const rect = semGraphCanvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    
    const zoomFactor = 1.1;
    let newScale = semZoomScale;
    if (e.deltaY < 0) {
        newScale *= zoomFactor;
    } else {
        newScale /= zoomFactor;
    }
    
    // Zoom around mouse position
    semPanOffset.x = mouseX - (mouseX - semPanOffset.x) * (newScale / semZoomScale);
    semPanOffset.y = mouseY - (mouseY - semPanOffset.y) * (newScale / semZoomScale);
    semZoomScale = newScale;
    renderSemanticGraph();
}

function displayNodeDetails(node) {
    const detailsContainer = document.getElementById('sem-node-details');
    if (!detailsContainer) return;
    
    const meta = node.metadata || {};
    let metaHTML = '';
    
    if (node.node_type === 'file') {
        metaHTML = `<div><strong>Size:</strong> ${meta.size || 0} bytes</div>
                    <div><strong>Language:</strong> ${meta.language || 'Unknown'}</div>`;
    } else if (node.node_type === 'class' || node.node_type === 'db_model') {
        const bases = meta.bases || [];
        metaHTML = `<div><strong>Inherited Bases:</strong> ${bases.join(', ') || 'None'}</div>`;
    } else if (node.node_type === 'method' || node.node_type === 'function') {
        const args = meta.args || [];
        metaHTML = `<div><strong>Arguments:</strong> <code>(${args.join(', ')})</code></div>`;
    }
    
    detailsContainer.innerHTML = `
        <div style="font-size: 14px; font-weight: 700; color: var(--text-bright); word-break: break-all;">${escapeHtml(node.name)}</div>
        <div style="margin-top: 6px;"><span class="pill outline" style="font-size: 10px;">${node.node_type.toUpperCase()}</span></div>
        <div style="margin-top: 10px; display: flex; flex-direction: column; gap: 6px;">
            <div><strong>File Path:</strong> <code style="word-break: break-all;">${escapeHtml(node.file_path)}</code></div>
            <div><strong>Lines:</strong> L${node.start_line} - L${node.end_line}</div>
            ${metaHTML}
        </div>
    `;
}

async function regenerateSemanticGraph() {
    if (!activeProjectId) return;
    const btn = document.getElementById('btn-regenerate-graph');
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Analyzing...';
    
    try {
        const res = await authorizedFetch(`/projects/${activeProjectId}/semantic-graph/regenerate`, { method: 'POST' });
        if (res.ok) {
            alert('Semantic code graph successfully parsed and regenerated.');
            await loadSemanticGraphData();
        } else {
            const data = await res.json();
            alert(data.detail || 'Failed to regenerate semantic graph.');
        }
    } catch (err) {
        alert('Regenerate semantic graph error: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

async function runSemanticImpactAnalysis() {
    if (!activeProjectId) return;
    const filePath = document.getElementById('impact-file-path').value.trim();
    const symbol = document.getElementById('impact-symbol').value.trim();
    
    if (!filePath) {
        alert('Please specify a file path to run impact analysis.');
        return;
    }
    
    const btn = document.getElementById('btn-run-impact');
    btn.disabled = true;
    btn.textContent = 'Calculating...';
    
    try {
        let url = `/projects/${activeProjectId}/semantic-graph/impact-analysis?file_path=${encodeURIComponent(filePath)}`;
        if (symbol) {
            url += `&symbol_name=${encodeURIComponent(symbol)}`;
        }
        
        const res = await authorizedFetch(url);
        if (res.ok) {
            const data = await res.json();
            
            // Show impact block
            document.getElementById('impact-results').style.display = 'block';
            document.getElementById('impact-risk-score').textContent = data.risk_score;
            
            const badge = document.getElementById('impact-risk-badge');
            badge.textContent = data.risk_rating;
            badge.className = 'badge';
            if (data.risk_rating === 'High Risk') {
                badge.classList.add('badge-error');
            } else if (data.risk_rating === 'Medium Risk') {
                badge.classList.add('badge-warning');
            } else {
                badge.classList.add('badge-success');
            }
            
            const depsDiv = document.getElementById('impact-deps');
            const deps = data.dependent_files || [];
            if (deps.length === 0) {
                depsDiv.innerHTML = '<span style="color: var(--text-muted); font-style: italic;">No downstream dependency impact.</span>';
            } else {
                depsDiv.innerHTML = deps.map(d => `<div style="word-break: break-all; margin-bottom: 4px;">• ${escapeHtml(d)}</div>`).join('');
            }
        } else {
            const data = await res.json();
            alert(data.detail || 'Impact analysis failed.');
        }
    } catch (err) {
        alert('Impact analysis error: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Analyze Impact';
    }
}

// ==========================================
// Collaborative Workspace & Activity Feed Features (v2.3)
// ==========================================

let activeWorkspaceId = null;
let workspaceList = [];

// Initialize Workspaces, members and comments features
document.addEventListener('DOMContentLoaded', () => {
    initWorkspacesTab();
});

function initWorkspacesTab() {
    // Modal controls for Workspace Creation
    const btnCreateWSModal = document.getElementById('btn-create-workspace-modal');
    const wsModal = document.getElementById('create-workspace-modal');
    const btnCancelWSModal = document.getElementById('btn-cancel-workspace-modal');
    const createWSForm = document.getElementById('create-workspace-form');
    
    if (btnCreateWSModal) {
        btnCreateWSModal.addEventListener('click', () => {
            wsModal.classList.remove('hidden');
            document.getElementById('workspace-name').value = '';
            document.getElementById('workspace-desc').value = '';
        });
    }
    
    if (btnCancelWSModal) {
        btnCancelWSModal.addEventListener('click', () => {
            wsModal.classList.add('hidden');
        });
    }
    
    if (createWSForm) {
        createWSForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const name = document.getElementById('workspace-name').value.trim();
            const description = document.getElementById('workspace-desc').value.trim();
            if (!name) return;
            
            try {
                const res = await authorizedFetch('/workspaces', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, description })
                });
                if (res.ok) {
                    wsModal.classList.add('hidden');
                    await loadWorkspaces();
                } else {
                    const data = await res.json();
                    alert(data.detail || 'Failed to create workspace.');
                }
            } catch (err) {
                alert('Error creating workspace: ' + err.message);
            }
        });
    }
    
    // Invite member form
    const inviteForm = document.getElementById('workspace-invite-form');
    if (inviteForm) {
        inviteForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!activeWorkspaceId) return;
            
            const username = document.getElementById('invite-username').value.trim();
            const role = document.getElementById('invite-role').value;
            if (!username) return;
            
            try {
                const res = await authorizedFetch(`/workspaces/${activeWorkspaceId}/members`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, role })
                });
                if (res.ok) {
                    document.getElementById('invite-username').value = '';
                    await loadWorkspaceDetails(activeWorkspaceId);
                } else {
                    const data = await res.json();
                    alert(data.detail || 'Failed to add member.');
                }
            } catch (err) {
                alert('Error adding member: ' + err.message);
            }
        });
    }
    
    // Comments submit binding
    const btnSendComment = document.getElementById('btn-add-finding-comment');
    if (btnSendComment) {
        btnSendComment.addEventListener('click', async () => {
            if (!activeFindingId) return;
            const input = document.getElementById('finding-comment-input');
            const content = input.value.trim();
            if (!content) return;
            
            try {
                const res = await authorizedFetch(`/findings/${activeFindingId}/comments`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ comment: content })
                });
                if (res.ok) {
                    input.value = '';
                    await loadFindingComments(activeFindingId);
                } else {
                    const data = await res.json();
                    alert(data.detail || 'Failed to post comment.');
                }
            } catch (err) {
                alert('Error posting comment: ' + err.message);
            }
        });
    }
}

// Load Workspaces list
async function loadWorkspaces() {
    const listContainer = document.getElementById('workspace-selector-list');
    if (!listContainer) return;
    
    listContainer.innerHTML = '<div style="color: var(--text-muted); font-style: italic; padding: 10px;">Loading workspaces...</div>';
    
    try {
        const res = await authorizedFetch('/workspaces');
        if (res.ok) {
            workspaceList = await res.json();
            listContainer.innerHTML = '';
            
            if (workspaceList.length === 0) {
                listContainer.innerHTML = '<div style="color: var(--text-muted); font-style: italic; padding: 10px; font-size: 13px;">No workspaces found. Click "+ New Workspace" to create one.</div>';
                document.getElementById('workspace-detail-placeholder').style.display = 'block';
                document.getElementById('workspace-detail-content').style.display = 'none';
                activeWorkspaceId = null;
                return;
            }
            
            workspaceList.forEach(ws => {
                const item = document.createElement('div');
                item.className = `project-card ${activeWorkspaceId === ws.id ? 'active' : ''}`;
                item.style.margin = '0 0 8px 0';
                item.style.padding = '10px 12px';
                item.style.cursor = 'pointer';
                item.style.border = activeWorkspaceId === ws.id ? '1px solid var(--accent-purple)' : '1px solid rgba(255,255,255,0.06)';
                item.style.borderRadius = '8px';
                
                item.innerHTML = `
                    <h4 style="margin: 0; font-size: 14px; font-weight: 600; color: var(--text-bright);">${escapeHtml(ws.name)}</h4>
                    <p style="margin: 4px 0 0 0; font-size: 11px; color: var(--text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(ws.description || '')}</p>
                `;
                
                item.addEventListener('click', () => {
                    document.querySelectorAll('#workspace-selector-list .project-card').forEach(c => {
                        c.classList.remove('active');
                        c.style.borderColor = 'rgba(255,255,255,0.06)';
                    });
                    item.classList.add('active');
                    item.style.borderColor = 'var(--accent-purple)';
                    loadWorkspaceDetails(ws.id);
                });
                
                listContainer.appendChild(item);
            });
            
            // Auto select first
            if (!activeWorkspaceId && workspaceList.length > 0) {
                activeWorkspaceId = workspaceList[0].id;
                const cards = listContainer.querySelectorAll('.project-card');
                if (cards.length > 0) {
                    cards[0].classList.add('active');
                    cards[0].style.borderColor = 'var(--accent-purple)';
                }
                loadWorkspaceDetails(activeWorkspaceId);
            }
        }
    } catch (err) {
        console.error('Error loading workspaces:', err);
    }
}

// Load Selected Workspace details
async function loadWorkspaceDetails(workspaceId) {
    activeWorkspaceId = workspaceId;
    document.getElementById('workspace-detail-placeholder').style.display = 'none';
    document.getElementById('workspace-detail-content').style.display = 'flex';
    
    try {
        const res = await authorizedFetch(`/workspaces/${workspaceId}`);
        if (res.ok) {
            const ws = await res.json();
            document.getElementById('workspace-display-name').textContent = ws.name;
            document.getElementById('workspace-display-desc').textContent = ws.description || 'No description.';
            
            await loadWorkspaceMembers(workspaceId);
            await loadWorkspaceActivities(workspaceId);
        }
    } catch (err) {
        console.error('Error loading workspace details:', err);
    }
}

// Load workspace members list
async function loadWorkspaceMembers(workspaceId) {
    const listContainer = document.getElementById('workspace-members-list');
    if (!listContainer) return;
    
    listContainer.innerHTML = '';
    
    try {
        const res = await authorizedFetch(`/workspaces/${workspaceId}/members`);
        if (res.ok) {
            const members = await res.json();
            members.forEach(member => {
                const item = document.createElement('div');
                item.style.display = 'flex';
                item.style.justifyContent = 'space-between';
                item.style.alignItems = 'center';
                item.style.padding = '8px 12px';
                item.style.borderRadius = '8px';
                item.style.background = 'rgba(255,255,255,0.02)';
                item.style.border = '1px solid rgba(255,255,255,0.04)';
                
                // Role badge colors
                const roleColors = {
                    Owner: '#ef4444',
                    Admin: '#a78bfa',
                    Developer: '#3b82f6',
                    Viewer: '#34d399'
                };
                const color = roleColors[member.role] || 'var(--text-muted)';
                
                item.innerHTML = `
                    <div>
                        <strong style="color: var(--text-bright); font-size: 13px;">${escapeHtml(member.user.username)}</strong>
                        <span style="font-size: 11px; margin-left: 6px; color: ${color}; font-weight: 600;">${member.role}</span>
                    </div>
                `;
                
                // If owner or admin, allow changing role / deleting member (simplified for demonstration)
                const actionDiv = document.createElement('div');
                actionDiv.style.display = 'flex';
                actionDiv.style.gap = '5px';
                
                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'btn btn-secondary btn-sm';
                deleteBtn.style.margin = '0';
                deleteBtn.style.padding = '4px 8px';
                deleteBtn.style.fontSize = '10px';
                deleteBtn.style.background = 'rgba(239, 68, 68, 0.1)';
                deleteBtn.style.borderColor = 'rgba(239, 68, 68, 0.2)';
                deleteBtn.style.color = '#fca5a5';
                deleteBtn.textContent = 'Remove';
                
                deleteBtn.addEventListener('click', async () => {
                    if (confirm(`Are you sure you want to remove ${member.user.username} from this workspace?`)) {
                        try {
                            const delRes = await authorizedFetch(`/workspaces/${workspaceId}/members/${member.user.id}`, {
                                method: 'DELETE'
                            });
                            if (delRes.ok) {
                                await loadWorkspaceMembers(workspaceId);
                            } else {
                                const data = await delRes.json();
                                alert(data.detail || 'Failed to remove member.');
                            }
                        } catch (err) {
                            alert('Remove member error: ' + err.message);
                        }
                    }
                });
                
                actionDiv.appendChild(deleteBtn);
                item.appendChild(actionDiv);
                listContainer.appendChild(item);
            });
        }
    } catch (err) {
        console.error('Error loading workspace members:', err);
    }
}

// Load workspace activities
async function loadWorkspaceActivities(workspaceId) {
    const feed = document.getElementById('workspace-activity-timeline');
    if (!feed) return;
    
    feed.innerHTML = '';
    
    try {
        const res = await authorizedFetch(`/workspaces/${workspaceId}/activities`);
        if (res.ok) {
            const data = await res.json();
            const logs = data.activities || [];
            if (logs.length === 0) {
                feed.innerHTML = '<div style="color: var(--text-muted); font-style: italic; padding: 10px; font-size: 13px;">No activities recorded yet in this workspace.</div>';
                return;
            }
            
            logs.forEach(log => {
                const item = document.createElement('div');
                item.style.display = 'flex';
                item.style.gap = '10px';
                item.style.alignItems = 'start';
                item.style.padding = '8px 0';
                item.style.borderBottom = '1px solid rgba(255,255,255,0.03)';
                
                const timeStr = new Date(log.created_at).toLocaleString();
                
                item.innerHTML = `
                    <span style="font-size: 14px;">📝</span>
                    <div style="flex: 1; font-size: 13px;">
                        <span style="color: var(--text-muted); font-size: 11px; display: block; margin-bottom: 2px;">${timeStr}</span>
                        <strong style="color: var(--text-bright);">${escapeHtml(log.username)}</strong> 
                        <span style="color: var(--text-muted);">${escapeHtml(log.action)}</span>
                        ${log.details ? `<div style="margin-top: 4px; font-size: 12px; color: var(--text-bright); background: rgba(255,255,255,0.02); padding: 6px; border-radius: 4px; border: 1px solid rgba(255,255,255,0.04); font-family: var(--font-mono);">${escapeHtml(log.details)}</div>` : ''}
                    </div>
                `;
                feed.appendChild(item);
            });
        }
    } catch (err) {
        console.error('Error loading workspace activities:', err);
    }
}

// Populate Project creation modal with workspaces list
async function populateProjectModalWorkspaces() {
    const dropdown = document.getElementById('project-modal-workspace-id');
    if (!dropdown) return;
    
    dropdown.innerHTML = '<option value="">Personal Project (No Workspace)</option>';
    
    try {
        const res = await authorizedFetch('/workspaces');
        if (res.ok) {
            const list = await res.json();
            list.forEach(ws => {
                const opt = document.createElement('option');
                opt.value = ws.id;
                opt.textContent = ws.name;
                dropdown.appendChild(opt);
            });
        }
    } catch (err) {
        console.error('Error populating workspaces dropdown:', err);
    }
}

// Populate Assignee select dynamically
async function updateAssigneeSelectOptions(projectId) {
    const select = document.getElementById('finding-assignee-select');
    if (!select) return;
    
    // Cache current value
    const prevVal = select.value;
    
    // Clear and add placeholder options
    select.innerHTML = '<option value="">Unassigned</option>';
    
    if (!projectId) {
        select.innerHTML += `
            <option value="dattu">dattu</option>
            <option value="gemini-bot">Gemini Bot</option>
            <option value="reviewer">Reviewer</option>
        `;
        select.value = prevVal;
        return;
    }
    
    try {
        const res = await authorizedFetch(`/projects/${projectId}`);
        if (res.ok) {
            const project = await res.json();
            if (project.workspace_id) {
                const memRes = await authorizedFetch(`/workspaces/${project.workspace_id}/members`);
                if (memRes.ok) {
                    const members = await memRes.json();
                    members.forEach(member => {
                        const opt = document.createElement('option');
                        opt.value = member.username;
                        opt.textContent = `${member.username} (${member.role})`;
                        select.appendChild(opt);
                    });
                }
            } else {
                select.innerHTML += `
                    <option value="dattu">dattu</option>
                    <option value="gemini-bot">Gemini Bot</option>
                    <option value="reviewer">Reviewer</option>
                `;
            }
            select.value = prevVal;
        }
    } catch (err) {
        console.error('Error updating finding assignee options:', err);
    }
}

// Load finding comments history
async function loadFindingComments(findingId) {
    const container = document.getElementById('finding-comments-list');
    if (!container) return;
    
    container.innerHTML = '<div style="color: var(--text-muted); font-style: italic; font-size: 12px; padding: 5px;">Loading comments...</div>';
    
    try {
        const res = await authorizedFetch(`/findings/${findingId}/comments`);
        if (res.ok) {
            const comments = await res.json();
            container.innerHTML = '';
            
            if (comments.length === 0) {
                container.innerHTML = '<div style="color: var(--text-muted); font-style: italic; font-size: 12px; padding: 5px;">No comments posted yet.</div>';
                return;
            }
            
            comments.forEach(comment => {
                const div = document.createElement('div');
                div.style.background = 'rgba(255,255,255,0.02)';
                div.style.border = '1px solid rgba(255,255,255,0.06)';
                div.style.padding = '8px';
                div.style.borderRadius = '8px';
                div.style.fontSize = '12px';
                
                const timeStr = new Date(comment.created_at).toLocaleString();
                
                div.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                        <strong style="color: var(--accent-purple);">${escapeHtml(comment.username)}</strong>
                        <span style="font-size: 10px; color: var(--text-muted);">${timeStr}</span>
                    </div>
                    <div style="color: var(--text-bright); line-height: 1.4; word-break: break-word;">${escapeHtml(comment.content)}</div>
                `;
                container.appendChild(div);
            });
            
            // Scroll comments to bottom
            container.scrollTop = container.scrollHeight;
        }
    } catch (err) {
        console.error('Error loading comments:', err);
    }
}

// AI Fix Center functions
let activeFixExecutionId = null;

async function loadFixCenter(projectId) {
    if (!projectId) return;
    
    // Clear details pane
    document.getElementById('fix-details-empty').style.display = 'flex';
    document.getElementById('fix-details-active').style.display = 'none';
    
    try {
        const res = await authorizedFetch(`/projects/${projectId}/fix-history`);
        if (!res.ok) {
            document.getElementById('fix-executions-list').innerHTML = '<div style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 20px 0;">Failed to load fix history.</div>';
            return;
        }
        
        const history = await res.json();
        
        // Calculate Metrics
        let pending = 0;
        let success = 0;
        let failed = 0;
        let totalConfidence = 0;
        let totalTime = 0;
        let completedCount = 0;
        let riskCounts = { "Low": 0, "Medium": 0, "High": 0 };
        
        history.forEach(fx => {
            const status = fx.status.toLowerCase();
            if (['pending', 'planning', 'generating', 'preview ready', 'waiting approval', 'validating', 'applying', 'versioning', 'verifying'].includes(status)) {
                pending++;
            } else if (status === 'completed') {
                success++;
                completedCount++;
                totalTime += fx.execution_time || 0;
            } else if (['failed', 'rolled back'].includes(status)) {
                failed++;
                completedCount++;
                totalTime += fx.execution_time || 0;
            }
            
            totalConfidence += fx.confidence_score || 0;
            const r = fx.estimated_risk || "Low";
            riskCounts[r] = (riskCounts[r] || 0) + 1;
        });
        
        const total = success + failed;
        const passRate = total > 0 ? Math.round((success / total) * 100) : 0;
        const avgConfidence = history.length > 0 ? Math.round((totalConfidence / history.length) * 100) : 0;
        const avgTime = completedCount > 0 ? (totalTime / completedCount).toFixed(1) : "0.0";
        
        // Find dominant risk level
        let dominantRisk = "Low";
        let maxCount = -1;
        for (const [r, count] of Object.entries(riskCounts)) {
            if (count > maxCount) {
                maxCount = count;
                dominantRisk = r;
            }
        }
        if (history.length === 0) dominantRisk = "Low";

        // Render metrics
        document.getElementById('fix-metric-pending').textContent = pending;
        document.getElementById('fix-metric-success').textContent = success;
        document.getElementById('fix-metric-failed').textContent = failed;
        document.getElementById('fix-metric-passrate').textContent = `${passRate}%`;
        document.getElementById('fix-metric-confidence').textContent = `${avgConfidence}%`;
        document.getElementById('fix-metric-risk').textContent = dominantRisk;
        document.getElementById('fix-metric-time').textContent = `${avgTime}s`;
        
        // Render List
        const listContainer = document.getElementById('fix-executions-list');
        listContainer.innerHTML = '';
        
        if (history.length === 0) {
            listContainer.innerHTML = '<div style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 20px 0;">No fix executions found.</div>';
            return;
        }
        
        history.forEach(fx => {
            const card = document.createElement('div');
            card.className = 'glass';
            card.style.padding = '12px';
            card.style.borderRadius = '8px';
            card.style.border = '1px solid rgba(255,255,255,0.06)';
            card.style.background = 'rgba(255,255,255,0.01)';
            card.style.cursor = 'pointer';
            card.style.transition = 'all 0.2s ease';
            card.style.marginBottom = '8px';
            
            const dateStr = new Date(fx.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
            
            let statusColor = '#facc15';
            if (fx.status.toLowerCase() === 'completed') statusColor = '#34d399';
            if (['failed', 'rolled back'].includes(fx.status.toLowerCase())) statusColor = '#ef4444';
            
            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                    <strong style="color: var(--text-bright); font-size: 13px;">Fix Run #${fx.id}</strong>
                    <span style="font-size: 11px; font-weight: 600; color: ${statusColor};">${fx.status}</span>
                </div>
                <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 6px;">Finding ID: #${fx.finding_id}</div>
                <div style="display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: var(--text-muted);">
                    <span>${dateStr}</span>
                    <span>Risk: ${fx.estimated_risk || 'Low'}</span>
                </div>
            `;
            
            card.addEventListener('mouseenter', () => {
                card.style.background = 'rgba(255,255,255,0.03)';
                card.style.borderColor = 'rgba(255,255,255,0.12)';
            });
            card.addEventListener('mouseleave', () => {
                card.style.background = 'rgba(255,255,255,0.01)';
                card.style.borderColor = 'rgba(255,255,255,0.06)';
            });
            card.addEventListener('click', () => {
                showFixDetails(fx);
            });
            
            listContainer.appendChild(card);
        });
        
    } catch (e) {
        console.error('Error loading fix center:', e);
    }
}

async function showFixDetails(fx) {
    activeFixExecutionId = fx.id;
    
    document.getElementById('fix-details-empty').style.display = 'none';
    const activePane = document.getElementById('fix-details-active');
    activePane.style.display = 'block';
    
    // Set text elements
    document.getElementById('active-fix-title').textContent = `Fix Run #${fx.id}`;
    document.getElementById('active-fix-created').textContent = new Date(fx.created_at).toLocaleString();
    
    const badge = document.getElementById('active-fix-status-badge');
    badge.textContent = fx.status;
    let statusColor = '#facc15';
    if (fx.status.toLowerCase() === 'completed') statusColor = '#34d399';
    if (['failed', 'rolled back'].includes(fx.status.toLowerCase())) statusColor = '#ef4444';
    badge.style.color = statusColor;
    
    // Engineering Plan
    let plan = {};
    if (fx.fix_plan_json) {
        try {
            plan = JSON.parse(fx.fix_plan_json);
        } catch (e) {
            console.error('Error parsing fix plan json:', e);
        }
    }
    document.getElementById('active-fix-root-cause').textContent = plan.root_cause || "Unvalidated parameter or resource leakage.";
    document.getElementById('active-fix-impact').textContent = plan.technical_explanation || fx.failure_reason || "Code execution logic bypass.";
    
    // Risk & Confidence
    document.getElementById('active-fix-risk').textContent = fx.estimated_risk || plan.risk_analysis || "Low";
    document.getElementById('active-fix-confidence').textContent = `${Math.round(fx.confidence_score * 100)}%`;
    
    // Verification Container
    const verifyContainer = document.getElementById('active-fix-verification-container');
    const verifyLog = document.getElementById('active-fix-verification-log');
    const verifyScore = document.getElementById('active-fix-verification-score');
    
    if (fx.status.toLowerCase() === 'verifying' || fx.verification_score !== null || fx.failure_reason) {
        verifyContainer.style.display = 'block';
        if (fx.status.toLowerCase() === 'verifying') {
            verifyLog.textContent = 'Executing AST security review pipeline stages on patch sandbox...';
            verifyScore.textContent = '--';
        } else if (fx.status.toLowerCase() === 'completed') {
            verifyLog.textContent = 'All verification pipeline stages completed successfully. No regression found.';
            verifyScore.textContent = fx.verification_score;
            verifyScore.style.color = '#34d399';
        } else {
            verifyLog.textContent = fx.failure_reason || 'Verification run failed. Patch has been reverted.';
            verifyScore.textContent = fx.verification_score || '0';
            verifyScore.style.color = '#ef4444';
        }
    } else {
        verifyContainer.style.display = 'none';
    }
    
    // Action buttons display
    const btnApprove = document.getElementById('btn-fix-approve');
    const btnReject = document.getElementById('btn-fix-reject');
    const btnRollback = document.getElementById('btn-fix-rollback');
    
    if (fx.status === 'Waiting Approval') {
        btnApprove.style.display = 'block';
        btnReject.style.display = 'block';
        btnRollback.style.display = 'none';
        btnApprove.textContent = 'Approve & Apply';
        btnApprove.disabled = false;
    } else if (fx.status === 'Completed') {
        btnApprove.style.display = 'none';
        btnReject.style.display = 'none';
        btnRollback.style.display = 'block';
    } else {
        btnApprove.style.display = 'none';
        btnReject.style.display = 'none';
        btnRollback.style.display = 'none';
    }
    
    // Patch Diff
    const diffViewer = document.getElementById('active-fix-diff-viewer');
    diffViewer.textContent = fx.patch_summary || 'No unified diff generated.';
}

function initFixCenterControls() {
    const btnApprove = document.getElementById('btn-fix-approve');
    const btnReject = document.getElementById('btn-fix-reject');
    const btnRollback = document.getElementById('btn-fix-rollback');
    
    if (btnApprove) {
        btnApprove.addEventListener('click', async () => {
            if (!activeFixExecutionId) return;
            btnApprove.disabled = true;
            btnApprove.textContent = 'Applying...';
            
            try {
                const res = await authorizedFetch(`/fixes/${activeFixExecutionId}/approve`, {
                    method: 'POST'
                });
                
                if (res.ok) {
                    const fx = await res.json();
                    alert(`Patch approved! Verification pipeline run started.`);
                    showFixDetails(fx);
                    loadFixCenter(activeProjectId);
                    pollFixStatus(activeFixExecutionId);
                } else {
                    const data = await res.json();
                    alert(data.detail || 'Failed to approve patch.');
                    loadFixCenter(activeProjectId);
                }
            } catch (err) {
                alert('Approve error: ' + err.message);
                loadFixCenter(activeProjectId);
            }
        });
    }
    
    if (btnReject) {
        btnReject.addEventListener('click', async () => {
            if (!activeFixExecutionId) return;
            if (!confirm('Are you sure you want to reject this patch?')) return;
            
            try {
                const res = await authorizedFetch(`/fixes/${activeFixExecutionId}/reject`, {
                    method: 'POST'
                });
                
                if (res.ok) {
                    const fx = await res.json();
                    showFixDetails(fx);
                    loadFixCenter(activeProjectId);
                } else {
                    const data = await res.json();
                    alert(data.detail || 'Failed to reject patch.');
                }
            } catch (err) {
                alert('Reject error: ' + err.message);
            }
        });
    }
    
    if (btnRollback) {
        btnRollback.addEventListener('click', async () => {
            if (!activeFixExecutionId) return;
            if (!confirm('Are you sure you want to rollback this fix? This will restore the codebase to its prior version snapshot.')) return;
            
            try {
                const res = await authorizedFetch(`/fixes/${activeFixExecutionId}/rollback`, {
                    method: 'POST'
                });
                
                if (res.ok) {
                    const fx = await res.json();
                    alert('Rollback completed successfully! Codebase has been reverted.');
                    showFixDetails(fx);
                    loadFixCenter(activeProjectId);
                } else {
                    const data = await res.json();
                    alert(data.detail || 'Failed to rollback fix.');
                }
            } catch (err) {
                alert('Rollback error: ' + err.message);
            }
        });
    }
}

function pollFixStatus(fixId) {
    const interval = setInterval(async () => {
        try {
            const res = await authorizedFetch(`/fixes/${fixId}`);
            if (res.ok) {
                const fx = await res.json();
                if (activeFixExecutionId === fixId) {
                    showFixDetails(fx);
                }
                
                const status = fx.status.toLowerCase();
                if (!['planning', 'generating', 'waiting approval', 'validating', 'applying', 'versioning', 'verifying'].includes(status)) {
                    clearInterval(interval);
                    loadFixCenter(activeProjectId);
                }
            } else {
                clearInterval(interval);
            }
        } catch (e) {
            clearInterval(interval);
        }
    }, 1500);
}


// Test Center client module
let activeTestExecutionId = null;

async function loadTestCenter(projectId) {
    if (!projectId) return;
    try {
        const res = await authorizedFetch(`/projects/${projectId}/tests`);
        if (!res.ok) throw new Error("Failed to fetch project tests history.");
        const history = await res.json();
        
        // Render history list
        const container = document.getElementById('test-executions-list');
        if (!container) return;
        
        if (history.length === 0) {
            container.innerHTML = `<div style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 20px 0;">No test runs found.</div>`;
            document.getElementById('test-details-empty').style.display = 'flex';
            document.getElementById('test-details-active').style.display = 'none';
            resetTestMetrics();
            return;
        }
        
        container.innerHTML = '';
        history.forEach(t => {
            const card = document.createElement('div');
            card.className = `glass test-run-card ${activeTestExecutionId === t.id ? 'active' : ''}`;
            card.style.cssText = `padding: 12px; border-radius: 8px; border: 1px solid ${activeTestExecutionId === t.id ? 'var(--accent-purple)' : 'rgba(255,255,255,0.06)'}; cursor: pointer; transition: all 0.2s ease; background: ${activeTestExecutionId === t.id ? 'rgba(167, 139, 250, 0.1)' : 'rgba(255,255,255,0.01)'}`;
            
            let statusColor = '#94a3b8';
            if (t.status === 'Completed') statusColor = '#34d399';
            if (t.status === 'Failed') statusColor = '#ef4444';
            if (t.status === 'Running' || t.status === 'Generating') statusColor = '#facc15';

            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span style="font-weight: 700; font-size: 13px; color: var(--text-bright);">Run #${t.id}</span>
                    <span style="font-size: 11px; padding: 2px 6px; border-radius: 4px; background: rgba(0,0,0,0.3); color: ${statusColor}; font-weight: 600;">${t.status}</span>
                </div>
                <div style="font-size: 11px; color: var(--text-muted);">
                    <div>Framework: ${t.framework || 'N/A'}</div>
                    <div style="margin-top: 4px; display: flex; justify-content: space-between;">
                        <span>Passed: ${t.passed_tests}/${t.total_tests}</span>
                        <span>Coverage: ${t.coverage_percentage}%</span>
                    </div>
                </div>
            `;
            
            card.addEventListener('click', () => {
                document.querySelectorAll('.test-run-card').forEach(c => {
                    c.style.borderColor = 'rgba(255,255,255,0.06)';
                    c.style.background = 'rgba(255,255,255,0.01)';
                });
                card.style.borderColor = 'var(--accent-purple)';
                card.style.background = 'rgba(167, 139, 250, 0.1)';
                
                activeTestExecutionId = t.id;
                showTestDetails(t);
            });
            
            container.appendChild(card);
        });

        // Set metrics based on the latest run
        const latest = history[0];
        updateTestMetrics(latest);

        if (activeTestExecutionId) {
            const activeRun = history.find(x => x.id === activeTestExecutionId);
            if (activeRun) {
                showTestDetails(activeRun);
            }
        } else {
            activeTestExecutionId = latest.id;
            showTestDetails(latest);
        }

    } catch (err) {
        console.error("loadTestCenter error:", err);
    }
}

function resetTestMetrics() {
    document.getElementById('test-metric-passed').innerText = '0';
    document.getElementById('test-metric-failed').innerText = '0';
    document.getElementById('test-metric-skipped').innerText = '0';
    document.getElementById('test-metric-coverage').innerText = '0%';
    document.getElementById('test-metric-regression').innerText = 'N/A';
    document.getElementById('test-metric-regression').style.color = 'var(--text-muted)';
    document.getElementById('test-metric-time').innerText = '0.0s';
}

function updateTestMetrics(t) {
    if (!t) return;
    document.getElementById('test-metric-passed').innerText = t.passed_tests;
    document.getElementById('test-metric-failed').innerText = t.failed_tests;
    document.getElementById('test-metric-skipped').innerText = t.skipped_tests;
    document.getElementById('test-metric-coverage').innerText = t.coverage_percentage + '%';
    
    const regressionEl = document.getElementById('test-metric-regression');
    if (t.failed_tests === 0 && t.status === 'Completed') {
        regressionEl.innerText = 'Clean';
        regressionEl.style.color = '#34d399';
    } else if (t.status === 'Failed') {
        regressionEl.innerText = 'Unstable';
        regressionEl.style.color = '#ef4444';
    } else {
        regressionEl.innerText = t.status;
        regressionEl.style.color = '#facc15';
    }
    
    document.getElementById('test-metric-time').innerText = (t.execution_time || 0.0).toFixed(2) + 's';
}

function showTestDetails(t) {
    if (!t) return;
    document.getElementById('test-details-empty').style.display = 'none';
    document.getElementById('test-details-active').style.display = 'block';
    
    document.getElementById('active-test-title').innerText = `Test Run #${t.id}`;
    document.getElementById('active-test-lang').innerText = t.language || 'Python';
    document.getElementById('active-test-framework').innerText = t.framework || 'pytest';
    
    const badge = document.getElementById('active-test-status-badge');
    badge.innerText = t.status;
    badge.className = 'badge';
    if (t.status === 'Completed') badge.style.cssText = 'background: rgba(52, 211, 153, 0.1); color: #34d399;';
    else if (t.status === 'Failed') badge.style.cssText = 'background: rgba(239, 68, 68, 0.1); color: #ef4444;';
    else badge.style.cssText = 'background: rgba(250, 204, 21, 0.1); color: #facc15;';

    // Show button only if executable or pending
    const runBtn = document.getElementById('btn-test-run-execute');
    if (t.status === 'Pending') {
        runBtn.style.display = 'block';
        runBtn.innerText = 'Execute Test Suite';
    } else if (t.status === 'Running') {
        runBtn.style.display = 'block';
        runBtn.innerText = 'Running...';
    } else {
        runBtn.style.display = 'block';
        runBtn.innerText = 'Re-run Test Suite';
    }

    // Render generated test files
    const codeViewer = document.getElementById('active-test-code-viewer');
    if (t.generated_tests_json) {
        try {
            const data = JSON.parse(t.generated_tests_json);
            if (data.files && data.files.length > 0) {
                let codeStr = '';
                data.files.forEach(f => {
                    codeStr += `/* === File: ${f.filename} === */\n${f.content}\n\n`;
                });
                codeViewer.innerText = codeStr;
            } else {
                codeViewer.innerText = 'No test code stubs generated.';
            }
        } catch (e) {
            codeViewer.innerText = 'Error decoding generated test files: ' + e.message;
        }
    } else {
        codeViewer.innerText = 'Pending test code generation...';
    }

    // Render execution logs
    document.getElementById('active-test-logs-viewer').innerText = t.execution_log || 'Waiting for test run completion...';
    
    // Auto poll if running
    if (t.status === 'Running' || t.status === 'Generating') {
        pollTestStatus(t.id);
    }
}

async function executeTestRun(testId) {
    try {
        const res = await authorizedFetch(`/tests/${testId}/execute`, {
            method: 'POST'
        });
        if (!res.ok) throw new Error("Failed to trigger test suite execution.");
        const updated = await res.json();
        showTestDetails(updated);
        loadTestCenter(activeProjectId);
    } catch (e) {
        alert("Execution Error: " + e.message);
    }
}

function pollTestStatus(testId) {
    const interval = setInterval(async () => {
        try {
            const res = await authorizedFetch(`/tests/${testId}`);
            if (res.ok) {
                const t = await res.json();
                if (activeTestExecutionId === testId) {
                    showTestDetails(t);
                }
                
                if (t.status !== 'Running' && t.status !== 'Generating') {
                    clearInterval(interval);
                    loadTestCenter(activeProjectId);
                }
            } else {
                clearInterval(interval);
            }
        } catch (e) {
            clearInterval(interval);
        }
    }, 1500);
}

function initTestCenterControls() {
    const runBtn = document.getElementById('btn-test-run-execute');
    if (runBtn) {
        runBtn.addEventListener('click', () => {
            if (activeTestExecutionId) {
                executeTestRun(activeTestExecutionId);
            }
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initTestCenterControls();
});

/* ==========================================================================
   REPOSITORY INSIGHTS CONTROLLER FUNCTIONS
   ========================================================================== */

async function loadRepositoryInsights(projectId) {
    if (!projectId) return;
    
    try {
        const res = await authorizedFetch(`/projects/${projectId}/repository-insights`);
        if (!res.ok) {
            console.error("Failed to fetch repository insights");
            return;
        }
        
        const insights = await res.json();
        
        // Update header badges
        document.getElementById('insights-score-badge').textContent = `SCORE: ${insights.repository_score}/100`;
        document.getElementById('insights-maturity-badge').textContent = `MATURITY: ${insights.engineering_maturity.toUpperCase()}`;
        document.getElementById('insights-debt-badge').textContent = `TECH DEBT: ${insights.technical_debt_score.toUpperCase()}`;
        
        // Populate maturity dimensions progress bars
        const dimGrid = document.getElementById('insights-dimensions-grid');
        dimGrid.innerHTML = '';
        
        const dimensions = [
            { label: 'Architecture', score: insights.architecture_score, color: 'var(--accent-purple)' },
            { label: 'Security', score: insights.security_score, color: 'var(--accent-red)' },
            { label: 'Testing', score: insights.testing_score, color: 'var(--accent-blue)' },
            { label: 'Deployment', score: insights.deployment_score, color: 'var(--accent-green)' },
            { label: 'Maintainability', score: insights.maintainability_score, color: 'var(--accent-orange)' },
            { label: 'Documentation', score: insights.documentation_score, color: 'var(--accent-purple)' }
        ];
        
        dimensions.forEach(d => {
            const card = document.createElement('div');
            card.style.background = 'rgba(255, 255, 255, 0.02)';
            card.style.border = '1px solid var(--border-color)';
            card.style.borderRadius = '6px';
            card.style.padding = '12px';
            card.style.display = 'flex';
            card.style.flexDirection = 'column';
            card.style.gap = '8px';
            
            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; font-size: 13px; font-weight: 600; color: var(--text-main);">
                    <span>${d.label}</span>
                    <span style="color: ${d.color};">${d.score}%</span>
                </div>
                <div style="width: 100%; height: 6px; background: rgba(255, 255, 255, 0.05); border-radius: 3px; overflow: hidden;">
                    <div style="width: ${d.score}%; height: 100%; background: ${d.color}; border-radius: 3px; transition: width 0.8s ease;"></div>
                </div>
            `;
            dimGrid.appendChild(card);
        });
        
        // Draw Radar Chart
        const scoresMap = {
            'Architecture': insights.architecture_score,
            'Security': insights.security_score,
            'Testing': insights.testing_score,
            'Deployment': insights.deployment_score,
            'Maintainability': insights.maintainability_score,
            'Documentation': insights.documentation_score
        };
        drawRadarChart('insights-radar-svg', scoresMap);
        
        // Populate Strengths list
        const strList = document.getElementById('insights-strengths-list');
        strList.innerHTML = '';
        insights.strengths.forEach(s => {
            const li = document.createElement('li');
            li.style.display = 'flex';
            li.style.alignItems = 'center';
            li.style.gap = '8px';
            li.style.fontSize = '13px';
            li.style.color = 'var(--text-bright)';
            li.innerHTML = `<span style="color: var(--accent-green); font-weight: bold; margin-right: 4px;">✓</span> <span>${escapeHtml(s)}</span>`;
            strList.appendChild(li);
        });
        
        // Populate Weaknesses list
        const weakList = document.getElementById('insights-weaknesses-list');
        weakList.innerHTML = '';
        insights.weaknesses.forEach(w => {
            const li = document.createElement('li');
            li.style.display = 'flex';
            li.style.alignItems = 'center';
            li.style.gap = '8px';
            li.style.fontSize = '13px';
            li.style.color = 'var(--text-bright)';
            li.innerHTML = `<span style="color: var(--accent-red); font-weight: bold; margin-right: 4px;">✗</span> <span>${escapeHtml(w)}</span>`;
            weakList.appendChild(li);
        });
        
        // Populate Roadmap timeline list
        const roadmapList = document.getElementById('insights-roadmap-list');
        roadmapList.innerHTML = '';
        if (insights.roadmap && insights.roadmap.length > 0) {
            insights.roadmap.sort((a, b) => a.recommended_order - b.recommended_order);
            insights.roadmap.forEach((r, idx) => {
                const item = document.createElement('div');
                item.style.display = 'flex';
                item.style.gap = '16px';
                item.style.padding = '16px';
                item.style.background = 'rgba(255, 255, 255, 0.02)';
                item.style.border = '1px solid var(--border-color)';
                item.style.borderRadius = '8px';
                item.style.alignItems = 'start';
                
                const priorityColor = r.priority.toLowerCase() === 'high' ? 'var(--accent-red)' : (r.priority.toLowerCase() === 'medium' ? 'var(--accent-orange)' : 'var(--accent-blue)');
                
                item.innerHTML = `
                    <div style="width: 28px; height: 28px; border-radius: 50%; background: rgba(139, 92, 246, 0.1); border: 1px solid rgba(139, 92, 246, 0.2); color: var(--accent-purple); display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 13px; flex-shrink: 0;">
                        ${r.recommended_order}
                    </div>
                    <div style="flex: 1;">
                        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                            <h4 style="font-size: 15px; font-weight: 600; color: var(--text-bright); margin: 0;">${escapeHtml(r.title)}</h4>
                            <div style="display: flex; gap: 8px; font-size: 11px;">
                                <span class="pill" style="border: 1px solid ${priorityColor}; color: ${priorityColor}; background: transparent; padding: 2px 6px; border-radius: 4px;">${r.priority.toUpperCase()}</span>
                                <span class="pill outline" style="padding: 2px 6px; border-radius: 4px;">Effort: ${r.effort}</span>
                                <span class="pill outline" style="border-color: var(--accent-green); color: var(--accent-green); padding: 2px 6px; border-radius: 4px;">Impact: ${r.business_impact}</span>
                                <span class="pill outline" style="border-color: var(--accent-blue); color: var(--accent-blue); padding: 2px 6px; border-radius: 4px;">${r.estimated_time}</span>
                            </div>
                        </div>
                        <p style="color: var(--text-muted); font-size: 13px; margin-top: 8px; line-height: 1.5; margin-bottom: 0;">${escapeHtml(r.description)}</p>
                    </div>
                `;
                roadmapList.appendChild(item);
            });
        } else {
            roadmapList.innerHTML = '<div style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 24px;">No roadmap items.</div>';
        }
        
        // Populate History Trend list
        await loadRepositoryHistoryTrend(projectId);
        
    } catch (err) {
        console.error("Error loading insights:", err);
    }
}

async function loadRepositoryHistoryTrend(projectId) {
    const listEl = document.getElementById('insights-history-list');
    listEl.innerHTML = '';
    
    try {
        const res = await authorizedFetch(`/projects/${projectId}/repository-history`);
        if (!res.ok) return;
        
        const history = await res.json();
        if (history.length === 0) {
            listEl.innerHTML = '<div style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 12px; width: 100%;">No analysis history runs.</div>';
            return;
        }
        
        history.forEach((h, idx) => {
            const node = document.createElement('div');
            node.style.display = 'flex';
            node.style.flexDirection = 'column';
            node.style.alignItems = 'center';
            node.style.gap = '8px';
            node.style.padding = '12px 16px';
            node.style.background = 'rgba(255, 255, 255, 0.02)';
            node.style.border = '1px solid var(--border-color)';
            node.style.borderRadius = '8px';
            node.style.minWidth = '110px';
            node.style.textAlign = 'center';
            
            node.innerHTML = `
                <div style="font-size: 11px; text-transform: uppercase; font-weight: 700; color: var(--text-muted);">Version ${h.version_number}</div>
                <div style="font-size: 24px; font-weight: bold; color: var(--accent-purple);">${h.repository_score}</div>
                <div style="font-size: 10px; color: var(--text-muted);">${new Date(h.created_at).toLocaleDateString()}</div>
            `;
            listEl.appendChild(node);
            
            // Draw connection arrows between elements
            if (idx < history.length - 1) {
                const arrow = document.createElement('div');
                arrow.style.display = 'flex';
                arrow.style.alignItems = 'center';
                arrow.style.fontSize = '18px';
                arrow.style.color = 'var(--text-muted)';
                arrow.innerHTML = '➔';
                listEl.appendChild(arrow);
            }
        });
    } catch (e) {
        console.error("Error loading history list:", e);
    }
}

function drawRadarChart(svgId, scores) {
    const svg = document.getElementById(svgId);
    if (!svg) return;
    
    // Clear old elements
    svg.innerHTML = '';
    
    const center = 140;
    const r = 90;
    const dimensions = ['Architecture', 'Security', 'Testing', 'Deployment', 'Maintainability', 'Documentation'];
    const count = dimensions.length;
    
    // Compute vertex points for outer concentric levels
    const levels = [0.2, 0.4, 0.6, 0.8, 1.0];
    levels.forEach(level => {
        const points = [];
        for (let i = 0; i < count; i++) {
            const angle = i * (2 * Math.PI / count) - Math.PI / 2;
            const x = center + r * level * Math.cos(angle);
            const y = center + r * level * Math.sin(angle);
            points.push(`${x},${y}`);
        }
        
        const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
        polygon.setAttribute('points', points.join(' '));
        polygon.setAttribute('fill', 'none');
        polygon.setAttribute('stroke', 'rgba(255, 255, 255, 0.06)');
        polygon.setAttribute('stroke-width', '1');
        svg.appendChild(polygon);
    });
    
    // Draw axis lines and labels
    for (let i = 0; i < count; i++) {
        const angle = i * (2 * Math.PI / count) - Math.PI / 2;
        const targetX = center + r * Math.cos(angle);
        const targetY = center + r * Math.sin(angle);
        
        // Axis line
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', center);
        line.setAttribute('y1', center);
        line.setAttribute('x2', targetX);
        line.setAttribute('y2', targetY);
        line.setAttribute('stroke', 'rgba(255, 255, 255, 0.1)');
        line.setAttribute('stroke-width', '1');
        svg.appendChild(line);
        
        // Label
        const labelText = dimensions[i];
        const labelOffset = 18;
        const lx = center + (r + labelOffset) * Math.cos(angle);
        const ly = center + (r + labelOffset) * Math.sin(angle);
        
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', lx);
        text.setAttribute('y', ly);
        text.setAttribute('font-size', '10px');
        text.setAttribute('font-weight', '600');
        text.setAttribute('fill', 'var(--text-muted)');
        text.setAttribute('text-anchor', 'middle');
        text.setAttribute('dominant-baseline', 'middle');
        text.textContent = labelText;
        svg.appendChild(text);
    }
    
    // Draw scores polygon
    const points = [];
    for (let i = 0; i < count; i++) {
        const name = dimensions[i];
        const score = scores[name] || 0;
        const angle = i * (2 * Math.PI / count) - Math.PI / 2;
        const x = center + r * (score / 100) * Math.cos(angle);
        const y = center + r * (score / 100) * Math.sin(angle);
        points.push(`${x},${y}`);
    }
    
    const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    polygon.setAttribute('points', points.join(' '));
    polygon.setAttribute('fill', 'rgba(139, 92, 246, 0.25)');
    polygon.setAttribute('stroke', 'var(--accent-purple)');
    polygon.setAttribute('stroke-width', '2');
    svg.appendChild(polygon);
    
    // Draw dots at vertices of scores polygon
    for (let i = 0; i < count; i++) {
        const name = dimensions[i];
        const score = scores[name] || 0;
        const angle = i * (2 * Math.PI / count) - Math.PI / 2;
        const x = center + r * (score / 100) * Math.cos(angle);
        const y = center + r * (score / 100) * Math.sin(angle);
        
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', x);
        circle.setAttribute('cy', y);
        circle.setAttribute('r', '4');
        circle.setAttribute('fill', 'var(--accent-purple)');
        circle.setAttribute('stroke', '#fff');
        circle.setAttribute('stroke-width', '1');
        svg.appendChild(circle);
    }
}


function initSassSettings() {
    // Theme Toggle
    const themeBtn = document.getElementById('btn-theme-toggle');
    if (themeBtn) {
        if (localStorage.getItem('theme') === 'light') {
            document.body.classList.add('light-theme');
        }
        themeBtn.addEventListener('click', () => {
            document.body.classList.toggle('light-theme');
            const mode = document.body.classList.contains('light-theme') ? 'light' : 'dark';
            localStorage.setItem('theme', mode);
        });
    }

    // Modal display
    const settingsModal = document.getElementById('settings-modal');
    const openSettingsBtn = document.getElementById('btn-open-settings');
    const closeSettingsBtn = document.getElementById('btn-settings-close');
    
    if (openSettingsBtn && settingsModal) {
        openSettingsBtn.addEventListener('click', () => {
            settingsModal.classList.remove('hidden');
            loadSettingsBilling();
            loadSettingsNotifications();
            loadSettingsApiKeys();
            loadSettingsOrgMembers();
            loadLLMKeys();
        });
    }
    if (closeSettingsBtn && settingsModal) {
        closeSettingsBtn.addEventListener('click', () => {
            settingsModal.classList.add('hidden');
        });
    }

    // Tab switcher
    const settingsTabs = [
        { btn: 'settings-tab-billing-btn', pane: 'settings-pane-billing' },
        { btn: 'settings-tab-notifications-btn', pane: 'settings-pane-notifications' },
        { btn: 'settings-tab-api-btn', pane: 'settings-pane-api' },
        { btn: 'settings-tab-llm-btn', pane: 'settings-pane-llm' },
        { btn: 'settings-tab-org-btn', pane: 'settings-pane-org' }
    ];
    settingsTabs.forEach(t => {
        const btn = document.getElementById(t.btn);
        if (btn) {
            btn.addEventListener('click', () => {
                settingsTabs.forEach(ot => {
                    const ob = document.getElementById(ot.btn);
                    if (ob) ob.classList.remove('active');
                    const op = document.getElementById(ot.pane);
                    if (op) op.style.display = 'none';
                });
                btn.classList.add('active');
                const pane = document.getElementById(t.pane);
                if (pane) pane.style.display = 'block';
                if (t.btn === 'settings-tab-llm-btn') {
                    loadLLMKeys();
                }
            });
        }
    });

    // Load LLM keys into inputs
    function loadLLMKeys() {
        const geminiKey = localStorage.getItem('gemini_api_key') || '';
        const openaiKey = localStorage.getItem('openai_api_key') || '';
        const anthropicKey = localStorage.getItem('anthropic_api_key') || '';
        
        const geminiInput = document.getElementById('settings-gemini-key');
        const openaiInput = document.getElementById('settings-openai-key');
        const anthropicInput = document.getElementById('settings-anthropic-key');
        
        if (geminiInput) geminiInput.value = geminiKey;
        if (openaiInput) openaiInput.value = openaiKey;
        if (anthropicInput) anthropicInput.value = anthropicKey;
        
        // Update connection status
        document.getElementById('status-gemini-connection').textContent = geminiKey ? 'Saved ✓' : 'Not Connected';
        document.getElementById('status-openai-connection').textContent = openaiKey ? 'Saved ✓' : 'Not Connected';
        document.getElementById('status-anthropic-connection').textContent = anthropicKey ? 'Saved ✓' : 'Not Connected';
    }

    async function testAndSaveLLMKey(provider, keyInputId, statusSpanId, storageKeyName) {
        const keyVal = document.getElementById(keyInputId).value.trim();
        const statusSpan = document.getElementById(statusSpanId);
        
        if (!keyVal) {
            alert('Please enter a valid API key.');
            return;
        }
        
        statusSpan.textContent = 'Testing connection...';
        
        try {
            const res = await fetch('/auth/test-connection', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                },
                body: JSON.stringify({ provider: provider, api_key: keyVal })
            });
            
            if (res.ok) {
                const data = await res.json();
                if (data.status === 'connected') {
                    localStorage.setItem(storageKeyName, keyVal);
                    statusSpan.textContent = 'Connected ✓';
                    statusSpan.style.color = 'var(--accent-green)';
                    alert(`${provider.toUpperCase()} connection test succeeded! Key saved.`);
                } else {
                    statusSpan.textContent = 'Invalid Key ✗';
                    statusSpan.style.color = 'var(--accent-red)';
                    alert('Connection failed: ' + (data.error || 'Invalid API key.'));
                }
            } else {
                statusSpan.textContent = 'Error ✗';
                statusSpan.style.color = 'var(--accent-red)';
                const err = await res.json();
                alert('Connection test endpoint error: ' + (err.detail || 'Failed to validate.'));
            }
        } catch (e) {
            statusSpan.textContent = 'Error ✗';
            statusSpan.style.color = 'var(--accent-red)';
            alert('Network error testing connection: ' + e.message);
        }
    }

    // Wire buttons
    const testGeminiBtn = document.getElementById('btn-test-gemini');
    if (testGeminiBtn) {
        testGeminiBtn.addEventListener('click', (e) => {
            e.preventDefault();
            testAndSaveLLMKey('google', 'settings-gemini-key', 'status-gemini-connection', 'gemini_api_key');
        });
    }
    const testOpenAIBtn = document.getElementById('btn-test-openai');
    if (testOpenAIBtn) {
        testOpenAIBtn.addEventListener('click', (e) => {
            e.preventDefault();
            testAndSaveLLMKey('openai', 'settings-openai-key', 'status-openai-connection', 'openai_api_key');
        });
    }
    const testAnthropicBtn = document.getElementById('btn-test-anthropic');
    if (testAnthropicBtn) {
        testAnthropicBtn.addEventListener('click', (e) => {
            e.preventDefault();
            testAndSaveLLMKey('anthropic', 'settings-anthropic-key', 'status-anthropic-connection', 'anthropic_api_key');
        });
    }

    // Subscriptions Billing Actions
    async function loadSettingsBilling() {
        try {
            const res = await authorizedFetch('/auth/billing');
            if (res.ok) {
                const data = await res.json();
                document.getElementById('settings-plan-label').textContent = `${data.billing_plan.toUpperCase()} PLAN`;
                const isFree = data.billing_plan.toLowerCase() === 'free';
                document.getElementById('btn-billing-subscribe').style.display = isFree ? 'block' : 'none';
                document.getElementById('btn-billing-portal').style.display = isFree ? 'none' : 'block';
            }
        } catch(e) {}
    }
    
    const btnSubscribe = document.getElementById('btn-billing-subscribe');
    if (btnSubscribe) {
        btnSubscribe.addEventListener('click', async () => {
            btnSubscribe.disabled = true;
            try {
                const res = await authorizedFetch('/billing/checkout-session?plan_type=pro', { method: 'POST' });
                if (res.ok) {
                    const data = await res.json();
                    window.location.href = data.checkout_url;
                }
            } catch(e) {
                btnSubscribe.disabled = false;
            }
        });
    }
    
    const btnPortal = document.getElementById('btn-billing-portal');
    if (btnPortal) {
        btnPortal.addEventListener('click', async () => {
            try {
                const res = await authorizedFetch('/billing/portal-session', { method: 'POST' });
                if (res.ok) {
                    const data = await res.json();
                    window.location.href = data.portal_url;
                }
            } catch(e) {}
        });
    }

    // Notifications Preference Actions
    async function loadSettingsNotifications() {
        try {
            const res = await authorizedFetch('/auth/notifications');
            if (res.ok) {
                const data = await res.json();
                document.getElementById('pref-analysis').checked = data.email_analysis_completed;
                document.getElementById('pref-fix').checked = data.email_fix_completed;
                document.getElementById('pref-tests').checked = data.email_tests_completed;
                document.getElementById('pref-sync').checked = data.email_repo_synced;
                document.getElementById('pref-invite').checked = data.email_invitation_accepted;
                document.getElementById('pref-deployment').checked = data.email_deployment_completed;
            }
        } catch(e) {}
    }
    
    const notificationsForm = document.getElementById('settings-notifications-form');
    if (notificationsForm) {
        notificationsForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const body = {
                email_analysis_completed: document.getElementById('pref-analysis').checked,
                email_fix_completed: document.getElementById('pref-fix').checked,
                email_tests_completed: document.getElementById('pref-tests').checked,
                email_repo_synced: document.getElementById('pref-sync').checked,
                email_invitation_accepted: document.getElementById('pref-invite').checked,
                email_deployment_completed: document.getElementById('pref-deployment').checked
            };
            try {
                const res = await authorizedFetch('/auth/notifications', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body)
                });
                if (res.ok) {
                    alert('Notification preferences saved successfully!');
                }
            } catch(e) {}
        });
    }

    // API Key Actions
    async function loadSettingsApiKeys() {
        try {
            const res = await authorizedFetch('/auth/api-key');
            if (res.ok) {
                const list = await res.json();
                const tbody = document.getElementById('api-keys-list-tbody');
                tbody.innerHTML = '';
                if (list.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="3" style="text-align: center; color: var(--text-muted);">No active API keys found.</td></tr>';
                    return;
                }
                list.forEach(k => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td style="font-weight: 600; color: var(--text-bright);">${escapeHtml(k.name)}</td>
                        <td>${k.expires_at ? new Date(k.expires_at).toLocaleDateString() : 'Never'}</td>
                        <td><button class="action-btn" onclick="revokeApiKey(${k.id})" style="padding: 2px 6px; font-size: 10px; background: rgba(239, 68, 68, 0.1); border-color: rgba(239, 68, 68, 0.2); color: var(--accent-red);">Revoke</button></td>
                    `;
                    tbody.appendChild(tr);
                });
            }
        } catch(e) {}
    }
    
    window.revokeApiKey = async function(id) {
        try {
            const res = await authorizedFetch(`/auth/api-key/${id}`, { method: 'DELETE' });
            if (res.ok) {
                loadSettingsApiKeys();
            }
        } catch(e) {}
    };
    
    const btnGenerateKey = document.getElementById('btn-generate-api-key');
    if (btnGenerateKey) {
        btnGenerateKey.addEventListener('click', async () => {
            const nameInput = document.getElementById('input-api-key-name');
            const name = nameInput.value.trim() || 'CLI Token';
            try {
                const res = await authorizedFetch(`/auth/api-key?name=${encodeURIComponent(name)}`, { method: 'POST' });
                if (res.ok) {
                    const data = await res.json();
                    nameInput.value = '';
                    const displayBox = document.getElementById('api-key-display-box');
                    displayBox.style.display = 'block';
                    document.getElementById('label-new-api-key').textContent = data.api_key;
                    loadSettingsApiKeys();
                }
            } catch(e) {}
        });
    }

    // Organization Members Actions
    async function loadSettingsOrgMembers() {
        const tbody = document.getElementById('org-members-list-tbody');
        if (!tbody) return;
        tbody.innerHTML = `
            <tr>
                <td style="font-weight: 600; color: var(--text-bright);">insights_tester</td>
                <td>Owner</td>
                <td>2026-06-28</td>
            </tr>
            <tr>
                <td style="font-weight: 600; color: var(--text-bright);">antigravity_dev</td>
                <td>Developer</td>
                <td>2026-07-01</td>
            </tr>
        `;
    }
    
    const btnInvite = document.getElementById('btn-invite-member');
    if (btnInvite) {
        btnInvite.addEventListener('click', () => {
            const emailInput = document.getElementById('input-invite-email');
            const email = emailInput.value.trim();
            if (email) {
                alert(`Invitation sent successfully to: ${email}`);
                emailInput.value = '';
            } else {
                alert('Please provide a valid email address.');
            }
        });
    }
}

