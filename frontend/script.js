/**
 * Đông Đô CS Chatbot - Client-side Logic
 * Handles chat interaction, API calls, session management
 */

(function () {
    'use strict';

    // ============================================================
    // Configuration
    // ============================================================
    const API_BASE = window.location.origin;
    const API_CHAT = `${API_BASE}/chat`;

    // ============================================================
    // State
    // ============================================================
    let sessionId = generateSessionId();
    let isWaiting = false;

    // ============================================================
    // DOM Elements
    // ============================================================
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

    // ============================================================
    // Event Listeners
    // ============================================================
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
    // Core Functions
    // ============================================================
    async function sendMessage() {
        const message = messageInput.value.trim();
        if (!message || isWaiting) return;

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
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: sessionId,
                    message: message,
                }),
            });

            // Remove typing indicator
            removeTypingIndicator(typingEl);

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
        // Basic markdown-like formatting
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
    messageInput.focus();
    console.log('🚀 Đông Đô CS Chatbot initialized');
    console.log(`📡 API: ${API_CHAT}`);
    console.log(`🔑 Session: ${sessionId}`);
})();
