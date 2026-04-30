import { useState } from 'react';
import { nexusApi } from '../services/api';
import { AgentVisualization } from '../components/AgentVisualization';

interface AgentsPageProps {
  workspace: string;
}

export function AgentsPage({ workspace }: AgentsPageProps) {
  const [goal, setGoal] = useState('');
  const [running, setRunning] = useState(false);

  const runAgent = async () => {
    if (!goal.trim()) return;
    setRunning(true);
    try {
      await nexusApi.runAgent(goal, workspace);
    } catch (err) {
      console.error(err);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="page agents-page">
      <h1>Autonomous Agents</h1>
      <div className="run-agent-form">
        <textarea
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="Enter goal for autonomous agent..."
          rows={3}
        />
        <button onClick={runAgent} disabled={running || !goal.trim()}>
          {running ? 'Starting...' : 'Run Agent'}
        </button>
      </div>
      <AgentVisualization workspace={workspace} />
    </div>
  );
}
