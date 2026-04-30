import * as vscode from 'vscode';
import { NexusClient } from './nexusClient';

export class ChatPanel {
    private panel: vscode.WebviewPanel | undefined;
    private extensionUri: vscode.Uri;
    private client: NexusClient;

    constructor(extensionUri: vscode.Uri, client: NexusClient) {
        this.extensionUri = extensionUri;
        this.client = client;
    }

    show(): void {
        if (this.panel) {
            this.panel.reveal(vscode.ViewColumn.One);
            return;
        }

        this.panel = vscode.window.createWebviewPanel(
            'nexusChat',
            'Nexus AI Chat',
            vscode.ViewColumn.One,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
            }
        );

        this.panel.webview.html = this.getHtml();

        this.panel.webview.onDidReceiveMessage(async (message) => {
            if (message.command === 'send') {
                await this.handleMessage(message.text);
            }
        });

        this.panel.onDidDispose(() => {
            this.panel = undefined;
        });
    }

    private async handleMessage(text: string): Promise<void> {
        this.panel?.webview.postMessage({ type: 'loading' });

        let fullResponse = '';
        await this.client.sendMessage(text, (chunk) => {
            fullResponse = chunk;
            this.panel?.webview.postMessage({ type: 'chunk', content: chunk });
        });

        this.panel?.webview.postMessage({ type: 'done', content: fullResponse });
    }

    async showLastDiff(): Promise<void> {
        const diff = this.client.getLastDiff();
        if (!diff) {
            vscode.window.showInformationMessage('No diff to show');
            return;
        }

        const doc = await vscode.workspace.openTextDocument({
            content: diff,
            language: 'diff',
        });
        await vscode.window.showTextDocument(doc);
    }

    async acceptDiff(): Promise<void> {
        vscode.window.showInformationMessage('Changes accepted');
    }

    async rejectDiff(): Promise<void> {
        vscode.window.showInformationMessage('Changes rejected');
    }

    private getHtml(): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nexus AI Chat</title>
    <style>
        body { font-family: var(--vscode-font-family); padding: 16px; color: var(--vscode-editor-foreground); }
        .chat-container { display: flex; flex-direction: column; height: 100vh; }
        .messages { flex: 1; overflow-y: auto; padding: 8px; }
        .message { margin: 8px 0; padding: 8px 12px; border-radius: 8px; max-width: 80%; }
        .message.user { background: var(--vscode-button-background); color: white; align-self: flex-end; margin-left: auto; }
        .message.assistant { background: var(--vscode-editor-background); border: 1px solid var(--vscode-editor-lineHighlightBorder); }
        .input-area { display: flex; gap: 8px; padding: 8px; border-top: 1px solid var(--vscode-editor-lineHighlightBorder); }
        .input-area input { flex: 1; padding: 8px; background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border); border-radius: 4px; }
        .input-area button { padding: 8px 16px; background: var(--vscode-button-background); color: white; border: none; border-radius: 4px; cursor: pointer; }
        .loading { opacity: 0.5; }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="messages" id="messages"></div>
        <div class="input-area">
            <input id="input" placeholder="Ask Nexus..." />
            <button id="send">Send</button>
        </div>
    </div>
    <script>
        const messages = document.getElementById('messages');
        const input = document.getElementById('input');
        const sendBtn = document.getElementById('send');

        function addMessage(role, content) {
            const div = document.createElement('div');
            div.className = 'message ' + role;
            div.textContent = content;
            messages.appendChild(div);
            messages.scrollTop = messages.scrollHeight;
        }

        sendBtn.addEventListener('click', () => {
            const text = input.value.trim();
            if (!text) return;
            addMessage('user', text);
            input.value = '';
            vscode.postMessage({ command: 'send', text });
        });

        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendBtn.click();
        });

        const vscode = acquireVsCodeApi();

        window.addEventListener('message', event => {
            const msg = event.data;
            if (msg.type === 'loading') {
                messages.classList.add('loading');
            } else if (msg.type === 'chunk') {
                messages.classList.remove('loading');
                let lastMsg = messages.querySelector('.message.assistant:last-child');
                if (!lastMsg) {
                    addMessage('assistant', '');
                    lastMsg = messages.querySelector('.message.assistant:last-child');
                }
                lastMsg.textContent = msg.content;
            } else if (msg.type === 'done') {
                messages.classList.remove('loading');
            }
        });
    </script>
</body>
</html>`;
    }

    dispose(): void {
        this.panel?.dispose();
    }
}
