"""Reconhecimento de voz: grava trechos curtos do microfone via `arecord`
(ALSA, já vem no sistema — evita depender de PyAudio/portaudio-dev) e
transcreve localmente com faster-whisper, sem mandar áudio pra fora.

Dois modelos:
- "tiny"  -> escuta contínua da palavra de ativação ("Acorda, Neo"), rápido
- "small" -> transcrição da pergunta em si, mais preciso
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from faster_whisper import WhisperModel

PALAVRA_ATIVACAO = "neo"

# Um WAV de 3s a 16kHz/16bit/mono válido tem ~96KB de áudio + 44 bytes de
# cabeçalho; qualquer coisa bem menor que isso é sinal de gravação falha
# (microfone ocupado por outro processo, dispositivo indisponível etc.)
TAMANHO_MINIMO_WAV_VALIDO = 2000

_MODELO_PERGUNTA = None
_MODELO_ATIVACAO = None


def _get_modelo_pergunta():
    global _MODELO_PERGUNTA
    if _MODELO_PERGUNTA is None:
        _MODELO_PERGUNTA = WhisperModel("small", device="cpu", compute_type="int8")
    return _MODELO_PERGUNTA


def _get_modelo_ativacao():
    global _MODELO_ATIVACAO
    if _MODELO_ATIVACAO is None:
        _MODELO_ATIVACAO = WhisperModel("tiny", device="cpu", compute_type="int8")
    return _MODELO_ATIVACAO


def gravar_clipe(duracao_segundos: float) -> Optional[Path]:
    """Grava um trecho de duração fixa do microfone padrão e devolve o WAV.

    Devolve None se a gravação falhar (ex.: microfone ocupado por outro
    processo) — quem chamar deve tratar esse caso, não presumir sucesso.
    """
    fd, caminho = tempfile.mkstemp(suffix=".wav", prefix="assistente_voz_")
    os.close(fd)
    destino = Path(caminho)

    # `arecord -d` só aceita segundos inteiros — passar "3.0" faz ele
    # rejeitar o argumento e a gravação falha sempre, silenciosamente.
    duracao_inteira = max(1, round(duracao_segundos))
    resultado = subprocess.run(
        ["arecord", "-f", "S16_LE", "-r", "16000", "-c", "1", "-d", str(duracao_inteira), str(destino)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    if resultado.returncode != 0 or destino.stat().st_size < TAMANHO_MINIMO_WAV_VALIDO:
        print(f"[stt] Gravação falhou (arecord: {resultado.stderr.strip()})")
        destino.unlink(missing_ok=True)
        return None

    return destino


def _transcrever_com(
    modelo: WhisperModel, caminho_wav: Path, idioma: str = "pt", dica_vocabulario: str = None
) -> str:
    segmentos, _info = modelo.transcribe(
        str(caminho_wav), language=idioma, vad_filter=True, initial_prompt=dica_vocabulario
    )
    return " ".join(seg.text.strip() for seg in segmentos).strip()


def transcrever(caminho_wav: Optional[Path], idioma: str = "pt") -> str:
    """Transcreve um trecho de fala (a pergunta em si) com o modelo mais preciso."""
    if caminho_wav is None:
        return ""
    texto = _transcrever_com(_get_modelo_pergunta(), caminho_wav, idioma)
    caminho_wav.unlink(missing_ok=True)
    return texto


def contem_palavra_ativacao(caminho_wav: Optional[Path], idioma: str = "pt") -> bool:
    """Checa (com o modelo leve) se o trecho contém a frase de ativação.

    "Neo" é um nome curto e incomum em português — o Whisper às vezes ouve
    coisas parecidas foneticamente (ex.: "acorda-lhe" em vez de "acorda,
    neo"). Por isso: (1) damos uma dica de vocabulário via initial_prompt,
    e (2) basta ouvir "acorda" OU "neo" pra disparar, não precisa das duas
    exatas — reduz falso-negativo às custas de mais falso-positivo, troca
    razoável pra um assistente pessoal.
    """
    if caminho_wav is None:
        return False
    texto = _transcrever_com(
        _get_modelo_ativacao(), caminho_wav, idioma, dica_vocabulario="Acorda, Neo."
    )
    caminho_wav.unlink(missing_ok=True)
    print(f"[stt] ouvi: {texto!r}")
    texto_normalizado = texto.lower().replace(",", "").replace(".", "").replace("-", " ")
    palavras = texto_normalizado.split()
    return "neo" in palavras or "acorda" in palavras
