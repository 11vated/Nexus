import { useState } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { ChatPage } from './pages/Chat';
import { DashboardPage } from './pages/Dashboard';
import { AgentsPage } from './pages/Agents';
import { PluginsPage } from './pages/Plugins';
import './App.css';

function Navigation() {
  const location = useLocation();

  const links = [
    { path: '/', label: 'Chat' },
    { path: '/dashboard', label: 'Dashboard' },
    { path: '/agents', label: 'Agents' },
    { path: '/plugins', label: 'Plugins' },
  ];

  return (
    <nav className="sidebar">
      <div className="sidebar-header">
        <h2>Nexus AI</h2>
      </div>
      <ul className="nav-links">
        {links.map((link) => (
          <li key={link.path}>
            <Link
              to={link.path}
              className={location.pathname === link.path ? 'active' : ''}
            >
              {link.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function AppContent() {
  const [workspace, setWorkspace] = useState('.');

  return (
    <div className="app-layout">
      <Navigation />
      <main className="main-content">
        <div className="top-bar">
          <label>
            Workspace:
            <input
              value={workspace}
              onChange={(e) => setWorkspace(e.target.value)}
              placeholder="/path/to/project"
            />
          </label>
        </div>
        <Routes>
          <Route path="/" element={<ChatPage workspace={workspace} />} />
          <Route path="/dashboard" element={<DashboardPage workspace={workspace} />} />
          <Route path="/agents" element={<AgentsPage workspace={workspace} />} />
          <Route path="/plugins" element={<PluginsPage workspace={workspace} />} />
        </Routes>
      </main>
    </div>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}
