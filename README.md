# 🕶️ Acorda, Neo

> **A lightweight Linux desktop voice assistant with offline Whisper STT, edge-tts, and Claude AI.**

App de desktop (GTK3) para conversar por voz com a IA Claude (Anthropic):
fica ouvindo em segundo plano e, quando você diz **"Acorda, Neo"**,
ele ativa, grava sua pergunta, envia para a Claude e reproduz a resposta falada
em voz neural natural — sem precisar apertar nenhum botão.

## ✨ Como funciona

1. Diga **"Acorda, Neo"** — o app escuta trechos em segundo plano esperando a ativação.
2. Assim que reconhece a ativação, grava sua fala e detecta o fim da frase com VAD em tempo real.
3. O áudio é processado e transcrito **localmente** via [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (sem enviar áudio bruto para a nuvem).
4. O texto é enviado para a API oficial da **Claude** (Anthropic), gerando a resposta.
5. A resposta é sintetizada em voz neural via **edge-tts** e reproduzida pelo sistema.

## 🧱 Stack

| Componente | Tecnologia |
|---|---|
| Interface gráfica | GTK3 (PyGObject) |
| Cérebro (LLM) | API oficial da Anthropic ([Claude](https://docs.anthropic.com)) |
| Reconhecimento de voz (STT) | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) + [Silero VAD](https://github.com/snakers4/silero-vad) locais (modelo `tiny` para palavra de ativação, modelo `small` para perguntas) |
| Normalização de áudio | AGC digital adaptativo e remoção de offset DC |
| Síntese de voz (TTS) | [edge-tts](https://github.com/rany2/edge-tts) com vozes neurais |
| Áudio / Sistema | `arecord` / `ffplay` (ALSA + ffmpeg) |

## 🚀 Como rodar

```bash
./run.sh
```

Na primeira execução, o script cria o ambiente virtual `.venv` (`--system-site-packages` para utilizar o GTK do sistema) e instala as dependências Python.

Pré-requisitos do sistema (Debian/Ubuntu/Pop!_OS):
```bash
sudo apt install python3-gi gir1.2-gtk-3.0 alsa-utils ffmpeg
```

## 🔑 Configuração

Na primeira inicialização, uma janela de preferências se abrirá solicitando sua chave da API da Anthropic:

- **Chave da API da Anthropic**: `sk-ant-...` (obtida no [Anthropic Console](https://console.anthropic.com)).

As configurações são armazenadas em `~/.config/acordaneo/config.json` com permissão restrita (`0600`), fora do repositório.

Para alterar a chave ou a voz a qualquer momento, clique no ícone de engrenagem (⚙️) na barra de título.

## 🖥️ Atalho no menu do sistema

```bash
cp assistente-voz.desktop ~/.local/share/applications/acordaneo.desktop
update-desktop-database ~/.local/share/applications/
```

## 🗣️ Vozes disponíveis

- Antônio (PT-BR, masculina)
- Francisca (PT-BR, feminina)
- Thalita (PT-BR, feminina)
- Duarte (PT-PT, masculina)
- Guy (EN-US, masculina)
- Jenny (EN-US, feminina)
