#!/usr/bin/env python3
"""
Ultimate LoRA/QLoRA fine-tuning script for coding models.
"""

import argparse
from pathlib import Path
from typing import Optional, Tuple

import torch
from datasets import Dataset, load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from trl import SFTTrainer


def setup_model(model_name: str) -> Tuple:
    """Load the base model and tokenizer with QLoRA quantization."""
    print(f"Loading model: {model_name}")

    if not torch.cuda.is_available():
        print("Warning: CUDA not available. Training will be very slow and may not succeed.")

    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float16,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
    )

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=quantization_config,
        device_map="auto",
        trust_remote_code=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=True,
    )
    tokenizer.pad_token = tokenizer.eos_token

    return model, tokenizer


def setup_lora_config() -> LoraConfig:
    """Create a LoRA configuration optimized for coding tasks."""
    return LoraConfig(
        r=64,
        lora_alpha=16,
        target_modules=[
            "q_proj",
            "v_proj",
            "k_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        lora_dropout=0.1,
        bias="none",
        task_type="CAUSAL_LM",
    )


def load_code_dataset(dataset_name: Optional[str] = None) -> Dataset:
    """Load a coding dataset, or fallback to a built-in sample."""
    if dataset_name:
        print(f"Loading dataset: {dataset_name}")
        return load_dataset(dataset_name, split="train")

    print("Loading default coding dataset...")
    try:
        dataset = load_dataset("sahil2801/CodeAlpaca-20k", split="train")
        print(f"Loaded {len(dataset)} examples from CodeAlpaca")
        return dataset
    except Exception as exc:
        print(f"Warning: failed to load default dataset: {exc}")

    sample_data = [
        {
            "instruction": "Write a Python function to reverse a string",
            "output": "def reverse_string(s):\n    return s[::-1]",
        },
        {
            "instruction": "Create a Flask route that returns JSON",
            "output": (
                "from flask import jsonify\n\n"
                "@app.route('/api/data')\n"
                "def get_data():\n"
                "    return jsonify({'message': 'Hello World'})"
            ),
        },
    ]

    print("Using fallback dataset with sample coding examples.")
    return Dataset.from_list(sample_data)


def format_instruction(example: dict) -> dict:
    """Format instruction/output pairs for training."""
    return {
        "text": (
            "Below is an instruction that describes a task. Write a response that appropriately completes the request.\n\n"
            f"### Instruction:\n{example['instruction']}\n\n"
            f"### Response:\n{example['output']}"
        )
    }


def print_trainable_parameters(model) -> None:
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    all_params = sum(p.numel() for p in model.parameters())
    ratio = 100 * trainable_params / all_params if all_params else 0
    print(f"Trainable parameters: {trainable_params} / {all_params} ({ratio:.2f}%)")


def train_model(model, tokenizer, dataset: Dataset, output_dir: str) -> Path:
    """Run the fine-tuning workflow."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, setup_lora_config())
    print_trainable_parameters(model)

    formatted_dataset = dataset.map(format_instruction, remove_columns=dataset.column_names)

    training_args = TrainingArguments(
        output_dir=str(output_path),
        num_train_epochs=2,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=16,
        gradient_checkpointing=True,
        learning_rate=2e-4,
        logging_steps=10,
        save_steps=500,
        save_strategy="steps",
        save_total_limit=3,
        fp16=torch.cuda.is_available(),
        logging_dir=str(output_path / "logs"),
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        args=training_args,
        train_dataset=formatted_dataset,
        dataset_text_field="text",
    )

    print("Starting training...")
    trainer.train()

    adapter_path = output_path / "adapter"
    model.save_pretrained(adapter_path)
    tokenizer.save_pretrained(adapter_path)

    print(f"Training complete! Adapter saved to: {adapter_path}")
    return adapter_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a LoRA adapter for a coding model.")
    parser.add_argument(
        "--model-name",
        default="Qwen/Qwen2.5-Coder-7B",
        help="Base model identifier for transformers",
    )
    parser.add_argument(
        "--dataset",
        default=None,
        help="Hugging Face dataset name to use for training",
    )
    parser.add_argument(
        "--output-dir",
        default="./output",
        help="Directory to save LoRA adapter and tokenizer",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("🚀 Starting Ultimate LLM Fine-Tuning for Coding")
    model, tokenizer = setup_model(args.model_name)
    dataset = load_code_dataset(args.dataset)
    adapter_path = train_model(model, tokenizer, dataset, args.output_dir)

    print("\n✅ Fine-tuning complete!")
    print(f"📁 Adapter location: {adapter_path}")
    print("🔄 Next steps:")
    print("1. Convert to GGUF format for Ollama")
    print("2. Create Ollama Modelfile")
    print("3. Test the fine-tuned model")


if __name__ == "__main__":
    main()
