# 🕶️ Acorda, Neo

App de desktop (GTK3) pra conversar por voz com a Claude: fica sempre
ouvindo em segundo plano, e quando você diz **"Acorda, Neo"** ele ativa,
escuta sua pergunta, manda pra API da Anthropic, e a resposta volta falada
— com várias vozes possíveis pra escolher. Sem botão nenhum pra apertar.

## ✨ Como funciona

1. Fale **"Acorda, Neo"** — o app está sempre escutando trechos curtos em
   segundo plano esperando essa frase
2. Assim que reconhece a ativação, começa a gravar sua pergunta e para
   sozinho quando você fica em silêncio por um instante
3. O áudio é transcrito **localmente** (Whisper, sem mandar sua voz pra
   nenhum servidor de terceiros)
4. O texto vai pra API da Claude, que responde em texto
5. A resposta é sintetizada em voz (você escolhe a voz no rodapé) e tocada
   — depois disso o app volta a escutar a próxima ativação

## 🧱 Stack

| Peça | Tecnologia |
|---|---|
| Interface | GTK3 (PyGObject) |
| Cérebro | API da Anthropic (Claude) |
| Reconhecimento de voz (STT) | [faster-whisper](https://github.com/SYSTRAN/faster-whisper), local, sem chave de API (modelo "tiny" pra escuta contínua da ativação, "small" pra transcrever a pergunta) |
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
