"""Janela principal GTK3: avatar, histórico da conversa e escuta contínua.

Sem botão de microfone — o app fica sempre ouvindo em segundo plano e só
"acorda" quando reconhece a frase de ativação ("Acorda, Neo").
"""

import os
import tempfile
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
from .chatgpt_web import ChatGPTWebClient, ChatGPTWebError
from .claude_client import ClaudeClient
from .tts import sintetizar, tocar

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
AVATAR_PATH = ASSETS_DIR / "avatar.png"

DURACAO_CLIPE_ATIVACAO = 3       # segundos por trecho enquanto espera "Acorda, Neo"
DURACAO_CLIPE_PERGUNTA = 2       # segundos por trecho enquanto ouve a pergunta
MAX_SILENCIOS_INICIAIS = 3       # até 6s de espera para o usuário começar a falar
MAX_SILENCIOS_APOS_FALA = 1      # 2s de pausa após a fala encerra a pergunta
MAX_SEGUNDOS_PERGUNTA = 25       # teto de segurança pra não gravar pra sempre


class JanelaPrincipal(Gtk.Window):
    def __init__(self):
        super().__init__(title="Acorda, Neo")
        self.set_default_size(440, 720)
        self.set_border_width(0)

        # Garante níveis saudáveis no microfone ALSA (sem saturação de boost)
        stt.configurar_microfone_sistema()

        self._config = config.carregar()
        self._claude = None
        self._chatgpt_web = None
        self._ocupado = False
        self._escutando = True

        self._montar_ui()
        self.connect("destroy", self._ao_fechar)

        if not self._tem_credenciais_do_provedor_atual():
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

        # --- Rodapé: seletor de provedor (Claude/ChatGPT) e de voz, sem botão ----
        rodape = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        rodape.set_border_width(16)
        raiz.pack_start(rodape, False, False, 0)

        rodape.pack_start(Gtk.Label(label="Quem responde:", xalign=0), False, False, 0)

        self._provedor_combo = Gtk.ComboBoxText()
        for id_provedor, nome in config.PROVEDORES_DISPONIVEIS:
            self._provedor_combo.append(id_provedor, nome)
        self._provedor_combo.set_active_id(self._config.get("provedor", config.DEFAULT_PROVEDOR))
        self._provedor_combo.connect("changed", self._on_trocar_provedor)
        rodape.pack_start(self._provedor_combo, False, False, 0)

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

        box.add(Gtk.Label(label="<b>Claude (API oficial)</b>", use_markup=True, xalign=0))
        box.add(Gtk.Label(label="Chave da API da Anthropic:", xalign=0))
        entrada_chave = Gtk.Entry()
        entrada_chave.set_visibility(False)
        entrada_chave.set_text(self._config.get("anthropic_api_key", ""))
        entrada_chave.set_placeholder_text("sk-ant-...")
        box.add(entrada_chave)

        box.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        box.add(Gtk.Label(label="<b>ChatGPT (navegador, gambiarra)</b>", use_markup=True, xalign=0))
        aviso_chatgpt = Gtk.Label(
            label="Faz login na sua conta do ChatGPT num navegador Chrome de verdade — "
            "a sessão fica salva, só precisa logar de novo se expirar.",
            xalign=0,
        )
        aviso_chatgpt.set_line_wrap(True)
        box.add(aviso_chatgpt)

        box.add(Gtk.Label(label="E-mail do ChatGPT:", xalign=0))
        entrada_email = Gtk.Entry()
        entrada_email.set_text(self._config.get("chatgpt_email", ""))
        entrada_email.set_placeholder_text("voce@email.com")
        box.add(entrada_email)

        box.add(Gtk.Label(label="Senha do ChatGPT:", xalign=0))
        entrada_senha = Gtk.Entry()
        entrada_senha.set_visibility(False)
        entrada_senha.set_text(self._config.get("chatgpt_senha", ""))
        box.add(entrada_senha)

        check_headless = Gtk.CheckButton(label="Rodar em segundo plano (sem mostrar a janela do navegador)")
        check_headless.set_active(bool(self._config.get("chatgpt_headless", True)))
        box.add(check_headless)

        box.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        box.add(Gtk.Label(label="Voz padrão:", xalign=0))
        combo_voz = Gtk.ComboBoxText()
        for id_voz, nome in config.VOZES_DISPONIVEIS:
            combo_voz.append(id_voz, nome)
        combo_voz.set_active_id(self._config.get("voz", config.DEFAULT_VOICE))
        box.add(combo_voz)

        if obrigatorio:
            aviso = Gtk.Label(
                label="Configure a Claude ou o ChatGPT (pelo menos um) pra começar a usar o assistente."
            )
            aviso.set_line_wrap(True)
            box.add(aviso)

        box.show_all()
        resposta = dialogo.run()

        if resposta == Gtk.ResponseType.OK:
            self._config["anthropic_api_key"] = entrada_chave.get_text().strip()
            self._config["chatgpt_email"] = entrada_email.get_text().strip()
            self._config["chatgpt_senha"] = entrada_senha.get_text()
            self._config["chatgpt_headless"] = check_headless.get_active()
            self._config["voz"] = combo_voz.get_active_id() or config.DEFAULT_VOICE
            config.salvar(self._config)
            self._voz_combo.set_active_id(self._config["voz"])
            self._claude = None  # força recriar os clientes com as credenciais novas
            if self._chatgpt_web is not None:
                self._chatgpt_web.fechar()
                self._chatgpt_web = None

        dialogo.destroy()
        return False

    def _tem_credenciais_do_provedor_atual(self) -> bool:
        provedor = self._config.get("provedor", config.DEFAULT_PROVEDOR)
        if provedor == config.PROVEDOR_CHATGPT_WEB:
            return bool(self._config.get("chatgpt_email")) and bool(self._config.get("chatgpt_senha"))
        return bool(self._config.get("anthropic_api_key"))

    def _on_trocar_provedor(self, combo):
        self._config["provedor"] = combo.get_active_id() or config.DEFAULT_PROVEDOR
        config.salvar(self._config)

    def _on_trocar_voz(self, combo):
        self._config["voz"] = combo.get_active_id() or config.DEFAULT_VOICE
        config.salvar(self._config)

    # ---------------------------------------------------------- Escuta contínua

    def _ao_fechar(self, *_args):
        self._escutando = False
        if self._chatgpt_web is not None:
            self._chatgpt_web.fechar()
        Gtk.main_quit()

    def _loop_escuta_continua(self):
        """Roda pra sempre numa thread separada: grava trechos curtos e checa se
        a frase de ativação foi dita. Pausa enquanto uma pergunta está sendo
        processada ou a resposta está sendo falada, pra não se auto-escutar.
        """
        while self._escutando:
            if self._ocupado or not self._tem_credenciais_do_provedor_atual():
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
        """Grava a fala do usuário acumulando trechos contínuos de áudio até detectar
        que o usuário terminou de falar (silêncio), e então transcreve a pergunta inteira
        de uma só vez com o modelo de alta precisão.
        """
        trechos = []
        segundos_gastos = 0
        silencios_iniciais = 0
        silencios_apos_fala = 0
        usuario_falou = False

        try:
            while segundos_gastos < MAX_SEGUNDOS_PERGUNTA:
                clipe = stt.gravar_clipe(DURACAO_CLIPE_PERGUNTA)
                if clipe is None:
                    time.sleep(0.5)
                    continue

                segundos_gastos += DURACAO_CLIPE_PERGUNTA
                tem_voz = stt.tem_voz(clipe)

                if tem_voz:
                    usuario_falou = True
                    trechos.append(clipe)
                    silencios_apos_fala = 0
                    GLib.idle_add(self._definir_status, "🎙️ Ouvindo...")
                else:
                    if not usuario_falou:
                        # Usuário ainda não começou a falar
                        clipe.unlink(missing_ok=True)
                        silencios_iniciais += 1
                        if silencios_iniciais >= MAX_SILENCIOS_INICIAIS:
                            # Passaram até 6s e ninguém falou
                            break
                    else:
                        # Usuário estava falando e fez pausa
                        trechos.append(clipe)  # preserva o fim da palavra
                        silencios_apos_fala += 1
                        if silencios_apos_fala >= MAX_SILENCIOS_APOS_FALA:
                            # Silêncio confirmado após fala -> encerra captura
                            break

            if not usuario_falou or not trechos:
                return ""

            GLib.idle_add(self._definir_status, "⏳ Entendendo...")
            fd, caminho_junto = tempfile.mkstemp(suffix=".wav", prefix="pergunta_completa_")
            os.close(fd)
            destino_junto = Path(caminho_junto)

            audio_completo = stt.concatenar_audios(trechos, destino_junto)
            if audio_completo is None:
                return ""

            return stt.transcrever(audio_completo)

        finally:
            for p in trechos:
                try:
                    p.unlink(missing_ok=True)
                except Exception:
                    pass

    def _processar_ciclo_pergunta(self):
        try:
            GLib.idle_add(self._definir_status, "🎙️ Pode perguntar...")
            texto_usuario = self._capturar_pergunta()

            if not texto_usuario:
                GLib.idle_add(self._definir_status, "Não entendi nada, diga \"Acorda, Neo\" de novo.")
                return

            GLib.idle_add(self._adicionar_balao, texto_usuario, "usuario")

            provedor = self._config.get("provedor", config.DEFAULT_PROVEDOR)
            if provedor == config.PROVEDOR_CHATGPT_WEB:
                GLib.idle_add(self._definir_status, "🤔 Pensando (ChatGPT)...")
                resposta = self._perguntar_chatgpt_web(texto_usuario)
            else:
                GLib.idle_add(self._definir_status, "🤔 Pensando (Claude)...")
                resposta = self._perguntar_claude(texto_usuario)

            GLib.idle_add(self._adicionar_balao, resposta, "assistente")
            GLib.idle_add(self._definir_status, "🗣️ Falando...")

            voz = self._config.get("voz", config.DEFAULT_VOICE)
            caminho_audio = sintetizar(resposta, voz)
            tocar(caminho_audio)
        except Exception as exc:  # noqa: BLE001 - mostrar qualquer erro pro usuário
            traceback.print_exc()
            GLib.idle_add(self._definir_status, f"⚠️ Erro: {exc}")

    def _perguntar_claude(self, texto_usuario: str) -> str:
        if self._claude is None:
            self._claude = ClaudeClient(
                api_key=self._config.get("anthropic_api_key", ""),
                model=self._config.get("modelo", config.DEFAULT_MODEL),
            )
        return self._claude.perguntar(texto_usuario)

    def _perguntar_chatgpt_web(self, texto_usuario: str) -> str:
        if self._chatgpt_web is None:
            self._chatgpt_web = ChatGPTWebClient(
                email=self._config.get("chatgpt_email", ""),
                senha=self._config.get("chatgpt_senha", ""),
                headless=bool(self._config.get("chatgpt_headless", True)),
            )
        try:
            return self._chatgpt_web.perguntar(texto_usuario)
        except ChatGPTWebError:
            # Sessão pode ter travado num estado ruim — descarta o navegador
            # pra tentar do zero na próxima pergunta, em vez de ficar preso.
            self._chatgpt_web.fechar()
            self._chatgpt_web = None
            raise
