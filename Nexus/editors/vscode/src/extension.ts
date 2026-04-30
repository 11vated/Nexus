import * as vscode from 'vscode';
import { NexusClient } from './nexusClient';
import { ChatPanel } from './chatPanel';

let chatPanel: ChatPanel | undefined;
let nexusClient: NexusClient | undefined;

export function activate(context: vscode.ExtensionContext) {
    const config = vscode.workspace.getConfiguration('nexus');
    const ollamaUrl = config.get<string>('ollamaUrl', 'http://localhost:11434');
    const workspacePath = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';

    nexusClient = new NexusClient(ollamaUrl, workspacePath);
    chatPanel = new ChatPanel(context.extensionUri, nexusClient);

    // Register commands
    const chatCmd = vscode.commands.registerCommand('nexus.chat', () => {
        chatPanel?.show();
    });

    const runCmd = vscode.commands.registerCommand('nexus.run', async () => {
        const goal = await vscode.window.showInputBox({
            prompt: 'Enter goal for autonomous agent',
            placeHolder: 'Build a Flask API with /health endpoint',
        });
        if (goal) {
            await nexusClient?.runAutonomous(goal);
        }
    });

    const diffCmd = vscode.commands.registerCommand('nexus.diff', async () => {
        await chatPanel?.showLastDiff();
    });

    const acceptCmd = vscode.commands.registerCommand('nexus.accept', async () => {
        await chatPanel?.acceptDiff();
    });

    const rejectCmd = vscode.commands.registerCommand('nexus.reject', async () => {
        await chatPanel?.rejectDiff();
    });

    context.subscriptions.push(chatCmd, runCmd, diffCmd, acceptCmd, rejectCmd);
}

export function deactivate() {
    nexusClient?.dispose();
    chatPanel?.dispose();
}
