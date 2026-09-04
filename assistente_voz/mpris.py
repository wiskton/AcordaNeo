"""Controle de mídia via MPRIS (Media Player Remote Interfacing Specification).

Permite pausar players de áudio (Spotify, VLC, navegadores, etc.) automaticamente
assim que o assistente desperta para escutar a pergunta, e retomar a música
apenas quando a conversa terminar (sem despausar o que já estava pausado antes).
Também provê suporte a comandos de voz como "pausar música", "próxima música", etc.
"""

import shutil
import subprocess
from typing import List, Optional, Set, Tuple
from gi.repository import Gio, GLib


_PLAYERS_PAUSADOS_POR_CONVERSA: Set[str] = set()
_TEM_PLAYERCTL = shutil.which("playerctl") is not None


def _listar_players_dbus() -> List[str]:
    """Lista todos os serviços MPRIS ativos no D-Bus de sessão."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        proxy = Gio.DBusProxy.new_sync(
            bus,
            Gio.DBusProxyFlags.NONE,
            None,
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            None,
        )
        names = proxy.ListNames()
        return [n for n in names if n.startswith("org.mpris.MediaPlayer2.")]
    except Exception as exc:
        print(f"[mpris] Erro ao listar players via D-Bus: {exc}")
        return []


def _status_player_dbus(nome_servico: str) -> str:
    """Retorna o PlaybackStatus ('Playing', 'Paused', 'Stopped') via D-Bus."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        props_proxy = Gio.DBusProxy.new_sync(
            bus,
            Gio.DBusProxyFlags.NONE,
            None,
            nome_servico,
            "/org/mpris/MediaPlayer2",
            "org.freedesktop.DBus.Properties",
            None,
        )
        val = props_proxy.Get("(ss)", "org.mpris.MediaPlayer2.Player", "PlaybackStatus")
        if val and hasattr(val, "unpack"):
            return str(val.unpack())
        return str(val) if val else ""
    except Exception:
        return ""


def _comando_player_dbus(nome_servico: str, metodo: str) -> bool:
    """Executa um método na interface org.mpris.MediaPlayer2.Player via D-Bus."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        player_proxy = Gio.DBusProxy.new_sync(
            bus,
            Gio.DBusProxyFlags.NONE,
            None,
            nome_servico,
            "/org/mpris/MediaPlayer2",
            "org.mpris.MediaPlayer2.Player",
            None,
        )
        player_proxy.call_sync(metodo, None, Gio.DBusCallFlags.NONE, 1000, None)
        return True
    except Exception as exc:
        print(f"[mpris] Erro ao enviar {metodo} para {nome_servico}: {exc}")
        return False


def obter_players_tocando() -> List[str]:
    """Retorna a lista de nomes de players que estão atualmente reproduzindo áudio."""
    tocando = []

    if _TEM_PLAYERCTL:
        try:
            res = subprocess.run(
                ["playerctl", "-l"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                for player in res.stdout.strip().splitlines():
                    player = player.strip()
                    if not player:
                        continue
                    status_res = subprocess.run(
                        ["playerctl", "-p", player, "status"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if status_res.stdout.strip().lower() == "playing":
                        tocando.append(player)
            return tocando
        except Exception:
            pass

    # Fallback via D-Bus nativo
    servicos = _listar_players_dbus()
    for s in servicos:
        if _status_player_dbus(s).lower() == "playing":
            tocando.append(s)
    return tocando


def pausar_para_conversa() -> List[str]:
    """Pausa qualquer mídia ativa (ex.: Spotify) e registra para retomar depois.
    Deve ser chamado assim que o assistente desperta com 'Acorda, Neo'.
    """
    global _PLAYERS_PAUSADOS_POR_CONVERSA
    players_ativos = obter_players_tocando()

    if not players_ativos:
        return []

    print(f"[mpris] Pausando players para conversa: {players_ativos}")
    for p in players_ativos:
        _PLAYERS_PAUSADOS_POR_CONVERSA.add(p)
        if _TEM_PLAYERCTL and not p.startswith("org.mpris."):
            subprocess.run(["playerctl", "-p", p, "pause"], capture_output=True, check=False)
        else:
            servico = p if p.startswith("org.mpris.") else f"org.mpris.MediaPlayer2.{p}"
            _comando_player_dbus(servico, "Pause")

    return list(players_ativos)


def retomar_apos_conversa():
    """Retoma a reprodução apenas dos players que haviam sido pausados pelo assistente."""
    global _PLAYERS_PAUSADOS_POR_CONVERSA
    if not _PLAYERS_PAUSADOS_POR_CONVERSA:
        return

    print(f"[mpris] Retomando reprodução dos players pausados: {_PLAYERS_PAUSADOS_POR_CONVERSA}")
    for p in list(_PLAYERS_PAUSADOS_POR_CONVERSA):
        try:
            if _TEM_PLAYERCTL and not p.startswith("org.mpris."):
                subprocess.run(["playerctl", "-p", p, "play"], capture_output=True, check=False)
            else:
                servico = p if p.startswith("org.mpris.") else f"org.mpris.MediaPlayer2.{p}"
                _comando_player_dbus(servico, "Play")
        except Exception as exc:
            print(f"[mpris] Erro ao retomar {p}: {exc}")

    _PLAYERS_PAUSADOS_POR_CONVERSA.clear()


import unicodedata


def executar_comando_midia(texto: str) -> Tuple[bool, str]:
    """Interpreta se o comando do usuário é de controle de mídia e executa.
    Retorna (reconhecido, mensagem_resposta).
    """
    sem_acentos = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    t = (
        sem_acentos.lower()
        .replace(",", " ")
        .replace(".", " ")
        .replace("!", " ")
        .replace("?", " ")
        .strip()
    )

    # 1. Pausa
    gatilhos_pausa = [
        "pausar musica", "pausar a musica", "pausa a musica", "pausa musica",
        "pausa spotify", "pausar spotify", "para a musica", "pare a musica",
        "parar musica", "pause musica", "pause a musica", "silenciar musica"
    ]
    if any(frase in t for frase in gatilhos_pausa):
        if _TEM_PLAYERCTL:
            subprocess.run(["playerctl", "pause"], capture_output=True, check=False)
        else:
            for s in _listar_players_dbus():
                _comando_player_dbus(s, "Pause")
        _PLAYERS_PAUSADOS_POR_CONVERSA.clear()
        return True, "Música pausada."

    # 2. Retomar / Play
    gatilhos_play = [
        "tocar musica", "continua musica", "continuar musica", "continua a musica",
        "continuar a musica", "play na musica", "play musica", "despausar musica",
        "despausa a musica", "despausa spotify", "solta o som", "toca a musica"
    ]
    if any(frase in t for frase in gatilhos_play):
        if _TEM_PLAYERCTL:
            subprocess.run(["playerctl", "play"], capture_output=True, check=False)
        else:
            for s in _listar_players_dbus():
                _comando_player_dbus(s, "Play")
        _PLAYERS_PAUSADOS_POR_CONVERSA.clear()
        return True, "Reprodução retomada."

    # 3. Próxima música
    gatilhos_next = [
        "proxima musica", "proxima faixa", "pular musica", "pula musica",
        "pula a musica", "avancar musica", "avanca a musica", "proximo som"
    ]
    if any(frase in t for frase in gatilhos_next):
        if _TEM_PLAYERCTL:
            subprocess.run(["playerctl", "next"], capture_output=True, check=False)
        else:
            for s in _listar_players_dbus():
                _comando_player_dbus(s, "Next")
        return True, "Próxima música."

    # 4. Música anterior
    gatilhos_prev = [
        "musica anterior", "faixa anterior", "voltar musica", "volta a musica",
        "volta musica", "retorna musica"
    ]
    if any(frase in t for frase in gatilhos_prev):
        if _TEM_PLAYERCTL:
            subprocess.run(["playerctl", "previous"], capture_output=True, check=False)
        else:
            for s in _listar_players_dbus():
                _comando_player_dbus(s, "Previous")
        return True, "Música anterior."

    # 5. Informações da música atual
    gatilhos_info = [
        "que musica esta tocando", "qual musica esta tocando", "o que esta tocando",
        "qual e a musica", "nome da musica"
    ]
    if any(frase in t for frase in gatilhos_info):
        if _TEM_PLAYERCTL:
            try:
                res = subprocess.run(
                    ["playerctl", "metadata", "--format", "{{title}} por {{artist}}"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                info = res.stdout.strip()
                if info and "No players found" not in info:
                    return True, f"Está tocando {info}."
            except Exception:
                pass
        return True, "Não há nenhuma música sendo reproduzida no momento."

    return False, ""
