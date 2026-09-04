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

---

## 🎯 Próximos Passos (Milestones)

### 📌 Fase 1: Experiência Desktop e Feedback Sonoro
*Foco: Usabilidade e integração nativa com o ambiente de trabalho.*

- [x] **Ícone na bandeja do sistema (System Tray / StatusNotifierItem):**
  - Integração nativa com COSMIC/Wayland, GNOME Shell e KDE via DBus StatusNotifierItem e DBusMenu.
  - Minimiza para a bandeja ao fechar a janela (`X`) para continuar escutando em segundo plano.
  - Menu com ações rápidas (Mostrar / Ocultar, Preferências, Sair).
  - Ícone dinâmico refletindo o estado atual (Ouvindo / Pensando / Falando).
- [ ] **Indicadores sonoros (Chimes):**
  - Som sutil ao reconhecer *"Acorda, Neo"* (feedback de que o assistente acordou).
  - Som discreto ao finalizar a escuta e iniciar o pensamento.
- [ ] **Atalho global de teclado (Push-to-Talk / Hotkey):**
  - Tecla de atalho (ex.: `Super + Espaço` ou configurável) para ativar mesmo sem falar o gatilho.
- [ ] **Histórico e rolagem aprimorados:**
  - Exportação da conversa em Markdown.
  - Botão para limpar a conversa atual.

---

### 📌 Fase 2: Inteligência e Memória Conversacional
*Foco: Conversas naturais com contexto e personalização do modelo.*

- [ ] **Memória contextual multi-turn:**
  - Manter o histórico da sessão para perguntas de acompanhamento (*"Quem pintou a Mona Lisa?"* -> *"E onde ele nasceu?"*).
- [ ] **Personalização do Prompt de Sistema:**
  - Campo nas preferências para personalizar instruções à IA (tom de voz, brevidade, estilo conciso).
- [ ] **Download de novos modelos direto da interface:**
  - Campo para digitar o nome de um modelo do Ollama (ex: `deepseek-r1:8b`) e baixar com barra de progresso.

---

### 📌 Fase 3: Automação do Sistema e Ações no Linux
*Foco: Controlar o computador usando a voz.*

- [ ] **Integração MPRIS2 (Controle de Mídia):**
  - Pausar Spotify / reprodutor de música automaticamente enquanto o usuário fala e enquanto a IA responde, retomando em seguida.
- [ ] **Comandos de sistema e Ferramentas (Tool Calling):**
  - Controle de volume (*"aumentar volume em 20%"*).
  - Abrir aplicativos (*"abrir o navegador"*, *"abrir o terminal"*).
  - Consultas rápidas locais (bateria, clima, hora/data, lembretes).
- [ ] **Wake Word customizável:**
  - Integração com `openWakeWord` para treinar e permitir palavras de ativação personalizadas.

---

### 📌 Fase 4: Modo 100% Offline Completo e Distribuição
*Foco: Total independência de internet e facilidade de instalação.*

- [x] **Provedor LLM Local (Ollama):** Concluído na v0.3!
- [ ] **TTS Local offline alternativo:**
  - Suporte ao [Piper TTS](https://github.com/rhasspy/piper) para síntese de voz rápida sem conexão com a internet.
- [ ] **Empacotamento Flatpak / AppImage / AUR:**
  - Instalação com um clique em qualquer distribuição Linux.

---

## 💡 Sugestões e Contribuições

Tem uma ideia ou sugestão de melhoria?
- Abra uma **[Issue](https://github.com/wiskton/AcordaNeo/issues)** no repositório.
- Envie um **Pull Request** seguindo o estilo do projeto.
