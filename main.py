#!/usr/bin/env python3
"""Assistente de Voz — pergunte por voz, a Claude responde por voz.

Uso: python3 main.py  (ou ./run.sh, que cria a venv e instala tudo sozinho)
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk

from assistente_voz.window import JanelaPrincipal

CSS = b"""
.balao-usuario {
    background-color: #2f5fd6;
    color: #ffffff;
    border-radius: 16px;
    padding: 10px 14px;
}
.balao-assistente {
    background-color: #1e2226;
    color: #e8e8e8;
    border-radius: 16px;
    padding: 10px 14px;
}
"""


def main():
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

    janela = JanelaPrincipal()
    janela.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
