# Ultimate Fine-Tuning Setup for Local LLMs

This directory contains tools for LoRA/QLoRA fine-tuning of coding-focused language models.

## Requirements

- Python 3.8+
- CUDA-compatible GPU (strongly recommended)
- 16GB+ RAM
- 50GB+ disk space

## Install dependencies

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install transformers peft bitsandbytes accelerate trl datasets wandb
```

## Choose a base model

Recommended models:

- `Qwen/Qwen2.5-Coder-7B` - best for coding
- `meta-llama/Llama-2-7b-hf` - balanced
- `microsoft/phi-2` - fast and reliable

## Prepare dataset

Use a dataset like CodeAlpaca or create your own in the format:

```json
[
  {"instruction": "...", "output": "..."},
  ...
]
```

## Run training

```bash
python train_lora.py --model-name Qwen/Qwen2.5-Coder-7B --output-dir ./output
```

## Convert to Ollama format

```bash
python convert_to_gguf.py --base-model /path/to/base-model.gguf --adapter ./output/adapter --output ./fine_tuned.gguf
```

## Create an Ollama Modelfile

Example `Modelfile`:

```text
FROM ./base-model.gguf
ADAPTER ./fine_tuned.gguf
SYSTEM "You are an expert autonomous coding agent..."
```

## Register the model

```bash
ollama create my-coder -f Modelfile
```
