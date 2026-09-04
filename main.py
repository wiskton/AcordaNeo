#!/usr/bin/env python3
"""Acorda, Neo — diga a frase de ativação e converse por voz com a IA (Ollama / Claude).

Uso: python3 main.py  (ou ./run.sh, que cria a venv e instala tudo sozinho)
"""

import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

# Identificadores de processo essenciais para Pop!_OS (COSMIC / GNOME / Wayland / X11)
GLib.set_prgname("acordaneo")
GLib.set_application_name("Acorda, Neo")

from assistente_voz import singleinstance
from assistente_voz.window import AVATAR_PATH, JanelaPrincipal

MATRIX_CSS = """
/* ==============================================================================
   ACORDA, NEO - TEMA MATRIX CYBERPUNK (GTK3)
   ============================================================================== */

window, .background {
    background-color: #040805;
    color: #a8f5c4;
}

headerbar {
    background-color: #060c08;
    border-bottom: 2px solid #00ff66;
    color: #00ff66;
    min-height: 46px;
    padding: 2px 8px;
}

headerbar .title {
    color: #00ff66;
    font-weight: 800;
    font-family: "JetBrains Mono", "Fira Code", "DejaVu Sans Mono", monospace;
    font-size: 14px;
}

headerbar .subtitle {
    color: #3bb366;
    font-family: "JetBrains Mono", "Fira Code", "DejaVu Sans Mono", monospace;
    font-size: 11px;
}

headerbar button {
    background-color: #08170d;
    border: 1px solid #1a4d27;
    border-radius: 8px;
    color: #00ff66;
    padding: 6px 10px;
}

headerbar button:hover {
    background-color: #0e2e18;
    border-color: #00ff66;
    color: #ffffff;
}

.matrix-topo-box {
    background-color: #060e08;
    border: 1px solid #143b1e;
    border-radius: 14px;
    padding: 16px;
    margin: 10px 14px 4px 14px;
}

.terminal-status {
    background-color: #020503;
    border: 1px solid #00ff66;
    border-radius: 8px;
    padding: 8px 16px;
    color: #00ff66;
    font-family: "JetBrains Mono", "Fira Code", "DejaVu Sans Mono", monospace;
    font-weight: 700;
    font-size: 12px;
}

.balao-usuario {
    background-color: #0a2414;
    border: 1px solid #00ff66;
    border-radius: 12px;
    padding: 10px 14px;
    margin: 3px 0;
}

.balao-assistente {
    background-color: #061109;
    border: 1px solid #1b4726;
    border-left: 4px solid #00ff66;
    border-radius: 12px;
    padding: 10px 14px;
    margin: 3px 0;
}

.balao-autor-usuario {
    color: #00ff66;
    font-family: "JetBrains Mono", "Fira Code", monospace;
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 1px;
    margin-bottom: 2px;
}

.balao-autor-assistente {
    color: #34d399;
    font-family: "JetBrains Mono", "Fira Code", monospace;
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 1px;
    margin-bottom: 2px;
}

.balao-texto-usuario {
    color: #e5ffe9;
    font-size: 13px;
    font-family: "JetBrains Mono", "Fira Code", "DejaVu Sans Mono", sans-serif;
}

.balao-texto-assistente {
    color: #a7f3d0;
    font-size: 13px;
    font-family: "JetBrains Mono", "Fira Code", "DejaVu Sans Mono", sans-serif;
}

.matrix-rodape {
    background-color: #050b07;
    border-top: 1px solid #14331d;
    padding: 12px 14px;
}

.matrix-label {
    color: #4ade80;
    font-family: "JetBrains Mono", "Fira Code", "DejaVu Sans Mono", monospace;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
}

combobox, combobox button, entry {
    background-color: #07130a;
    color: #00ff66;
    border: 1px solid #164e28;
    border-radius: 6px;
    font-family: "JetBrains Mono", "Fira Code", "DejaVu Sans Mono", monospace;
    font-size: 12px;
    padding: 4px 8px;
}

combobox:hover, combobox button:hover, entry:focus {
    border-color: #00ff66;
    color: #00ff66;
}

combobox menu, combobox window {
    background-color: #050b07;
    border: 1px solid #00ff66;
    color: #a8f5c4;
}

combobox menuitem:hover {
    background-color: #0d2816;
    color: #00ff66;
}

button {
    background-color: #08170d;
    color: #00ff66;
    border: 1px solid #1b4726;
    border-radius: 6px;
    padding: 6px 14px;
    font-family: "JetBrains Mono", "Fira Code", "DejaVu Sans Mono", monospace;
    font-weight: bold;
}

button:hover {
    background-color: #0f3019;
    border-color: #00ff66;
    color: #ffffff;
}

dialog {
    background-color: #050a06;
    color: #a8f5c4;
}

dialog .dialog-action-area button {
    margin: 4px;
}

scrollbar trough {
    background-color: #040805;
}

scrollbar slider {
    background-color: #143b1e;
    border-radius: 4px;
    min-width: 6px;
    min-height: 6px;
}

scrollbar slider:hover {
    background-color: #00ff66;
}

separator {
    background-color: #14331d;
    min-height: 1px;
}
""".encode("utf-8")


def main():
    if not singleinstance.adquirir():
        dialogo = Gtk.MessageDialog(
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text="O Acorda, Neo já está rodando.",
            secondary_text="Só pode ter uma instância aberta por vez (as duas ficariam "
            "brigando pelo microfone). Feche a outra janela antes de abrir de novo.",
        )
        if AVATAR_PATH.exists():
            dialogo.set_icon_from_file(str(AVATAR_PATH))
        dialogo.run()
        dialogo.destroy()
        sys.exit(1)

    # Configura ícone padrão das janelas
    if AVATAR_PATH.exists():
        Gtk.Window.set_default_icon_from_file(str(AVATAR_PATH))
    Gtk.Window.set_default_icon_name("acordaneo")

    provider = Gtk.CssProvider()
    provider.load_from_data(MATRIX_CSS)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

    janela = JanelaPrincipal()
    janela.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()

