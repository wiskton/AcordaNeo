"""Janela principal GTK3: avatar, histórico da conversa e escuta contínua.

Sem botão de microfone — o app fica sempre ouvindo em segundo plano e só
"acorda" quando reconhece a frase de ativação ("Acorda, Neo").
"""

import threading
import time
import traceback
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, GLib, Gtk

from . import config
from . import stt
from .claude_client import ClaudeClient
from .tts import sintetizar, tocar

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
AVATAR_PATH = ASSETS_DIR / "avatar.png"

DURACAO_CLIPE_ATIVACAO = 3.0     # segundos por trecho enquanto espera "Acorda, Neo"
DURACAO_CLIPE_PERGUNTA = 2.5     # segundos por trecho enquanto ouve a pergunta
TOLERANCIA_SILENCIO = 1          # nº de trechos vazios seguidos até considerar que a pergunta acabou
MAX_SEGUNDOS_PERGUNTA = 20       # teto de segurança pra não gravar pra sempre


class JanelaPrincipal(Gtk.Window):
    def __init__(self):
        super().__init__(title="Acorda, Neo")
        self.set_default_size(440, 720)
        self.set_border_width(0)

        self._config = config.carregar()
        self._claude = None
        self._ocupado = False
        self._escutando = True

        self._montar_ui()
        self.connect("destroy", self._ao_fechar)

        if not self._config.get("anthropic_api_key"):
            GLib.idle_add(self._abrir_preferencias, True)

        thread_escuta = threading.Thread(target=self._loop_escuta_continua, daemon=True)
        thread_escuta.start()

    # ------------------------------------------------------------------ UI

    def _montar_ui(self):
        header = Gtk.HeaderBar(title="Acorda, Neo", show_close_button=True)
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

        self._status_label = Gtk.Label(label="👂 Diga \"Acorda, Neo\" pra começar.")
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

        # --- Rodapé: só o seletor de voz, sem botão ------------------------------
        rodape = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        rodape.set_border_width(16)
        raiz.pack_start(rodape, False, False, 0)

        rodape.pack_start(Gtk.Label(label="Voz das respostas:", xalign=0), False, False, 0)

        self._voz_combo = Gtk.ComboBoxText()
        for id_voz, nome in config.VOZES_DISPONIVEIS:
            self._voz_combo.append(id_voz, nome)
        voz_atual = self._config.get("voz", config.DEFAULT_VOICE)
        self._voz_combo.set_active_id(voz_atual)
        self._voz_combo.connect("changed", self._on_trocar_voz)
        rodape.pack_start(self._voz_combo, False, False, 0)

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
        return False

    def _definir_status(self, texto: str):
        self._status_label.set_text(texto)
        return False

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

    # ---------------------------------------------------------- Escuta contínua

    def _ao_fechar(self, *_args):
        self._escutando = False
        Gtk.main_quit()

    def _loop_escuta_continua(self):
        """Roda pra sempre numa thread separada: grava trechos curtos e checa se
        a frase de ativação foi dita. Pausa enquanto uma pergunta está sendo
        processada ou a resposta está sendo falada, pra não se auto-escutar.
        """
        while self._escutando:
            if self._ocupado or not self._config.get("anthropic_api_key"):
                time.sleep(0.2)
                continue

            try:
                GLib.idle_add(self._definir_status, "👂 Diga \"Acorda, Neo\" pra começar.")
                clipe = stt.gravar_clipe(DURACAO_CLIPE_ATIVACAO)

                if not self._escutando:
                    break

                if clipe is None:
                    # Gravação falhou (mic ocupado, dispositivo indisponível...) —
                    # espera um pouco antes de tentar de novo, sem girar sem parar.
                    time.sleep(1.0)
                    continue

                if stt.contem_palavra_ativacao(clipe):
                    self._ocupado = True
                    self._processar_ciclo_pergunta()
                    self._ocupado = False
            except Exception:
                traceback.print_exc()
                self._ocupado = False
                time.sleep(1.0)

    def _capturar_pergunta(self) -> str:
        """Grava trechos curtos em sequência, transcrevendo cada um, até detectar
        um trecho de silêncio (ou estourar o tempo máximo)."""
        texto_total = []
        segundos_gastos = 0.0
        trechos_vazios_seguidos = 0

        while segundos_gastos < MAX_SEGUNDOS_PERGUNTA:
            clipe = stt.gravar_clipe(DURACAO_CLIPE_PERGUNTA)
            segundos_gastos += DURACAO_CLIPE_PERGUNTA
            texto = stt.transcrever(clipe)

            if texto:
                texto_total.append(texto)
                trechos_vazios_seguidos = 0
            else:
                trechos_vazios_seguidos += 1
                if texto_total and trechos_vazios_seguidos >= TOLERANCIA_SILENCIO:
                    break

        return " ".join(texto_total).strip()

    def _processar_ciclo_pergunta(self):
        try:
            GLib.idle_add(self._definir_status, "🎙️ Pode perguntar...")
            texto_usuario = self._capturar_pergunta()

            if not texto_usuario:
                GLib.idle_add(self._definir_status, "Não entendi nada, diga \"Acorda, Neo\" de novo.")
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
        except Exception as exc:  # noqa: BLE001 - mostrar qualquer erro pro usuário
            traceback.print_exc()
            GLib.idle_add(self._definir_status, f"⚠️ Erro: {exc}")
