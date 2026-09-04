#!/usr/bin/env bash
# ==============================================================================
# Script de Submissão para o Flathub
# ==============================================================================
set -e

APP_ID="com.github.wiskton.AcordaNeo"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MANIFEST_SRC="${REPO_ROOT}/packaging/flatpak/${APP_ID}.yaml"
TEMP_DIR="/tmp/flathub-submission"

echo "📦 Preparando submissão do ${APP_ID} para o Flathub..."

# 1. Verifica se o fork existe
echo "🔍 Verificando acesso ao seu fork no GitHub (git@github.com:wiskton/flathub.git)..."
if ! git ls-remote git@github.com:wiskton/flathub.git >/dev/null 2>&1; then
    echo "⚠️  Seu fork de flathub/flathub ainda não foi detectado no GitHub."
    echo ""
    echo "👉 Por favor, abra este link no navegador e clique no botão 'Fork':"
    echo "   🔗 https://github.com/flathub/flathub/fork"
    echo ""
    echo "Assim que criar o Fork, execute este script novamente:"
    echo "   ./packaging/flatpak/submit-to-flathub.sh"
    exit 1
fi

# 2. Clona o fork em diretório temporário
rm -rf "${TEMP_DIR}"
echo "⬇️ Clonando seu fork flathub..."
git clone --depth=1 git@github.com:wiskton/flathub.git "${TEMP_DIR}"
cd "${TEMP_DIR}"

# 3. Cria a branch do novo aplicativo
BRANCH_NAME="new-pr/${APP_ID}"
echo "🌿 Criando branch ${BRANCH_NAME}..."
git checkout -b "${BRANCH_NAME}"

# 4. Copia o manifesto para a raiz do repositório
echo "📋 Copiando manifesto ${APP_ID}.yaml..."
cp "${MANIFEST_SRC}" "${APP_ID}.yaml"

git add "${APP_ID}.yaml"
git commit -m "Add ${APP_ID}"

# 5. Envia a branch para o fork do usuário
echo "🚀 Enviando branch para o GitHub..."
git push -u origin "${BRANCH_NAME}" --force

echo ""
echo "======================================================================"
echo "🎉 Branch enviada com sucesso para o seu GitHub!"
echo ""
echo "👉 Clique no link abaixo para abrir o Pull Request oficial no Flathub:"
echo "   🔗 https://github.com/flathub/flathub/compare/master...wiskton:flathub:${BRANCH_NAME}?expand=1"
echo "======================================================================"
