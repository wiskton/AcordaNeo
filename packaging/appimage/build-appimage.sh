#!/usr/bin/env bash
# ==============================================================================
# Script de Build do AppImage para Acorda, Neo
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BUILD_DIR="${REPO_ROOT}/build/appimage"
APPDIR="${BUILD_DIR}/AcordaNeo.AppDir"
OUTPUT_DIR="${REPO_ROOT}/dist"

echo "🔨 Preparando estrutura do AppDir..."
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin"
mkdir -p "${APPDIR}/usr/share/acordaneo"
mkdir -p "${APPDIR}/usr/share/applications"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"
mkdir -p "${OUTPUT_DIR}"

# Copia arquivos do projeto
echo "📦 Copiando arquivos da aplicação..."
cp -r "${REPO_ROOT}/assistente_voz" "${APPDIR}/usr/share/acordaneo/"
cp -r "${REPO_ROOT}/assets" "${APPDIR}/usr/share/acordaneo/"
cp "${REPO_ROOT}/main.py" "${APPDIR}/usr/share/acordaneo/"
cp "${REPO_ROOT}/requirements.txt" "${APPDIR}/usr/share/acordaneo/"

# Ícone e Desktop file
cp "${REPO_ROOT}/assets/avatar.png" "${APPDIR}/usr/share/icons/hicolor/256x256/apps/acordaneo.png"
cp "${REPO_ROOT}/assets/avatar.png" "${APPDIR}/acordaneo.png"
cp "${REPO_ROOT}/assets/avatar.png" "${APPDIR}/.DirIcon"

cat << 'EOF' > "${APPDIR}/acordaneo.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=Acorda, Neo
GenericName=Assistente de Voz com IA
Comment=Diga "Acorda, Neo" pra ativar — converse por voz com IA offline ou em nuvem
Exec=acordaneo %U
Icon=acordaneo
Terminal=false
Categories=Utility;AudioVideo;
Keywords=voz;assistente;ia;claude;ollama;audio;chat;neo;matrix;
StartupNotify=true
StartupWMClass=acordaneo
EOF

cp "${APPDIR}/acordaneo.desktop" "${APPDIR}/usr/share/applications/"

# Copia AppRun
cp "${SCRIPT_DIR}/AppRun" "${APPDIR}/AppRun"
chmod +x "${APPDIR}/AppRun"

# Wrapper executável em usr/bin
cat << 'EOF' > "${APPDIR}/usr/bin/acordaneo"
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "${0}")")/.."
exec python3 "${HERE}/share/acordaneo/main.py" "$@"
EOF
chmod +x "${APPDIR}/usr/bin/acordaneo"

# Baixa appimagetool se não estiver presente
APPIMAGETOOL="${BUILD_DIR}/appimagetool"
if ! command -v appimagetool >/dev/null 2>&1; then
    if [ ! -f "${APPIMAGETOOL}" ]; then
        echo "⬇️ Baixando appimagetool..."
        curl -sSL "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" -o "${APPIMAGETOOL}"
        chmod +x "${APPIMAGETOOL}"
    fi
    TOOL_CMD="${APPIMAGETOOL}"
else
    TOOL_CMD="appimagetool"
fi

echo "🚀 Gerando AppImage..."
ARCH=x86_64 "${TOOL_CMD}" "${APPDIR}" "${OUTPUT_DIR}/AcordaNeo-x86_64.AppImage"

echo "✅ AppImage gerado com sucesso em: ${OUTPUT_DIR}/AcordaNeo-x86_64.AppImage"
