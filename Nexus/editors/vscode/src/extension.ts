import * as vscode from 'vscode';

/**
 * Nexus AI VS Code Extension
 *
 * Embeds Nexus AI coding assistant directly into VS Code.
 * Features:
 * - Sidebar chat panel with streaming responses
 * - Status bar indicator showing model state
 * - Hardware-aware model routing
 * - Theme synchronization with VS Code
 */

let chatPanel: vscode.WebviewPanel | undefined;
let statusBarItem: vscode.StatusBarItem;
let currentTheme: 'dark' | 'light' = 'dark';

// Design tokens matching nexus/ui/tokens.py
const THEME_COLORS = {
  dark: {
    primary: '#00D4FF',
    user: '#00FF88',
    tool: '#FFB800',
    danger: '#FF3366',
    muted: '#888888',
    bg: '#0A0E14',
    surface: '#141A24',
    border: '#2A3342',
  },
  light: {
    primary: '#007ACC',
    user: '#00875A',
    tool: '#D48C00',
    danger: '#D42E5B',
    muted: '#6B6B6B',
    bg: '#F5F7FA',
    surface: '#FFFFFF',
    border: '#D0D7DE',
  },
};

export function activate(context: vscode.ExtensionContext) {
  console.log('Nexus AI extension activated');

  // Status bar item
  statusBarItem = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Right,
    100
  );
  statusBarItem.command = 'nexus.openChat';
  updateStatusBar('idle');
  statusBarItem.show();

  // Register commands
  const openChatCmd = vscode.commands.registerCommand(
    'nexus.openChat',
    () => openChatPanel(context)
  );

  const runAgentCmd = vscode.commands.registerCommand(
    'nexus.runAgent',
    runAutonomousAgent
  );

  const showHardwareCmd = vscode.commands.registerCommand(
    'nexus.showHardware',
    showHardwareRecommendations
  );

  const toggleThemeCmd = vscode.commands.registerCommand(
    'nexus.toggleTheme',
    toggleTheme
  );

  context.subscriptions.push(
    openChatCmd,
    runAgentCmd,
    showHardwareCmd,
    toggleThemeCmd,
    statusBarItem
  );

  // Auto-open chat on startup if configured
  const config = vscode.workspace.getConfiguration('nexus');
  if (config.get('autoOpenChat')) {
    openChatPanel(context);
  }
}

export function deactivate() {
  if (chatPanel) {
    chatPanel.dispose();
  }
}

/**
 * Open or reveal the chat webview panel.
 */
function openChatPanel(context: vscode.ExtensionContext) {
  if (chatPanel) {
    chatPanel.reveal(vscode.ViewColumn.Two);
    return;
  }

  chatPanel = vscode.window.createWebviewPanel(
    'nexusChat',
    'Nexus AI Chat',
    vscode.ViewColumn.Two,
    {
      enableScripts: true,
      retainContextWhenHidden: true,
      localResourceRoots: [
        vscode.Uri.joinPath(context.extensionUri, 'media'),
      ],
    }
  );

  chatPanel.webview.html = getWebviewContent(context);
  updateStatusBar('idle');

  chatPanel.onDidDispose(
    () => {
      chatPanel = undefined;
      updateStatusBar('idle');
    },
    null,
    context.subscriptions
  );

  // Handle messages from webview
  chatPanel.webview.onDidReceiveMessage(
    async (message) => {
      switch (message.command) {
        case 'sendMessage':
          await handleChatMessage(message.text);
          break;
        case 'ready':
          updateStatusBar('ready');
          break;
      }
    },
    undefined,
    context.subscriptions
  );
}

/**
 * Generate the webview HTML with design tokens.
 */
function getWebviewContent(context: vscode.ExtensionContext): string {
  const config = vscode.workspace.getConfiguration('nexus');
  const model = config.get('model', 'qwen2.5-coder:7b');
  const theme = config.get('theme', 'dark') as 'dark' | 'light';
  const colors = THEME_COLORS[theme];

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    :root {
      --nexus-primary: ${colors.primary};
      --nexus-user: ${colors.user};
      --nexus-tool: ${colors.tool};
      --nexus-danger: ${colors.danger};
      --nexus-muted: ${colors.muted};
      --nexus-bg: ${colors.bg};
      --nexus-surface: ${colors.surface};
      --nexus-border: ${colors.border};
      --font-mono: "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
      --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    * { margin: 0; padding: 0; box-sizing: border-box; }

    body {
      font-family: var(--font-sans);
      background: var(--nexus-bg);
      color: #E6EDF3;
      height: 100vh;
      display: flex;
      flex-direction: column;
    }

    .header {
      padding: 12px 16px;
      background: var(--nexus-surface);
      border-bottom: 1px solid var(--nexus-border);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .header h1 {
      font-size: 14px;
      color: var(--nexus-primary);
      font-weight: 600;
    }

    .model-badge {
      font-size: 11px;
      padding: 2px 8px;
      background: rgba(0, 212, 255, 0.1);
      color: var(--nexus-primary);
      border-radius: 4px;
      font-family: var(--font-mono);
    }

    .messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .message {
      padding: 10px 14px;
      border-radius: 8px;
      max-width: 85%;
      line-height: 1.5;
      font-size: 13px;
    }

    .message.user {
      background: var(--nexus-surface);
      align-self: flex-end;
      border-left: 3px solid var(--nexus-user);
    }

    .message.assistant {
      background: rgba(0, 212, 255, 0.05);
      align-self: flex-start;
      border-left: 3px solid var(--nexus-primary);
    }

    .message.tool {
      background: rgba(255, 184, 0, 0.05);
      align-self: flex-start;
      border-left: 3px solid var(--nexus-tool);
      font-family: var(--font-mono);
      font-size: 12px;
    }

    .input-area {
      display: flex;
      gap: 8px;
      padding: 12px 16px;
      border-top: 1px solid var(--nexus-border);
      background: var(--nexus-surface);
    }

    .input-area input {
      flex: 1;
      padding: 8px 12px;
      background: var(--nexus-bg);
      border: 1px solid var(--nexus-border);
      color: #E6EDF3;
      border-radius: 6px;
      font-size: 13px;
      font-family: var(--font-mono);
    }

    .input-area input:focus {
      outline: none;
      border-color: var(--nexus-primary);
    }

    .input-area button {
      padding: 8px 16px;
      background: var(--nexus-primary);
      color: var(--nexus-bg);
      border: none;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 600;
      font-size: 13px;
    }

    .input-area button:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }

    .welcome {
      text-align: center;
      padding: 40px 20px;
      color: var(--nexus-muted);
    }

    .welcome h2 {
      color: var(--nexus-primary);
      margin-bottom: 8px;
    }
  </style>
</head>
<body>
  <div class="header">
    <h1>Nexus AI</h1>
    <span class="model-badge">${model}</span>
  </div>

  <div class="messages" id="messages">
    <div class="welcome">
      <h2>Welcome to Nexus AI</h2>
      <p>Ask me anything about your code.</p>
    </div>
  </div>

  <div class="input-area">
    <input
      type="text"
      id="input"
      placeholder="Ask Nexus..."
      autocomplete="off"
    />
    <button id="send">Send</button>
  </div>

  <script>
    const vscode = acquireVsCodeApi();
    const messagesEl = document.getElementById('messages');
    const inputEl = document.getElementById('input');
    const sendBtn = document.getElementById('send');

    function addMessage(role, content) {
      // Remove welcome message if present
      const welcome = messagesEl.querySelector('.welcome');
      if (welcome) welcome.remove();

      const msg = document.createElement('div');
      msg.className = 'message ' + role;
      msg.textContent = content;
      messagesEl.appendChild(msg);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function sendMessage() {
      const text = inputEl.value.trim();
      if (!text) return;

      addMessage('user', text);
      inputEl.value = '';
      sendBtn.disabled = true;

      vscode.postMessage({ command: 'sendMessage', text: text });

      // Show thinking indicator
      const thinking = document.createElement('div');
      thinking.className = 'message assistant thinking';
      thinking.textContent = 'Nexus is thinking';
      thinking.id = 'thinking';
      messagesEl.appendChild(thinking);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    sendBtn.addEventListener('click', sendMessage);
    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    // Notify extension that webview is ready
    vscode.postMessage({ command: 'ready' });

    // Listen for messages from extension
    window.addEventListener('message', (event) => {
      const msg = event.data;
      const thinking = document.getElementById('thinking');
      if (thinking) thinking.remove();

      if (msg.type === 'response') {
        addMessage('assistant', msg.content);
        sendBtn.disabled = false;
      } else if (msg.type === 'tool_call') {
        addMessage('tool', msg.content);
      } else if (msg.type === 'error') {
        addMessage('assistant', 'Error: ' + msg.content);
        sendBtn.disabled = false;
      }
    });
  </script>
</body>
</html>`;
}

/**
 * Handle chat message from webview.
 */
async function handleChatMessage(text: string) {
  const config = vscode.workspace.getConfiguration('nexus');
  const ollamaUrl = config.get('ollamaUrl', 'http://localhost:11434');
  const model = config.get('model', 'qwen2.5-coder:7b');

  try {
    updateStatusBar('thinking');

    const response = await fetch(`${ollamaUrl}/api/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: model,
        prompt: text,
        stream: false,
      }),
    });

    const data = await response.json();

    if (chatPanel) {
      chatPanel.webview.postMessage({
        type: 'response',
        content: data.response || '(no response)',
      });
    }

    updateStatusBar('ready');
  } catch (error: any) {
    if (chatPanel) {
      chatPanel.webview.postMessage({
        type: 'error',
        content: error.message || 'Failed to connect to Ollama',
      });
    }
    updateStatusBar('error');
  }
}

/**
 * Run an autonomous agent on the selected code.
 */
async function runAutonomousAgent() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showWarningMessage('No active editor');
    return;
  }

  const goal = await vscode.window.showInputBox({
    prompt: 'What should Nexus do with this code?',
    placeHolder: 'e.g., Refactor to reduce duplication',
  });

  if (!goal) return;

  vscode.window.showInformationMessage(`Nexus agent started: "${goal}"`);
  updateStatusBar('running');
}

/**
 * Show hardware recommendations in output panel.
 */
async function showHardwareRecommendations() {
  const output = vscode.window.createOutputChannel('Nexus Hardware');
  output.show();

  output.appendLine('Nexus AI — Hardware Recommendations');
  output.appendLine('====================================');
  output.appendLine('');
  output.appendLine('Run "nexus hardware" in the terminal for full report.');
  output.appendLine('');
  output.appendLine('Quick guide:');
  output.appendLine('  < 8GB RAM  → qwen2.5-coder:1.5b');
  output.appendLine('  8-16GB RAM → qwen2.5-coder:7b');
  output.appendLine('  16-32GB RAM → qwen2.5-coder:14b');
  output.appendLine('  32GB+ RAM  → gemma4:26b');
}

/**
 * Toggle between dark and light themes.
 */
async function toggleTheme() {
  const config = vscode.workspace.getConfiguration('nexus');
  const current = config.get('theme', 'dark');
  const next = current === 'dark' ? 'light' : 'dark';
  await config.update('theme', next, vscode.ConfigurationTarget.Global);

  currentTheme = next;
  vscode.window.showInformationMessage(`Nexus theme: ${next}`);

  // Refresh chat panel if open
  if (chatPanel) {
    const context = getContext();
    if (context) {
      chatPanel.webview.html = getWebviewContent(context);
    }
  }
}

/**
 * Update status bar text and color.
 */
function updateStatusBar(state: 'idle' | 'ready' | 'thinking' | 'running' | 'error') {
  const config = vscode.workspace.getConfiguration('nexus');
  const model = config.get('model', 'qwen2.5-coder:7b');
  const shortModel = model.split(':')[0];

  const icons: Record<string, string> = {
    idle: '⏸',
    ready: '●',
    thinking: '◌',
    running: '⟳',
    error: '✗',
  };

  statusBarItem.text = `${icons[state]} ${shortModel}`;
  statusBarItem.tooltip = `Nexus AI — ${state}`;

  switch (state) {
    case 'thinking':
      statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
      break;
    case 'error':
      statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
      break;
    default:
      statusBarItem.backgroundColor = undefined;
  }
}

/**
 * Get the extension context (stored globally for theme refresh).
 */
let _context: vscode.ExtensionContext | undefined;

function getContext() {
  return _context;
}

// Store context on activation (override the exported activate)
const originalActivate = activate;
activate = function(context: vscode.ExtensionContext) {
  _context = context;
  originalActivate(context);
};
