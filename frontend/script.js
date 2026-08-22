/**
 * Đông Đô CS Chatbot - Client-side Logic
 * Handles chat interaction, Authentication, API calls, session management
 */

(function () {
    'use strict';

    // ============================================================
    // Configuration & API Endpoints
    // ============================================================
    const API_BASE = window.location.origin;
    const API_CHAT = `${API_BASE}/chat`;
    const API_LOGIN = `${API_BASE}/auth/login`;
    const API_ME = `${API_BASE}/auth/me`;
    const API_LOGOUT = `${API_BASE}/auth/logout`;

    const TOKEN_KEY = 'dongdo_auth_token';

    // ============================================================
    // State
    // ============================================================
    let sessionId = generateSessionId();
    let isWaiting = false;
    let currentUser = null;

    // ============================================================
    // DOM Elements
    // ============================================================
    const loginOverlay = document.getElementById('loginOverlay');
    const loginForm = document.getElementById('loginForm');
    const loginUsernameInput = document.getElementById('loginUsername');
    const loginPasswordInput = document.getElementById('loginPassword');
    const loginError = document.getElementById('loginError');
    const btnLoginSubmit = document.getElementById('btnLoginSubmit');

    const userNameDisplay = document.getElementById('userName');
    const btnLogout = document.getElementById('btnLogout');

    const chatMessages = document.getElementById('chatMessages');
    const welcomeScreen = document.getElementById('welcomeScreen');
    const messageInput = document.getElementById('messageInput');
    const btnSend = document.getElementById('btnSend');
    const btnNewChat = document.getElementById('btnNewChat');
    const charCount = document.getElementById('charCount');

    // ============================================================
    // Session Management
    // ============================================================
    function generateSessionId() {
        return 'session-' + Date.now() + '-' + Math.random().toString(36).substring(2, 9);
    }

    function getToken() {
        return localStorage.getItem(TOKEN_KEY);
    }

    function setToken(token) {
        if (token) {
            localStorage.setItem(TOKEN_KEY, token);
        } else {
            localStorage.removeItem(TOKEN_KEY);
        }
    }

    function getAuthHeaders() {
        const token = getToken();
        const headers = { 'Content-Type': 'application/json' };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        return headers;
    }

    // ============================================================
    // Authentication Functions
    // ============================================================
    async function checkAuth() {
        const token = getToken();
        if (!token) {
            showLoginModal();
            return false;
        }

        try {
            const res = await fetch(API_ME, {
                headers: getAuthHeaders(),
            });

            if (res.ok) {
                const user = await res.json();
                currentUser = user;
                onLoginSuccess(user);
                return true;
            } else {
                setToken(null);
                showLoginModal();
                return false;
            }
        } catch (err) {
            console.error('Auth verification error:', err);
            showLoginModal();
            return false;
        }
    }

    function showLoginModal(errMsg = '') {
        loginOverlay.classList.remove('hidden');
        if (errMsg) {
            loginError.textContent = errMsg;
            loginError.classList.add('visible');
        } else {
            loginError.classList.remove('visible');
            loginError.textContent = '';
        }
        setTimeout(() => loginUsernameInput.focus(), 100);
    }

    function hideLoginModal() {
        loginOverlay.classList.add('hidden');
        loginError.classList.remove('visible');
        loginError.textContent = '';
        messageInput.focus();
    }

    function onLoginSuccess(user) {
        currentUser = user;
        userNameDisplay.textContent = user.full_name || user.username;
        hideLoginModal();
    }

    async function handleLoginSubmit(e) {
        e.preventDefault();
        const username = loginUsernameInput.value.trim();
        const password = loginPasswordInput.value;

        if (!username || !password) {
            showLoginModal('Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu.');
            return;
        }

        btnLoginSubmit.disabled = true;
        btnLoginSubmit.innerHTML = '<span>Đang đăng nhập...</span>';
        loginError.classList.remove('visible');

        try {
            const res = await fetch(API_LOGIN, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password }),
            });

            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.detail || 'Đăng nhập thất bại.');
            }

            setToken(data.token);
            onLoginSuccess(data);
            loginPasswordInput.value = '';
        } catch (err) {
            showLoginModal(err.message || 'Tên đăng nhập hoặc mật khẩu không chính xác.');
        } finally {
            btnLoginSubmit.disabled = false;
            btnLoginSubmit.innerHTML = '<span>Đăng nhập hệ thống</span>';
        }
    }

    async function handleLogout() {
        try {
            await fetch(API_LOGOUT, {
                method: 'POST',
                headers: getAuthHeaders(),
            });
        } catch (err) {
            console.warn('Logout API error:', err);
        } finally {
            setToken(null);
            currentUser = null;
            userNameDisplay.textContent = 'Chưa đăng nhập';
            showLoginModal();
        }
    }

    // ============================================================
    // Event Listeners
    // ============================================================
    loginForm.addEventListener('submit', handleLoginSubmit);
    btnLogout.addEventListener('click', handleLogout);

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
        sessionId = generateSessionId();
        chatMessages.innerHTML = '';
        chatMessages.appendChild(welcomeScreen);
        welcomeScreen.classList.remove('hidden');
        messageInput.value = '';
        messageInput.style.height = 'auto';
        updateCharCount();
        updateSendButton();
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
    // Core Chat Functions
    // ============================================================
    async function sendMessage() {
        const message = messageInput.value.trim();
        if (!message || isWaiting) return;

        if (!getToken()) {
            showLoginModal('Vui lòng đăng nhập để gửi tin nhắn.');
            return;
        }

        // Hide welcome screen
        welcomeScreen.classList.add('hidden');

        // Add user message
        appendMessage('user', message);

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

            // Remove typing indicator
            removeTypingIndicator(typingEl);

            if (response.status === 401) {
                setToken(null);
                showLoginModal('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
                return;
            }

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            const data = await response.json();

            // Update session_id from server if needed
            if (data.session_id) {
                sessionId = data.session_id;
            }

            // Add bot response
            appendMessage('assistant', data.reply, data.sources);
        } catch (error) {
            removeTypingIndicator(typingEl);
            console.error('Chat error:', error);
            showError(`Không thể kết nối: ${error.message}`);
            appendMessage(
                'assistant',
                'Xin lỗi, đã xảy ra lỗi khi xử lý yêu cầu của bạn. Vui lòng thử lại sau.'
            );
        } finally {
            isWaiting = false;
            messageInput.focus();
        }
    }

    function appendMessage(role, content, sources = []) {
        const row = document.createElement('div');
        row.className = `message-row ${role}`;

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.innerHTML = role === 'user' ? '👤' : '🤖';

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
        time.textContent = formatTime(new Date());
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
    console.log('🚀 Đông Đô CS Chatbot initialized with Authentication');
})();
