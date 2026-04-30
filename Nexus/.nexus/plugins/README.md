# Nexus Plugins

Create custom plugins to extend Nexus with new tools, hooks, stances, and commands.

## Quick Start

1. Create a directory in `.nexus/plugins/`:
   ```
   .nexus/plugins/my_plugin/
   └── plugin.py
   ```

2. Create `plugin.py` with a class that inherits from `Plugin`:
   ```python
   from nexus.plugins.base import Plugin, NexusAPI, PluginMetadata

   class MyPlugin(Plugin):
       metadata = PluginMetadata(
           name="my_plugin",
           version="1.0.0",
           description="My custom plugin",
           author="Your Name",
       )

       def register(self, api: NexusAPI) -> None:
           # Register tools, hooks, stances, commands, panels
           api.register_tool("my_tool", MyTool, "Does something useful")
           api.register_hook("post_tool_call", self.my_hook)
           api.register_command("mycommand", self.my_handler, "My custom command")
   ```

3. Enable the plugin:
   ```bash
   nexus plugin enable my_plugin
   ```

## Plugin API Reference

### `api.register_tool(name, tool_class, description)`
Register a tool the agent can use. Tool class must have:
- `description` (str): Tool description
- `schema` (dict): Parameter descriptions
- `async def execute(self, **args) -> str`: Execution method

### `api.register_hook(event, callback, priority)`
Hook into Nexus events. Available events:
- `pre_tool_call` / `post_tool_call`
- `pre_llm_call` / `post_llm_call`
- `on_session_start` / `on_session_end`
- `on_goal_complete` / `on_error`
- `on_message_received` / `on_message_sent`

### `api.register_stance(name, system_prompt_modifier, model_override, temperature_override)`
Add a new conversation stance.

### `api.register_command(name, handler, description, aliases)`
Add a CLI/TUI command callable by the user.

### `api.register_panel(name, title, renderer, position)`
Add a panel to the TUI dashboard.

## Lifecycle Methods

Override these in your plugin class:
- `on_load()` — Called when plugin is loaded
- `on_enable()` — Called when plugin is enabled
- `on_disable()` — Called when plugin is disabled
- `on_unload()` — Called when plugin is unloaded
- `on_error(error)` — Called when an error occurs

## Best Practices

1. **Error isolation**: Wrap tool execution in try/except
2. **Async support**: Use `async def` for I/O operations
3. **No global state**: Store state in your plugin instance
4. **Clean teardown**: Release resources in `on_disable()`
5. **Metadata**: Fill in all metadata fields for discoverability
