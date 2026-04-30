import { useState, useEffect } from 'react';
import { nexusApi } from '../services/api';

interface DashboardPageProps {
  workspace: string;
}

export function DashboardPage({ workspace }: DashboardPageProps) {
  const [health, setHealth] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    nexusApi.health().then(setHealth).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading">Loading dashboard...</div>;

  return (
    <div className="page dashboard-page">
      <h1>Dashboard</h1>
      <div className="stats-grid">
        <div className="stat-card">
          <h3>Status</h3>
          <p className="stat-value">{String(health.status || 'unknown')}</p>
        </div>
        <div className="stat-card">
          <h3>Version</h3>
          <p className="stat-value">{String(health.version || 'N/A')}</p>
        </div>
        <div className="stat-card">
          <h3>Active Sessions</h3>
          <p className="stat-value">{String(health.active_sessions || 0)}</p>
        </div>
        <div className="stat-card">
          <h3>Active Agents</h3>
          <p className="stat-value">{String(health.active_agents || 0)}</p>
        </div>
      </div>
    </div>
  );
}
