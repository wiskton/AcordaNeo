"""Síntese de voz local 100% offline com Piper TTS.

Permite resposta em áudio ultrarrápida sem nenhuma dependência de internet,
utilizando modelos ONNX locais rodando diretamente no processador.
"""

from pathlib import Path
import tempfile
import threading
from typing import Callable, Optional
import urllib.request
import wave

PIPER_DIR = Path(__file__).resolve().parent.parent / "assets" / "piper"
MODELO_NOME = "pt_BR-edresson-low"
ONNX_PATH = PIPER_DIR / f"{MODELO_NOME}.onnx"
JSON_PATH = PIPER_DIR / f"{MODELO_NOME}.onnx.json"

URL_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/edresson/low"
URL_ONNX = f"{URL_BASE}/pt_BR-edresson-low.onnx"
URL_JSON = f"{URL_BASE}/pt_BR-edresson-low.onnx.json"

_voice_instance = None
_voice_lock = threading.Lock()


def modelo_instalado() -> bool:
    """Verifica se o modelo ONNX e o arquivo JSON de configuração estão disponíveis localmente."""
    return ONNX_PATH.exists() and JSON_PATH.exists() and ONNX_PATH.stat().st_size > 1000000


def garantir_modelo(callback_progresso: Optional[Callable[[str, float], None]] = None) -> bool:
    """Faz o download do modelo local do Piper se ainda não estiver presente."""
    if modelo_instalado():
        return True

    PIPER_DIR.mkdir(parents=True, exist_ok=True)
    try:
        if callback_progresso:
            callback_progresso("Baixando configuração do Piper...", 0.1)
        if not JSON_PATH.exists():
            urllib.request.urlretrieve(URL_JSON, JSON_PATH)

        if callback_progresso:
            callback_progresso("Baixando modelo neural offline (~15MB)...", 0.3)

        def _reporthook(count, block_size, total_size):
            if callback_progresso and total_size > 0:
                p = 0.3 + 0.7 * (count * block_size / total_size)
                callback_progresso(f"Baixando modelo Piper ({int(p*100)}%)...", min(1.0, p))

        urllib.request.urlretrieve(URL_ONNX, ONNX_PATH, reporthook=_reporthook)

        if callback_progresso:
            callback_progresso("Modelo Piper pronto!", 1.0)
        return True
    except Exception as exc:
        print(f"[piper_tts] Erro ao baixar modelo: {exc}")
        return False


def _obter_voz():
    """Carrega a instância do PiperVoice em memória com lock de thread."""
    global _voice_instance
    with _voice_lock:
        if _voice_instance is None:
            if not modelo_instalado():
                sucesso = garantir_modelo()
                if not sucesso:
                    raise RuntimeError("Modelo Piper TTS não pôde ser baixado.")
            try:
                from piper.voice import PiperVoice

                _voice_instance = PiperVoice.load(str(ONNX_PATH), config_path=str(JSON_PATH))
            except ImportError:
                raise RuntimeError("Pacote 'piper-tts' não instalado. Execute: pip install piper-tts")
        return _voice_instance


def sintetizar(texto: str) -> Path:
    """Gera um arquivo WAV com a fala sintetizada localmente pelo Piper e retorna o caminho."""
    voz = _obter_voz()
    fd, caminho_str = tempfile.mkstemp(suffix=".wav", prefix="piper_tts_")
    import os
    os.close(fd)
    destino = Path(caminho_str)

    with wave.open(str(destino), "wb") as wav_file:
        voz.synthesize_wav(texto, wav_file)

    return destino
