"""Comandos de automação do sistema Linux (volume, aplicativos, data/hora, bateria e exportação).

Permite que o Neo controle o ambiente local instantaneamente sem depender de chamadas à LLM.
"""

from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import subprocess
import unicodedata
from typing import List, Optional, Tuple

DIAS_SEMANA = [
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
]

MESES = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]


def _normalizar(texto: str) -> str:
    """Remove acentos, pontuações e converte para minúsculas."""
    sem_acentos = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return (
        sem_acentos.lower()
        .replace(",", " ")
        .replace(".", " ")
        .replace("!", " ")
        .replace("?", " ")
        .strip()
    )


# ------------------------------------------------------------- Volume do Sistema


def obter_volume() -> Tuple[Optional[int], bool]:
    """Obtém o volume atual (0-100) e o estado de mudo via wpctl ou pactl."""
    # 1. Tenta wpctl (PipeWire padrão)
    if shutil.which("wpctl"):
        try:
            out = subprocess.check_output(
                ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=1.5,
            )
            m = re.search(r"Volume:\s*([0-9.]+)", out)
            if m:
                vol = round(float(m.group(1)) * 100)
                mudo = "[MUTED]" in out
                return vol, mudo
        except Exception:
            pass

    # 2. Tenta pactl (PulseAudio / PipeWire-Pulse)
    if shutil.which("pactl"):
        try:
            out = subprocess.check_output(
                ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=1.5,
            )
            m = re.search(r"/ +(\d+)% +/", out)
            if m:
                vol = int(m.group(1))
                out_mute = subprocess.check_output(
                    ["pactl", "get-sink-mute", "@DEFAULT_SINK@"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                    timeout=1.5,
                )
                mudo = "yes" in out_mute.lower()
                return vol, mudo
        except Exception:
            pass

    return None, False


def alterar_volume(delta_percentual: int) -> Tuple[bool, str]:
    """Aumenta ou diminui o volume pelo valor relativo indicado."""
    sinal = "+" if delta_percentual > 0 else "-"
    abs_val = abs(delta_percentual)

    if shutil.which("wpctl"):
        try:
            subprocess.run(
                ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{abs_val}%{sinal}"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            vol, _ = obter_volume()
            vol_str = f" em {vol}%" if vol is not None else ""
            acao = "aumentado" if delta_percentual > 0 else "diminuído"
            return True, f"Volume {acao}{vol_str}."
        except Exception:
            pass

    if shutil.which("pactl"):
        try:
            subprocess.run(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{sinal}{abs_val}%"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            vol, _ = obter_volume()
            vol_str = f" em {vol}%" if vol is not None else ""
            acao = "aumentado" if delta_percentual > 0 else "diminuído"
            return True, f"Volume {acao}{vol_str}."
        except Exception:
            pass

    return False, "Não consegui ajustar o volume no sistema."


def definir_volume_absoluto(porcentagem: int) -> Tuple[bool, str]:
    """Define o volume em uma porcentagem fixa (0 a 100)."""
    p = max(0, min(100, porcentagem))
    fracao = f"{p / 100:.2f}"

    if shutil.which("wpctl"):
        try:
            subprocess.run(
                ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", fracao],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Desmuta automaticamente ao definir volume explícito
            subprocess.run(
                ["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True, f"Volume ajustado para {p}%."
        except Exception:
            pass

    if shutil.which("pactl"):
        try:
            subprocess.run(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{p}%"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True, f"Volume ajustado para {p}%."
        except Exception:
            pass

    return False, "Não foi possível alterar o volume para este valor."


def alternar_mudo(mutar: Optional[bool] = None) -> Tuple[bool, str]:
    """Muta, desmuta ou alterna o áudio do sistema."""
    if shutil.which("wpctl"):
        try:
            arg = "toggle" if mutar is None else ("1" if mutar else "0")
            subprocess.run(
                ["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", arg],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            _, mudo_agora = obter_volume()
            if mudo_agora:
                return True, "Áudio silenciado."
            return True, "Áudio reativado."
        except Exception:
            pass

    if shutil.which("pactl"):
        try:
            arg = "toggle" if mutar is None else ("1" if mutar else "0")
            subprocess.run(
                ["pactl", "set-sink-mute", "@DEFAULT_SINK@", arg],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            _, mudo_agora = obter_volume()
            if mudo_agora:
                return True, "Áudio silenciado."
            return True, "Áudio reativado."
        except Exception:
            pass

    return False, "Não consegui alterar o estado de mudo."


# ------------------------------------------------------------- Data, Hora e Bateria


def obter_hora_atual() -> str:
    """Retorna a hora atual de forma natural em português."""
    agora = datetime.now()
    hora = agora.hour
    minuto = agora.minute

    if minuto == 0:
        minutos_str = "em ponto"
    elif minuto == 1:
        minutos_str = "e um minuto"
    else:
        minutos_str = f"e {minuto} minutos"

    hora_str = "uma hora" if hora in (1, 13) and hora == 1 else f"{hora} horas"
    return f"Agora são {hora_str} {minutos_str}."


def obter_data_atual() -> str:
    """Retorna a data atual por extenso em português."""
    agora = datetime.now()
    dia_sem = DIAS_SEMANA[agora.weekday()]
    mes = MESES[agora.month - 1]
    return f"Hoje é {dia_sem}, dia {agora.day} de {mes} de {agora.year}."


def obter_status_bateria() -> str:
    """Consulta o nível de carga e status da bateria."""
    # 1. Tenta leitura direta do sysfs (mais rápida)
    bat_dirs = list(Path("/sys/class/power_supply").glob("BAT*"))
    if bat_dirs:
        bat = bat_dirs[0]
        cap_file = bat / "capacity"
        status_file = bat / "status"
        if cap_file.exists():
            try:
                cap = cap_file.read_text().strip()
                status_trad = {
                    "charging": "carregando",
                    "discharging": "descarregando",
                    "full": "totalmente carregada",
                    "not charging": "conectada à energia sem carregar",
                }
                st = (
                    status_trad.get(status_file.read_text().strip().lower(), "")
                    if status_file.exists()
                    else ""
                )
                if st:
                    return f"A bateria está em {cap}%, {st}."
                return f"A bateria está com {cap}% de carga."
            except Exception:
                pass

    # 2. Tenta upower
    if shutil.which("upower"):
        try:
            out = subprocess.check_output(
                ["upower", "-i", "/org/freedesktop/UPower/devices/battery_BAT0"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=2.0,
            )
            m_pct = re.search(r"percentage:\s*(\d+)%", out)
            m_state = re.search(r"state:\s*([a-zA-Z-]+)", out)
            if m_pct:
                pct = m_pct.group(1)
                st_map = {
                    "charging": "carregando",
                    "discharging": "descarregando",
                    "fully-charged": "totalmente carregada",
                    "pending-charge": "aguardando carga",
                }
                st_raw = m_state.group(1).lower() if m_state else ""
                st_txt = st_map.get(st_raw, "")
                if st_txt:
                    return f"A bateria está em {pct}%, {st_txt}."
                return f"A bateria está em {pct}% de carga."
        except Exception:
            pass

    return "Não encontrei informações de bateria neste computador."


# ------------------------------------------------------------- Lançador de Aplicativos


def abrir_aplicativo_sistema(categoria: str) -> Tuple[bool, str]:
    """Inicia aplicativos locais do ambiente Linux em segundo plano."""
    categoria = categoria.lower()

    # Mapeamento com prioridade para COSMIC / Pop!_OS / GNOME
    candidatos = []
    if categoria == "navegador":
        candidatos = [
            ["gtk-launch", "com.brave.Origin.nightly"],
            ["gtk-launch", "com.brave.Browser"],
            ["gtk-launch", "com.google.Chrome"],
            ["gtk-launch", "firefox"],
            ["xdg-open", "https://google.com"],
        ]
        nome_amigavel = "o navegador"
    elif categoria == "terminal":
        candidatos = [
            ["cosmic-term"],
            ["x-terminal-emulator"],
            ["gnome-terminal"],
            ["ptyxis"],
            ["alacritty"],
            ["kitty"],
        ]
        nome_amigavel = "o terminal"
    elif categoria == "arquivos":
        candidatos = [
            ["cosmic-files"],
            ["nautilus"],
            ["xdg-open", str(Path.home())],
        ]
        nome_amigavel = "o gerenciador de arquivos"
    elif categoria == "configuracoes":
        candidatos = [
            ["cosmic-settings"],
            ["gnome-control-center"],
        ]
        nome_amigavel = "as configurações do sistema"
    elif categoria == "editor":
        candidatos = [
            ["cosmic-edit"],
            ["gedit"],
            ["code"],
        ]
        nome_amigavel = "o editor de texto"
    elif categoria == "spotify":
        candidatos = [
            ["spotify"],
            ["flatpak", "run", "com.spotify.Client"],
        ]
        nome_amigavel = "o Spotify"
    else:
        return False, f"Não sei como abrir {categoria}."

    for cmd in candidatos:
        exe = cmd[0]
        if shutil.which(exe):
            try:
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                return True, f"Abrindo {nome_amigavel}."
            except Exception:
                continue

    return False, f"Não foi possível iniciar {nome_amigavel}."


# ------------------------------------------------------------- Exportação Markdown


def exportar_historico_markdown(
    historico: List[dict],
    caminho_destino: Optional[Path] = None,
    provedor_info: str = "Ollama",
) -> Path:
    """Salva a conversa atual formatada em arquivo Markdown (.md)."""
    if caminho_destino is None:
        docs = Path.home() / "Documents"
        if not docs.exists():
            docs = Path.home()
        agora = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        caminho_destino = docs / f"conversa_neo_{agora}.md"

    linhas = [
        "# 🕶️ Acorda, Neo — Histórico da Conversa",
        f"- **Data de exportação:** {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}",
        f"- **Cérebro / Provedor:** {provedor_info}",
        "",
        "---",
        "",
    ]

    if not historico:
        linhas.append("*Nenhuma mensagem registrada nesta sessão.*")
    else:
        for item in historico:
            papel = item.get("role")
            conteudo = item.get("content", "").strip()
            if papel == "user":
                linhas.extend([
                    "### 🧑 Você",
                    conteudo,
                    "",
                ])
            elif papel == "assistant":
                linhas.extend([
                    "### 🕶️ Neo",
                    conteudo,
                    "",
                ])

    caminho_destino.write_text("\n".join(linhas), encoding="utf-8")
    return caminho_destino


# ------------------------------------------------------------- Reconhecimento de Comandos


def executar_comando_sistema(texto_bruto: str, historico: List[dict] = None) -> Tuple[bool, str]:
    """Analisa a fala do usuário e executa o comando de sistema correspondente se houver.
    Retorna (True, mensagem_resposta) se o comando foi tratado, ou (False, "") caso contrário.
    """
    t = _normalizar(texto_bruto)

    # 1. Volume do sistema
    if any(g in t for g in ["aumentar volume", "aumente o volume", "mais volume", "subir o volume", "aumente volume"]):
        sucesso, msg = alterar_volume(+10)
        return True, msg

    if any(g in t for g in ["diminuir volume", "diminua o volume", "abaixar volume", "abaixe o volume", "baixe o volume", "menos volume"]):
        sucesso, msg = alterar_volume(-10)
        return True, msg

    if any(t == g or t.startswith(f"{g} ") for g in ["mutar", "mudo", "silenciar", "mutar som", "mutar audio"]):
        sucesso, msg = alternar_mudo(True)
        return True, msg

    if any(g in t for g in ["desmutar", "desilenciar", "ativar som", "desmutar audio"]):
        sucesso, msg = alternar_mudo(False)
        return True, msg

    m_vol = re.search(r"volume (?:em|para|de)\s*(\d{1,3})", t)
    if m_vol:
        num = int(m_vol.group(1))
        sucesso, msg = definir_volume_absoluto(num)
        return True, msg

    if any(g in t for g in ["qual o volume", "como esta o volume", "nivel do volume", "volume atual"]):
        vol, mudo = obter_volume()
        if vol is not None:
            st = " e está mutado" if mudo else ""
            return True, f"O volume está em {vol}%{st}."
        return True, "Não consegui ler o volume atual."

    # 2. Data e Hora
    if any(g in t for g in ["que horas sao", "qual a hora", "horas agora", "que hora e"]):
        return True, obter_hora_atual()

    if any(g in t for g in ["que dia e hoje", "qual a data de hoje", "qual a data", "data de hoje"]):
        return True, obter_data_atual()

    # 3. Bateria
    if any(g in t for g in ["quanto de bateria", "nivel da bateria", "status da bateria", "como esta a bateria", "porcentagem da bateria"]):
        return True, obter_status_bateria()

    # 4. Abrir Aplicativos
    if any(g in t for g in ["abrir navegador", "abra o navegador", "abrir a internet", "abrir chrome", "abrir brave", "abrir firefox"]):
        sucesso, msg = abrir_aplicativo_sistema("navegador")
        return True, msg

    if any(g in t for g in ["abrir terminal", "abra o terminal", "abrir console", "abra o console"]):
        sucesso, msg = abrir_aplicativo_sistema("terminal")
        return True, msg

    if any(g in t for g in ["abrir arquivos", "abra os arquivos", "abrir pastas", "abrir gerenciador de arquivos", "abrir nautilus"]):
        sucesso, msg = abrir_aplicativo_sistema("arquivos")
        return True, msg

    if any(g in t for g in ["abrir configuracoes", "abra as configuracoes", "abrir painel de controle", "abrir ajustes"]):
        sucesso, msg = abrir_aplicativo_sistema("configuracoes")
        return True, msg

    if any(g in t for g in ["abrir editor", "abra o editor", "abrir editor de texto", "abrir vscode", "abrir code"]):
        sucesso, msg = abrir_aplicativo_sistema("editor")
        return True, msg

    if any(g in t for g in ["abrir spotify", "abra o spotify"]):
        sucesso, msg = abrir_aplicativo_sistema("spotify")
        return True, msg

    # 5. Exportar Conversa
    if any(g in t for g in ["exportar conversa", "exportar historico", "salvar conversa", "salvar historico", "fazer backup da conversa"]):
        arq = exportar_historico_markdown(historico or [])
        return True, f"Conversa exportada com sucesso para {arq.name} na sua pasta Documentos."

    return False, ""
