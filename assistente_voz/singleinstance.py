"""Garante que só uma instância do app rode por vez.

Importante aqui especificamente porque o app fica sempre gravando do
microfone em segundo plano — duas instâncias ao mesmo tempo brigam pelo
dispositivo de áudio e cada gravação falha, travando o app num loop de erro.

Usa flock (trava consultiva do kernel): se o processo cair/travar, o SO
libera a trava sozinho — sem risco de "lockfile fantasma" sobrando.
"""

import fcntl
from pathlib import Path

from .config import CONFIG_DIR

_LOCK_FILE = CONFIG_DIR / "app.lock"
_arquivo_travado = None  # precisa ficar em memória - fechar o fd libera a trava


def adquirir() -> bool:
    """Tenta travar. Devolve True se essa é a única instância, False se já tem outra rodando."""
    global _arquivo_travado
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _arquivo_travado = open(_LOCK_FILE, "w")
    try:
        fcntl.flock(_arquivo_travado, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        _arquivo_travado.close()
        _arquivo_travado = None
        return False
