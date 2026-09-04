# 🕶️ Acorda, Neo

App de desktop (GTK3) pra conversar por voz com a Claude (ou o ChatGPT):
fica sempre ouvindo em segundo plano, e quando você diz **"Acorda, Neo"**
ele ativa, escuta sua pergunta, manda pro provedor escolhido, e a resposta
volta falada — com várias vozes possíveis pra escolher. Sem botão nenhum
pra apertar.

## ✨ Como funciona

1. Fale **"Acorda, Neo"** — o app está sempre escutando trechos curtos em
   segundo plano esperando essa frase
2. Assim que reconhece a ativação, começa a gravar sua pergunta e para
   sozinho quando você fica em silêncio por um instante
3. O áudio é transcrito **localmente** (Whisper, sem mandar sua voz pra
   nenhum servidor de terceiros)
4. O texto vai pro provedor escolhido no rodapé — **Claude** (API oficial)
   ou **ChatGPT** (login no navegador, sem precisar de chave paga) — e
   volta a resposta em texto
5. A resposta é sintetizada em voz (você escolhe a voz no rodapé) e tocada
   — depois disso o app volta a escutar a próxima ativação

## 🧱 Stack

| Peça | Tecnologia |
|---|---|
| Interface | GTK3 (PyGObject) |
| Cérebro (opção 1) | API da Anthropic (Claude) |
| Cérebro (opção 2) | ChatGPT via automação do navegador ([Playwright](https://playwright.dev/) + Chrome do sistema) — "gambiarra" pra quem prefere usar a própria conta do ChatGPT em vez de pagar API |
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

Na primeira vez, o app pede pra configurar pelo menos um provedor:

- **Claude**: chave da API da Anthropic (`sk-ant-...`, veja em
  https://console.anthropic.com — precisa de crédito, a assinatura do
  Claude.ai não vale pra API)
- **ChatGPT**: e-mail e senha da sua conta (login normal por e-mail/senha —
  contas via Google/Microsoft não funcionam com essa automação). Faz login
  num Chrome de verdade e guarda a sessão, então só pede login de novo se
  expirar. Se aparecer captcha, desmarque "Rodar em segundo plano" pra
  logar manualmente uma vez.

Tudo fica salvo em `~/.config/assistente-voz/config.json` — nunca no
repositório. Escolha qual provedor usar no seletor **"Quem responde"** no
rodapé da janela, e troque quando quiser sem reiniciar o app.

Pra editar as credenciais ou a voz depois, use o botão de engrenagem (⚙️)
no topo da janela.

## 🖥️ Atalho no menu do sistema

```bash
cp assistente-voz.desktop ~/.local/share/applications/
update-desktop-database ~/.local/share/applications/
```

## 🗣️ Vozes disponíveis

Antônio e Duarte (masculinas, PT-BR/PT-PT), Francisca e Thalita (femininas,
PT-BR), além de Guy e Jenny (EN-US) — todas via edge-tts. Dá pra trocar a
qualquer momento no seletor do rodapé ou nas Preferências.
