"""Janela principal GTK3: avatar, histórico da conversa e escuta contínua.

Sem botão de microfone — o app fica sempre ouvindo em segundo plano e só
"acorda" quando reconhece a frase de ativação ("Acorda, Neo").
Prioriza inteligência local 100% offline via Ollama, com Claude como opção.
"""

import os
import tempfile
import threading
import time
import traceback
import unicodedata
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, GLib, Gtk

from . import config
from . import mpris
from . import singleinstance
from . import sistema
from . import sons
from . import stt
from . import tts
from .claude_client import ClaudeClient
from .ollama_client import OllamaClient, OllamaError
from .tray import TrayManager
from .tts import sintetizar, tocar

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
AVATAR_PATH = ASSETS_DIR / "avatar.png"

DURACAO_CLIPE_ATIVACAO = 3       # segundos por trecho enquanto espera "Acorda, Neo"
DURACAO_CLIPE_PERGUNTA = 2       # segundos por trecho enquanto ouve a pergunta
DURACAO_CLIPE_INTERRUPCAO = 1    # segundos por trecho enquanto monitora interrupção (barge-in)
MAX_SILENCIOS_INICIAIS = 2       # até 4s de espera para o usuário começar a falar
MAX_SILENCIOS_APOS_FALA = 1      # 2s de pausa após a fala encerra a pergunta
MAX_SEGUNDOS_PERGUNTA = 25       # teto de segurança pra não gravar pra sempre


class JanelaPrincipal(Gtk.Window):
    def __init__(self):
        super().__init__(title="Acorda, Neo")
        self.set_default_size(440, 680)
        self.set_border_width(0)

        # Configura ícone da janela e identificadores para o ambiente desktop Pop!_OS / COSMIC / GNOME
        if AVATAR_PATH.exists():
            self.set_icon_from_file(str(AVATAR_PATH))
        self.set_icon_name("acordaneo")
        self.set_wmclass("acordaneo", "acordaneo")
        self.set_role("acordaneo")

        # Garante níveis saudáveis no microfone ALSA (sem saturação de boost)
        stt.configurar_microfone_sistema()

        self._config = config.carregar()
        self._claude = None
        self._ollama = None
        self._ocupado = False
        self._escutando = True
        self._historico = []

        self._montar_ui()
        self.connect("delete-event", self._ao_deletar_janela)
        self.connect("destroy", self._ao_fechar)

        # Inicializa servidor IPC para atalhos globais de teclado (Push-to-Talk)
        singleinstance.iniciar_servidor_comandos(self._ao_comando_ipc)

        # Inicializa o ícone da bandeja do sistema (System Tray)
        self._tray = TrayManager(
            ao_alternar_janela=self._alternar_visibilidade_janela,
            ao_abrir_preferencias=lambda: self._abrir_preferencias(False),
            ao_sair=self._sair_aplicativo,
            icone_path=AVATAR_PATH,
            ao_exportar_conversa=self._exportar_conversa_ui,
        )

        if not self._tem_credenciais_ou_provedor_pronto():
            GLib.idle_add(self._abrir_preferencias, True)

        thread_escuta = threading.Thread(target=self._loop_escuta_continua, daemon=True)
        thread_escuta.start()

    # ------------------------------------------------------------------ UI

    def _montar_ui(self):
        header = Gtk.HeaderBar(title="Acorda, Neo", show_close_button=True)

        botao_config = Gtk.Button.new_from_icon_name("preferences-system-symbolic", Gtk.IconSize.BUTTON)
        botao_config.set_tooltip_text("Configurações (Cérebro, Modelo, Voz e Prompt)")
        botao_config.connect("clicked", lambda *_a: self._abrir_preferencias(False))
        header.pack_end(botao_config)

        botao_exportar = Gtk.Button.new_from_icon_name("document-save-symbolic", Gtk.IconSize.BUTTON)
        botao_exportar.set_tooltip_text("Exportar conversa para Markdown (.md)")
        botao_exportar.connect("clicked", lambda *_a: self._exportar_conversa_ui())
        header.pack_end(botao_exportar)

        botao_limpar = Gtk.Button.new_from_icon_name("edit-clear-all-symbolic", Gtk.IconSize.BUTTON)
        botao_limpar.set_tooltip_text("Limpar histórico da conversa (Novo chat)")
        botao_limpar.connect("clicked", lambda *_a: self._limpar_historico_ui())
        header.pack_end(botao_limpar)

        self.set_titlebar(header)
        self._header = header
        self._atualizar_subtitulo_header()

        raiz = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(raiz)

        # --- Avatar + status (Card Matrix centralizado) -------------------------
        topo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        topo.get_style_context().add_class("matrix-topo-box")
        raiz.pack_start(topo, False, False, 0)

        self._avatar_img = Gtk.Image()
        self._carregar_avatar(175)
        topo.pack_start(self._avatar_img, False, False, 0)

        self._status_label = Gtk.Label(label="[ SYSTEM ONLINE ]  Diga \"Acorda, Neo\"")
        self._status_label.set_justify(Gtk.Justification.CENTER)
        self._status_label.get_style_context().add_class("terminal-status")
        topo.pack_start(self._status_label, False, False, 0)

        # --- Histórico da conversa ----------------------------------------------
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        raiz.pack_start(scroll, True, True, 0)

        self._chat_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._chat_box.set_border_width(14)
        scroll.add(self._chat_box)
        self._scroll_window = scroll

    def _atualizar_subtitulo_header(self):
        if not hasattr(self, "_header") or not self._header:
            return
        provedor = self._config.get("provedor", config.DEFAULT_PROVEDOR)
        if provedor == config.PROVEDOR_OLLAMA:
            mod = self._config.get("ollama_model", config.DEFAULT_OLLAMA_MODEL)
            self._header.set_subtitle(f"OLLAMA LOCAL // {mod}")
        else:
            mod = self._config.get("modelo", config.DEFAULT_MODEL) or config.DEFAULT_MODEL
            self._header.set_subtitle(f"CLAUDE // {mod}")

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

        box_conteudo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        prefixo = "🧑 VOCÊ" if autor == "usuario" else "🕶️ NEO"
        lbl_autor = Gtk.Label(label=prefixo)
        lbl_autor.set_xalign(1.0 if autor == "usuario" else 0.0)
        lbl_autor.get_style_context().add_class(f"balao-autor-{cor_classe}")
        box_conteudo.pack_start(lbl_autor, False, False, 0)

        label = Gtk.Label(label=texto)
        label.set_line_wrap(True)
        label.set_max_width_chars(38)
        label.set_xalign(0)
        label.set_selectable(True)
        label.get_style_context().add_class(f"balao-texto-{cor_classe}")
        box_conteudo.pack_start(label, False, False, 0)

        moldura = Gtk.Frame()
        moldura.set_shadow_type(Gtk.ShadowType.NONE)
        moldura.get_style_context().add_class(f"balao-{cor_classe}")
        moldura.add(box_conteudo)
        moldura.set_halign(alinhamento)
        moldura.set_border_width(4)

        self._chat_box.pack_start(moldura, False, False, 0)
        self._chat_box.show_all()

        adj = self._scroll_window.get_vadjustment()
        GLib.idle_add(lambda: adj.set_value(adj.get_upper()))
        return False

    def _definir_status(self, texto: str, estado: str = "escutando"):
        self._status_label.set_text(texto)
        if hasattr(self, "_tray") and self._tray:
            self._tray.definir_status(texto, estado)
        return False

    # ------------------------------------------------------------ Preferências

    def _abrir_preferencias(self, obrigatorio: bool):
        dialogo = Gtk.Dialog(title="Configurações do Sistema", transient_for=self, modal=True)
        dialogo.set_default_size(480, 620)
        if AVATAR_PATH.exists():
            dialogo.set_icon_from_file(str(AVATAR_PATH))
        dialogo.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK)

        area_conteudo = dialogo.get_content_area()
        area_conteudo.set_border_width(8)

        scroll_dialog = Gtk.ScrolledWindow()
        scroll_dialog.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll_dialog.set_propagate_natural_height(True)
        area_conteudo.pack_start(scroll_dialog, True, True, 0)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(12)
        scroll_dialog.add(box)

        # 1. Cérebro da IA (Provedor)
        box.add(Gtk.Label(label="<b>🧠 Cérebro da IA (Provedor):</b>", use_markup=True, xalign=0))
        combo_prov = Gtk.ComboBoxText()
        for id_p, nome_p in config.PROVEDORES_DISPONIVEIS:
            combo_prov.append(id_p, nome_p)
        combo_prov.set_active_id(self._config.get("provedor", config.DEFAULT_PROVEDOR))
        box.add(combo_prov)

        box.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # 2. Ollama (Local / 100% Offline)
        box.add(Gtk.Label(label="<b>🖥️ Ollama (Local / 100% Offline / Gratuito)</b>", use_markup=True, xalign=0))
        box.add(Gtk.Label(label="Endereço do Servidor Ollama:", xalign=0))
        entrada_ollama_host = Gtk.Entry()
        entrada_ollama_host.set_text(self._config.get("ollama_host", config.DEFAULT_OLLAMA_HOST))
        box.add(entrada_ollama_host)

        box.add(Gtk.Label(label="Modelo Local do Ollama:", xalign=0))
        combo_ollama_model = Gtk.ComboBoxText.new_with_entry()
        host_atual = entrada_ollama_host.get_text().strip() or config.DEFAULT_OLLAMA_HOST
        client_test = OllamaClient(host=host_atual)
        modelos_locais = client_test.listar_modelos()
        if not modelos_locais:
            modelos_locais = ["llama3.2:3b", "llama3.2", "qwen3:8b", "mistral"]
        for m in modelos_locais:
            combo_ollama_model.append(m, m)
        modelo_salvo = self._config.get("ollama_model", config.DEFAULT_OLLAMA_MODEL)
        combo_ollama_model.get_child().set_text(modelo_salvo)
        box.add(combo_ollama_model)

        # Baixar novo modelo do Ollama direto pela interface
        box.add(Gtk.Label(label="Baixar novo modelo (ex: deepseek-r1:8b, mistral):", xalign=0))
        box_pull = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        entrada_pull = Gtk.Entry()
        entrada_pull.set_placeholder_text("Nome do modelo...")
        btn_pull = Gtk.Button(label="Baixar Modelo")
        box_pull.pack_start(entrada_pull, True, True, 0)
        box_pull.pack_end(btn_pull, False, False, 0)
        box.add(box_pull)

        progresso_pull = Gtk.ProgressBar()
        progresso_pull.set_no_show_all(True)
        lbl_status_pull = Gtk.Label(xalign=0)
        lbl_status_pull.set_no_show_all(True)
        box.add(progresso_pull)
        box.add(lbl_status_pull)

        def _executar_pull(*_a):
            mod_alvo = entrada_pull.get_text().strip()
            if not mod_alvo:
                return
            btn_pull.set_sensitive(False)
            progresso_pull.set_fraction(0.0)
            progresso_pull.show()
            lbl_status_pull.set_text(f"Iniciando download de {mod_alvo}...")
            lbl_status_pull.show()

            def _thread_pull():
                def _progresso(status_txt, fracao):
                    GLib.idle_add(lbl_status_pull.set_text, status_txt)
                    if fracao > 0:
                        GLib.idle_add(progresso_pull.set_fraction, fracao)
                    else:
                        GLib.idle_add(progresso_pull.pulse)

                try:
                    c = OllamaClient(host=entrada_ollama_host.get_text().strip() or config.DEFAULT_OLLAMA_HOST)
                    c.puxar_modelo(mod_alvo, callback_progresso=_progresso)
                    def _sucesso():
                        lbl_status_pull.set_text(f"✅ {mod_alvo} baixado com sucesso!")
                        progresso_pull.set_fraction(1.0)
                        btn_pull.set_sensitive(True)
                        combo_ollama_model.append(mod_alvo, mod_alvo)
                        combo_ollama_model.get_child().set_text(mod_alvo)
                        sons.tocar_sucesso(self._config.get("sons_ativados", True))
                    GLib.idle_add(_sucesso)
                except Exception as err:
                    def _erro():
                        lbl_status_pull.set_text(f"⚠️ Erro: {err}")
                        btn_pull.set_sensitive(True)
                    GLib.idle_add(_erro)

            threading.Thread(target=_thread_pull, daemon=True).start()

        btn_pull.connect("clicked", _executar_pull)

        # Status Ollama
        online = client_test.testar_conexao()
        status_txt = "🟢 Ollama conectado e ativo" if online else "🟡 Ollama não conectado (execute 'ollama serve')"
        box.add(Gtk.Label(label=f"<small>{status_txt}</small>", use_markup=True, xalign=0))

        box.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # 3. Claude (API)
        box.add(Gtk.Label(label="<b>☁️ Claude (API Anthropic - Opcional)</b>", use_markup=True, xalign=0))
        box.add(Gtk.Label(label="Chave da API da Anthropic:", xalign=0))
        entrada_chave = Gtk.Entry()
        entrada_chave.set_visibility(False)
        entrada_chave.set_text(self._config.get("anthropic_api_key", ""))
        entrada_chave.set_placeholder_text("sk-ant-...")
        box.add(entrada_chave)

        box.add(Gtk.Label(label="Modelo Claude:", xalign=0))
        combo_claude_model = Gtk.ComboBoxText()
        for mod_id in ["claude-sonnet-4-5", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"]:
            combo_claude_model.append(mod_id, mod_id)
        combo_claude_model.set_active_id(self._config.get("modelo", config.DEFAULT_MODEL) or config.DEFAULT_MODEL)
        box.add(combo_claude_model)

        box.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # 4. Voz do Neo e Motor de TTS
        box.add(Gtk.Label(label="<b>🗣️ Motor de Fala (TTS) e Voz:</b>", use_markup=True, xalign=0))
        box.add(Gtk.Label(label="Motor de Síntese de Voz:", xalign=0))
        combo_motor_tts = Gtk.ComboBoxText()
        for id_m, nome_m in config.MOTORES_TTS_DISPONIVEIS:
            combo_motor_tts.append(id_m, nome_m)
        combo_motor_tts.set_active_id(self._config.get("motor_tts", config.DEFAULT_MOTOR_TTS))
        box.add(combo_motor_tts)

        box.add(Gtk.Label(label="Perfil de Voz:", xalign=0))
        combo_voz = Gtk.ComboBoxText()
        for id_voz, nome in config.VOZES_DISPONIVEIS:
            combo_voz.append(id_voz, nome)
        voz_atual = self._config.get("voz", config.DEFAULT_VOICE)
        if voz_atual not in [v[0] for v in config.VOZES_DISPONIVEIS]:
            voz_atual = config.DEFAULT_VOICE
        combo_voz.set_active_id(voz_atual)
        box.add(combo_voz)

        box.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # 5. Frase de Ativação (Wake Word)
        box.add(Gtk.Label(label="<b>👂 Frase de Ativação (Wake Word):</b>", use_markup=True, xalign=0))
        combo_wake = Gtk.ComboBoxText.new_with_entry()
        for ww in config.WAKE_WORDS_PRESETS:
            combo_wake.append(ww, ww)
        wake_atual = self._config.get("palavra_ativacao", config.DEFAULT_WAKE_WORD)
        combo_wake.get_child().set_text(wake_atual)
        box.add(combo_wake)

        box.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # 6. Atalho Global de Teclado (Push-to-Talk)
        box.add(Gtk.Label(label="<b>⌨️ Atalho Global de Teclado (Push-to-Talk):</b>", use_markup=True, xalign=0))
        box.add(Gtk.Label(
            label="<small>Para ativar o Neo via tecla de atalho sem falar a frase de ativação, associe uma tecla nas configurações do sistema ao comando:</small>\n<code>acordaneo --wake</code>",
            use_markup=True,
            xalign=0,
        ))

        box.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # 7. Feedback Sonoro (Chimes)
        box.add(Gtk.Label(label="<b>🔊 Feedback Sonoro:</b>", use_markup=True, xalign=0))
        check_sons = Gtk.CheckButton(label="Habilitar indicadores sonoros (Chimes de ativação e status)")
        check_sons.set_active(self._config.get("sons_ativados", True))
        box.add(check_sons)

        box.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # 8. Personalização do Prompt de Sistema (System Prompt)
        box.add(Gtk.Label(label="<b>📜 Instruções do Sistema (Prompt da IA):</b>", use_markup=True, xalign=0))
        box.add(Gtk.Label(
            label="<small>Personalize o comportamento, tom e regras de resposta da IA:</small>",
            use_markup=True,
            xalign=0,
        ))

        scroll_prompt = Gtk.ScrolledWindow()
        scroll_prompt.set_min_content_height(100)
        scroll_prompt.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll_prompt.set_shadow_type(Gtk.ShadowType.IN)

        textview_prompt = Gtk.TextView()
        textview_prompt.set_wrap_mode(Gtk.WrapMode.WORD)
        textview_prompt.set_left_margin(8)
        textview_prompt.set_right_margin(8)
        textview_prompt.set_top_margin(6)
        textview_prompt.set_bottom_margin(6)
        buffer_prompt = textview_prompt.get_buffer()
        buffer_prompt.set_text(self._config.get("system_prompt", config.DEFAULT_SYSTEM_PROMPT))
        scroll_prompt.add(textview_prompt)
        box.add(scroll_prompt)

        btn_reset_prompt = Gtk.Button(label="Restaurar Prompt Padrão")
        btn_reset_prompt.set_halign(Gtk.Align.START)
        btn_reset_prompt.connect(
            "clicked", lambda *_a: buffer_prompt.set_text(config.DEFAULT_SYSTEM_PROMPT)
        )
        box.add(btn_reset_prompt)

        if obrigatorio:
            box.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
            aviso = Gtk.Label(
                label="Bem-vindo ao Acorda, Neo! Verifique as configurações para começar."
            )
            aviso.set_line_wrap(True)
            box.add(aviso)

        dialogo.show_all()
        resposta = dialogo.run()

        if resposta == Gtk.ResponseType.OK:
            self._config["provedor"] = combo_prov.get_active_id() or config.DEFAULT_PROVEDOR
            self._config["ollama_host"] = entrada_ollama_host.get_text().strip() or config.DEFAULT_OLLAMA_HOST

            modelo_escolhido = combo_ollama_model.get_active_id() or combo_ollama_model.get_child().get_text().strip()
            self._config["ollama_model"] = modelo_escolhido or config.DEFAULT_OLLAMA_MODEL

            self._config["anthropic_api_key"] = entrada_chave.get_text().strip()
            self._config["modelo"] = combo_claude_model.get_active_id() or config.DEFAULT_MODEL
            self._config["motor_tts"] = combo_motor_tts.get_active_id() or config.DEFAULT_MOTOR_TTS
            self._config["voz"] = combo_voz.get_active_id() or config.DEFAULT_VOICE

            wake_escolhida = combo_wake.get_active_id() or combo_wake.get_child().get_text().strip()
            self._config["palavra_ativacao"] = wake_escolhida or config.DEFAULT_WAKE_WORD

            self._config["sons_ativados"] = check_sons.get_active()

            inicio, fim = buffer_prompt.get_bounds()
            prompt_digitado = buffer_prompt.get_text(inicio, fim, True).strip()
            self._config["system_prompt"] = prompt_digitado or config.DEFAULT_SYSTEM_PROMPT

            config.salvar(self._config)

            self._atualizar_subtitulo_header()

            self._claude = None
            self._ollama = None

        dialogo.destroy()
        return False

    def _tem_credenciais_ou_provedor_pronto(self) -> bool:
        provedor = self._config.get("provedor", config.DEFAULT_PROVEDOR)
        if provedor == config.PROVEDOR_OLLAMA:
            # Ollama é local e gratuito, não requer chave prévia
            return True
        return bool(self._config.get("anthropic_api_key"))

    # ---------------------------------------------------------- Escuta contínua

    def _ao_deletar_janela(self, widget, event):
        """Oculta a janela em vez de encerrar a aplicação para continuar escutando na bandeja."""
        self.hide()
        return True

    def _alternar_visibilidade_janela(self):
        if self.is_visible():
            self.hide()
        else:
            self.present()

    def _ao_comando_ipc(self, comando: str):
        """Processa mensagens recebidas pelo socket IPC (ex: acordaneo --wake)."""
        cmd = comando.strip().upper()
        if cmd in ("WAKE", "PUSH_TO_TALK", "PTT"):
            GLib.idle_add(self.ativar_push_to_talk)
        elif cmd == "TOGGLE":
            GLib.idle_add(self._alternar_visibilidade_janela)
        elif cmd == "PRESENT":
            GLib.idle_add(self.present)

    def ativar_push_to_talk(self):
        """Acorda o assistente imediatamente via atalho global de teclado / Push-to-Talk."""
        self.present()
        sons.tocar_wake(self._config.get("sons_ativados", True))
        if not self._ocupado:
            self._ocupado = True
            threading.Thread(target=self._executar_ciclo_push_to_talk, daemon=True).start()

    def _executar_ciclo_push_to_talk(self):
        try:
            self._processar_ciclo_pergunta()
        finally:
            self._ocupado = False

    def _sair_aplicativo(self):
        self._escutando = False
        tts.parar()
        mpris.retomar_apos_conversa()
        if hasattr(self, "_tray") and self._tray:
            self._tray.destruir()
        Gtk.main_quit()
        os._exit(0)

    def _ao_fechar(self, *_args):
        self._sair_aplicativo()

    def _loop_escuta_continua(self):
        """Roda pra sempre numa thread separada: grava trechos curtos e checa se
        a frase de ativação foi dita. Pausa enquanto uma pergunta está sendo
        processada ou a resposta está sendo falada, pra não se auto-escutar.
        """
        while self._escutando:
            if self._ocupado or not self._tem_credenciais_ou_provedor_pronto():
                time.sleep(0.2)
                continue

            try:
                palavra_chave = self._config.get("palavra_ativacao", config.DEFAULT_WAKE_WORD)
                GLib.idle_add(self._definir_status, f'👂 Diga "{palavra_chave}" pra começar.')
                clipe = stt.gravar_clipe(DURACAO_CLIPE_ATIVACAO)

                if not self._escutando:
                    break

                if clipe is None:
                    # Gravação falhou (mic ocupado, dispositivo indisponível...)
                    time.sleep(1.0)
                    continue

                if stt.contem_palavra_ativacao(clipe, palavra_chave=palavra_chave):
                    self._ocupado = True
                    sons.tocar_wake(self._config.get("sons_ativados", True))
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
                            # Passaram até 4s e ninguém falou
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
            sons.tocar_think(self._config.get("sons_ativados", True))
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

    def _reproduzir_resposta_com_interrupcao(self, caminho_audio: Path) -> bool:
        """Reproduz a resposta do Neo enquanto escuta trechos curtos para interrupção (Barge-in).
        Retorna True se o usuário chamou a frase de ativação ou pediu para parar durante a fala,
        ou False se a reprodução terminou normalmente.
        """
        proc = tts.iniciar_reproducao(caminho_audio)
        if proc is None:
            return False

        interrompido = False
        palavra_chave = self._config.get("palavra_ativacao", config.DEFAULT_WAKE_WORD)
        try:
            while self._escutando and proc.poll() is None:
                clipe = stt.gravar_clipe(DURACAO_CLIPE_INTERRUPCAO)
                if proc.poll() is not None:
                    # A fala terminou normalmente durante ou logo após a gravação
                    if clipe:
                        clipe.unlink(missing_ok=True)
                    break

                if clipe is None:
                    time.sleep(0.1)
                    continue

                if stt.contem_palavra_ativacao(clipe, durante_fala=True, palavra_chave=palavra_chave):
                    print("[window] ⚡ Interrupção por voz detectada! Parando fala do Neo...")
                    tts.parar()
                    interrompido = True
                    break
        finally:
            tts.parar()

        return interrompido

    def _checar_comando_limpar_conversa(self, texto: str) -> bool:
        sem_acentos = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
        t = (
            sem_acentos.lower()
            .replace(",", " ")
            .replace(".", " ")
            .replace("!", " ")
            .replace("?", " ")
            .strip()
        )
        gatilhos = [
            "limpar conversa", "limpar historico", "limpe a conversa",
            "esquecer conversa", "esqueca a conversa", "esqueca tudo",
            "novo chat", "nova conversa", "reiniciar conversa", "limpar memoria",
            "apagar conversa", "apagar historico"
        ]
        return any(g in t for g in gatilhos)

    def _limpar_historico_conversa(self):
        self._historico.clear()
        if self._ollama:
            self._ollama.limpar_historico()
        if self._claude:
            self._claude.limpar_historico()

    def _limpar_historico_ui(self):
        self._limpar_historico_conversa()
        for child in self._chat_box.get_children():
            self._chat_box.remove(child)
        self._definir_status("[ SYSTEM ONLINE ]  Diga \"Acorda, Neo\"")

    def _exportar_conversa_ui(self):
        """Exporta o histórico da conversa para um arquivo Markdown (.md)."""
        if not self._historico:
            self._definir_status("💬 Nenhuma conversa registrada para exportar.")
            return

        dialogo = Gtk.FileChooserDialog(
            title="Exportar Conversa para Markdown",
            transient_for=self,
            action=Gtk.FileChooserAction.SAVE,
        )
        dialogo.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK,
        )
        dialogo.set_do_overwrite_confirmation(True)

        docs = Path.home() / "Documents"
        if not docs.exists():
            docs = Path.home()
        dialogo.set_current_folder(str(docs))

        agora = time.strftime("%Y-%m-%d_%H-%M-%S")
        dialogo.set_current_name(f"conversa_neo_{agora}.md")

        filtro = Gtk.FileFilter()
        filtro.set_name("Arquivos Markdown (*.md)")
        filtro.add_pattern("*.md")
        dialogo.add_filter(filtro)

        resposta = dialogo.run()
        if resposta == Gtk.ResponseType.OK:
            caminho_escolhido = Path(dialogo.get_filename())
            if not caminho_escolhido.name.endswith(".md"):
                caminho_escolhido = caminho_escolhido.with_suffix(".md")

            provedor = self._config.get("provedor", config.DEFAULT_PROVEDOR)
            if provedor == config.PROVEDOR_OLLAMA:
                mod = self._config.get("ollama_model", config.DEFAULT_OLLAMA_MODEL)
                info = f"Ollama Local ({mod})"
            else:
                mod = self._config.get("modelo", config.DEFAULT_MODEL)
                info = f"Claude ({mod})"

            destino = sistema.exportar_historico_markdown(
                self._historico, caminho_destino=caminho_escolhido, provedor_info=info
            )
            sons.tocar_sucesso(self._config.get("sons_ativados", True))
            self._definir_status(f"💾 Conversa salva em: {destino.name}")

        dialogo.destroy()

    def _processar_ciclo_pergunta(self):
        try:
            # 1. Pausa o Spotify / reprodutores de mídia ativos para não competir com o microfone
            mpris.pausar_para_conversa()

            while self._escutando:
                try:
                    GLib.idle_add(self.present)
                    GLib.idle_add(self._definir_status, "🎙️ Pode perguntar...", "escutando")
                    texto_usuario = self._capturar_pergunta()

                    if not texto_usuario:
                        GLib.idle_add(self._definir_status, "Não entendi nada, diga \"Acorda, Neo\" de novo.", "escutando")
                        break

                    GLib.idle_add(self._adicionar_balao, texto_usuario, "usuario")

                    # 2. Comando de voz para limpar memória / novo chat
                    motor_tts = self._config.get("motor_tts", config.DEFAULT_MOTOR_TTS)
                    if self._checar_comando_limpar_conversa(texto_usuario):
                        self._limpar_historico_conversa()
                        resposta = "Histórico de conversa apagado. Memória reiniciada, Neo."
                        GLib.idle_add(self._adicionar_balao, resposta, "assistente")
                        GLib.idle_add(self._definir_status, "🗣️ Falando...", "falando")
                        voz = self._config.get("voz", config.DEFAULT_VOICE)
                        caminho_audio = sintetizar(resposta, voz, motor=motor_tts)
                        self._reproduzir_resposta_com_interrupcao(caminho_audio)
                        break

                    # 3. Comandos de voz de mídia MPRIS (pausar, tocar, próxima música...)
                    reconhecido_midia, msg_midia = mpris.executar_comando_midia(texto_usuario)
                    if reconhecido_midia:
                        GLib.idle_add(self._adicionar_balao, msg_midia, "assistente")
                        GLib.idle_add(self._definir_status, "🗣️ Falando...", "falando")
                        voz = self._config.get("voz", config.DEFAULT_VOICE)
                        caminho_audio = sintetizar(msg_midia, voz, motor=motor_tts)
                        self._reproduzir_resposta_com_interrupcao(caminho_audio)
                        break

                    # 4. Comandos de automação do Linux (volume, aplicativos, data/hora, bateria e exportação)
                    reconhecido_sis, msg_sis = sistema.executar_comando_sistema(texto_usuario, self._historico)
                    if reconhecido_sis:
                        GLib.idle_add(self._adicionar_balao, msg_sis, "assistente")
                        GLib.idle_add(self._definir_status, "🗣️ Falando...", "falando")
                        voz = self._config.get("voz", config.DEFAULT_VOICE)
                        caminho_audio = sintetizar(msg_sis, voz, motor=motor_tts)
                        self._reproduzir_resposta_com_interrupcao(caminho_audio)
                        break

                    # 5. Consulta ao cérebro da IA (mantendo memória multi-turn na conversa)
                    provedor = self._config.get("provedor", config.DEFAULT_PROVEDOR)
                    if provedor == config.PROVEDOR_OLLAMA:
                        modelo_nome = self._config.get("ollama_model", config.DEFAULT_OLLAMA_MODEL)
                        GLib.idle_add(self._definir_status, f"🤔 Pensando (Ollama • {modelo_nome})...", "pensando")
                        resposta = self._perguntar_ollama(texto_usuario)
                    else:
                        GLib.idle_add(self._definir_status, "🤔 Pensando (Claude)...", "pensando")
                        resposta = self._perguntar_claude(texto_usuario)

                    # Registra a troca no histórico da conversa multi-turn
                    self._historico.append({"role": "user", "content": texto_usuario})
                    self._historico.append({"role": "assistant", "content": resposta})
                    if len(self._historico) > 20:
                        self._historico = self._historico[-20:]

                    GLib.idle_add(self._adicionar_balao, resposta, "assistente")
                    palavra_gatilho = self._config.get("palavra_ativacao", config.DEFAULT_WAKE_WORD)
                    GLib.idle_add(self._definir_status, f"🗣️ Falando... (Diga \"{palavra_gatilho}\" para interromper)", "falando")

                    voz = self._config.get("voz", config.DEFAULT_VOICE)
                    caminho_audio = sintetizar(resposta, voz, motor=motor_tts)
                    interrompido = self._reproduzir_resposta_com_interrupcao(caminho_audio)

                    if interrompido:
                        GLib.idle_add(self._definir_status, "⚡ Interrompido! Ouvindo você...", "escutando")
                        # Continua o loop de escuta com o Spotify ainda pausado
                        continue
                    else:
                        break
                except Exception as exc:  # noqa: BLE001 - mostrar qualquer erro pro usuário
                    traceback.print_exc()
                    GLib.idle_add(self._definir_status, f"⚠️ Erro: {exc}")
                    break
        finally:
            # 6. Retoma automaticamente a mídia pausada quando a conversa termina
            mpris.retomar_apos_conversa()

    def _perguntar_ollama(self, texto_usuario: str) -> str:
        host = self._config.get("ollama_host", config.DEFAULT_OLLAMA_HOST)
        model = self._config.get("ollama_model", config.DEFAULT_OLLAMA_MODEL)
        prompt = self._config.get("system_prompt", config.DEFAULT_SYSTEM_PROMPT)
        if (
            self._ollama is None
            or self._ollama.host != host
            or self._ollama.model != model
            or getattr(self._ollama, "system_prompt", None) != prompt
        ):
            self._ollama = OllamaClient(host=host, model=model, system_prompt=prompt)
        return self._ollama.perguntar(texto_usuario, historico=self._historico)

    def _perguntar_claude(self, texto_usuario: str) -> str:
        api_key = self._config.get("anthropic_api_key", "")
        model = self._config.get("modelo", config.DEFAULT_MODEL)
        prompt = self._config.get("system_prompt", config.DEFAULT_SYSTEM_PROMPT)
        if (
            self._claude is None
            or getattr(self._claude, "_model", None) != model
            or getattr(self._claude, "system_prompt", None) != prompt
        ):
            self._claude = ClaudeClient(
                api_key=api_key,
                model=model,
                system_prompt=prompt,
            )
        return self._claude.perguntar(texto_usuario, historico=self._historico)
