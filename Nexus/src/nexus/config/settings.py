from pathlib import Path
from typing import Optional, Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class NexusConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore"
    )

    workspace_root: Path = Field(
        default=Path.cwd() / "workspace",
        description="Root workspace directory for Nexus"
    )
    tools_dir: Path = Field(
        default=Path.cwd() / "tools",
        description="Directory for external tool executables"
    )
    logs_dir: Path = Field(
        default=Path.cwd() / "logs",
        description="Directory for log files"
    )

    opencode_path: Optional[Path] = Field(
        default=None,
        description="Path to OpenCode executable"
    )
    aider_path: Optional[Path] = Field(
        default=None,
        description="Path to Aider executable"
    )
    goose_path: Optional[Path] = Field(
        default=None,
        description="Path to Goose executable"
    )

    default_model: str = Field(
        default="qwen2.5-coder:14b",
        description="Default Ollama model"
    )
    ollama_url: str = Field(
        default="http://localhost:11434",
        description="Ollama server URL"
    )
    model_timeout_seconds: int = Field(
        default=120,
        description="Timeout for model queries"
    )

    api_keys_encryption_key: Optional[str] = Field(
        default=None,
        description="Encryption key for API keys"
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging level"
    )
    max_concurrent_tools: int = Field(
        default=4,
        description="Maximum concurrent tool executions"
    )
    enable_telemetry: bool = Field(
        default=False,
        description="Enable anonymous telemetry"
    )

    def find_tool(self, tool_name: str) -> Optional[Path]:
        """Find tool in PATH or configured directories."""
        import shutil
        exe = shutil.which(tool_name)
        if exe:
            return Path(exe)
        
        check_path = getattr(self, f"{tool_name}_path", None)
        if check_path and check_path.exists():
            return check_path
        
        if tool_name == "opencode" and self.opencode_path:
            return self.opencode_path
        if tool_name == "aider" and self.aider_path:
            return self.aider_path
        if tool_name == "goose" and self.goose_path:
            return self.goose_path
        
        return None


config = NexusConfig()