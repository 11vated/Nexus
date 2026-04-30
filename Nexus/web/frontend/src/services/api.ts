const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface AgentStatus {
  agent_id: string;
  goal: string;
  status: 'running' | 'completed' | 'error';
  workspace: string;
  started_at: number;
  result?: Record<string, unknown>;
  error?: string;
}

export interface PluginInfo {
  name: string;
  version: string;
  description: string;
  author: string;
  state: string;
  enabled: boolean;
  dependencies: string[];
  tags: string[];
}

export interface EvolutionStats {
  generations: number;
  best_fitness: number;
  best_genome?: Record<string, unknown>;
  stats?: Record<string, unknown>;
}

export class NexusApi {
  async health(): Promise<Record<string, unknown>> {
    const res = await fetch(`${API_BASE}/api/health`);
    return res.json();
  }

  async chat(messages: ChatMessage[], workspace: string): Promise<{ response: string }> {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages, workspace, stream: false }),
    });
    return res.json();
  }

  async runAgent(goal: string, workspace: string): Promise<{ agent_id: string; status: string }> {
    const res = await fetch(`${API_BASE}/api/agent/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ goal, workspace }),
    });
    return res.json();
  }

  async getAgentStatus(agentId: string): Promise<AgentStatus> {
    const res = await fetch(`${API_BASE}/api/agent/${agentId}`);
    return res.json();
  }

  async listAgents(): Promise<AgentStatus[]> {
    const res = await fetch(`${API_BASE}/api/agents`);
    return res.json();
  }

  async listPlugins(workspace: string): Promise<PluginInfo[]> {
    const res = await fetch(`${API_BASE}/api/plugins`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'list', workspace }),
    });
    const data = await res.json();
    return data.plugins || [];
  }

  async enablePlugin(name: string, workspace: string): Promise<Record<string, unknown>> {
    const res = await fetch(`${API_BASE}/api/plugins`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'enable', plugin_name: name, workspace }),
    });
    return res.json();
  }

  async runEvolution(workspace: string, maxGenerations: number): Promise<EvolutionStats> {
    const res = await fetch(`${API_BASE}/api/evolution/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workspace, max_generations: maxGenerations }),
    });
    return res.json();
  }

  connectWebSocket(sessionId: string): WebSocket {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/chat/${sessionId}`;
    return new WebSocket(wsUrl);
  }
}

export const nexusApi = new NexusApi();
