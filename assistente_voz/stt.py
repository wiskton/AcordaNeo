"""Reconhecimento de voz: grava trechos de microfone via `arecord`
(ALSA, nativo do sistema — sem dependência de PyAudio/portaudio-dev) e
transcreve localmente com faster-whisper, sem mandar áudio pra fora.

Conta com:
- Correção de bias/offset DC analógico (bug comum em chips ALC257)
- Normalização adaptativa de ganho (AGC digital) para microfones baixos
- Detecção de voz em tempo real (Silero VAD integrado)
- Dois modelos:
  * "tiny"  -> detecção ágil da frase de ativação ("Acorda, Neo")
  * "small" -> transcrição de alta precisão da pergunta
"""

import os
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import List, Optional

import numpy as np
from faster_whisper import WhisperModel
from faster_whisper.vad import VadOptions, get_speech_timestamps

PALAVRA_ATIVACAO = "neo"

# Um WAV a 16kHz/16bit/mono válido tem ~32KB por segundo + 44 bytes de
# cabeçalho; qualquer arquivo bem menor é sinal de gravação corrompida/falha.
TAMANHO_MINIMO_WAV_VALIDO = 2000

_MODELO_PERGUNTA = None
_MODELO_ATIVACAO = None


def configurar_microfone_sistema():
    """Ajusta o ganho no ALSA para evitar distorção/saturação analógica.
    No codec Realtek ALC257, se 'Internal Mic Boost' estiver acima de 0dB,
    o sinal atinge o limite negativo (-32768) e satura em onda quadrada.
    """
    try:
        subprocess.run(
            ["amixer", "-c", "0", "sset", "Internal Mic Boost", "0"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        subprocess.run(
            ["amixer", "-c", "0", "sset", "Capture", "45"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except Exception:
        pass


def normalizar_audio(caminho_wav: Path) -> bool:
    """Remove offset DC e aplica ganho automático (AGC) ao arquivo WAV."""
    if not caminho_wav.exists() or caminho_wav.stat().st_size < TAMANHO_MINIMO_WAV_VALIDO:
        return False

    try:
        with wave.open(str(caminho_wav), "rb") as w:
            params = w.getparams()
            raw = w.readframes(w.getnframes())

        if not raw:
            return False

        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)

        # 1. Remove bias DC analógico (centraliza em zero)
        samples = samples - np.mean(samples)

        # 2. Normalização de ganho (Peak AGC com teto de ganho)
        pico = float(np.max(np.abs(samples)))
        if pico > 50.0:
            alvo = 24000.0  # ~-2.7 dBFS headroom
            fator_ganho = min(alvo / pico, 12.0)
            samples = samples * fator_ganho

        ajustado = np.clip(samples, -32767.0, 32767.0).astype(np.int16)

        with wave.open(str(caminho_wav), "wb") as w:
            w.setparams(params)
            w.writeframes(ajustado.tobytes())

        return True
    except Exception as exc:
        print(f"[stt] Erro ao normalizar áudio {caminho_wav}: {exc}")
        return False


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
    """Grava um trecho de duração fixa do microfone padrão e devolve o WAV normalizado.

    Devolve None se a gravação falhar (ex.: microfone ocupado por outro
    processo) — quem chamar deve tratar esse caso, não presumir sucesso.
    """
    fd, caminho = tempfile.mkstemp(suffix=".wav", prefix="assistente_voz_")
    os.close(fd)
    destino = Path(caminho)

    # `arecord -d` só aceita segundos inteiros
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

    normalizar_audio(destino)
    return destino


def tem_voz(caminho_wav: Path) -> bool:
    """Verifica com alta sensibilidade se o clipe contém voz humana
    usando Silero VAD e confirmação rápida pelo Whisper tiny.
    """
    if not caminho_wav.exists() or caminho_wav.stat().st_size < TAMANHO_MINIMO_WAV_VALIDO:
        return False

    try:
        with wave.open(str(caminho_wav), "rb") as w:
            raw = w.readframes(w.getnframes())

        if not raw:
            return False

        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        pico = float(np.max(np.abs(samples)))
        if pico < 150.0:
            return False

        # VAD Silero em escala [-1.0, 1.0]
        audio_norm = samples / max(pico, 32768.0)
        ts = get_speech_timestamps(
            audio_norm,
            vad_options=VadOptions(
                threshold=0.28,
                min_speech_duration_ms=100,
                min_silence_duration_ms=300,
            ),
        )
        if ts:
            return True

        # Fallback de segurança: checagem rápida via Whisper tiny (~30ms)
        modelo_ativacao = _get_modelo_ativacao()
        segmentos, _ = modelo_ativacao.transcribe(
            str(caminho_wav),
            language="pt",
            vad_filter=True,
            vad_parameters=dict(threshold=0.28),
        )
        texto = "".join(seg.text for seg in segmentos).strip()
        return len(texto) > 0
    except Exception as exc:
        print(f"[stt] Erro ao checar voz: {exc}")
        return False


def concatenar_audios(caminhos: List[Path], destino: Path) -> Optional[Path]:
    """Combina múltiplos arquivos WAV de mesma taxa em um único arquivo WAV contínuo."""
    caminhos_validos = [p for p in caminhos if p.exists() and p.stat().st_size >= TAMANHO_MINIMO_WAV_VALIDO]
    if not caminhos_validos:
        return None

    try:
        with wave.open(str(destino), "wb") as saida:
            params_definidos = False
            for p in caminhos_validos:
                with wave.open(str(p), "rb") as entrada:
                    if not params_definidos:
                        saida.setparams(entrada.getparams())
                        params_definidos = True
                    saida.writeframes(entrada.readframes(entrada.getnframes()))

        normalizar_audio(destino)
        return destino
    except Exception as exc:
        print(f"[stt] Erro ao concatenar áudios: {exc}")
        destino.unlink(missing_ok=True)
        return None


def _transcrever_com(
    modelo: WhisperModel, caminho_wav: Path, idioma: str = "pt", dica_vocabulario: str = None
) -> str:
    segmentos, _info = modelo.transcribe(
        str(caminho_wav),
        language=idioma,
        vad_filter=True,
        vad_parameters=dict(
            threshold=0.30,
            min_speech_duration_ms=100,
            min_silence_duration_ms=400,
        ),
        beam_size=5,
        initial_prompt=dica_vocabulario,
    )
    return " ".join(seg.text.strip() for seg in segmentos).strip()


def transcrever(caminho_wav: Optional[Path], idioma: str = "pt") -> str:
    """Transcreve um trecho de fala (a pergunta em si) com o modelo mais preciso."""
    if caminho_wav is None:
        return ""
    dica = "Conversa em português do Brasil com pontuação e acentuação corretas."
    texto = _transcrever_com(_get_modelo_pergunta(), caminho_wav, idioma, dica_vocabulario=dica)
    caminho_wav.unlink(missing_ok=True)
    return texto


def contem_palavra_ativacao(
    caminho_wav: Optional[Path],
    idioma: str = "pt",
    durante_fala: bool = False,
    palavra_chave: str = "Acorda, Neo",
) -> bool:
    """Checa (com o modelo leve) se o trecho contém a frase de ativação ou pedido de parada."""
    if caminho_wav is None:
        return False

    palavra_alvo = palavra_chave.strip() if palavra_chave else "Acorda, Neo"
    dica = (
        f"{palavra_alvo}."
        if not durante_fala
        else f"{palavra_alvo}, pare, para, silêncio."
    )
    texto = _transcrever_com(
        _get_modelo_ativacao(), caminho_wav, idioma, dica_vocabulario=dica
    )
    caminho_wav.unlink(missing_ok=True)
    if texto:
        contexto = " [DURANTE FALA]" if durante_fala else ""
        print(f"[stt] ouvi{contexto}: {texto!r}")
    texto_normalizado = (
        texto.lower()
        .replace(",", " ")
        .replace(".", " ")
        .replace("!", " ")
        .replace("?", " ")
        .replace("-", " ")
    )
    palavras = set(texto_normalizado.split())

    if durante_fala:
        gatilhos_interrupcao = {
            "acorda", "acorde", "corda", "desperte",
            "para", "pare", "cancela", "cancelar", "silêncio", "silencio",
            "calado", "chega", "interromper", "basta"
        }
        if palavras.intersection(gatilhos_interrupcao):
            return True
        tokens_alvo = set(
            palavra_alvo.lower()
            .replace(",", " ")
            .replace(".", " ")
            .split()
        )
        if tokens_alvo and tokens_alvo.issubset(palavras):
            return True
        return False

    tokens_gatilho = set(
        palavra_alvo.lower()
        .replace(",", " ")
        .replace(".", " ")
        .replace("!", " ")
        .replace("?", " ")
        .split()
    )
    if "neo" in tokens_gatilho:
        tokens_gatilho.update({"néo", "nêo", "acorda", "acorde", "corda"})

    return bool(palavras.intersection(tokens_gatilho))

