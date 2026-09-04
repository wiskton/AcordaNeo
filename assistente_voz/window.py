"""Janela principal GTK3: avatar, histórico da conversa, botão de microfone
e seletor de voz.
"""

import threading
import traceback
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GdkPixbuf, GLib, Gtk

from . import config
from .claude_client import ClaudeClient
from .stt import Gravador, transcrever
from .tts import sintetizar, tocar

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
AVATAR_PATH = ASSETS_DIR / "avatar.png"


class JanelaPrincipal(Gtk.Window):
    def __init__(self):
        super().__init__(title="Assistente de Voz")
        self.set_default_size(440, 720)
        self.set_border_width(0)

        self._config = config.carregar()
        self._claude = None
        self._gravador = None
        self._gravando = False
        self._ocupado = False

        self._montar_ui()
        self.connect("destroy", Gtk.main_quit)

        if not self._config.get("anthropic_api_key"):
            GLib.idle_add(self._abrir_preferencias, True)

    # ------------------------------------------------------------------ UI

    def _montar_ui(self):
        header = Gtk.HeaderBar(title="Assistente de Voz", show_close_button=True)
        botao_config = Gtk.Button.new_from_icon_name("preferences-system-symbolic", Gtk.IconSize.BUTTON)
        botao_config.set_tooltip_text("Preferências (chave da API e voz)")
        botao_config.connect("clicked", lambda *_a: self._abrir_preferencias(False))
        header.pack_end(botao_config)
        self.set_titlebar(header)

        raiz = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(raiz)

        # --- Avatar + status ---------------------------------------------------
        topo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        topo.set_border_width(20)
        raiz.pack_start(topo, False, False, 0)

        self._avatar_img = Gtk.Image()
        self._carregar_avatar(180)
        topo.pack_start(self._avatar_img, False, False, 0)

        self._status_label = Gtk.Label(label="Pronto. Clique no microfone e fale.")
        self._status_label.set_justify(Gtk.Justification.CENTER)
        topo.pack_start(self._status_label, False, False, 0)

        # --- Histórico da conversa ----------------------------------------------
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        raiz.pack_start(scroll, True, True, 0)

        self._chat_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._chat_box.set_border_width(14)
        scroll.add(self._chat_box)
        self._scroll_window = scroll

        # --- Rodapé: voz + microfone ---------------------------------------------
        rodape = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        rodape.set_border_width(16)
        raiz.pack_start(rodape, False, False, 0)

        self._voz_combo = Gtk.ComboBoxText()
        for id_voz, nome in config.VOZES_DISPONIVEIS:
            self._voz_combo.append(id_voz, nome)
        voz_atual = self._config.get("voz", config.DEFAULT_VOICE)
        self._voz_combo.set_active_id(voz_atual)
        self._voz_combo.connect("changed", self._on_trocar_voz)
        rodape.pack_start(self._voz_combo, False, False, 0)

        self._botao_mic = Gtk.ToggleButton()
        self._botao_mic.set_label("🎙️  Falar")
        self._botao_mic.get_style_context().add_class("suggested-action")
        self._botao_mic.connect("toggled", self._on_alternar_gravacao)
        rodape.pack_start(self._botao_mic, False, False, 0)

    def _carregar_avatar(self, tamanho: int):
        if AVATAR_PATH.exists():
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                str(AVATAR_PATH), tamanho, tamanho, True
            )
            self._avatar_img.set_from_pixbuf(pixbuf)
        else:
            self._avatar_img.set_from_icon_name("avatar-default-symbolic", Gtk.IconSize.DIALOG)

    # --------------------------------------------------------------- Chat UI

    def _adicionar_balao(self, texto: str, autor: str):
        alinhamento = Gtk.Align.END if autor == "usuario" else Gtk.Align.START
        cor_classe = "usuario" if autor == "usuario" else "assistente"

        label = Gtk.Label(label=texto)
        label.set_line_wrap(True)
        label.set_max_width_chars(38)
        label.set_xalign(0)
        label.set_selectable(True)

        moldura = Gtk.Frame()
        moldura.set_shadow_type(Gtk.ShadowType.NONE)
        moldura.get_style_context().add_class(f"balao-{cor_classe}")
        moldura.add(label)
        moldura.set_halign(alinhamento)
        moldura.set_border_width(6)

        self._chat_box.pack_start(moldura, False, False, 0)
        self._chat_box.show_all()

        adj = self._scroll_window.get_vadjustment()
        GLib.idle_add(lambda: adj.set_value(adj.get_upper()))

    def _definir_status(self, texto: str):
        self._status_label.set_text(texto)

    # ------------------------------------------------------------ Preferências

    def _abrir_preferencias(self, obrigatorio: bool):
        dialogo = Gtk.Dialog(title="Preferências", transient_for=self, modal=True)
        dialogo.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        box = dialogo.get_content_area()
        box.set_border_width(16)
        box.set_spacing(10)

        box.add(Gtk.Label(label="Chave da API da Anthropic (Claude):", xalign=0))
        entrada_chave = Gtk.Entry()
        entrada_chave.set_visibility(False)
        entrada_chave.set_text(self._config.get("anthropic_api_key", ""))
        entrada_chave.set_placeholder_text("sk-ant-...")
        box.add(entrada_chave)

        box.add(Gtk.Label(label="Voz padrão:", xalign=0))
        combo = Gtk.ComboBoxText()
        for id_voz, nome in config.VOZES_DISPONIVEIS:
            combo.append(id_voz, nome)
        combo.set_active_id(self._config.get("voz", config.DEFAULT_VOICE))
        box.add(combo)

        if obrigatorio:
            aviso = Gtk.Label(
                label="Configure sua chave da API pra começar a usar o assistente."
            )
            aviso.set_line_wrap(True)
            box.add(aviso)

        box.show_all()
        resposta = dialogo.run()

        if resposta == Gtk.ResponseType.OK:
            self._config["anthropic_api_key"] = entrada_chave.get_text().strip()
            self._config["voz"] = combo.get_active_id() or config.DEFAULT_VOICE
            config.salvar(self._config)
            self._voz_combo.set_active_id(self._config["voz"])
            self._claude = None  # força recriar o cliente com a chave nova

        dialogo.destroy()
        return False

    def _on_trocar_voz(self, combo):
        self._config["voz"] = combo.get_active_id() or config.DEFAULT_VOICE
        config.salvar(self._config)

    # -------------------------------------------------------------- Gravação

    def _on_alternar_gravacao(self, botao: Gtk.ToggleButton):
        if self._ocupado:
            botao.set_active(self._gravando)
            return

        if botao.get_active():
            self._iniciar_gravacao()
        else:
            self._parar_gravacao_e_processar()

    def _iniciar_gravacao(self):
        self._gravando = True
        self._botao_mic.set_label("⏹️  Parar")
        self._definir_status("🎙️ Ouvindo... clique em \"Parar\" quando terminar.")
        self._gravador = Gravador()
        self._gravador.iniciar()

    def _parar_gravacao_e_processar(self):
        self._gravando = False
        self._ocupado = True
        self._botao_mic.set_sensitive(False)
        self._botao_mic.set_label("🎙️  Falar")
        self._definir_status("🤔 Processando o que você disse...")

        thread = threading.Thread(target=self._processar_pergunta, daemon=True)
        thread.start()

    # --------------------------------------------------------- Pipeline (thread)

    def _processar_pergunta(self):
        try:
            caminho_wav = self._gravador.parar()
            texto_usuario = transcrever(caminho_wav)

            if not texto_usuario:
                GLib.idle_add(self._definir_status, "Não entendi nada, tenta de novo.")
                GLib.idle_add(self._finalizar_processamento)
                return

            GLib.idle_add(self._adicionar_balao, texto_usuario, "usuario")
            GLib.idle_add(self._definir_status, "🤔 Pensando...")

            if self._claude is None:
                self._claude = ClaudeClient(
                    api_key=self._config.get("anthropic_api_key", ""),
                    model=self._config.get("modelo", config.DEFAULT_MODEL),
                )

            resposta = self._claude.perguntar(texto_usuario)
            GLib.idle_add(self._adicionar_balao, resposta, "assistente")
            GLib.idle_add(self._definir_status, "🗣️ Falando...")

            voz = self._config.get("voz", config.DEFAULT_VOICE)
            caminho_audio = sintetizar(resposta, voz)
            tocar(caminho_audio)

            GLib.idle_add(self._definir_status, "Pronto. Clique no microfone e fale.")
        except Exception as exc:  # noqa: BLE001 - mostrar qualquer erro pro usuário
            traceback.print_exc()
            GLib.idle_add(self._definir_status, f"⚠️ Erro: {exc}")
        finally:
            GLib.idle_add(self._finalizar_processamento)

    def _finalizar_processamento(self):
        self._ocupado = False
        self._botao_mic.set_sensitive(True)
        return False
