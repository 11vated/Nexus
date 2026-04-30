import { useState, useEffect } from 'react';
import { nexusApi, PluginInfo } from '../services/api';

interface PluginsPageProps {
  workspace: string;
}

export function PluginsPage({ workspace }: PluginsPageProps) {
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [loading, setLoading] = useState(true);

  const loadPlugins = async () => {
    try {
      const list = await nexusApi.listPlugins(workspace);
      setPlugins(list);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPlugins();
  }, [workspace]);

  const togglePlugin = async (plugin: PluginInfo) => {
    try {
      await nexusApi.enablePlugin(plugin.name, workspace);
      loadPlugins();
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) return <div className="loading">Loading plugins...</div>;

  if (plugins.length === 0) {
    return (
      <div className="page plugins-page">
        <h1>Plugins</h1>
        <div className="empty-state">
          <p>No plugins found. Create one in <code>.nexus/plugins/</code></p>
        </div>
      </div>
    );
  }

  return (
    <div className="page plugins-page">
      <h1>Plugins</h1>
      <div className="plugin-list">
        {plugins.map((plugin) => (
          <div key={plugin.name} className="plugin-card">
            <div className="plugin-header">
              <h3>{plugin.name}</h3>
              <span className={`version-badge`}>v{plugin.version}</span>
              <span className={`status-badge ${plugin.enabled ? 'enabled' : 'disabled'}`}>
                {plugin.enabled ? 'Enabled' : 'Disabled'}
              </span>
            </div>
            <p className="plugin-desc">{plugin.description}</p>
            {plugin.tags.length > 0 && (
              <div className="plugin-tags">
                {plugin.tags.map((tag) => (
                  <span key={tag} className="tag">{tag}</span>
                ))}
              </div>
            )}
            <button onClick={() => togglePlugin(plugin)} className="plugin-action">
              {plugin.enabled ? 'Disable' : 'Enable'}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
