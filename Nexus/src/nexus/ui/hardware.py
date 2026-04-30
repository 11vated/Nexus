"""Hardware detection and auto model routing.

Detects the user's hardware (RAM, CPU, GPU) and software (Ollama, models),
then recommends optimal models and routing configuration.
"""
from __future__ import annotations

import platform
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Hardware profiles
# ---------------------------------------------------------------------------

@dataclass
class HardwareProfile:
    """Detected hardware capabilities."""
    os_name: str = ""
    os_version: str = ""
    arch: str = ""
    cpu_count: int = 0
    cpu_name: str = ""
    ram_total_gb: float = 0.0
    ram_available_gb: float = 0.0
    gpu_name: str = ""
    gpu_vram_gb: float = 0.0
    has_gpu: bool = False
    disk_free_gb: float = 0.0

    @property
    def tier(self) -> str:
        """Classify hardware into tiers for model recommendations."""
        if self.gpu_vram_gb >= 24 or self.ram_total_gb >= 64:
            return "enthusiast"
        elif self.gpu_vram_gb >= 12 or self.ram_total_gb >= 32:
            return "high"
        elif self.gpu_vram_gb >= 6 or self.ram_total_gb >= 16:
            return "mid"
        else:
            return "low"

    @property
    def max_model_size_gb(self) -> float:
        """Maximum model size that can reasonably run on this hardware."""
        if self.gpu_vram_gb > 0:
            # Use 80% of VRAM for model (leave room for context)
            return self.gpu_vram_gb * 0.8
        else:
            # CPU inference can use more RAM via memory mapping and swap.
            # Use 70% of total RAM (not just available) since OS will page.
            return self.ram_total_gb * 0.7


# ---------------------------------------------------------------------------
# Hardware detection
# ---------------------------------------------------------------------------

def detect_hardware() -> HardwareProfile:
    """Detect system hardware capabilities."""
    profile = HardwareProfile()

    # OS info
    profile.os_name = platform.system()
    profile.os_version = platform.version()
    profile.arch = platform.machine()

    # CPU
    profile.cpu_count = _detect_cpu_count()
    profile.cpu_name = _detect_cpu_name()

    # RAM
    profile.ram_total_gb, profile.ram_available_gb = _detect_ram()

    # GPU
    profile.has_gpu, profile.gpu_name, profile.gpu_vram_gb = _detect_gpu()

    # Disk
    profile.disk_free_gb = _detect_disk_free()

    return profile


def _detect_cpu_count() -> int:
    """Detect CPU core count."""
    try:
        import multiprocessing
        return multiprocessing.cpu_count()
    except Exception:
        return 1


def _detect_cpu_name() -> str:
    """Detect CPU model name."""
    try:
        if platform.system() == "Windows":
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            )
            name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            winreg.CloseKey(key)
            return name.strip()
        elif platform.system() == "Darwin":
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip()
        else:
            result = subprocess.run(
                ["cat", "/proc/cpuinfo"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split("\n"):
                if "model name" in line:
                    return line.split(":")[1].strip()
    except Exception:
        pass
    return "Unknown CPU"


def _detect_ram() -> Tuple[float, float]:
    """Detect total and available RAM in GB."""
    try:
        if platform.system() == "Windows":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            c_ulonglong = ctypes.c_ulonglong

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", c_ulonglong),
                    ("ullAvailPhys", c_ulonglong),
                    ("ullTotalPageFile", c_ulonglong),
                    ("ullAvailPageFile", c_ulonglong),
                    ("ullTotalVirtual", c_ulonglong),
                    ("ullAvailVirtual", c_ulonglong),
                    ("ullExtendedVirtual", c_ulonglong),
                ]

            mem = MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))

            total_gb = mem.ullTotalPhys / (1024**3)
            avail_gb = mem.ullAvailPhys / (1024**3)
            return total_gb, avail_gb

        elif platform.system() == "Darwin":
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=5
            )
            total_gb = int(result.stdout.strip()) / (1024**3)
            # macOS available is harder to get, estimate 60%
            return total_gb, total_gb * 0.6

        else:
            # Linux
            total_gb = _read_meminfo_linux("MemTotal")
            avail_gb = _read_meminfo_linux("MemAvailable")
            return total_gb, avail_gb
    except Exception:
        return 8.0, 4.0  # Safe default


def _read_meminfo_linux(key: str) -> float:
    """Read a value from /proc/meminfo on Linux."""
    with open("/proc/meminfo", "r") as f:
        for line in f:
            if line.startswith(key):
                # Value is in kB
                parts = line.split()
                return int(parts[1]) / (1024 * 1024)  # kB -> GB
    return 0.0


def _detect_gpu() -> Tuple[bool, str, float]:
    """Detect GPU name and VRAM in GB."""
    has_gpu = False
    gpu_name = ""
    vram_gb = 0.0

    try:
        if platform.system() == "Windows":
            # Try nvidia-smi
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                has_gpu = True
                lines = result.stdout.strip().split("\n")
                parts = lines[0].split(",")
                gpu_name = parts[0].strip()
                vram_gb = float(parts[1].strip()) / 1024
                return has_gpu, gpu_name, vram_gb

            # Try wmic as fallback
            result = subprocess.run(
                ["wmic", "path", "win32_videocontroller", "get", "name"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if len(lines) > 1:
                    has_gpu = True
                    gpu_name = lines[1].strip()
        elif platform.system() == "Darwin":
            # Apple Silicon has unified memory (already counted in RAM)
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "Chipset Model" in line:
                        gpu_name = line.split(":")[1].strip()
                        has_gpu = bool(gpu_name)
                        if "Apple" in gpu_name:
                            # Unified memory - already counted in RAM
                            vram_gb = 0.0
        else:
            # Linux - try nvidia-smi
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                has_gpu = True
                lines = result.stdout.strip().split("\n")
                parts = lines[0].split(",")
                gpu_name = parts[0].strip()
                vram_gb = float(parts[1].strip()) / 1024
                return has_gpu, gpu_name, vram_gb

            # Try lspci
            result = subprocess.run(
                ["lspci"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "VGA" in line or "3D" in line:
                        gpu_name = line.split(":")[2].strip() if ":" in line else line
                        has_gpu = True
                        break
    except Exception:
        pass

    return has_gpu, gpu_name, vram_gb


def _detect_disk_free() -> float:
    """Detect free disk space in GB for the current directory."""
    try:
        if platform.system() == "Windows":
            import ctypes
            free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                ctypes.c_wchar_p("."),
                None, None, ctypes.byref(free_bytes)
            )
            return free_bytes.value / (1024**3)
        else:
            import shutil
            total, used, free = shutil.disk_usage(".")
            return free / (1024**3)
    except Exception:
        return 10.0  # Safe default


# ---------------------------------------------------------------------------
# Model size database (approximate sizes for common quantizations)
# ---------------------------------------------------------------------------

MODEL_SIZES_GB: Dict[str, float] = {
    # Small models
    "qwen2.5-coder:1.5b": 1.0,
    "deepseek-r1:1.5b": 1.0,
    "gemma4:e2b": 2.0,
    # Medium models
    "qwen2.5-coder:7b": 4.5,
    "deepseek-r1:7b": 4.5,
    "codellama:7b": 3.8,
    "dolphin-mistral:7b": 4.1,
    "gemma4:e4b": 8.0,
    # Large models
    "qwen2.5-coder:14b": 9.0,
    "qwen2.5-coder:14b-instruct-q4_K_M": 9.0,
    "gemma4:26b": 18.0,
    # Vision models
    "llava:latest": 4.7,
    "moondream:latest": 1.7,
}


# ---------------------------------------------------------------------------
# Recommendations engine
# ---------------------------------------------------------------------------

@dataclass
class ModelRecommendation:
    """A model recommendation with reasoning."""
    model: str
    purpose: str
    reason: str
    fits: bool  # Whether it fits on this hardware
    expected_speed: str  # "fast", "medium", "slow"


def get_recommendations(hardware: HardwareProfile) -> Dict[str, List[ModelRecommendation]]:
    """Get model recommendations based on hardware profile.

    Returns a dict with categories:
    - "best_overall": Best all-purpose model
    - "fastest": Fastest model for quick tasks
    - "smartest": Most capable model that fits
    - "all": All models that fit, sorted by capability
    """
    max_size = hardware.max_model_size_gb
    tier = hardware.tier

    recommendations: Dict[str, List[ModelRecommendation]] = {
        "best_overall": [],
        "fastest": [],
        "smartest": [],
        "all": [],
    }

    all_recs: List[Tuple[str, str, str, str]] = [
        # (model, purpose, reason_when_fits, speed)
        ("qwen2.5-coder:14b", "Best code generation", "14B code model, highest quality", "medium"),
        ("qwen2.5-coder:7b", "Fast code tasks", "7B code model, good balance", "fast"),
        ("qwen2.5-coder:1.5b", "Ultra-fast tasks", "Tiny code model for quick edits", "fast"),
        ("deepseek-r1:7b", "Deep reasoning", "7B reasoning model with chain-of-thought", "medium"),
        ("deepseek-r1:1.5b", "Quick reasoning", "Tiny reasoning model", "fast"),
        ("gemma4:26b", "Heavy reasoning", "26B model for complex architecture decisions", "slow"),
        ("gemma4:e4b", "Documentation & planning", "8B balanced model for text tasks", "medium"),
        ("gemma4:e2b", "Summaries & light tasks", "5B model for quick text processing", "fast"),
        ("codellama:7b", "Code review", "Meta's code model, great for review", "fast"),
        ("dolphin-mistral:7b", "Creative & brainstorming", "Uncensored model for creative tasks", "fast"),
        ("llava:latest", "Vision tasks", "Multimodal model for image understanding", "medium"),
        ("moondream:latest", "Fast vision", "Tiny vision model for quick image analysis", "fast"),
    ]

    fitting_models: List[ModelRecommendation] = []

    for model, purpose, reason, speed in all_recs:
        size_gb = MODEL_SIZES_GB.get(model, 10.0)  # Default assume large
        fits = size_gb <= max_size

        if fits:
            expected = speed
            rec = ModelRecommendation(
                model=model,
                purpose=purpose,
                reason=reason,
                fits=True,
                expected_speed=expected,
            )
            fitting_models.append(rec)

            # Categorize
            if "14b" in model or "26b" in model:
                recommendations["smartest"].append(rec)
            if "1.5b" in model or "e2b" in model:
                recommendations["fastest"].append(rec)
            if "7b" in model and "coder" in model:
                recommendations["best_overall"].append(rec)

    # Fallbacks if no specific category matched
    if not recommendations["best_overall"] and fitting_models:
        # Pick the medium-sized code model
        for m in fitting_models:
            if "coder" in m.model or "code" in m.purpose.lower():
                recommendations["best_overall"].append(m)
                break
        if not recommendations["best_overall"]:
            recommendations["best_overall"].append(fitting_models[0])

    if not recommendations["fastest"] and fitting_models:
        # Pick the smallest model
        recommendations["fastest"].append(fitting_models[-1])

    if not recommendations["smartest"] and fitting_models:
        # Pick the largest fitting model
        recommendations["smartest"].append(fitting_models[0])

    recommendations["all"] = fitting_models

    return recommendations


def generate_routing_config(hardware: HardwareProfile) -> Dict[str, str]:
    """Generate optimal model routing configuration for this hardware.

    Returns a dict mapping task types to model names.
    """
    recs = get_recommendations(hardware)
    all_models = [r.model for r in recs["all"]]
    max_size = hardware.max_model_size_gb

    # Helper: pick best model matching criteria
    def pick_model(preferences: List[str], fallback: str) -> str:
        for pref in preferences:
            if pref in all_models:
                return pref
        # If none of the preferred models fit, find the largest fitting one
        for model in all_models:
            size = MODEL_SIZES_GB.get(model, 10.0)
            if size <= max_size:
                return model
        return fallback

    # Code generation: prefer largest coder model that fits
    code_prefs = ["qwen2.5-coder:14b", "qwen2.5-coder:7b", "qwen2.5-coder:1.5b"]
    code_model = pick_model(code_prefs, "qwen2.5-coder:7b")

    # Planning: prefer reasoning model
    planning_prefs = ["deepseek-r1:7b", "gemma4:e4b", "gemma4:e2b"]
    planning_model = pick_model(planning_prefs, "gemma4:e4b")

    # Architecture: prefer largest model
    arch_prefs = ["gemma4:26b", "qwen2.5-coder:14b", "deepseek-r1:7b", "gemma4:e4b"]
    arch_model = pick_model(arch_prefs, "gemma4:e4b")

    # Fast tasks: prefer smallest
    fast_prefs = ["qwen2.5-coder:1.5b", "gemma4:e2b", "deepseek-r1:1.5b"]
    fast_model = pick_model(fast_prefs, "qwen2.5-coder:1.5b")

    # Build routing map
    routing = {
        "code_generation": code_model,
        "code_review": "codellama:7b" if "codellama:7b" in all_models else code_model,
        "code_edit": fast_model,
        "planning": planning_model,
        "reasoning": planning_model,
        "architecture": arch_model,
        "ui_generation": code_model,
        "documentation": "gemma4:e4b" if "gemma4:e4b" in all_models else fast_model,
        "summarize": "gemma4:e2b" if "gemma4:e2b" in all_models else fast_model,
        "chat": code_model,
        "shell_command": fast_model,
    }

    return routing


def print_hardware_report(hardware: HardwareProfile) -> str:
    """Generate a human-readable hardware report."""
    lines = [
        "=" * 60,
        "  NEXUS HARDWARE REPORT",
        "=" * 60,
        "",
        f"  OS:          {hardware.os_name} {hardware.os_version}",
        f"  Arch:        {hardware.arch}",
        f"  CPU:         {hardware.cpu_name} ({hardware.cpu_count} cores)",
        f"  RAM:         {hardware.ram_total_gb:.1f} GB total, {hardware.ram_available_gb:.1f} GB available",
    ]

    if hardware.has_gpu:
        lines.append(f"  GPU:         {hardware.gpu_name} ({hardware.gpu_vram_gb:.1f} GB VRAM)")
    else:
        lines.append("  GPU:         None detected (CPU inference only)")

    lines.extend([
        f"  Disk free:   {hardware.disk_free_gb:.1f} GB",
        f"  Hardware tier: {hardware.tier.upper()}",
        f"  Max model:   ~{hardware.max_model_size_gb:.1f} GB",
        "",
    ])

    return "\n".join(lines)


def print_recommendation_report(hardware: HardwareProfile) -> str:
    """Generate a human-readable recommendation report."""
    recs = get_recommendations(hardware)

    lines = [
        "=" * 60,
        "  NEXUS MODEL RECOMMENDATIONS",
        f"  (Hardware tier: {hardware.tier.upper()})",
        "=" * 60,
        "",
        f"  Best overall:   {recs['best_overall'][0].model if recs['best_overall'] else 'N/A'}",
        f"                  {recs['best_overall'][0].purpose if recs['best_overall'] else ''}",
        "",
        f"  Fastest:        {recs['fastest'][0].model if recs['fastest'] else 'N/A'}",
        f"                  {recs['fastest'][0].purpose if recs['fastest'] else ''}",
        "",
        f"  Smartest:       {recs['smartest'][0].model if recs['smartest'] else 'N/A'}",
        f"                  {recs['smartest'][0].purpose if recs['smartest'] else ''}",
        "",
        "  All compatible models:",
    ]

    for rec in recs["all"]:
        lines.append(f"    + {rec.model}")
        lines.append(f"      Purpose: {rec.purpose}")
        lines.append(f"      Speed: {rec.expected_speed}")

    lines.append("")
    lines.append("  Recommended routing:")
    routing = generate_routing_config(hardware)
    for task, model in routing.items():
        lines.append(f"    {task}: {model}")

    lines.append("")
    return "\n".join(lines)
