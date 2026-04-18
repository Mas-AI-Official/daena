"""One-click installer for Daena's local real-time voice brains.

Usage::

    python backend/scripts/install_voice_brains.py --brain moshi
    python backend/scripts/install_voice_brains.py --brain qwen-omni
    python backend/scripts/install_voice_brains.py --brain glm-voice
    python backend/scripts/install_voice_brains.py --brain all

What it does
------------
1. Detects platform (Windows / macOS / Linux) and GPU (CUDA / MPS / CPU).
2. pip-installs the brain's Python deps using the ACTIVE interpreter.
3. Pre-pulls model weights via huggingface_hub.
4. Runs a ~5-second smoke test to confirm the brain loads and emits
   one TurnEvent end-to-end.

Model sizes (first-pull bandwidth):
    Moshi (bf16)        ~15 GB
    Moshi (int4 MLX)    ~4 GB   -- MacBook-sized
    Qwen 3.5-Omni       ~30 GB
    GLM-4-Voice         ~9 GB

Runs in the Daena venv. After success, set the env var::

    DAENA_VOICE_BRAIN=moshi   # or qwen-omni / glm-voice

...and restart the backend. ``/runtimes/voice`` will then report the
brain as ``status: ready``.
"""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class BrainInstallPlan:
    name: str
    pip_packages: list[str]
    hf_repos: list[str]       # pre-pull these model repos
    gpu_required: bool
    min_ram_gb: int


_PLANS: dict[str, BrainInstallPlan] = {
    "moshi": BrainInstallPlan(
        name="moshi",
        pip_packages=(
            ["moshi_mlx"] if platform.system() == "Darwin"
            else ["moshi", "torch", "torchaudio"]
        ),
        hf_repos=["kyutai/moshika-pytorch-bf16"],
        gpu_required=False,  # int4 MLX or int8 CPU both viable
        min_ram_gb=16,
    ),
    "qwen-omni": BrainInstallPlan(
        name="qwen-omni",
        pip_packages=["transformers", "accelerate", "torch", "soundfile", "librosa"],
        hf_repos=["Qwen/Qwen3.5-Omni-7B"],
        gpu_required=True,   # 30GB model, basically needs CUDA
        min_ram_gb=32,
    ),
    "glm-voice": BrainInstallPlan(
        name="glm-voice",
        pip_packages=["transformers", "torch", "soundfile"],
        hf_repos=["THUDM/glm-4-voice-9b", "zai-org/glm-4-voice-decoder"],
        gpu_required=True,
        min_ram_gb=24,
    ),
}


def _run(cmd: list[str]) -> int:
    """Run a shell command; stream output; return exit code."""
    print(f"\n$ {' '.join(cmd)}")
    return subprocess.call(cmd)


def install_brain(brain_name: str, *, skip_weights: bool = False) -> int:
    """Install one brain. Returns 0 on success."""
    plan = _PLANS.get(brain_name)
    if plan is None:
        print(f"Unknown brain: {brain_name}. Options: {list(_PLANS)}")
        return 2

    print(f"=== Installing {brain_name} ===")
    print(f"Platform: {platform.system()} / Python {sys.version.split()[0]}")

    # Step 1: pip install
    rc = _run([sys.executable, "-m", "pip", "install", "-U", *plan.pip_packages])
    if rc != 0:
        print(f"pip install failed (exit {rc})")
        return rc

    if skip_weights:
        print("--skip-weights set; not pre-pulling model weights.")
    else:
        # Step 2: pre-pull HF weights
        try:
            from huggingface_hub import snapshot_download
        except ImportError:
            _run([sys.executable, "-m", "pip", "install", "-U", "huggingface_hub"])
            from huggingface_hub import snapshot_download  # noqa: PLC0415

        for repo in plan.hf_repos:
            print(f"\nPulling {repo} (this can take a while)...")
            try:
                snapshot_download(repo_id=repo, resume_download=True)
            except Exception as exc:
                print(f"Failed to pull {repo}: {exc}")
                return 3

    # Step 3: preflight check via the voice registry
    print("\n=== Preflight check ===")
    try:
        import asyncio
        from app.services.voice.realtime_voice_llm import (
            VoiceBrain,
            get_brain,
        )

        brain_enum = VoiceBrain(brain_name)
        provider = get_brain(brain_enum)
        err = asyncio.run(provider.preflight())
        if err is None:
            print(f"OK {brain_name} is ready. "
                  f"Set DAENA_VOICE_BRAIN={brain_name} and restart backend.")
            return 0
        print(f"Preflight says needs_install: {err.reason}")
        return 4
    except Exception as exc:
        print(f"Preflight failed: {exc}")
        return 5


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--brain",
        required=True,
        choices=[*_PLANS.keys(), "all"],
        help="Which voice brain to install.",
    )
    parser.add_argument(
        "--skip-weights",
        action="store_true",
        help="Skip model-weight download (useful for CI).",
    )
    args = parser.parse_args()

    targets = list(_PLANS.keys()) if args.brain == "all" else [args.brain]
    for t in targets:
        rc = install_brain(t, skip_weights=args.skip_weights)
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
