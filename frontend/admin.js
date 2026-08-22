/* ============================================================================
   ĐÔNG ĐÔ CS STUDIO - SCRIPT ENGINE
   Authentication, Live CS Inbox, Realtime Learning & VectorDB Management
   ============================================================================ */

let currentTab = 'inbox';
let activeSessionId = null;
let currentFilter = '';
let autoRefreshTimer = null;
let currentAgent = {
    username: '',
    full_name: 'Chuyên viên CSKH',
    role: 'user',
};

// ============================================================
// Auth Token & Headers Helper
// ============================================================
function getAuthToken() {
    return localStorage.getItem('dongdo_admin_token') || '';
}

function getAuthHeaders() {
    const token = getAuthToken();
    return {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
    };
}

// ============================================================
// Initialization & Auth Flow
// ============================================================
document.addEventListener('DOMContentLoaded', async () => {
    setupTabs();
    setupDropzone();
    setupLoginForm();
    setupChatInputs();

    const isAuthenticated = await checkAuth();
    if (isAuthenticated) {
        initStudio();
    }
});

async function checkAuth() {
    const token = getAuthToken();
    if (!token) {
        showLoginModal();
        return false;
    }

    try {
        const res = await fetch('/auth/me', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) {
            showLoginModal();
            return false;
        }
        const data = await res.json();
        currentAgent = data;
        updateAgentProfileUI();
        hideLoginModal();
        return true;
    } catch (e) {
        showLoginModal();
        return false;
    }
}

function showLoginModal() {
    const overlay = document.getElementById('adminLoginOverlay');
    if (overlay) overlay.classList.remove('hidden');
}

function hideLoginModal() {
    const overlay = document.getElementById('adminLoginOverlay');
    if (overlay) overlay.classList.add('hidden');
}

function updateAgentProfileUI() {
    const nameEl = document.getElementById('current-agent-name');
    if (nameEl) {
        nameEl.innerText = currentAgent.full_name || currentAgent.username || 'Chuyên viên CSKH';
    }
}

function setupLoginForm() {
    const form = document.getElementById('adminLoginForm');
    const errBox = document.getElementById('adminLoginError');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        errBox.classList.remove('visible');
        errBox.innerText = '';

        const username = document.getElementById('adminUsername').value.trim();
        const password = document.getElementById('adminPassword').value;

        try {
            const res = await fetch('/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            const data = await res.json();
            if (!res.ok) {
                errBox.innerText = data.detail || 'Tên đăng nhập hoặc mật khẩu không chính xác';
                errBox.classList.add('visible');
                return;
            }

            localStorage.setItem('dongdo_admin_token', data.token);
            currentAgent = data;
            updateAgentProfileUI();
            hideLoginModal();
            initStudio();
        } catch (err) {
            errBox.innerText = 'Lỗi kết nối máy chủ: ' + err.message;
            errBox.classList.add('visible');
        }
    });
}

async function handleLogout() {
    if (confirm('Bạn có chắc chắn muốn đăng xuất khỏi CS Studio?')) {
        const token = getAuthToken();
        try {
            await fetch('/auth/logout', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
        } catch (e) {}

        localStorage.removeItem('dongdo_admin_token');
        if (autoRefreshTimer) clearInterval(autoRefreshTimer);
        showLoginModal();
    }
}

function initStudio() {
    refreshCurrentTab();

    if (autoRefreshTimer) clearInterval(autoRefreshTimer);
    autoRefreshTimer = setInterval(() => {
        if (currentTab === 'inbox') {
            loadCasesList();
            if (activeSessionId) {
                loadActiveCaseMessages(activeSessionId);
            }
        } else if (currentTab === 'learning') {
            loadPendingLearning();
        }
    }, 4000);
}

// ============================================================
// Tab Management
// ============================================================
function setupTabs() {
    document.querySelectorAll('.nav-item').forEach((btn) => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.nav-item').forEach((b) => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach((t) => t.classList.remove('active'));

            btn.classList.add('active');
            currentTab = btn.getAttribute('data-tab');
            document.getElementById(`tab-${currentTab}`).classList.add('active');

            updateHeaderTitles();
            refreshCurrentTab();
        });
    });
}

function updateHeaderTitles() {
    const titleMap = {
        inbox: { title: 'Live CS Inbox - Hỗ Trợ Trực Tiếp', sub: 'Tiếp nhận & chat xử lý các case khách hàng cần hỗ trợ' },
        learning: { title: '🧠 Quản Lý Cơ Chế Tự Học Của AI', sub: 'Cấu hình chế độ tự động học và phê duyệt các cặp Q&A' },
        knowledge: { title: '📚 Quản Lý Kho Tri Thức Vector DB', sub: 'Tải lên tài liệu .docx và xem thống kê ChromaDB' },
        analytics: { title: '📊 Báo Cáo & Thống Kê Hiệu Suất CS', sub: 'Tổng quan tỷ lệ tự động hóa và tăng trưởng tri thức' },
        config: { title: '⚙️ Cấu Hình Hệ Thống AI Engine', sub: 'Tùy chỉnh System Prompt và tham số mô hình Claude' },
    };

    const info = titleMap[currentTab] || titleMap.inbox;
    document.getElementById('page-title').innerText = info.title;
    document.getElementById('page-subtitle').innerText = info.sub;
}

function refreshCurrentTab() {
    if (currentTab === 'inbox') {
        loadCasesList();
        if (activeSessionId) loadActiveCaseMessages(activeSessionId);
    } else if (currentTab === 'learning') {
        loadLearningSettings();
        loadPendingLearning();
    } else if (currentTab === 'knowledge') {
        loadKnowledgeSummary();
    } else if (currentTab === 'analytics') {
        loadAnalytics();
    } else if (currentTab === 'config') {
        loadSystemConfig();
    }
}

// ============================================================
// TAB 1: Live CS Inbox
// ============================================================
async function loadCasesList() {
    try {
        const url = currentFilter ? `/api/admin/cases?status=${currentFilter}` : '/api/admin/cases';
        const res = await fetch(url, { headers: getAuthHeaders() });
        if (!res.ok) return;

        const data = await res.json();
        const cases = data.cases || [];

        // Update badge count
        const pendingCount = cases.filter((c) => c.status === 'NEEDS_HUMAN_CS').length;
        document.getElementById('badge-inbox-count').innerText = pendingCount;

        const container = document.getElementById('cases-list-container');
        if (cases.length === 0) {
            container.innerHTML = '<div class="empty-state">Không có case nào trong danh sách.</div>';
            return;
        }

        container.innerHTML = cases.map((c) => `
            <div class="case-card ${c.session_id === activeSessionId ? 'active' : ''}" onclick="selectCase('${c.session_id}')">
                <div class="top">
                    <span class="user">👤 ${escapeHtml(c.user_id || c.customer_name || 'Khách hàng')}</span>
                    <span class="time">${formatTime(c.updated_at)}</span>
                </div>
                <div class="query">${escapeHtml(c.last_user_query || 'Chưa có tin nhắn')}</div>
                <div style="margin-top: 0.5rem; display: flex; justify-content: space-between; align-items: center;">
                    <span class="status-badge ${c.status}">${getStatusLabel(c.status)}</span>
                    <span style="font-size: 0.72rem; color: var(--text-tertiary);">${c.assigned_cs ? 'CS: ' + escapeHtml(c.assigned_cs) : ''}</span>
                </div>
            </div>
        `).join('');
    } catch (err) {
        console.error('Error loading cases:', err);
    }
}

function filterCases(status) {
    currentFilter = status;
    document.querySelectorAll('.filter-group .btn-filter').forEach((btn) => btn.classList.remove('active'));
    event.target.classList.add('active');
    loadCasesList();
}

async function selectCase(sessionId) {
    activeSessionId = sessionId;
    document.getElementById('empty-chat-state').classList.add('hidden');
    document.getElementById('chat-detail-container').classList.remove('hidden');

    loadCasesList();
    loadActiveCaseMessages(sessionId);
}

let currentActiveCaseMessages = [];

async function loadActiveCaseMessages(sessionId) {
    try {
        const res = await fetch(`/history/${sessionId}`);
        if (!res.ok) return;
        const data = await res.json();

        currentActiveCaseMessages = data.messages || [];

        document.getElementById('detail-session-id').innerText = `Session: ${sessionId.substring(0, 18)}...`;
        document.getElementById('detail-status-tag').className = `status-badge ${data.status}`;
        document.getElementById('detail-status-tag').innerText = getStatusLabel(data.status);
        document.getElementById('detail-cs-tag').innerText = data.assigned_cs ? `CS: ${data.assigned_cs}` : 'Chưa phân công';

        const msgContainer = document.getElementById('detail-messages-container');
        const messages = data.messages || [];

        msgContainer.innerHTML = messages.map((m) => `
            <div class="msg-bubble ${m.role}">
                <div><strong>${getRoleLabel(m.role)}:</strong> ${escapeHtml(m.content)}</div>
                <span class="msg-meta">${formatTime(m.timestamp)}</span>
            </div>
        `).join('');

        msgContainer.scrollTop = msgContainer.scrollHeight;
    } catch (err) {
        console.error('Error loading active case messages:', err);
    }
}

async function takeActiveCase() {
    if (!activeSessionId) return;
    const agentName = currentAgent.full_name || currentAgent.username || 'Chuyên viên CSKH';

    const formData = new FormData();
    formData.append('agent_name', agentName);

    try {
        const token = getAuthToken();
        const res = await fetch(`/api/admin/cases/${activeSessionId}/take`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData,
        });

        if (res.ok) {
            loadCasesList();
            loadActiveCaseMessages(activeSessionId);
        }
    } catch (err) {
        alert('Lỗi tiếp nhận case: ' + err);
    }
}

function setupChatInputs() {
    const input = document.getElementById('cs-reply-input');
    if (!input) return;

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendHumanReply();
        }
    });
}

async function sendHumanReply() {
    if (!activeSessionId) return;
    const input = document.getElementById('cs-reply-input');
    const msg = input.value.trim();
    if (!msg) return;

    const agentName = currentAgent.full_name || currentAgent.username || 'Chuyên viên CSKH';

    try {
        const res = await fetch(`/api/admin/cases/${activeSessionId}/reply`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ agent_name: agentName, message: msg }),
        });

        if (res.ok) {
            input.value = '';
            loadActiveCaseMessages(activeSessionId);
        }
    } catch (err) {
        alert('Lỗi gửi tin nhắn CSKH: ' + err);
    }
}

// Resolve Modal
function openResolveModal() {
    if (!activeSessionId) return;
    document.getElementById('resolve-modal').classList.remove('hidden');

    // Reset checkbox to checked
    const enableLearnChk = document.getElementById('modal-enable-learn');
    if (enableLearnChk) {
        enableLearnChk.checked = true;
        toggleModalLearnFields(true);
    }

    let lastUserQ = '';
    let lastCSA = '';

    // 1. Trích xuất từ data mảng messages hiện tại
    if (currentActiveCaseMessages && currentActiveCaseMessages.length > 0) {
        const userMsgs = currentActiveCaseMessages.filter((m) => m.role === 'user');
        const csMsgs = currentActiveCaseMessages.filter((m) => m.role === 'human_cs');

        if (userMsgs.length > 0) {
            lastUserQ = userMsgs[userMsgs.length - 1].content.trim();
        }
        if (csMsgs.length > 0) {
            lastCSA = csMsgs.map((m) => m.content.trim()).filter(Boolean).join('\n');
        }
    }

    // 2. Dự phòng: Nếu mảng rỗng thì bóc tách trực tiếp từ giao diện DOM (đã lọc sạch timestamp và icon)
    if (!lastUserQ) {
        const msgContainer = document.getElementById('detail-messages-container');
        const userBubbles = msgContainer.querySelectorAll('.msg-bubble.user');
        if (userBubbles.length > 0) {
            const clone = userBubbles[userBubbles.length - 1].cloneNode(true);
            const meta = clone.querySelector('.msg-meta');
            if (meta) meta.remove();
            lastUserQ = clone.innerText.replace(/Khách hàng:/g, '').replace(/👤/g, '').trim();
        }
    }

    if (!lastCSA) {
        const msgContainer = document.getElementById('detail-messages-container');
        const csBubbles = msgContainer.querySelectorAll('.msg-bubble.human_cs');
        if (csBubbles.length > 0) {
            const clone = csBubbles[csBubbles.length - 1].cloneNode(true);
            const meta = clone.querySelector('.msg-meta');
            if (meta) meta.remove();
            lastCSA = clone.innerText.replace(/Chuyên viên CSKH:/g, '').replace(/CSKH:/g, '').replace(/👨‍💼/g, '').trim();
        }
    }

    document.getElementById('modal-extract-q').value = lastUserQ;
    document.getElementById('modal-extract-a').value = lastCSA;
}

function toggleModalLearnFields(isChecked) {
    const fields = document.getElementById('modal-learn-fields');
    const hint = document.getElementById('modal-auto-hint');
    const submitBtn = document.getElementById('btn-submit-resolve');

    if (isChecked) {
        if (fields) fields.style.display = 'block';
        if (hint) hint.style.display = 'block';
        if (submitBtn) submitBtn.innerText = 'Hoàn Tất Đóng Case & Nạp Tri Thức 🚀';
    } else {
        if (fields) fields.style.display = 'none';
        if (hint) hint.style.display = 'none';
        if (submitBtn) submitBtn.innerText = 'Đóng Case (Không nạp tri thức)';
    }
}

function closeResolveModal() {
    document.getElementById('resolve-modal').classList.add('hidden');
}

async function submitResolveCase() {
    if (!activeSessionId) return;
    const note = document.getElementById('modal-resolve-note').value.trim();
    const enableLearn = document.getElementById('modal-enable-learn').checked;

    let q = '';
    let a = '';
    if (enableLearn) {
        q = document.getElementById('modal-extract-q').value.trim();
        a = document.getElementById('modal-extract-a').value.trim();
    }
    const agentName = currentAgent.full_name || currentAgent.username || 'Chuyên viên CSKH';

    try {
        const res = await fetch(`/api/admin/cases/${activeSessionId}/resolve`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                agent_name: agentName,
                resolution_note: note,
                extract_question: q,
                extract_answer: a,
            }),
        });

        const data = await res.json();
        if (res.ok) {
            closeResolveModal();
            loadCasesList();
            loadActiveCaseMessages(activeSessionId);
            alert(data.message || 'Đã đóng case thành công!');
        }
    } catch (err) {
        alert('Lỗi giải quyết case: ' + err);
    }
}

// ============================================================
// TAB 2: Continuous Learning Queue & Auto-Learn Toggle
// ============================================================
async function loadLearningSettings() {
    try {
        const res = await fetch('/api/admin/learning/settings', { headers: getAuthHeaders() });
        if (!res.ok) return;
        const data = await res.json();

        const chk = document.getElementById('chk-auto-learning');
        const hint = document.getElementById('toggle-hint-text');

        chk.checked = !!data.auto_learning_enabled;
        if (chk.checked) {
            hint.innerHTML = '🟢 <strong>Đang BẬT tự động:</strong> Khi CSKH đóng case, câu trả lời sẽ được tạo Vector và nạp thẳng vào ChromaDB luôn.';
        } else {
            hint.innerHTML = '🟡 <strong>Đang TẮT tự động (Chế độ duyệt thủ công):</strong> Khi CSKH đóng case, Q&A sẽ đưa vào danh sách bên dưới để Admin/CSKH bấm Duyệt mới nạp.';
        }
    } catch (e) {
        console.error('Error loading learning settings:', e);
    }
}

async function handleToggleAutoLearn(isChecked) {
    const hint = document.getElementById('toggle-hint-text');
    if (isChecked) {
        hint.innerHTML = '🟢 <strong>Đang BẬT tự động:</strong> Khi CSKH đóng case, câu trả lời sẽ được tạo Vector và nạp thẳng vào ChromaDB luôn.';
    } else {
        hint.innerHTML = '🟡 <strong>Đang TẮT tự động (Chế độ duyệt thủ công):</strong> Khi CSKH đóng case, Q&A sẽ đưa vào danh sách bên dưới để Admin/CSKH bấm Duyệt mới nạp.';
    }

    try {
        const res = await fetch('/api/admin/learning/settings', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ auto_learning_enabled: isChecked }),
        });
        const data = await res.json();
        if (res.ok) {
            console.log('Saved learning settings:', data);
        }
    } catch (e) {
        alert('Lỗi lưu cài đặt: ' + e.message);
    }
}

async function loadPendingLearning() {
    try {
        const res = await fetch('/api/admin/learning/pending', { headers: getAuthHeaders() });
        if (!res.ok) return;

        const data = await res.json();
        const items = data.pending_items || [];

        document.getElementById('badge-learning-count').innerText = items.length;
        document.getElementById('stat-pending-num').innerText = items.length;

        const container = document.getElementById('learning-list-container');
        if (items.length === 0) {
            container.innerHTML = '<div class="card empty-state">📭 Hiện tại không có mẩu Q&A nào chờ phê duyệt. Khi chuyên viên CSKH đóng case ở chế độ duyệt thủ công, Q&A sẽ hiển thị tại đây!</div>';
            return;
        }

        container.innerHTML = items.map((item) => `
            <div class="learning-item-card" id="learning-item-${item.id}">
                <div class="qa-box">
                    <div class="qa-field">
                        <label>❓ Câu hỏi của Khách hàng:</label>
                        <input type="text" id="learn-q-${item.id}" value="${escapeHtml(item.question)}" />
                    </div>
                    <div class="qa-field">
                        <label>💡 Câu trả lời chuẩn của CSKH:</label>
                        <textarea id="learn-a-${item.id}" rows="3">${escapeHtml(item.answer)}</textarea>
                    </div>
                </div>
                <div class="learning-actions">
                    <button class="btn-reject" onclick="rejectLearningItem(${item.id})">🗑️ Bỏ qua</button>
                    <button class="btn-approve" onclick="approveLearningItem(${item.id})">✅ Phê Duyệt &amp; Nạp Cho AI Học</button>
                </div>
            </div>
        `).join('');
    } catch (err) {
        console.error('Error loading pending learning:', err);
    }
}

async function approveLearningItem(itemId) {
    try {
        const res = await fetch(`/api/admin/learning/approve/${itemId}`, {
            method: 'POST',
            headers: getAuthHeaders(),
        });
        const data = await res.json();
        if (res.ok) {
            alert(data.message || 'Đã phê duyệt và nạp tri thức thành công!');
            loadPendingLearning();
        }
    } catch (err) {
        alert('Lỗi phê duyệt tri thức: ' + err);
    }
}

async function rejectLearningItem(itemId) {
    try {
        const res = await fetch(`/api/admin/learning/reject/${itemId}`, {
            method: 'POST',
            headers: getAuthHeaders(),
        });
        if (res.ok) {
            loadPendingLearning();
        }
    } catch (err) {
        alert('Lỗi từ chối: ' + err);
    }
}

// ============================================================
// TAB 3: Knowledge Base Manager
// ============================================================
async function loadKnowledgeSummary() {
    try {
        const res = await fetch('/api/admin/knowledge', { headers: getAuthHeaders() });
        if (!res.ok) return;

        const data = await res.json();

        document.getElementById('kb-chunk-count').innerText = data.total_chunks || 0;
        document.getElementById('kb-doc-count').innerText = data.total_documents || 0;
        document.getElementById('kb-embed-model').innerText = data.embedding_model || 'all-MiniLM-L6-v2';

        const tbody = document.getElementById('docs-list-tbody');
        const docs = data.documents || [];
        if (docs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3">Chưa có tài liệu nào trong thư mục tailieu/</td></tr>';
            return;
        }

        tbody.innerHTML = docs.map((d) => `
            <tr>
                <td>📄 <strong>${escapeHtml(d.filename)}</strong></td>
                <td>${d.size_kb} KB</td>
                <td><span class="status-badge RESOLVED" style="color:#10b981;border-color:rgba(16,185,129,0.3);">Đã Embed Index</span></td>
            </tr>
        `).join('');
    } catch (err) {
        console.error('Error loading knowledge summary:', err);
    }
}

function setupDropzone() {
    const fileInput = document.getElementById('docx-file-input');
    const dropLabel = document.getElementById('dropzone-label');
    if (!fileInput || !dropLabel) return;

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            dropLabel.innerText = `Đã chọn: ${fileInput.files[0].name}`;
        }
    });
}

async function handleDocUpload(e) {
    e.preventDefault();
    const fileInput = document.getElementById('docx-file-input');
    if (!fileInput.files.length) return;

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    const resultBox = document.getElementById('upload-result');
    const submitBtn = document.getElementById('btnUploadSubmit');

    resultBox.innerText = '⏳ Đang đọc nội dung, chia nhỏ chunks và tạo Vector Embedding... Vui lòng đợi...';
    resultBox.classList.remove('hidden');
    submitBtn.disabled = true;

    try {
        const token = getAuthToken();
        const res = await fetch('/api/admin/knowledge/upload', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData,
        });

        const data = await res.json();
        submitBtn.disabled = false;

        if (res.ok) {
            resultBox.innerText = `✅ ${data.message}`;
            fileInput.value = '';
            document.getElementById('dropzone-label').innerText = 'Kéo thả file .docx vào đây hoặc bấm chọn file';
            loadKnowledgeSummary();
        } else {
            resultBox.innerText = `❌ Lỗi: ${data.detail || 'Không thể tải tài liệu'}`;
        }
    } catch (err) {
        submitBtn.disabled = false;
        resultBox.innerText = `❌ Lỗi upload: ${err.message}`;
    }
}

// ============================================================
// TAB 4: Analytics
// ============================================================
async function loadAnalytics() {
    try {
        const res = await fetch('/api/admin/analytics', { headers: getAuthHeaders() });
        if (!res.ok) return;

        const data = await res.json();

        document.getElementById('analytic-self-rate').innerText = `${data.ai_self_service_rate || 0}%`;
        document.getElementById('analytic-active-cs').innerText = data.active_human_cases || 0;
        document.getElementById('analytic-resolved').innerText = data.resolved_cases || 0;
        document.getElementById('analytic-learned-qa').innerText = data.total_learned_qa || 0;
        document.getElementById('analytic-total-sessions').innerText = data.total_sessions || 0;
        document.getElementById('analytic-pending-qa').innerText = data.pending_learn_count || 0;
    } catch (err) {
        console.error('Error loading analytics:', err);
    }
}

// ============================================================
// TAB 5: System Config
// ============================================================
async function loadSystemConfig() {
    try {
        const res = await fetch('/api/admin/config', { headers: getAuthHeaders() });
        if (!res.ok) return;

        const data = await res.json();

        document.getElementById('cfg-system-prompt').value = data.system_prompt || '';
        document.getElementById('cfg-model').value = data.llm_model || 'claude-haiku-4-5-20251001';
        document.getElementById('cfg-temp').value = data.temperature !== undefined ? data.temperature : 0.1;
    } catch (err) {
        console.error('Error loading system config:', err);
    }
}

async function handleConfigSave(e) {
    e.preventDefault();
    const prompt = document.getElementById('cfg-system-prompt').value;
    const model = document.getElementById('cfg-model').value;
    const temp = parseFloat(document.getElementById('cfg-temp').value);

    const msgBox = document.getElementById('config-save-msg');
    msgBox.innerText = 'Đang lưu cấu hình và nạp lại mô hình...';
    msgBox.classList.remove('hidden');

    try {
        const res = await fetch('/api/admin/config', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ system_prompt: prompt, llm_model: model, temperature: temp }),
        });

        const data = await res.json();
        if (res.ok) {
            msgBox.innerText = '✅ Đã lưu cấu hình thành công và cập nhật LLM Engine!';
            setTimeout(() => msgBox.classList.add('hidden'), 4000);
        }
    } catch (err) {
        msgBox.innerText = `❌ Lỗi lưu cấu hình: ${err.message}`;
    }
}

// ============================================================
// Utility Helpers
// ============================================================
function getStatusLabel(status) {
    const map = {
        NEEDS_HUMAN_CS: 'Chờ CSKH',
        HUMAN_CS_ACTIVE: 'CSKH Đang Xử Lý',
        RESOLVED: 'Đã Giải Quyết',
        AI_ACTIVE: 'AI Đang Tư Vấn',
    };
    return map[status] || status;
}

function getRoleLabel(role) {
    if (role === 'user') return '👤 Khách hàng';
    if (role === 'human_cs') return '👨‍💼 Chuyên viên CSKH';
    return '🤖 AI Assistant';
}

function formatTime(isoStr) {
    if (!isoStr) return '';
    try {
        const d = new Date(isoStr);
        const hours = d.getHours().toString().padStart(2, '0');
        const mins = d.getMinutes().toString().padStart(2, '0');
        const day = d.getDate().toString().padStart(2, '0');
        const month = (d.getMonth() + 1).toString().padStart(2, '0');
        return `${hours}:${mins} ${day}/${month}`;
    } catch (e) {
        return isoStr;
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
