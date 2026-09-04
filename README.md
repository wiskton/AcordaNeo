# 🎙️ Assistente de Voz

App de desktop (GTK3) pra conversar por voz com a Claude: você pergunta
falando, o app transcreve, manda pra API da Anthropic, e a resposta volta
falada — com várias vozes possíveis pra escolher.

## ✨ Como funciona

1. Clique em **🎙️ Falar**, faça sua pergunta, clique em **⏹️ Parar**
2. O áudio é transcrito **localmente** (Whisper, sem mandar sua voz pra
   nenhum servidor de terceiros)
3. O texto vai pra API da Claude, que responde em texto
4. A resposta é sintetizada em voz (você escolhe a voz no rodapé) e tocada

## 🧱 Stack

| Peça | Tecnologia |
|---|---|
| Interface | GTK3 (PyGObject) |
| Cérebro | API da Anthropic (Claude) |
| Reconhecimento de voz (STT) | [faster-whisper](https://github.com/SYSTRAN/faster-whisper), local, sem chave de API |
| Síntese de voz (TTS) | [edge-tts](https://github.com/rany2/edge-tts), gratuito, várias vozes neurais |
| Gravação/reprodução de áudio | `arecord` / `ffplay` (ALSA + ffmpeg, evita depender de PyAudio) |

## 🚀 Como rodar

```bash
./run.sh
```

Na primeira execução isso cria a virtualenv (`--system-site-packages`, pra
enxergar o GTK do sistema), instala as dependências Python e baixa o modelo
Whisper (~500MB, só na primeira vez que você falar algo).

Pré-requisitos do sistema (Pop!_OS/Ubuntu):
```bash
sudo apt install python3-gi gir1.2-gtk-3.0 alsa-utils ffmpeg
```

## 🔑 Configuração

Na primeira vez, o app pede sua **chave da API da Anthropic**
(`sk-ant-...`, veja em https://console.anthropic.com). Ela fica salva em
`~/.config/assistente-voz/config.json` — nunca no repositório.

Pra trocar a chave ou a voz depois, use o botão de engrenagem (⚙️) no topo
da janela.

## 🖥️ Atalho no menu do sistema

```bash
cp assistente-voz.desktop ~/.local/share/applications/
update-desktop-database ~/.local/share/applications/
```

## 🗣️ Vozes disponíveis

Antônio e Duarte (masculinas, PT-BR/PT-PT), Francisca e Thalita (femininas,
PT-BR), além de Guy e Jenny (EN-US) — todas via edge-tts. Dá pra trocar a
qualquer momento no seletor do rodapé ou nas Preferências.
