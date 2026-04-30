"""Model Registry — manage fine-tuned models.

Stores, loads, and tracks fine-tuned model variants:
- Model metadata (base model, training data, metrics)
- Version tracking
- Selection and comparison
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelEntry:
    """Registry entry for a fine-tuned model."""
    name: str
    base_model: str
    version: str
    created_at: float
    training_samples: int
    training_data_path: str
    metrics: Dict[str, float] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    description: str = ""
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "base_model": self.base_model,
            "version": self.version,
            "created_at": self.created_at,
            "training_samples": self.training_samples,
            "training_data_path": self.training_data_path,
            "metrics": self.metrics,
            "tags": self.tags,
            "description": self.description,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelEntry":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class ModelRegistry:
    """Registry for fine-tuned models.

    Persists model metadata to disk and provides:
    - Registration of new models
    - Version management
    - Model selection
    - Comparison between variants
    """

    def __init__(self, registry_path: Optional[str] = None):
        self.registry_path = Path(registry_path) if registry_path else Path(".nexus_models/registry.json")
        self._models: List[ModelEntry] = []
        self._load()

    def register(
        self,
        name: str,
        base_model: str,
        training_samples: int,
        training_data_path: str,
        metrics: Optional[Dict[str, float]] = None,
        tags: Optional[List[str]] = None,
        description: str = "",
    ) -> ModelEntry:
        """Register a new fine-tuned model.

        Args:
            name: Model name (e.g., "nexus-python-specialist").
            base_model: Base model used for fine-tuning.
            training_samples: Number of training examples.
            training_data_path: Path to training data file.
            metrics: Training/evaluation metrics.
            tags: Model tags.
            description: Model description.

        Returns:
            The registered ModelEntry.
        """
        # Auto-version
        existing = [m for m in self._models if m.name == name]
        version = f"v{len(existing) + 1}"

        entry = ModelEntry(
            name=name,
            base_model=base_model,
            version=version,
            created_at=time.time(),
            training_samples=training_samples,
            training_data_path=training_data_path,
            metrics=metrics or {},
            tags=tags or [],
            description=description,
        )

        self._models.append(entry)
        self._save()

        logger.info(
            "Registered model: %s %s (%d samples)",
            name, version, training_samples,
        )
        return entry

    def get(self, name: str) -> Optional[ModelEntry]:
        """Get a model by name (latest version)."""
        matches = [m for m in self._models if m.name == name and m.active]
        if not matches:
            return None
        return max(matches, key=lambda m: m.created_at)

    def list_models(self, active_only: bool = True) -> List[ModelEntry]:
        """List registered models."""
        if active_only:
            return [m for m in self._models if m.active]
        return list(self._models)

    def get_by_tag(self, tag: str) -> List[ModelEntry]:
        """Get models with a specific tag."""
        return [m for m in self._models if tag in m.tags and m.active]

    def compare(self, names: List[str]) -> Dict[str, Dict[str, Any]]:
        """Compare multiple models."""
        result = {}
        for name in names:
            model = self.get(name)
            if model:
                result[name] = {
                    "version": model.version,
                    "base_model": model.base_model,
                    "training_samples": model.training_samples,
                    "metrics": model.metrics,
                    "created": time.strftime("%Y-%m-%d", time.localtime(model.created_at)),
                }
        return result

    def deactivate(self, name: str) -> bool:
        """Deactivate a model."""
        for model in self._models:
            if model.name == name:
                model.active = False
                self._save()
                return True
        return False

    def _save(self) -> None:
        """Persist registry to disk."""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        data = [m.to_dict() for m in self._models]
        self.registry_path.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )

    def _load(self) -> None:
        """Load registry from disk."""
        if self.registry_path.exists():
            try:
                data = json.loads(self.registry_path.read_text(encoding="utf-8"))
                self._models = [ModelEntry.from_dict(d) for d in data]
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load model registry: %s", exc)
                self._models = []

    @property
    def model_count(self) -> int:
        return len(self._models)

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        return {
            "total_models": len(self._models),
            "active_models": sum(1 for m in self._models if m.active),
            "total_training_samples": sum(m.training_samples for m in self._models),
            "models": [m.to_dict() for m in self._models],
        }
