"""Configuração local do app: chave da API e preferências (voz, modelo).

Fica em ~/.config/assistente-voz/config.json (fora do repositório) — nunca
comitar chave de API no projeto.
"""

import json
import os
from pathlib import Path

_BASE_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
CONFIG_DIR_ACORDANEO = _BASE_CONFIG / "acordaneo"
CONFIG_DIR_LEGACY = _BASE_CONFIG / "assistente-voz"

# Prioriza ~/.config/acordaneo se existir ou se a pasta antiga não existir
if CONFIG_DIR_ACORDANEO.exists() or not CONFIG_DIR_LEGACY.exists():
    CONFIG_DIR = CONFIG_DIR_ACORDANEO
else:
    CONFIG_DIR = CONFIG_DIR_LEGACY

CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_VOICE = "pt-BR-AntonioNeural"
DEFAULT_MODEL = "claude-sonnet-4-5"

VOZES_DISPONIVEIS = [
    ("pt-BR-AntonioNeural", "Antônio (PT-BR, masculina)"),
    ("pt-BR-FranciscaNeural", "Francisca (PT-BR, feminina)"),
    ("pt-BR-ThalitaNeural", "Thalita (PT-BR, feminina)"),
    ("pt-PT-DuarteNeural", "Duarte (PT-PT, masculina)"),
    ("en-US-GuyNeural", "Guy (EN-US, masculina)"),
    ("en-US-JennyNeural", "Jenny (EN-US, feminina)"),
]

PROVEDOR_CLAUDE = "claude"
PROVEDOR_CHATGPT_WEB = "chatgpt_web"
DEFAULT_PROVEDOR = PROVEDOR_CLAUDE

PROVEDORES_DISPONIVEIS = [
    (PROVEDOR_CLAUDE, "Claude (API oficial)"),
    (PROVEDOR_CHATGPT_WEB, "ChatGPT (navegador, gambiarra)"),
]


def _defaults():
    return {
        "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
        "voz": DEFAULT_VOICE,
        "modelo": DEFAULT_MODEL,
        "provedor": DEFAULT_PROVEDOR,
        "chatgpt_email": "",
        "chatgpt_senha": "",
        "chatgpt_headless": True,
    }


def carregar():
    for arq in (CONFIG_FILE, CONFIG_DIR_LEGACY / "config.json"):
        if arq.exists():
            try:
                dados = json.loads(arq.read_text(encoding="utf-8"))
                base = _defaults()
                base.update({k: v for k, v in dados.items() if v not in (None, "")})
                return base
            except (json.JSONDecodeError, OSError):
                pass
    return _defaults()


def salvar(config: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        CONFIG_FILE.chmod(0o600)
    except OSError:
        pass
