/**
 * Đông Đô CS Chatbot - Client-side Logic (Khách Hàng)
 * Handles customer authentication, chat, API calls, real-time CS polling
 */

(function () {
    'use strict';

    // ============================================================
    // Configuration & State
    // ============================================================
    const API_BASE = window.location.origin;
    const API_CHAT = `${API_BASE}/chat`;
    const TOKEN_KEY = 'dongdo_client_token';

    let sessionId = getOrCreateSessionId();
    let isWaiting = false;
    let csPollTimer = null;
    let displayedMessageCount = 0;
    let currentCustomer = null;

    // ============================================================
    // DOM Elements
    // ============================================================
    const clientLoginOverlay = document.getElementById('clientLoginOverlay');
    const clientLoginForm = document.getElementById('clientLoginForm');
    const clientUsernameInput = document.getElementById('clientUsername');
    const clientPasswordInput = document.getElementById('clientPassword');
    const clientLoginError = document.getElementById('clientLoginError');
    const btnClientLogin = document.getElementById('btnClientLogin');
    const customerProfile = document.getElementById('customerProfile');
    const clientUserName = document.getElementById('clientUserName');
    const btnClientLogout = document.getElementById('btnClientLogout');

    const chatMessages = document.getElementById('chatMessages');
    const welcomeScreen = document.getElementById('welcomeScreen');
    const messageInput = document.getElementById('messageInput');
    const btnSend = document.getElementById('btnSend');
    const btnNewChat = document.getElementById('btnNewChat');
    const charCount = document.getElementById('charCount');
    const statusBadge = document.getElementById('statusBadge');

    // ============================================================
    // Session Management
    // ============================================================
    function getOrCreateSessionId() {
        let sid = sessionStorage.getItem('dongdo_client_session_id');
        if (!sid) {
            sid = 'session-' + Date.now() + '-' + Math.random().toString(36).substring(2, 9);
            sessionStorage.setItem('dongdo_client_session_id', sid);
        }
        return sid;
    }

    function createNewSession() {
        const sid = 'session-' + Date.now() + '-' + Math.random().toString(36).substring(2, 9);
        sessionStorage.setItem('dongdo_client_session_id', sid);
        return sid;
    }

    // ============================================================
    // Authentication Management
    // ============================================================
    function getAuthToken() {
        return localStorage.getItem(TOKEN_KEY);
    }

    function getAuthHeaders() {
        const token = getAuthToken();
        const headers = { 'Content-Type': 'application/json' };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        return headers;
    }

    async function checkAuth() {
        const token = getAuthToken();
        if (!token) {
            showLoginModal();
            return false;
        }

        try {
            const res = await fetch(`${API_BASE}/auth/me`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const user = await res.json();
                setLoggedInUser(user);
                return true;
            } else {
                localStorage.removeItem(TOKEN_KEY);
                showLoginModal();
                return false;
            }
        } catch (err) {
            console.error('Auth verification failed:', err);
            showLoginModal();
            return false;
        }
    }

    function showLoginModal(errorMsg = '') {
        if (clientLoginOverlay) {
            clientLoginOverlay.style.display = 'flex';
            clientLoginOverlay.classList.remove('hidden');
        }
        if (customerProfile) {
            customerProfile.style.display = 'none';
        }
        if (clientLoginError) {
            if (errorMsg) {
                clientLoginError.textContent = errorMsg;
                clientLoginError.style.display = 'block';
            } else {
                clientLoginError.textContent = '';
                clientLoginError.style.display = 'none';
            }
        }
        if (clientUsernameInput) {
            setTimeout(() => clientUsernameInput.focus(), 200);
        }
    }

    function hideLoginModal() {
        if (clientLoginOverlay) {
            clientLoginOverlay.style.display = 'none';
            clientLoginOverlay.classList.add('hidden');
        }
    }

    function setLoggedInUser(user) {
        currentCustomer = user;
        hideLoginModal();
        if (customerProfile && clientUserName) {
            customerProfile.style.display = 'flex';
            clientUserName.textContent = `👤 ${user.full_name || user.username}`;
        }
        messageInput.focus();
    }

    async function handleLogin(e) {
        e.preventDefault();
        const username = clientUsernameInput.value.trim();
        const password = clientPasswordInput.value;

        if (!username || !password) {
            showLoginModal('Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu');
            return;
        }

        btnClientLogin.disabled = true;
        btnClientLogin.innerHTML = '<span>Đang đăng nhập...</span>';
        if (clientLoginError) clientLoginError.style.display = 'none';

        try {
            const formData = new FormData();
            formData.append('username', username);
            formData.append('password', password);

            const res = await fetch(`${API_BASE}/auth/login`, {
                method: 'POST',
                body: formData,
            });

            const data = await res.json();
            if (res.ok && data.token) {
                localStorage.setItem(TOKEN_KEY, data.token);
                setLoggedInUser(data.user);
            } else {
                showLoginModal(data.detail || 'Tên đăng nhập hoặc mật khẩu không chính xác');
            }
        } catch (err) {
            showLoginModal('Lỗi kết nối máy chủ: ' + err.message);
        } finally {
            btnClientLogin.disabled = false;
            btnClientLogin.innerHTML = `<span>Đăng Nhập Ngay</span>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M5 12h14M12 5l7 7-7 7"/>
                </svg>`;
        }
    }

    function handleLogout() {
        if (confirm('Bạn có chắc chắn muốn đăng xuất tài khoản?')) {
            const token = getAuthToken();
            if (token) {
                fetch(`${API_BASE}/auth/logout`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}` }
                }).catch(() => {});
            }
            localStorage.removeItem(TOKEN_KEY);
            currentCustomer = null;
            if (csPollTimer) {
                clearInterval(csPollTimer);
                csPollTimer = null;
            }
            sessionId = createNewSession();
            displayedMessageCount = 0;
            chatMessages.innerHTML = '';
            chatMessages.appendChild(welcomeScreen);
            welcomeScreen.classList.remove('hidden');
            showLoginModal();
        }
    }

    // ============================================================
    // Event Listeners
    // ============================================================
    if (clientLoginForm) {
        clientLoginForm.addEventListener('submit', handleLogin);
    }

    if (btnClientLogout) {
        btnClientLogout.addEventListener('click', handleLogout);
    }

    messageInput.addEventListener('input', () => {
        autoResize(messageInput);
        updateCharCount();
        updateSendButton();
    });

    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    btnSend.addEventListener('click', sendMessage);

    btnNewChat.addEventListener('click', () => {
        if (csPollTimer) {
            clearInterval(csPollTimer);
            csPollTimer = null;
        }
        sessionId = createNewSession();
        displayedMessageCount = 0;
        chatMessages.innerHTML = '';
        chatMessages.appendChild(welcomeScreen);
        welcomeScreen.classList.remove('hidden');
        messageInput.value = '';
        messageInput.style.height = 'auto';
        updateCharCount();
        updateSendButton();
        resetStatusBadge();
    });

    // Suggestion chips
    document.querySelectorAll('.chip').forEach((chip) => {
        chip.addEventListener('click', () => {
            const msg = chip.getAttribute('data-message');
            if (msg) {
                messageInput.value = msg;
                updateCharCount();
                updateSendButton();
                sendMessage();
            }
        });
    });

    // ============================================================
    // Core Functions
    // ============================================================
    async function sendMessage() {
        const message = messageInput.value.trim();
        if (!message || isWaiting) return;

        // Check if token exists
        if (!getAuthToken()) {
            showLoginModal('Vui lòng đăng nhập để bắt đầu trò chuyện.');
            return;
        }

        // Hide welcome screen
        welcomeScreen.classList.add('hidden');

        // Add user message
        appendMessage('user', message);
        displayedMessageCount++;

        // Clear input
        messageInput.value = '';
        messageInput.style.height = 'auto';
        updateCharCount();
        updateSendButton();

        // Show typing indicator
        const typingEl = showTypingIndicator();
        isWaiting = true;

        try {
            const response = await fetch(API_CHAT, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({
                    session_id: sessionId,
                    message: message,
                }),
            });

            removeTypingIndicator(typingEl);

            if (response.status === 401) {
                showLoginModal('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
                return;
            }

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            const data = await response.json();

            if (data.session_id) {
                sessionId = data.session_id;
                sessionStorage.setItem('dongdo_client_session_id', sessionId);
            }

            // Add response message
            const role = data.status === 'HUMAN_CS_ACTIVE' ? 'human_cs' : 'assistant';
            appendMessage(role, data.reply, data.sources);
            displayedMessageCount++;

            // Check if waiting for CS
            if (data.waiting_for_cs || data.status === 'NEEDS_HUMAN_CS' || data.status === 'HUMAN_CS_ACTIVE') {
                updateCSStatusBadge(data.cs_agent ? `Chuyên viên ${data.cs_agent} đang kết nối` : 'Đang chuyển giao Chuyên viên CSKH');
                startCSPolling();
            }
        } catch (error) {
            removeTypingIndicator(typingEl);
            console.error('Chat error:', error);
            showError(`Không thể kết nối: ${error.message}`);
            appendMessage(
                'assistant',
                'Dạ xin lỗi anh/chị, hệ thống đang bận xử lý hoặc kết nối gián đoạn. Vui lòng thử lại sau giây lát.'
            );
            displayedMessageCount++;
        } finally {
            isWaiting = false;
            messageInput.focus();
        }
    }

    function updateCSStatusBadge(text) {
        if (statusBadge) {
            statusBadge.innerHTML = `<span class="status-dot" style="background:#10b981;box-shadow:0 0 10px #10b981;"></span> ${text}`;
        }
    }

    function resetStatusBadge() {
        if (statusBadge) {
            statusBadge.innerHTML = `<span class="status-dot"></span> Chuyên viên CSKH đang trực tuyến`;
        }
    }

    function startCSPolling() {
        if (csPollTimer) return;
        csPollTimer = setInterval(async () => {
            try {
                const res = await fetch(`${API_BASE}/history/${sessionId}`);
                if (!res.ok) return;
                const data = await res.json();
                const msgs = data.messages || [];

                if (data.assigned_cs) {
                    updateCSStatusBadge(`Chuyên viên CSKH: ${data.assigned_cs}`);
                }

                // If new messages from human CS exist that haven't been rendered
                if (msgs.length > displayedMessageCount) {
                    const newMsgs = msgs.slice(displayedMessageCount);
                    newMsgs.forEach((m) => {
                        if (m.role === 'human_cs') {
                            appendMessage('human_cs', m.content);
                        }
                    });
                    displayedMessageCount = msgs.length;
                }
            } catch (e) {
                console.error('CS Polling error:', e);
            }
        }, 3000);
    }

    function appendMessage(role, content, sources = []) {
        const row = document.createElement('div');
        row.className = `message-row ${role}`;

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        if (role === 'user') {
            avatar.innerHTML = '👤';
        } else if (role === 'human_cs') {
            avatar.innerHTML = '👨‍💼';
            avatar.title = 'Chuyên viên CSKH Đông Đô Partners';
        } else {
            avatar.innerHTML = '🤖';
            avatar.title = 'Chuyên viên CSKH Đông Đô';
        }

        const bubble = document.createElement('div');
        bubble.className = 'message-content';
        bubble.innerHTML = formatMessage(content);

        const wrapper = document.createElement('div');
        wrapper.style.display = 'flex';
        wrapper.style.flexDirection = 'column';

        wrapper.appendChild(bubble);

        // Add timestamp
        const time = document.createElement('div');
        time.className = 'message-time';
        time.textContent = (role === 'human_cs' ? '👨‍💼 CSKH • ' : '') + formatTime(new Date());
        wrapper.appendChild(time);

        row.appendChild(avatar);
        row.appendChild(wrapper);

        chatMessages.appendChild(row);
        scrollToBottom();
    }

    function formatMessage(text) {
        let html = text;

        // Escape HTML
        html = html
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        // Bold: **text** or __text__
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/__(.*?)__/g, '<strong>$1</strong>');

        // Italic: *text* or _text_
        html = html.replace(/(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)/g, '<em>$1</em>');

        // Bullet lists: - item or • item
        html = html.replace(/^[\-•]\s+(.+)$/gm, '<li>$1</li>');
        html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');

        // Numbered lists: 1. item
        html = html.replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>');

        // Line breaks
        html = html.replace(/\n\n/g, '</p><p>');
        html = html.replace(/\n/g, '<br>');

        // Wrap in paragraph if not already
        if (!html.startsWith('<')) {
            html = `<p>${html}</p>`;
        }

        return html;
    }

    function formatTime(date) {
        return date.toLocaleTimeString('vi-VN', {
            hour: '2-digit',
            minute: '2-digit',
        });
    }

    // ============================================================
    // Typing Indicator
    // ============================================================
    function showTypingIndicator() {
        const el = document.createElement('div');
        el.className = 'typing-indicator';
        el.id = 'typingIndicator';

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.style.background = 'var(--surface-glass)';
        avatar.style.border = '1px solid var(--border-subtle)';
        avatar.innerHTML = '🤖';

        const dots = document.createElement('div');
        dots.className = 'typing-dots';
        dots.innerHTML = '<span></span><span></span><span></span>';

        el.appendChild(avatar);
        el.appendChild(dots);

        chatMessages.appendChild(el);
        scrollToBottom();
        return el;
    }

    function removeTypingIndicator(el) {
        if (el && el.parentNode) {
            el.parentNode.removeChild(el);
        }
    }

    // ============================================================
    // UI Helpers
    // ============================================================
    function autoResize(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }

    function updateCharCount() {
        const len = messageInput.value.length;
        charCount.textContent = `${len} / 2000`;
    }

    function updateSendButton() {
        btnSend.disabled = !messageInput.value.trim() || isWaiting;
    }

    function scrollToBottom() {
        requestAnimationFrame(() => {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        });
    }

    function showError(message) {
        let toast = document.querySelector('.error-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.className = 'error-toast';
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        toast.classList.add('visible');

        setTimeout(() => {
            toast.classList.remove('visible');
        }, 4000);
    }

    // ============================================================
    // Init
    // ============================================================
    checkAuth();
    console.log('🚀 Đông Đô CS Chatbot initialized');
})();
