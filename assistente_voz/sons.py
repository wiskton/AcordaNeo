"""Indicadores e feedbacks sonoros (chimes) do assistente de voz.

Reproduz sons sutis de confirmação com baixa latência (via paplay, pw-play, aplay ou ffplay)
quando a frase de ativação é reconhecida, ao iniciar o processamento ou ao concluir ações.
"""

import math
from pathlib import Path
import shutil
import struct
import subprocess
import threading
import wave
from typing import List, Tuple

ASSETS_SONS_DIR = Path(__file__).resolve().parent.parent / "assets" / "sons"


def _gerar_onda_senoidal(freqs_durs: List[Tuple[float, float]], destino: Path):
    """Gera um arquivo WAV suave com envelope de ataque/decaimento sem cliques."""
    sample_rate = 44100
    destino.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destino), "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        frames = bytearray()
        for freq, dur in freqs_durs:
            n_samples = int(sample_rate * dur)
            for i in range(n_samples):
                t = i / sample_rate
                attack = min(1.0, i / (sample_rate * 0.008))
                decay = math.exp(-4.5 * (i / n_samples))
                # Harmônicos sutis para sonoridade limpa estilo terminal sci-fi
                val = 0.32 * attack * decay * (
                    0.85 * math.sin(2.0 * math.pi * freq * t)
                    + 0.15 * math.sin(4.0 * math.pi * freq * t)
                )
                sample = int(max(-32767, min(32767, val * 32767)))
                frames.extend(struct.pack("<h", sample))
        f.writeframes(frames)


def garantir_sons():
    """Garante que os arquivos de som padrão existam no diretório assets/sons."""
    ASSETS_SONS_DIR.mkdir(parents=True, exist_ok=True)

    wake_file = ASSETS_SONS_DIR / "wake.wav"
    if not wake_file.exists() or wake_file.stat().st_size == 0:
        # Duplo bipe ascendente suave (D5 587Hz -> A5 880Hz)
        _gerar_onda_senoidal([(587.33, 0.08), (880.0, 0.16)], wake_file)

    think_file = ASSETS_SONS_DIR / "think.wav"
    if not think_file.exists() or think_file.stat().st_size == 0:
        # Chime curto descendente/transição (E5 659Hz)
        _gerar_onda_senoidal([(659.25, 0.13)], think_file)

    sucesso_file = ASSETS_SONS_DIR / "sucesso.wav"
    if not sucesso_file.exists() or sucesso_file.stat().st_size == 0:
        # Tríade suave de confirmação (C5 -> E5 -> G5)
        _gerar_onda_senoidal([(523.25, 0.06), (659.25, 0.06), (783.99, 0.14)], sucesso_file)


def _reproduzir_arquivo(caminho: Path):
    """Executa o player disponível no sistema com a menor latência possível."""
    if not caminho.exists():
        return

    players = [
        ["paplay", str(caminho)],
        ["pw-play", str(caminho)],
        ["aplay", "-q", str(caminho)],
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(caminho)],
    ]

    for cmd in players:
        if shutil.which(cmd[0]):
            try:
                subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                return
            except Exception:
                continue


def tocar_som(nome: str, assincrono: bool = True, habilitado: bool = True):
    """Toca um efeito sonoro pelo nome ('wake', 'think', 'sucesso')."""
    if not habilitado:
        return

    caminho = ASSETS_SONS_DIR / f"{nome}.wav"
    if not caminho.exists():
        garantir_sons()

    if assincrono:
        t = threading.Thread(target=_reproduzir_arquivo, args=(caminho,), daemon=True)
        t.start()
    else:
        _reproduzir_arquivo(caminho)


def tocar_wake(habilitado: bool = True):
    tocar_som("wake", assincrono=True, habilitado=habilitado)


def tocar_think(habilitado: bool = True):
    tocar_som("think", assincrono=True, habilitado=habilitado)


def tocar_sucesso(habilitado: bool = True):
    tocar_som("sucesso", assincrono=True, habilitado=habilitado)
