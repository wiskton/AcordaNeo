"""Configuração local do app: chave da API e preferências (voz, modelo).

Fica em ~/.config/assistente-voz/config.json (fora do repositório) — nunca
comitar chave de API no projeto.
"""

import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "assistente-voz"
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


def _defaults():
    return {
        "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
        "voz": DEFAULT_VOICE,
        "modelo": DEFAULT_MODEL,
    }


def carregar():
    if CONFIG_FILE.exists():
        try:
            dados = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
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
