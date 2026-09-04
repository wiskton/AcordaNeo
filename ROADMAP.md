# 🗺️ Acorda, Neo — Roadmap

Este documento delineia a visão e o planejamento de evolução do **Acorda, Neo**, um assistente de voz hands-free, privativo e leve para o desktop Linux.

---

## 📍 Status Atual: v0.2 (Fundação Sólida)

- [x] **Escuta contínua hands-free:** Detecção em segundo plano da frase de ativação (*"Acorda, Neo"*).
- [x] **Privacidade no STT:** Transcrição local com `faster-whisper` (modelos `tiny` e `small`), sem enviar voz para a nuvem.
- [x] **Processamento de áudio robusto:**
  - Remoção automática de bias/offset DC analógico.
  - Normalização inteligente de ganho adaptativo (AGC digital).
  - Calibração automática do preamp ALSA para codecs sensíveis (ex.: Realtek ALC257).
- [x] **Detecção de atividade de voz (VAD):** Integração com Silero VAD para detecção ágil do fim da fala sem cortes abruptos.
- [x] **Captura de frases completas:** Acumulação contínua de áudio e transcrição em passagem única.
- [x] **Cérebro com IA de ponta:** Integração com a API oficial da Anthropic (Claude 3.5 Sonnet).
- [x] **Síntese de voz neural natural:** Suporte a vozes neurais PT-BR, PT-PT e EN-US com `edge-tts`.
- [x] **Interface gráfica GTK3:** Avatar, balões de chat estilo mensageiro e configuração de preferências.

---

## 🎯 Próximos Passos (Milestones)

### 📌 Fase 1: Experiência Desktop e Feedback Sonoro
*Foco: Usabilidade e integração nativa com o ambiente de trabalho.*

- [ ] **Indicadores sonoros (Chimes):**
  - Som sutil ao reconhecer *"Acorda, Neo"* (feedback de que o assistente acordou).
  - Som discreto ao finalizar a escuta e iniciar o pensamento.
- [ ] **Ícone na bandeja do sistema (System Tray / AppIndicator):**
  - Indicador de estado (Ouvindo / Pensando / Falando / Silenciado).
  - Menu rápido para pausar/retomar escuta, abrir preferências ou fechar.
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
  - Campo nas preferências para personalizar instruções à Claude (tom de voz, brevidade, estilo conciso).
- [ ] **Seletor de modelos da Anthropic:**
  - Alternar facilmente entre `Claude 3.5 Sonnet`, `Claude 3.5 Haiku` (mais rápido/econômico) e `Claude 3 Opus`.

---

### 📌 Fase 3: Automação do Sistema e Ações no Linux
*Foco: Controlar o computador usando a voz.*

- [ ] **Integração MPRIS2 (Controle de Mídia):**
  - Pausar Spotify / reprodutor de música automaticamente enquanto o usuário fala e enquanto a Claude responde, retomando em seguida.
- [ ] **Comandos de sistema e Ferramentas (Tool Calling):**
  - Controle de volume (*"aumentar volume em 20%"*).
  - Abrir aplicativos (*"abrir o navegador"*, *"abrir o terminal"*).
  - Consultas rápidas locais (bateria, clima, hora/data, lembretes).
- [ ] **Wake Word customizável:**
  - Integração com `openWakeWord` para treinar e permitir palavras de ativação personalizadas.

---

### 📌 Fase 4: Modo 100% Offline e Distribuição
*Foco: Total independência de internet e facilidade de instalação.*

- [ ] **Provedor LLM Local (Ollama):**
  - Opção para rodar modelos locais como Llama 3, Mistral ou Phi-3 via Ollama, permitindo funcionamento 100% offline.
- [ ] **TTS Local offline alternativo:**
  - Suporte ao [Piper TTS](https://github.com/rhasspy/piper) para síntese de voz rápida sem conexão com a internet.
- [ ] **Empacotamento Flatpak / AppImage / AUR:**
  - Instalação com um clique em qualquer distribuição Linux.

---

## 💡 Sugestões e Contribuições

Tem uma ideia ou sugestão de melhoria?
- Abra uma **[Issue](https://github.com/wiskton/AcordaNeo/issues)** no repositório.
- Envie um **Pull Request** seguindo o estilo do projeto.
