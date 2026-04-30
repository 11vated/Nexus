"""Fine-Tuning Pipeline for Nexus.

Enables training custom models on session data:
1. Extract training data from conversations
2. Format as Alpaca/OpenAI instruction format
3. Run LoRA fine-tuning with Ollama
4. Register and manage fine-tuned models
5. Auto-trigger retraining based on performance
"""

from nexus.fine_tuning.pipeline import FineTuningPipeline
from nexus.fine_tuning.data_prep import SessionDataExtractor
from nexus.fine_tuning.model_registry import ModelRegistry
from nexus.fine_tuning.triggers import RetrainingTrigger

__all__ = [
    "FineTuningPipeline",
    "SessionDataExtractor",
    "ModelRegistry",
    "RetrainingTrigger",
]
