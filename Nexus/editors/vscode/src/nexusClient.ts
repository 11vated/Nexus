import * as vscode from 'vscode';

interface NexusResponse {
    type: 'text' | 'tool_call' | 'diff' | 'error' | 'done';
    content: string;
    data?: Record<string, unknown>;
}

export class NexusClient {
    private ollamaUrl: string;
    private workspacePath: string;
    private lastDiff: string | undefined;

    constructor(ollamaUrl: string, workspacePath: string) {
        this.ollamaUrl = ollamaUrl;
        this.workspacePath = workspacePath;
    }

    async sendMessage(message: string, onChunk: (chunk: string) => void): Promise<string> {
        // Connect to Nexus MCP server via HTTP
        try {
            const response = await fetch(`${this.ollamaUrl}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model: 'qwen2.5-coder:14b',
                    messages: [{ role: 'user', content: message }],
                    stream: false,
                }),
            });

            if (!response.ok) {
                throw new Error(`Nexus error: ${response.status}`);
            }

            const data = await response.json();
            const text = data.message?.content || '';
            onChunk(text);
            return text;
        } catch (error) {
            const errorMsg = error instanceof Error ? error.message : 'Unknown error';
            onChunk(`[Error: ${errorMsg}]`);
            return '';
        }
    }

    async runAutonomous(goal: string): Promise<void> {
        const outputChannel = vscode.window.createOutputChannel('Nexus Agent');
        outputChannel.show();
        outputChannel.appendLine(`Starting autonomous agent: ${goal}`);

        try {
            // Connect to Nexus HTTP endpoint
            const response = await fetch(`${this.ollamaUrl}/api/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model: 'qwen2.5-coder:14b',
                    prompt: `Goal: ${goal}\n\nExecute this goal autonomously.`,
                    stream: false,
                }),
            });

            if (!response.ok) {
                throw new Error(`Agent error: ${response.status}`);
            }

            const data = await response.json();
            outputChannel.appendLine(data.response || 'Completed');
        } catch (error) {
            const errorMsg = error instanceof Error ? error.message : 'Unknown error';
            outputChannel.appendLine(`Error: ${errorMsg}`);
            vscode.window.showErrorMessage(`Nexus agent failed: ${errorMsg}`);
        }
    }

    setLastDiff(diff: string): void {
        this.lastDiff = diff;
    }

    getLastDiff(): string | undefined {
        return this.lastDiff;
    }

    dispose(): void {
        // Cleanup if needed
    }
}
