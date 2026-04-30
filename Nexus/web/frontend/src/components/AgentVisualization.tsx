import { useEffect, useState } from 'react';
import { nexusApi, AgentStatus } from '../services/api';

interface AgentVisualizationProps {
  workspace: string;
}

export function AgentVisualization({ workspace }: AgentVisualizationProps) {
  const [agents, setAgents] = useState<AgentStatus[]>([]);

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        const list = await nexusApi.listAgents();
        setAgents(list);
      } catch {
        // Ignore errors
      }
    };

    fetchAgents();
    const interval = setInterval(fetchAgents, 3000);
    return () => clearInterval(interval);
  }, []);

  if (agents.length === 0) {
    return <div className="empty-state">No active agents</div>;
  }

  return (
    <div className="agent-list">
      {agents.map((agent) => (
        <div key={agent.agent_id} className="agent-card">
          <div className="agent-header">
            <span className={`status-badge ${agent.status}`}>{agent.status}</span>
            <span className="agent-id">{agent.agent_id}</span>
          </div>
          <p className="agent-goal">{agent.goal}</p>
          <div className="agent-meta">
            <span>Started: {new Date(agent.started_at * 1000).toLocaleTimeString()}</span>
            <span>Workspace: {agent.workspace}</span>
          </div>
          {agent.error && <p className="agent-error">{agent.error}</p>}
        </div>
      ))}
    </div>
  );
}
