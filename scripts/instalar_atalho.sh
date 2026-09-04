#!/usr/bin/env bash
# ==============================================================================
# Script de Configuração de Atalho Global (Push-to-Talk) para Acorda, Neo
# Suporta GNOME, COSMIC (Pop!_OS), KDE, Hyprland, Sway e i3
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Atalho padrão: Super+A (ou Ctrl+Alt+Espaço)
SHORTCUT="${1:-<Super>a}"
RUN_CMD="${REPO_ROOT}/run.sh --wake"

echo "🎙️  Configurando Atalho Global para o Acorda, Neo"
echo "👉 Comando a ser executado: ${RUN_CMD}"
echo "👉 Combinação de teclas:    ${SHORTCUT}"
echo ""

DESKTOP_ENV="${XDG_CURRENT_DESKTOP:-$DESKTOP_SESSION}"
echo "🔍 Ambiente detectado: ${DESKTOP_ENV}"

# ------------------------------------------------------------------------------
# GNOME / Ubuntu / Pop!_OS (GNOME Shell)
# ------------------------------------------------------------------------------
if echo "${DESKTOP_ENV}" | grep -iqE "gnome|pop|ubuntu"; then
    echo "⚙️ Configurando atalho no GNOME via gsettings..."

    BINDING_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/acordaneo/"
    SCHEMA_CUSTOM="org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:${BINDING_PATH}"

    # Recupera lista atual de atalhos customizados
    CURRENT_LIST=$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings 2>/dev/null || echo "@as []")

    # Adiciona acordaneo se não estiver na lista
    if ! echo "${CURRENT_LIST}" | grep -q "${BINDING_PATH}"; then
        if [ "${CURRENT_LIST}" = "@as []" ] || [ "${CURRENT_LIST}" = "[]" ]; then
            NEW_LIST="['${BINDING_PATH}']"
        else
            NEW_LIST=$(echo "${CURRENT_LIST}" | sed "s/]/, '${BINDING_PATH//\//\\/}']/")
        fi
        gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "${NEW_LIST}"
    fi

    # Configura nome, comando e atalho
    gsettings set "${SCHEMA_CUSTOM}" name "Acorda, Neo (Push-to-Talk)"
    gsettings set "${SCHEMA_CUSTOM}" command "${RUN_CMD}"
    gsettings set "${SCHEMA_CUSTOM}" binding "${SHORTCUT}"

    echo "✅ Atalho registrado no GNOME com sucesso! Pressione ${SHORTCUT} para ativar a escuta."
    exit 0
fi

# ------------------------------------------------------------------------------
# KDE Plasma
# ------------------------------------------------------------------------------
if echo "${DESKTOP_ENV}" | grep -iq "kde"; then
    echo "💡 No KDE Plasma, adicione um atalho personalizado:"
    echo "   1. Abra Configurações do Sistema -> Atalhos -> Atalhos Personalizados"
    echo "   2. Adicione 'Novo Atalho Global' -> Comando/URL"
    echo "   3. Nome: Acorda, Neo (Push-to-Talk)"
    echo "   4. Gatilho: ${SHORTCUT} (ex: Meta+A)"
    echo "   5. Ação: ${RUN_CMD}"
    exit 0
fi

# ------------------------------------------------------------------------------
# Sway / Hyprland / i3
# ------------------------------------------------------------------------------
echo "💡 Para gerenciadores de janela baseados em Wayland / X11:"
echo ""
echo "📌 Hyprland (~/.config/hypr/hyprland.conf):"
echo "   bind = SUPER, A, exec, ${RUN_CMD}"
echo ""
echo "📌 Sway (~/.config/sway/config) ou i3 (~/.config/i3/config):"
echo "   bindsym Mod4+a exec ${RUN_CMD}"
echo ""
