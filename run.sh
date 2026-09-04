#!/usr/bin/env bash
# ==============================================================================
# Assistente de Voz — cria a venv (se precisar) e roda o app.
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d .venv ]; then
    echo "📦 Primeira execução: criando ambiente virtual..."
    python3 -m venv .venv --system-site-packages
fi

source .venv/bin/activate

if ! python3 -c "import anthropic, faster_whisper, edge_tts" 2>/dev/null; then
    echo "📦 Instalando dependências..."
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
fi

for cmd in arecord ffplay; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "⚠️  Comando '$cmd' não encontrado. Instale com: sudo apt install alsa-utils ffmpeg"
    fi
done

# Calibra ganho do microfone interno (evita distorção e saturação no codec ALC257)
amixer -c 0 sset 'Internal Mic Boost' 0 >/dev/null 2>&1 || true
amixer -c 0 sset 'Capture' 45 >/dev/null 2>&1 || true

# Inicia o Ollama se estiver disponível e não estiver respondendo
if command -v ollama >/dev/null 2>&1; then
    if ! curl -s http://localhost:11434/api/version >/dev/null 2>&1; then
        systemctl start ollama 2>/dev/null || (ollama serve >/dev/null 2>&1 &)
    fi
fi

# Integração com o Pop!_OS / Desktop (ícone e lançador)
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons"
if [ -f "$SCRIPT_DIR/acordaneo.desktop" ]; then
    mkdir -p "$DESKTOP_DIR" "$ICON_DIR"
    cp -f "$SCRIPT_DIR/assets/avatar.png" "$ICON_DIR/acordaneo.png" 2>/dev/null || true
    cp -f "$SCRIPT_DIR/acordaneo.desktop" "$DESKTOP_DIR/acordaneo.desktop" 2>/dev/null || true
fi

echo "🚀 Iniciando Acorda, Neo..."
exec python3 main.py

