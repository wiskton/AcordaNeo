# 🗺️ Acorda, Neo — Roadmap

Este documento delineia a visão e o planejamento de evolução do **Acorda, Neo**, um assistente de voz hands-free, privativo e leve para o desktop Linux.

---

## 📍 Status Atual: v0.3 (Ollama Offline + Fundação Sólida)

- [x] **Escuta contínua hands-free:** Detecção em segundo plano da frase de ativação (*"Acorda, Neo"*).
- [x] **Inteligência 100% Local com Ollama (Padrão & Gratuito):** Suporte a modelos locais (`llama3.2:3b`, `qwen3:8b`, `mistral`) sem chave de API, sem custos e sem enviar dados para a nuvem.
- [x] **Opção Claude 3.5 Sonnet (API Oficial):** Provedor alternativo na nuvem para respostas de alta complexidade.
- [x] **Vozes personalizadas do Neo (Matrix):** Calibração acústica (pitch e rate) simulando a dublagem clássica PT-BR e o estilo original do Keanu Reeves.
- [x] **Privacidade no STT:** Transcrição local com `faster-whisper` (modelos `tiny` e `small`), sem enviar voz para a nuvem.
- [x] **Processamento de áudio robusto:**
  - Remoção automática de bias/offset DC analógico.
  - Normalização inteligente de ganho adaptativo (AGC digital).
  - Calibração automática do preamp ALSA para codecs sensíveis (ex.: Realtek ALC257).
- [x] **Detecção de atividade de voz (VAD):** Integração com Silero VAD para detecção ágil do fim da fala sem cortes abruptos.
- [x] **Captura de frases completas:** Acumulação contínua de áudio e transcrição em passagem única.
- [x] **Interface gráfica GTK3 com Tema Matrix:** Design cyberpunk com paleta verde fósforo (#00ff66), cabeçalho terminal, balões de conversa com tags e console de controle no rodapé.
- [x] **Integração completa com Pop!_OS / COSMIC / GNOME:** Ícones em múltiplas resoluções, mapeamento de StartupWMClass e suporte a Wayland sem ícone genérico.
- [x] **Interrupção de voz em tempo real (Barge-in):** Interrompe o áudio da fala instantaneamente se o usuário disser *"Acorda, Neo"* ou *"Pare"*, prestando atenção imediatamente na nova pergunta.

---

## 🎯 Próximos Passos (Milestones)

### 📌 Fase 1: Experiência Desktop e Feedback Sonoro
*Foco: Usabilidade e integração nativa com o ambiente de trabalho.*

- [x] **Ícone na bandeja do sistema (System Tray / StatusNotifierItem):**
  - Integração nativa com COSMIC/Wayland, GNOME Shell e KDE via DBus StatusNotifierItem e DBusMenu.
  - Minimiza para a bandeja ao fechar a janela (`X`) para continuar escutando em segundo plano.
  - Menu com ações rápidas (Mostrar / Ocultar, Preferências, Sair).
  - Ícone dinâmico refletindo o estado atual (Ouvindo / Pensando / Falando).
- [x] **Indicadores sonoros (Chimes):**
  - Som sutil ao reconhecer *"Acorda, Neo"* (feedback imediato de que o assistente acordou).
  - Som discreto ao finalizar a escuta e iniciar o processamento/pensamento.
  - Opção para habilitar/desabilitar efeitos sonoros nas configurações.
- [x] **Atalho global de teclado (Push-to-Talk / Hotkey):**
  - Servidor IPC via UNIX socket (`~/.config/acordaneo/acordaneo.sock`) imune a restrições do Wayland.
  - Flags de linha de comando: `--wake` (ativa escuta imediata), `--toggle` (alterna visibilidade), `--present` (traz para frente).
  - Script auxiliar `scripts/instalar_atalho.sh` para configuração automática no GNOME, COSMIC, KDE, Sway e Hyprland.
- [x] **Histórico e rolagem aprimorados:**
  - [x] Exportação da conversa em Markdown (via botão no cabeçalho, menu da bandeja e comando de voz).
  - [x] Botão para limpar a conversa atual no cabeçalho e comando de voz.

---

### 📌 Fase 2: Inteligência e Memória Conversacional
*Foco: Conversas naturais com contexto e personalização do modelo.*

- [x] **Memória contextual multi-turn:**
  - Manter o histórico da sessão para perguntas de acompanhamento (*"Quem dirigiu Matrix?"* -> *"E quais outros filmes elas fizeram?"*).
  - Contexto unificado e persistente entre Ollama e Claude.
- [x] **Personalização do Prompt de Sistema:**
  - Campo nas preferências para personalizar instruções à IA (tom de voz, brevidade, regras personalizadas) e botão para restaurar o padrão.
- [x] **Download de novos modelos direto da interface:**
  - Campo nas preferências para digitar o nome do modelo (ex: `deepseek-r1:8b`, `gemma2:2b`, `qwen2.5:7b`).
  - Barra de progresso contínua em tempo real com indicador de status, porcentagem e botão para cancelar o download.
  - Atualização automática da lista de modelos disponíveis assim que o download é concluído.

---

### 📌 Fase 3: Automação do Sistema e Ações no Linux
*Foco: Controlar o computador usando a voz.*

- [x] **Integração MPRIS2 (Controle de Mídia):**
  - Pausar Spotify / reprodutor de música automaticamente enquanto o usuário fala e enquanto a IA responde, retomando apenas os players pausados ao finalizar.
  - Comandos diretos de voz para pausar, retomar, próxima e anterior.
- [x] **Comandos de sistema e Ferramentas (Tool Calling):**
  - Controle de volume (*"aumentar volume"*, *"diminuir volume"*, *"mutar"*, *"desmutar"*, *"volume em 50%"*).
  - Abrir aplicativos (*"abrir o navegador"*, *"abrir o terminal"*, *"abrir arquivos"*, *"abrir editor"*, *"abrir configurações"*, *"abrir spotify"*).
  - Consultas rápidas locais (bateria, hora e data do sistema).
- [x] **Wake Word customizável:**
  - Campo de configuração nas preferências para personalizar a palavra ou frase de ativação (ex.: *"Acorda, Neo"*, *"Computador"*, *"Jarvis"*, *"Neo"*).
  - Adaptação dinâmica do vocabulário do Whisper (`initial_prompt`) para garantir alta taxa de acerto na palavra escolhida.
  - Interrupção por voz (barge-in) sincronizada dinamicamente com a wake word configurada.

---

### 📌 Fase 4: Modo 100% Offline Completo e Distribuição
*Foco: Total independência de internet e facilidade de instalação.*

- [x] **Provedor LLM Local (Ollama):** Concluído na v0.3!
- [x] **TTS Local offline alternativo (Piper TTS):**
  - Suporte ao [Piper TTS](https://github.com/rhasspy/piper) integrado com modelo neural pt_BR (`pt_BR-edresson-low`).
  - Geração local ultra-rápida sem nenhuma dependência de internet ou serviços externos.
  - Seletor de motor de voz nas preferências (Edge TTS Online vs Piper TTS Offline) com fallback automático.
- [x] **Empacotamento Flatpak / AppImage / AUR / systemd:**
  - Manifest Flatpak (`packaging/flatpak/com.github.wiskton.AcordaNeo.yaml`) para isolamento seguro e distribuição no Flathub.
  - Scripts AppImage (`packaging/appimage/AppRun` e `packaging/appimage/build-appimage.sh`) para executável universal em qualquer distro.
  - Script `PKGBUILD` para Arch Linux e AUR (`packaging/aur/PKGBUILD`).
  - Unidade de serviço de usuário systemd (`packaging/systemd/acordaneo.service`) para inicialização automática no login.

---

## 💡 Sugestões e Contribuições

Tem uma ideia ou sugestão de melhoria?
- Abra uma **[Issue](https://github.com/wiskton/AcordaNeo/issues)** no repositório.
- Envie um **Pull Request** seguindo o estilo do projeto.
