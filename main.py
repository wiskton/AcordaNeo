#!/usr/bin/env python3
"""Acorda, Neo — diga a frase de ativação e converse por voz com a Claude.

Uso: python3 main.py  (ou ./run.sh, que cria a venv e instala tudo sozinho)
"""

import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

from assistente_voz import singleinstance
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
    if not singleinstance.adquirir():
        dialogo = Gtk.MessageDialog(
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text="O Acorda, Neo já está rodando.",
            secondary_text="Só pode ter uma instância aberta por vez (as duas ficariam "
            "brigando pelo microfone). Feche a outra janela antes de abrir de novo.",
        )
        dialogo.run()
        dialogo.destroy()
        sys.exit(1)

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
