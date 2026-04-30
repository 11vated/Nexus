"""Training data format converters.

Supports multiple fine-tuning data formats:
- Alpaca (instruction/input/output JSON)
- OpenAI (chat completion JSONL)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class AlpacaFormat:
    """Alpaca-style instruction tuning format."""

    @staticmethod
    def convert(
        instruction: str,
        output: str,
        input_text: str = "",
    ) -> Dict[str, str]:
        return {
            "instruction": instruction,
            "input": input_text,
            "output": output,
        }

    @staticmethod
    def export(pairs: List[Dict[str, str]], output_path: str) -> int:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(
            json.dumps(pairs, indent=2),
            encoding="utf-8",
        )
        return len(pairs)

    @staticmethod
    def load(input_path: str) -> List[Dict[str, str]]:
        data = Path(input_path).read_text(encoding="utf-8")
        return json.loads(data)


class OpenAIFormat:
    """OpenAI chat completion fine-tuning format (JSONL)."""

    @staticmethod
    def convert(
        instruction: str,
        output: str,
        system_prompt: str = "You are Nexus, a helpful AI coding assistant.",
    ) -> Dict[str, List[Dict[str, str]]]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": instruction},
            {"role": "assistant", "content": output},
        ]
        return {"messages": messages}

    @staticmethod
    def export(
        pairs: List[Dict[str, List[Dict[str, str]]]],
        output_path: str,
    ) -> int:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for pair in pairs:
                f.write(json.dumps(pair) + "\n")
        return len(pairs)

    @staticmethod
    def load(input_path: str) -> List[Dict[str, Any]]:
        pairs = []
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    pairs.append(json.loads(line))
        return pairs
