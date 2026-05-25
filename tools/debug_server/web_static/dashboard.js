// WebSocket连接
let ws = null;
let isConnected = false;
// 连接到调试服务器
function connect() {
    const url = document.getElementById('ws-url').value;
    const tokenInput = document.getElementById('auth-token');
    const authToken = tokenInput ? tokenInput.value : '';

    try {
        ws = new WebSocket(url);

        ws.onopen = () => {
            // 发送认证
            ws.send(JSON.stringify({
                type: 'web_auth',
                token: authToken
            }));
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            // 处理认证响应
            if (data.type === 'telemetry') {
                updateTelemetry(data);
            }

            // 处理键盘确认
            if (data.type === 'key_ack') {
                addLog(`按键确认: ${data.key} ${data.action}`);
            }

            // 处理pong
            if (data.type === 'pong') {
                // 心跳响应，可以忽略
            }
        };

        ws.onclose = () => {
            setConnectionStatus(false);
            isConnected = false;

            // 10秒后自动重连
            setTimeout(() => {
                if (!isConnected) {
                    addLog('尝试重连...');
                    connect();
                }
            }, 10000);
        };

        ws.onerror = (error) => {
            console.error('WebSocket错误:', error);
            setConnectionStatus(false);
            isConnected = false;
        };

    } catch (error) {
        console.error('连接失败:', error);
        addLog('连接失败: ' + error.message);
    }
}

// 设置连接状态
function setConnectionStatus(connected) {
    const statusEl = document.getElementById('connection-status');

    if (connected) {
        statusEl.textContent = '已连接';
        statusEl.className = 'connection-status connected';
        isConnected = true;
        addLog('✓ 已连接到调试服务器');
    } else {
        statusEl.textContent = '未连接';
        statusEl.className = 'connection-status disconnected';
        isConnected = false;
    }
}

// 更新遥测数据
function updateTelemetry(data) {
    if (data.gear !== undefined) {
        document.getElementById('gear').textContent = data.gear;
    }

    if (data.rpm !== undefined) {
        document.getElementById('rpm').textContent = Math.round(data.rpm);
    }

    if (data.speed !== undefined) {
        document.getElementById('speed').textContent = data.speed.toFixed(1);
    }

    if (data.tire_slip_RL !== undefined) {
        document.getElementById('tire-rl').textContent = (data.tire_slip_RL * 100).toFixed(1) + '%';
    }
}

// 发送键盘命令
function sendKey(key, action) {
    if (!isConnected) {
        addLog('错误: 未连接到服务器');
        return;
    }

    const command = {
        type: 'key_press',
        key: key,
        action: action
    };

    try {
        ws.send(JSON.stringify(command));

        // 视觉反馈
        const button = document.getElementById(`key-${key}`);
        if (button) {
            if (action === 'press') {
                button.classList.add('active');
            } else {
                button.classList.remove('active');
            }
        }

        addLog(`发送: ${key.toUpperCase()} ${action}`);

    } catch (error) {
        console.error('发送命令失败:', error);
        addLog('错误: 发送命令失败');
    }
}

// 添加日志
function addLog(message) {
    const logOutput = document.getElementById('log-output');
    const entry = document.createElement('div');
    entry.className = 'log-entry';

    const time = new Date().toLocaleTimeString();
    entry.textContent = `[${time}] ${message}`;

    logOutput.insertBefore(entry, logOutput.firstChild);

    // 限制日志条数
    while (logOutput.children.length > 50) {
        logOutput.removeChild(logOutput.lastChild);
    }
}

// 键盘监听（本地键盘控制）
document.addEventListener('keydown', (e) => {
    if (['w', 'a', 's', 'd'].includes(e.key.toLowerCase())) {
        sendKey(e.key.toLowerCase(), 'press');
        e.preventDefault();
    }
});

document.addEventListener('keyup', (e) => {
    if (['w', 'a', 's', 'd'].includes(e.key.toLowerCase())) {
        sendKey(e.key.toLowerCase(), 'release');
        e.preventDefault();
    }
});

// 页面加载完成后自动连接
window.addEventListener('load', () => {
    addLog('页面加载完成');
    addLog('点击"连接"按钮连接到调试服务器');
});
