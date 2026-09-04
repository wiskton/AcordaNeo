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

PROVEDOR_OLLAMA = "ollama"
PROVEDOR_CLAUDE = "claude"
DEFAULT_PROVEDOR = PROVEDOR_OLLAMA

PROVEDORES_DISPONIVEIS = [
    (PROVEDOR_OLLAMA, "Ollama (Local / 100% Offline / Gratuito)"),
    (PROVEDOR_CLAUDE, "Claude (Anthropic API oficial)"),
]

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2:3b"

DEFAULT_VOICE = "neo"
DEFAULT_MODEL = "claude-sonnet-4-5"

VOZES_DISPONIVEIS = [
    ("neo", "🕶️ Neo (Matrix - Dublado PT-BR)"),
    ("neo-keanu", "🕶️ Neo (Keanu Reeves - Original)"),
]


def _defaults():
    return {
        "provedor": DEFAULT_PROVEDOR,
        "ollama_host": DEFAULT_OLLAMA_HOST,
        "ollama_model": DEFAULT_OLLAMA_MODEL,
        "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
        "voz": DEFAULT_VOICE,
        "modelo": DEFAULT_MODEL,
    }


def carregar():
    vozes_validas = {v[0] for v in VOZES_DISPONIVEIS}
    for arq in (CONFIG_FILE, CONFIG_DIR_LEGACY / "config.json"):
        if arq.exists():
            try:
                dados = json.loads(arq.read_text(encoding="utf-8"))
                base = _defaults()
                base.update({k: v for k, v in dados.items() if v not in (None, "")})
                if base.get("voz") not in vozes_validas:
                    base["voz"] = DEFAULT_VOICE
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
