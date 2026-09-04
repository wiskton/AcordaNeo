"""Reconhecimento de voz: grava áudio do microfone via `arecord` (ALSA, já vem
no sistema — evita depender de PyAudio/portaudio-dev) e transcreve localmente
com faster-whisper, sem precisar mandar áudio pra nenhuma API externa.
"""

import subprocess
import tempfile
from pathlib import Path

from faster_whisper import WhisperModel

_MODELO_WHISPER = None


def _get_modelo():
    global _MODELO_WHISPER
    if _MODELO_WHISPER is None:
        # "small" é um bom equilíbrio precisão/velocidade em CPU para PT-BR;
        # baixa (~500MB) automaticamente na primeira execução e fica em cache.
        _MODELO_WHISPER = WhisperModel("small", device="cpu", compute_type="int8")
    return _MODELO_WHISPER


class Gravador:
    """Grava áudio do microfone padrão até `parar()` ser chamado."""

    def __init__(self):
        self._processo = None
        self._arquivo = None

    def iniciar(self):
        self._arquivo = Path(tempfile.mkstemp(suffix=".wav", prefix="assistente_voz_")[1])
        self._processo = subprocess.Popen(
            ["arecord", "-f", "S16_LE", "-r", "16000", "-c", "1", str(self._arquivo)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def parar(self) -> Path:
        if self._processo:
            self._processo.terminate()
            self._processo.wait(timeout=5)
            self._processo = None
        return self._arquivo


def transcrever(caminho_wav: Path, idioma: str = "pt") -> str:
    """Transcreve um arquivo WAV para texto usando o Whisper local."""
    modelo = _get_modelo()
    segmentos, _info = modelo.transcribe(str(caminho_wav), language=idioma, vad_filter=True)
    texto = " ".join(seg.text.strip() for seg in segmentos).strip()
    caminho_wav.unlink(missing_ok=True)
    return texto
