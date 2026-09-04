"""Síntese de voz com múltiplas vozes via edge-tts (gratuito, sem chave de API,
mesmas vozes neurais usadas no "Ler em voz alta" do navegador Edge).
"""

import asyncio
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Optional

import edge_tts


# Perfis de voz personalizados exclusivos do Neo (Matrix)
PERFIS_VOZ = {
    "neo": {
        "voz": "pt-BR-AntonioNeural",
        "pitch": "-20Hz",
        "rate": "-7%",
    },
    "neo-keanu": {
        "voz": "en-US-BrianMultilingualNeural",
        "pitch": "-14Hz",
        "rate": "-6%",
    },
}

_processo_audio: Optional[subprocess.Popen] = None
_caminho_audio_atual: Optional[Path] = None
_lock_audio = threading.Lock()


async def _sintetizar_async(texto: str, identificador_voz: str, destino: Path):
    perfil = PERFIS_VOZ.get(identificador_voz, PERFIS_VOZ["neo"])
    voz_real = perfil["voz"]
    pitch = perfil.get("pitch", "-20Hz")
    rate = perfil.get("rate", "-7%")

    comunicador = edge_tts.Communicate(texto, voz_real, pitch=pitch, rate=rate)
    await comunicador.save(str(destino))


def sintetizar(texto: str, voz: str) -> Path:
    """Gera um MP3 com a fala e devolve o caminho do arquivo."""
    destino = Path(tempfile.mkstemp(suffix=".mp3", prefix="assistente_voz_")[1])
    asyncio.run(_sintetizar_async(texto, voz, destino))
    return destino


def iniciar_reproducao(caminho_audio: Path) -> Optional[subprocess.Popen]:
    """Inicia a reprodução do áudio em segundo plano com ffplay e devolve o processo.
    Permite monitorar e interromper a fala em tempo real (barge-in).
    """
    global _processo_audio, _caminho_audio_atual
    parar()

    with _lock_audio:
        try:
            _caminho_audio_atual = caminho_audio
            _processo_audio = subprocess.Popen(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(caminho_audio)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return _processo_audio
        except Exception as exc:
            print(f"[tts] Erro ao iniciar reprodução com ffplay: {exc}")
            if caminho_audio:
                caminho_audio.unlink(missing_ok=True)
            _caminho_audio_atual = None
            _processo_audio = None
            return None


def parar():
    """Interrompe imediatamente qualquer áudio sendo reproduzido e remove o arquivo temporário."""
    global _processo_audio, _caminho_audio_atual
    with _lock_audio:
        if _processo_audio is not None:
            try:
                if _processo_audio.poll() is None:
                    _processo_audio.terminate()
                    try:
                        _processo_audio.wait(timeout=0.3)
                    except subprocess.TimeoutExpired:
                        _processo_audio.kill()
            except Exception:
                pass
            _processo_audio = None

        if _caminho_audio_atual is not None:
            try:
                _caminho_audio_atual.unlink(missing_ok=True)
            except Exception:
                pass
            _caminho_audio_atual = None


def esta_tocando() -> bool:
    """Verifica de forma segura se há áudio sendo reproduzido no momento."""
    with _lock_audio:
        if _processo_audio is None:
            return False
        return _processo_audio.poll() is None


def tocar(caminho_audio: Path):
    """Reproduz o áudio e apaga o arquivo temporário ao terminar (síncrono)."""
    proc = iniciar_reproducao(caminho_audio)
    if proc:
        try:
            proc.wait()
        finally:
            parar()
