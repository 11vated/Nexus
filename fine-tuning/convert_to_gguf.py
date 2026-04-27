#!/usr/bin/env python3
"""
Convert a LoRA adapter to GGUF format for Ollama.
"""

import argparse
import subprocess
from pathlib import Path


def find_export_binary(llama_cpp_dir: Path) -> Path | None:
    candidates = [llama_cpp_dir / "export-lora", llama_cpp_dir / "export-lora.exe"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def print_instructions(base_model_path: str, adapter_path: str, output_path: str) -> None:
    print("\n📋 Manual conversion steps:")
    print("1. Install llama.cpp:")
    print("   git clone https://github.com/ggerganov/llama.cpp")
    print("   cd llama.cpp && make")
    print("")
    print("2. Convert the base model to GGUF if needed:")
    print(f"   python convert.py {base_model_path}")
    print("")
    print("3. Apply the LoRA adapter with llama.cpp export-lora:")
    print(f"   ./llama.cpp/export-lora {base_model_path} {adapter_path} {output_path}")
    print("")
    print("4. Create an Ollama Modelfile:")
    print("   FROM ./output.gguf")
    print("   ADAPTER ./adapter.gguf")
    print("   SYSTEM 'You are an expert autonomous coding agent...' ")
    print("")
    print("5. Register the model in Ollama:")
    print("   ollama create my-coder -f Modelfile")


def convert_to_gguf(base_model_path: str, adapter_path: str, output_path: str, llama_cpp_dir: str) -> None:
    print(f"Converting LoRA adapter to GGUF...")
    print(f"Base model: {base_model_path}")
    print(f"Adapter: {adapter_path}")
    print(f"Output: {output_path}")

    llama_cpp_path = Path(llama_cpp_dir).expanduser().resolve()
    export_binary = find_export_binary(llama_cpp_path)

    if export_binary is None:
        print("\nCould not find export-lora in llama.cpp.\n")
        print_instructions(base_model_path, adapter_path, output_path)
        return

    print(f"Found export binary: {export_binary}")

    command = [str(export_binary), str(base_model_path), str(adapter_path), str(output_path)]
    print(f"Running: {' '.join(command)}")
    subprocess.run(command, check=True)
    print(f"Conversion finished: {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert LoRA adapter to GGUF for Ollama")
    parser.add_argument("--base-model", required=True, help="Path to the base GGUF model or model directory")
    parser.add_argument("--adapter", required=True, help="Path to the LoRA adapter directory")
    parser.add_argument("--output", required=True, help="Path to write the output GGUF file")
    parser.add_argument(
        "--llama-cpp-dir",
        default="llama.cpp",
        help="Path to the llama.cpp repository containing export-lora",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    convert_to_gguf(args.base_model, args.adapter, args.output, args.llama_cpp_dir)


if __name__ == "__main__":
    main()
