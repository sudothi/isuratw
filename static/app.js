(function () {
    'use strict';
    let ws = null;
    let botRunning = false;
    let currentView = 'dashboard';
    const $ = (s) => document.querySelector(s);
    const $$ = (s) => document.querySelectorAll(s);
    const views = {
        dashboard: $('#view-dashboard'),
        proxies: $('#view-proxies'),
        settings: $('#view-settings'),
        guide: $('#view-guide'),
    };
    const els = {
        channelInput: $('#channel-input'),
        btnStart: $('#btn-start'),
        statusDot: $('#status-dot'),
        statusLabel: $('#status-label'),
        uptime: $('#uptime'),
        statViewers: $('#stat-viewers'),
        statProxies: $('#stat-proxies'),
        statMax: $('#stat-max'),
        logList: $('#log-list'),
        proxyList: $('#proxy-list'),
        proxyCount: $('#proxy-count'),
        sidebarStatus: $('#sidebar-status'),
        sidebarDot: $('#sidebar-dot'),
        settingsMax: $('#settings-max'),
        settingsProxies: $('#settings-proxies'),
    };
    function connect() {
        const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
        ws = new WebSocket(`${protocol}://${location.host}/ws`);
        ws.onopen = () => {
            addLog('info', 'Connected to server');
        };
        ws.onclose = () => {
            addLog('warning', 'Disconnected. Reconnecting...');
            setTimeout(connect, 2000);
        };
        ws.onerror = () => { };
        ws.onmessage = (e) => {
            const msg = JSON.parse(e.data);
            handleMessage(msg);
        };
    }
    function send(data) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(data));
        }
    }
    function handleMessage(msg) {
        switch (msg.type) {
            case 'init':
                handleInit(msg.data);
                break;
            case 'log':
                renderLog(msg.data);
                break;
            case 'stats':
                updateStats(msg.data);
                break;
            case 'status':
                setStatus(msg.data);
                break;
            case 'proxies':
                renderProxies(msg.data);
                break;
            case 'settings_saved':
                showToast();
                break;
            case 'error':
                addLog('error', msg.data);
                break;
        }
    }
    function handleInit(data) {
        setStatus(data.status);
        if (data.channel) els.channelInput.value = data.channel;
        if (data.logs) {
            data.logs.forEach(renderLog);
        }
        if (data.proxies) {
            renderProxies(data.proxies);
        }
        if (data.max_concurrent) {
            els.settingsMax.value = data.max_concurrent;
        }
    }
    function setStatus(status) {
        botRunning = status === 'running';
        els.statusDot.className = 'status-dot' + (botRunning ? ' running' : '');
        els.statusLabel.textContent = botRunning ? 'RUNNING' : 'IDLE';
        els.statusLabel.className = 'status-label' + (botRunning ? ' running' : '');
        els.btnStart.textContent = botRunning ? 'STOP' : 'START';
        els.btnStart.className = 'btn-start' + (botRunning ? ' running' : '');
        els.sidebarDot.className = 'status-dot' + (botRunning ? ' running' : '');
        els.sidebarStatus.textContent = botRunning ? 'Bot Running' : 'Bot Idle';
        if (!botRunning) {
            els.channelInput.disabled = false;
        }
    }
    function updateStats(data) {
        els.uptime.textContent = data.uptime || '00:00:00';
        els.statViewers.textContent = data.viewers_active || '0';
        els.statProxies.textContent = data.proxies_total || '0';
        els.statMax.textContent = data.max_concurrent || '0';
    }
    function renderLog(entry) {
        const div = document.createElement('div');
        div.className = 'log-entry' + (entry.level === 'error' ? ' error' : entry.level === 'warning' ? ' warning' : '');
        div.innerHTML = `<span class="log-time">${entry.time}</span><span class="log-msg">${escapeHtml(entry.message)}</span>`;
        els.logList.appendChild(div);
        els.logList.scrollTop = els.logList.scrollHeight;
        while (els.logList.children.length > 200) {
            els.logList.removeChild(els.logList.firstChild);
        }
    }
    function addLog(level, message) {
        renderLog({
            time: new Date().toLocaleTimeString('en-US', { hour12: false }),
            message,
            level,
        });
    }
    function renderProxies(proxies) {
        els.proxyList.innerHTML = '';
        els.proxyCount.textContent = `${proxies.length} proxies`;
        proxies.forEach((p) => {
            const row = document.createElement('div');
            row.className = 'proxy-row';
            const statusIcon = { ready: '⚪', ok: '🟢', error: '❌', cooldown: '❄️' };
            row.innerHTML = `
                <span class="proxy-addr">${escapeHtml(p.display)}</span>
                <span class="proxy-status">${statusIcon[p.status] || '⚪'} ${p.status.toUpperCase()}</span>
                <span class="proxy-latency">${p.latency ? p.latency + 'ms' : '--'}</span>
            `;
            els.proxyList.appendChild(row);
        });
        if (els.settingsProxies.value === '') {
            els.settingsProxies.value = proxies.map((p) => p.raw).join('\n');
        }
    }
    function startStop() {
        if (botRunning) {
            send({ action: 'stop' });
        } else {
            const channel = els.channelInput.value.trim();
            if (!channel) {
                els.channelInput.focus();
                els.channelInput.style.borderColor = 'var(--danger)';
                setTimeout(() => els.channelInput.style.borderColor = '', 2000);
                return;
            }
            const maxConcurrent = parseInt(els.settingsMax.value) || 5;
            send({ action: 'start', channel, max_concurrent: maxConcurrent });
            els.channelInput.disabled = true;
        }
    }
    function saveSettings() {
        const maxConcurrent = parseInt(els.settingsMax.value) || 5;
        const proxies = els.settingsProxies.value;
        send({ action: 'save_settings', max_concurrent: maxConcurrent, proxies });
    }
    function showToast() {
        const toast = $('#save-toast');
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 2500);
    }
    function switchView(name) {
        currentView = name;
        $$('.nav-item').forEach((el) => {
            el.classList.toggle('active', el.dataset.view === name);
        });
        Object.entries(views).forEach(([key, el]) => {
            el.classList.toggle('active', key === name);
        });
        if (name === 'proxies') {
            send({ action: 'get_proxies' });
        }
    }
    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
    function init() {
        $$('.nav-item').forEach((el) => {
            el.addEventListener('click', () => switchView(el.dataset.view));
        });
        els.btnStart.addEventListener('click', startStop);
        els.channelInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') startStop();
        });
        $('#btn-save').addEventListener('click', saveSettings);
        connect();
    }
    document.addEventListener('DOMContentLoaded', init);
})();
