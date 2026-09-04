"""Síntese de voz com múltiplas vozes via edge-tts (gratuito, sem chave de API,
mesmas vozes neurais usadas no "Ler em voz alta" do navegador Edge).
"""

import asyncio
import subprocess
import tempfile
from pathlib import Path

import edge_tts


async def _sintetizar_async(texto: str, voz: str, destino: Path):
    comunicador = edge_tts.Communicate(texto, voz)
    await comunicador.save(str(destino))


def sintetizar(texto: str, voz: str) -> Path:
    """Gera um MP3 com a fala e devolve o caminho do arquivo."""
    destino = Path(tempfile.mkstemp(suffix=".mp3", prefix="assistente_voz_")[1])
    asyncio.run(_sintetizar_async(texto, voz, destino))
    return destino


def tocar(caminho_audio: Path):
    """Reproduz o áudio e apaga o arquivo temporário ao terminar."""
    try:
        subprocess.run(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(caminho_audio)],
            check=True,
        )
    finally:
        caminho_audio.unlink(missing_ok=True)
