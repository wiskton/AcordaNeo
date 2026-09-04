"""Garante que só uma instância do app rode por vez e gerencia IPC local (Push-to-Talk).

Usa flock (trava consultiva do kernel) e um socket UNIX local para que chamadas
externas (ex: acordaneo --wake / atalhos de teclado globais) possam acordar ou alternar
a janela da instância principal instantaneamente.
"""

import fcntl
import os
from pathlib import Path
import socket
import threading
from typing import Callable, Optional

from .config import CONFIG_DIR

_LOCK_FILE = CONFIG_DIR / "app.lock"
_SOCKET_FILE = CONFIG_DIR / "acordaneo.sock"
_arquivo_travado = None
_servidor_sock: Optional[socket.socket] = None


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


def enviar_comando_instancia(comando: str) -> bool:
    """Envia um comando textual ('WAKE', 'TOGGLE', etc.) para a instância ativa via socket UNIX."""
    if not _SOCKET_FILE.exists():
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(2.0)
            s.connect(str(_SOCKET_FILE))
            s.sendall((comando.strip() + "\n").encode("utf-8"))
            return True
    except Exception:
        return False


def iniciar_servidor_comandos(ao_receber_comando: Callable[[str], None]):
    """Inicia um servidor UNIX Domain Socket em background para ouvir comandos de outras instâncias ou atalhos."""
    global _servidor_sock

    if _SOCKET_FILE.exists():
        try:
            _SOCKET_FILE.unlink()
        except OSError:
            pass

    try:
        _servidor_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        _servidor_sock.bind(str(_SOCKET_FILE))
        _SOCKET_FILE.chmod(0o600)
        _servidor_sock.listen(5)
    except Exception as e:
        print(f"[singleinstance] Erro ao iniciar socket IPC: {e}")
        return

    def _loop_servidor():
        while _servidor_sock:
            try:
                conn, _ = _servidor_sock.accept()
                with conn:
                    conn.settimeout(1.0)
                    dados = conn.recv(1024).decode("utf-8").strip()
                    if dados:
                        ao_receber_comando(dados)
            except Exception:
                if not _servidor_sock:
                    break

    t = threading.Thread(target=_loop_servidor, daemon=True)
    t.start()


def liberar():
    """Libera o lockfile e o socket UNIX."""
    global _arquivo_travado, _servidor_sock
    if _servidor_sock:
        try:
            _servidor_sock.close()
        except Exception:
            pass
        _servidor_sock = None

    if _SOCKET_FILE.exists():
        try:
            _SOCKET_FILE.unlink()
        except OSError:
            pass

    if _arquivo_travado:
        try:
            fcntl.flock(_arquivo_travado, fcntl.LOCK_UN)
            _arquivo_travado.close()
        except Exception:
            pass
        _arquivo_travado = None
