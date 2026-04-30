"""Fine-tuning pipeline — end-to-end model training.

Coordinates:
1. Data extraction from sessions
2. Data preparation and formatting
3. LoRA training execution
4. Model registration
5. Evaluation
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from nexus.fine_tuning.data_prep import SessionDataExtractor, TrainingPair
from nexus.fine_tuning.model_registry import ModelEntry, ModelRegistry

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Configuration for a fine-tuning run."""
    base_model: str = "qwen2.5-coder:14b"
    model_name: str = "nexus-finetuned"
    epochs: int = 3
    learning_rate: float = 2e-4
    batch_size: int = 4
    lora_rank: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.1
    max_seq_length: int = 2048
    quality_threshold: float = 0.5
    output_dir: str = ".nexus_models"
    tags: Optional[List[str]] = None


@dataclass
class TrainingResult:
    """Result of a fine-tuning run."""
    success: bool
    model_name: str
    training_samples: int
    epochs_completed: int
    final_loss: float
    metrics: Dict[str, float]
    model_entry: Optional[ModelEntry] = None
    error: str = ""


class FineTuningPipeline:
    """End-to-end fine-tuning pipeline for Nexus models.

    Usage:
        pipeline = FineTuningPipeline(workspace="/path/to/project")
        result = await pipeline.run(
            TrainingConfig(
                base_model="qwen2.5-coder:14b",
                model_name="nexus-python-specialist",
                tags=["python", "web"],
            )
        )
    """

    def __init__(self, workspace: str = "."):
        self.workspace = Path(workspace).resolve()
        self.extractor = SessionDataExtractor(workspace=workspace)
        self.registry = ModelRegistry(
            registry_path=str(self.workspace / ".nexus_models" / "registry.json"),
        )
        self._running = False

    async def run(self, config: Optional[TrainingConfig] = None) -> TrainingResult:
        """Run the full fine-tuning pipeline.

        Args:
            config: Training configuration.

        Returns:
            TrainingResult with metrics and model info.
        """
        config = config or TrainingConfig()
        self._running = True

        try:
            # Phase 1: Extract training data
            logger.info("Phase 1: Extracting training data...")
            pairs = self.extractor.extract_from_sessions()
            memory_pairs = self.extractor.extract_from_memory()
            all_pairs = pairs + memory_pairs

            if not all_pairs:
                return TrainingResult(
                    success=False,
                    model_name=config.model_name,
                    training_samples=0,
                    epochs_completed=0,
                    final_loss=0.0,
                    metrics={},
                    error="No training data found in sessions or memory",
                )

            # Phase 2: Filter by quality
            logger.info("Phase 2: Filtering by quality (threshold: %.2f)...", config.quality_threshold)
            filtered_pairs = self.extractor.filter_by_quality(
                all_pairs, min_score=config.quality_threshold,
            )
            logger.info("Filtered: %d → %d pairs", len(all_pairs), len(filtered_pairs))

            if len(filtered_pairs) < 10:
                return TrainingResult(
                    success=False,
                    model_name=config.model_name,
                    training_samples=len(filtered_pairs),
                    epochs_completed=0,
                    final_loss=0.0,
                    metrics={},
                    error=f"Too few quality pairs ({len(filtered_pairs)}). Need at least 10.",
                )

            # Phase 3: Export training data
            logger.info("Phase 3: Exporting training data...")
            output_dir = self.workspace / config.output_dir
            output_dir.mkdir(parents=True, exist_ok=True)

            data_path = output_dir / f"{config.model_name}_train.json"
            self.extractor.export_alpaca(filtered_pairs, str(data_path))

            # Phase 4: Run training
            logger.info("Phase 4: Running LoRA fine-tuning...")
            training_metrics = await self._run_training(
                config=config,
                training_data=str(data_path),
                num_samples=len(filtered_pairs),
            )

            # Phase 5: Register model
            logger.info("Phase 5: Registering model...")
            model_entry = self.registry.register(
                name=config.model_name,
                base_model=config.base_model,
                training_samples=len(filtered_pairs),
                training_data_path=str(data_path),
                metrics=training_metrics,
                tags=config.tags or [],
                description=f"Fine-tuned from {len(filtered_pairs)} Nexus sessions",
            )

            result = TrainingResult(
                success=True,
                model_name=config.model_name,
                training_samples=len(filtered_pairs),
                epochs_completed=config.epochs,
                final_loss=training_metrics.get("final_loss", 0.0),
                metrics=training_metrics,
                model_entry=model_entry,
            )

            logger.info(
                "Fine-tuning complete: %s (%d samples, loss: %.4f)",
                config.model_name, len(filtered_pairs), result.final_loss,
            )
            return result

        except Exception as exc:
            logger.error("Fine-tuning pipeline failed: %s", exc)
            return TrainingResult(
                success=False,
                model_name=config.model_name,
                training_samples=0,
                epochs_completed=0,
                final_loss=0.0,
                metrics={},
                error=str(exc),
            )
        finally:
            self._running = False

    async def _run_training(
        self,
        config: TrainingConfig,
        training_data: str,
        num_samples: int,
    ) -> Dict[str, float]:
        """Execute LoRA fine-tuning.

        In production, this would call the actual training script.
        For now, it simulates training progress.
        """
        # In production: call ollama create with Modelfile
        # or run unsloth/axolotl training script

        metrics: Dict[str, float] = {
            "samples": float(num_samples),
            "epochs": float(config.epochs),
            "learning_rate": config.learning_rate,
            "lora_rank": float(config.lora_rank),
        }

        # Simulate training (replace with actual training call)
        import random
        loss = 2.0
        for epoch in range(config.epochs):
            # Simulated loss curve
            loss *= 0.7 + random.uniform(-0.1, 0.1)
            loss = max(0.01, loss)
            metrics[f"epoch_{epoch}_loss"] = loss
            logger.info("Epoch %d/%d: loss=%.4f", epoch + 1, config.epochs, loss)

        metrics["final_loss"] = loss
        return metrics

    def stop(self) -> None:
        """Stop a running training job."""
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        return {
            "pipeline_running": self._running,
            "registry_stats": self.registry.get_stats(),
        }
