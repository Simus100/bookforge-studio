"""Persistent Qwen3-TTS worker: JSON lines on stdout, diagnostics on stderr."""
import contextlib
import json
import os
import sys
from pathlib import Path


def main():
    model_dir = Path(sys.argv[1])
    model = None
    for line in sys.stdin:
        try:
            data = json.loads(line)
            with contextlib.redirect_stdout(sys.stderr):
                import torch
                import soundfile as sf
                from qwen_tts import Qwen3TTSModel
                if not torch.cuda.is_available():
                    raise RuntimeError("Studio richiede una GPU NVIDIA con CUDA. Su questo PC scegli Paola o Riccardo.")
                if model is None:
                    model = Qwen3TTSModel.from_pretrained(str(model_dir), device_map="cuda:0",
                                                         dtype=torch.float16, attn_implementation="sdpa", local_files_only=True)
                torch.manual_seed(42)
                with torch.inference_mode():
                    wavs, sample_rate = model.generate_custom_voice(text=data["text"], language="Italian", speaker="Ryan",
                                                                   instruct=data["instruct"], max_new_tokens=4096)
                sf.write(data["output"], wavs[0], sample_rate, subtype="PCM_16")
            print(json.dumps({"ok": True}), flush=True)
        except Exception as exc:
            print(json.dumps({"ok": False, "error": str(exc)}), flush=True)


if __name__ == "__main__":
    main()
