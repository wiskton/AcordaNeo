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
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, GLib, Gtk

from . import config
from . import stt
from .claude_client import ClaudeClient
from .ollama_client import OllamaClient, OllamaError
from .tray import TrayManager
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
        self.set_default_size(460, 750)
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

        self._montar_ui()
        self.connect("delete-event", self._ao_deletar_janela)
        self.connect("destroy", self._ao_fechar)

        # Inicializa o ícone da bandeja do sistema (System Tray)
        self._tray = TrayManager(
            ao_alternar_janela=self._alternar_visibilidade_janela,
            ao_abrir_preferencias=lambda: self._abrir_preferencias(False),
            ao_sair=self._sair_aplicativo,
            icone_path=AVATAR_PATH,
        )

        if not self._tem_credenciais_ou_provedor_pronto():
            GLib.idle_add(self._abrir_preferencias, True)

        thread_escuta = threading.Thread(target=self._loop_escuta_continua, daemon=True)
        thread_escuta.start()

    # ------------------------------------------------------------------ UI

    def _montar_ui(self):
        header = Gtk.HeaderBar(title="Acorda, Neo", show_close_button=True)
        header.set_subtitle("SYSTEM READY // MATRIX AI")
        botao_config = Gtk.Button.new_from_icon_name("preferences-system-symbolic", Gtk.IconSize.BUTTON)
        botao_config.set_tooltip_text("Preferências (IA, modelo e voz)")
        botao_config.connect("clicked", lambda *_a: self._abrir_preferencias(False))
        header.pack_end(botao_config)
        self.set_titlebar(header)

        raiz = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(raiz)

        # --- Avatar + status (Card Matrix) --------------------------------------
        topo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        topo.get_style_context().add_class("matrix-topo-box")
        raiz.pack_start(topo, False, False, 0)

        self._avatar_img = Gtk.Image()
        self._carregar_avatar(160)
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

        # --- Rodapé: seletores de Provedor, Modelo e Voz (Console Matrix) -------
        rodape = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        rodape.get_style_context().add_class("matrix-rodape")
        raiz.pack_start(rodape, False, False, 0)

        # Seletor de Cérebro (IA)
        linha_provedor = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_p = Gtk.Label(label="CÉREBRO IA:", xalign=0)
        lbl_p.get_style_context().add_class("matrix-label")
        linha_provedor.pack_start(lbl_p, False, False, 0)
        self._provedor_combo = Gtk.ComboBoxText()
        for id_p, nome_p in config.PROVEDORES_DISPONIVEIS:
            self._provedor_combo.append(id_p, nome_p)
        self._provedor_combo.set_active_id(self._config.get("provedor", config.DEFAULT_PROVEDOR))
        self._provedor_combo.connect("changed", self._on_trocar_provedor)
        linha_provedor.pack_start(self._provedor_combo, True, True, 0)
        rodape.pack_start(linha_provedor, False, False, 0)

        # Seletor de Modelo Local Ollama
        self._linha_modelo_ollama = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_m = Gtk.Label(label="MODELO LOCAL:", xalign=0)
        lbl_m.get_style_context().add_class("matrix-label")
        self._linha_modelo_ollama.pack_start(lbl_m, False, False, 0)
        self._modelo_ollama_combo = Gtk.ComboBoxText()
        self._atualizar_modelos_ollama_combo()
        self._modelo_ollama_combo.connect("changed", self._on_trocar_modelo_ollama)
        self._linha_modelo_ollama.pack_start(self._modelo_ollama_combo, True, True, 0)
        rodape.pack_start(self._linha_modelo_ollama, False, False, 0)

        # Seletor de Voz
        linha_voz = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_v = Gtk.Label(label="VOZ DO NEO:", xalign=0)
        lbl_v.get_style_context().add_class("matrix-label")
        linha_voz.pack_start(lbl_v, False, False, 0)
        self._voz_combo = Gtk.ComboBoxText()
        for id_voz, nome in config.VOZES_DISPONIVEIS:
            self._voz_combo.append(id_voz, nome)
        voz_atual = self._config.get("voz", config.DEFAULT_VOICE)
        self._voz_combo.set_active_id(voz_atual)
        self._voz_combo.connect("changed", self._on_trocar_voz)
        linha_voz.pack_start(self._voz_combo, True, True, 0)
        rodape.pack_start(linha_voz, False, False, 0)

        self._ajustar_visibilidade_modelo_ollama()

    def _carregar_avatar(self, tamanho: int):
        if AVATAR_PATH.exists():
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                str(AVATAR_PATH), tamanho, tamanho, True
            )
            self._avatar_img.set_from_pixbuf(pixbuf)
        else:
            self._avatar_img.set_from_icon_name("avatar-default-symbolic", Gtk.IconSize.DIALOG)

    def _ajustar_visibilidade_modelo_ollama(self):
        provedor = self._config.get("provedor", config.DEFAULT_PROVEDOR)
        self._linha_modelo_ollama.set_visible(provedor == config.PROVEDOR_OLLAMA)

    def _atualizar_modelos_ollama_combo(self):
        self._modelo_ollama_combo.remove_all()
        client = OllamaClient(host=self._config.get("ollama_host", config.DEFAULT_OLLAMA_HOST))
        modelos = client.listar_modelos()
        if not modelos:
            modelos = ["llama3.2:3b", "llama3.2", "qwen3:8b", "mistral"]
        for m in modelos:
            self._modelo_ollama_combo.append(m, m)

        atual = self._config.get("ollama_model", config.DEFAULT_OLLAMA_MODEL)
        if atual in modelos:
            self._modelo_ollama_combo.set_active_id(atual)
        else:
            self._modelo_ollama_combo.set_active(0)

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
        dialogo = Gtk.Dialog(title="Preferências do Sistema", transient_for=self, modal=True)
        if AVATAR_PATH.exists():
            dialogo.set_icon_from_file(str(AVATAR_PATH))
        dialogo.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        box = dialogo.get_content_area()
        box.set_border_width(16)
        box.set_spacing(10)

        # Provedor
        box.add(Gtk.Label(label="<b>Provedor Principal:</b>", use_markup=True, xalign=0))
        combo_prov = Gtk.ComboBoxText()
        for id_p, nome_p in config.PROVEDORES_DISPONIVEIS:
            combo_prov.append(id_p, nome_p)
        combo_prov.set_active_id(self._config.get("provedor", config.DEFAULT_PROVEDOR))
        box.add(combo_prov)

        box.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Ollama (Local)
        box.add(Gtk.Label(label="<b>Ollama (100% Offline / Gratuito)</b>", use_markup=True, xalign=0))
        box.add(Gtk.Label(label="Endereço do Servidor Ollama:", xalign=0))
        entrada_ollama_host = Gtk.Entry()
        entrada_ollama_host.set_text(self._config.get("ollama_host", config.DEFAULT_OLLAMA_HOST))
        box.add(entrada_ollama_host)

        box.add(Gtk.Label(label="Modelo Local do Ollama:", xalign=0))
        entrada_ollama_model = Gtk.Entry()
        entrada_ollama_model.set_text(self._config.get("ollama_model", config.DEFAULT_OLLAMA_MODEL))
        box.add(entrada_ollama_model)

        # Status Ollama
        client_test = OllamaClient(host=entrada_ollama_host.get_text().strip())
        online = client_test.testar_conexao()
        status_txt = "🟢 Ollama conectado e ativo" if online else "🟡 Ollama não conectado (execute 'ollama serve')"
        box.add(Gtk.Label(label=f"<small>{status_txt}</small>", use_markup=True, xalign=0))

        box.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Claude (API)
        box.add(Gtk.Label(label="<b>Claude (API Anthropic - Opcional)</b>", use_markup=True, xalign=0))
        box.add(Gtk.Label(label="Chave da API da Anthropic:", xalign=0))
        entrada_chave = Gtk.Entry()
        entrada_chave.set_visibility(False)
        entrada_chave.set_text(self._config.get("anthropic_api_key", ""))
        entrada_chave.set_placeholder_text("sk-ant-...")
        box.add(entrada_chave)

        box.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Voz
        box.add(Gtk.Label(label="<b>Voz do Neo:</b>", use_markup=True, xalign=0))
        combo_voz = Gtk.ComboBoxText()
        for id_voz, nome in config.VOZES_DISPONIVEIS:
            combo_voz.append(id_voz, nome)
        voz_atual = self._config.get("voz", config.DEFAULT_VOICE)
        if voz_atual not in [v[0] for v in config.VOZES_DISPONIVEIS]:
            voz_atual = config.DEFAULT_VOICE
        combo_voz.set_active_id(voz_atual)
        box.add(combo_voz)

        if obrigatorio:
            aviso = Gtk.Label(
                label="Bem-vindo ao Acorda, Neo! Verifique as configurações para começar."
            )
            aviso.set_line_wrap(True)
            box.add(aviso)

        box.show_all()
        resposta = dialogo.run()

        if resposta == Gtk.ResponseType.OK:
            self._config["provedor"] = combo_prov.get_active_id() or config.DEFAULT_PROVEDOR
            self._config["ollama_host"] = entrada_ollama_host.get_text().strip() or config.DEFAULT_OLLAMA_HOST
            self._config["ollama_model"] = entrada_ollama_model.get_text().strip() or config.DEFAULT_OLLAMA_MODEL
            self._config["anthropic_api_key"] = entrada_chave.get_text().strip()
            self._config["voz"] = combo_voz.get_active_id() or config.DEFAULT_VOICE
            config.salvar(self._config)

            self._provedor_combo.set_active_id(self._config["provedor"])
            self._atualizar_modelos_ollama_combo()
            self._voz_combo.set_active_id(self._config["voz"])
            self._ajustar_visibilidade_modelo_ollama()

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

    def _on_trocar_provedor(self, combo):
        self._config["provedor"] = combo.get_active_id() or config.DEFAULT_PROVEDOR
        config.salvar(self._config)
        self._ajustar_visibilidade_modelo_ollama()
        if self._config["provedor"] == config.PROVEDOR_CLAUDE and not self._config.get("anthropic_api_key"):
            self._abrir_preferencias(True)

    def _on_trocar_modelo_ollama(self, combo):
        mod = combo.get_active_id()
        if mod:
            self._config["ollama_model"] = mod
            config.salvar(self._config)
            self._ollama = None

    def _on_trocar_voz(self, combo):
        self._config["voz"] = combo.get_active_id() or config.DEFAULT_VOICE
        config.salvar(self._config)

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

    def _sair_aplicativo(self):
        self._escutando = False
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
                GLib.idle_add(self._definir_status, "👂 Diga \"Acorda, Neo\" pra começar.")
                clipe = stt.gravar_clipe(DURACAO_CLIPE_ATIVACAO)

                if not self._escutando:
                    break

                if clipe is None:
                    # Gravação falhou (mic ocupado, dispositivo indisponível...)
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
            GLib.idle_add(self.present)
            GLib.idle_add(self._definir_status, "🎙️ Pode perguntar...", "escutando")
            texto_usuario = self._capturar_pergunta()

            if not texto_usuario:
                GLib.idle_add(self._definir_status, "Não entendi nada, diga \"Acorda, Neo\" de novo.", "escutando")
                return

            GLib.idle_add(self._adicionar_balao, texto_usuario, "usuario")

            provedor = self._config.get("provedor", config.DEFAULT_PROVEDOR)
            if provedor == config.PROVEDOR_OLLAMA:
                modelo_nome = self._config.get("ollama_model", config.DEFAULT_OLLAMA_MODEL)
                GLib.idle_add(self._definir_status, f"🤔 Pensando (Ollama • {modelo_nome})...", "pensando")
                resposta = self._perguntar_ollama(texto_usuario)
            else:
                GLib.idle_add(self._definir_status, "🤔 Pensando (Claude)...", "pensando")
                resposta = self._perguntar_claude(texto_usuario)

            GLib.idle_add(self._adicionar_balao, resposta, "assistente")
            GLib.idle_add(self._definir_status, "🗣️ Falando...", "falando")

            voz = self._config.get("voz", config.DEFAULT_VOICE)
            caminho_audio = sintetizar(resposta, voz)
            tocar(caminho_audio)
        except Exception as exc:  # noqa: BLE001 - mostrar qualquer erro pro usuário
            traceback.print_exc()
            GLib.idle_add(self._definir_status, f"⚠️ Erro: {exc}")

    def _perguntar_ollama(self, texto_usuario: str) -> str:
        host = self._config.get("ollama_host", config.DEFAULT_OLLAMA_HOST)
        model = self._config.get("ollama_model", config.DEFAULT_OLLAMA_MODEL)
        if self._ollama is None or self._ollama.host != host or self._ollama.model != model:
            self._ollama = OllamaClient(host=host, model=model)
        return self._ollama.perguntar(texto_usuario)

    def _perguntar_claude(self, texto_usuario: str) -> str:
        if self._claude is None:
            self._claude = ClaudeClient(
                api_key=self._config.get("anthropic_api_key", ""),
                model=self._config.get("modelo", config.DEFAULT_MODEL),
            )
        return self._claude.perguntar(texto_usuario)
