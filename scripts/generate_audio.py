#!/usr/bin/env python3
"""
Gera áudio TTS a partir de texto lido de um arquivo ou string.
"""
import sys
import os
import argparse
import soundfile as sf
import numpy as np
from pathlib import Path
from kokoro_onnx import Kokoro


def load_env():
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, _, val = line.partition("=")
                key = key.strip()
                if key not in os.environ:
                    os.environ[key] = val.strip().strip("\"'")


def main():
    load_env()

    parser = argparse.ArgumentParser(description="Gerador de áudio TTS usando Kokoro")
    parser.add_argument("--text-file", help="Caminho para o arquivo contendo o texto")
    parser.add_argument("--output", required=True, help="Caminho de saída para o arquivo .wav")
    
    args = parser.parse_args()

    if args.text_file:
        if not os.path.exists(args.text_file):
            print(f"ERRO: Arquivo {args.text_file} não encontrado.", file=sys.stderr)
            sys.exit(1)
        with open(args.text_file, "r", encoding="utf-8") as f:
            texto = f.read()
    else:
        print("ERRO: É necessário fornecer um arquivo de texto via --text-file", file=sys.stderr)
        sys.exit(1)

    # Limpeza de caracteres Markdown que o TTS lê literalmente
    texto = texto.replace("*", "").replace("#", "")
    
    if not texto.strip():
        print("ERRO: Texto vazio", file=sys.stderr)
        sys.exit(1)

    model_path = os.environ.get("KOKORO_MODEL_PATH", "models/kokoro-v1.0.onnx")
    voices_path = os.environ.get("KOKORO_VOICES_PATH", "models/voices-v1.0.bin")
    voice = os.environ.get("KOKORO_VOICE", "pf_dora")
    lang = os.environ.get("KOKORO_LANG", "pt-br")

    kokoro = Kokoro(model_path, voices_path)

    # Chunking para textos longos (max ~400 chars por chunk)
    max_chunk = 400
    chunks = []
    sentences = texto.replace(". ", ".\n").split("\n")
    current = ""
    for s in sentences:
        if len(current) + len(s) > max_chunk and current:
            chunks.append(current.strip())
            current = s
        else:
            current = current + " " + s if current else s
    if current.strip():
        chunks.append(current.strip())

    all_samples = []
    sample_rate = 24000

    for i, chunk in enumerate(chunks, 1):
        print(f"  Chunk {i}/{len(chunks)}: {len(chunk)} chars", file=sys.stderr)
        samples, sr = kokoro.create(chunk, voice=voice, speed=1.0, lang=lang)
        sample_rate = sr
        all_samples.append(samples)

    combined = np.concatenate(all_samples)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    sf.write(args.output, combined, sample_rate)
    print(args.output)

if __name__ == "__main__":
    main()

