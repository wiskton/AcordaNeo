"""ChatGPT via automação de navegador — a "gambiarra" alternativa à API da
Anthropic, pra quando o usuário prefere usar a própria conta do ChatGPT em
vez de pagar pela API. Usa o Chrome já instalado no sistema (via Playwright
`channel="chrome"`) com um perfil persistente, então o login fica salvo
entre uma pergunta e outra — só loga de novo se a sessão expirar.

Reaproveita a lógica (seletores, fluxo de login) já validada no projeto
PhotoVerse (chatgpt_web.js), portada aqui pra Python/Playwright.
"""

import re
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright

from .config import CONFIG_DIR

PERFIL_DIR = CONFIG_DIR / "chatgpt_browser_profile"

_SELETOR_PROMPT = '#prompt-textarea, textarea[placeholder*="ChatGPT"], div[contenteditable="true"]'
_SELETOR_ENVIAR = 'button[data-testid="send-button"], button[aria-label*="Send"], button[aria-label*="Enviar"]'
_SELETOR_PARAR = 'button[aria-label*="Stop"], button[aria-label*="Parar"], button[data-testid="stop-button"]'
_SELETOR_EMAIL = 'input[name="username"], input[type="email"], #username, input[autocomplete="username"]'
_SELETOR_SENHA = 'input[name="password"], input[type="password"], #password'
_SELETOR_SUBMIT = 'button[type="submit"], button[name="action"], button.btn-primary'


class ChatGPTWebError(RuntimeError):
    pass


class ChatGPTWebClient:
    def __init__(self, email: str, senha: str, headless: bool = True):
        self._email = email
        self._senha = senha
        self._headless = headless
        self._playwright = None
        self._contexto = None
        self._pagina = None

    def _garantir_sessao(self):
        if self._pagina is not None:
            return

        PERFIL_DIR.mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        self._contexto = self._playwright.chromium.launch_persistent_context(
            str(PERFIL_DIR),
            channel="chrome",
            headless=self._headless,
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._pagina = self._contexto.pages[0] if self._contexto.pages else self._contexto.new_page()
        self._pagina.goto("https://chatgpt.com", wait_until="domcontentloaded", timeout=60000)
        self._pagina.wait_for_timeout(3000)
        self._tentar_login()

    def _tentar_login(self):
        if not (self._email and self._senha):
            return

        pagina = self._pagina
        botao_login = pagina.locator(
            'button[data-testid="login-button"], a[href*="login"], [data-testid="welcome-login-button"]'
        ).first
        if botao_login.count() == 0:
            botao_login = pagina.get_by_text(re.compile(r"log in|entrar", re.I)).first
        if botao_login.count() == 0:
            return  # já logado (perfil persistente lembrou a sessão)

        botao_login.click()
        pagina.wait_for_load_state("domcontentloaded", timeout=20000)
        pagina.wait_for_timeout(2000)

        if pagina.locator('iframe[src*="challenges.cloudflare.com"], .cf-turnstile').count() > 0 and self._headless:
            raise ChatGPTWebError(
                "O ChatGPT pediu um desafio de segurança (CAPTCHA) no login. "
                "Desative \"Rodar em segundo plano\" nas Preferências pra completar "
                "o login numa janela visível uma vez — depois disso a sessão fica salva."
            )

        campo_email = pagina.locator(_SELETOR_EMAIL).first
        if campo_email.count() > 0:
            campo_email.fill(self._email)
            botao = pagina.locator(_SELETOR_SUBMIT).first
            if botao.count() > 0:
                botao.click()
            pagina.wait_for_timeout(3000)

        campo_senha = pagina.locator(_SELETOR_SENHA).first
        try:
            campo_senha.wait_for(timeout=10000)
        except Exception:
            campo_senha = None
        if campo_senha and campo_senha.count() > 0:
            campo_senha.fill(self._senha)
            botao = pagina.locator(_SELETOR_SUBMIT).first
            if botao.count() > 0:
                botao.click()
            pagina.wait_for_load_state("domcontentloaded", timeout=25000)
            pagina.wait_for_timeout(3000)

    def perguntar(self, pergunta: str, timeout_resposta: int = 90) -> str:
        self._garantir_sessao()
        pagina = self._pagina

        try:
            campo = pagina.wait_for_selector(_SELETOR_PROMPT, timeout=35000)
        except Exception as exc:
            raise ChatGPTWebError(
                "Não achei a caixa de texto do ChatGPT — provavelmente o login não "
                "foi concluído. Desative \"Rodar em segundo plano\" nas Preferências "
                "pra logar manualmente uma vez."
            ) from exc

        campo.click()
        campo.fill(pergunta)
        pagina.keyboard.press("Enter")

        segundos_passados = 0
        while segundos_passados < timeout_resposta:
            pagina.wait_for_timeout(1500)
            segundos_passados += 1.5

            texto_assistente = pagina.evaluate(
                """() => {
                    const msgs = document.querySelectorAll('div[data-message-author-role="assistant"]');
                    return msgs.length ? msgs[msgs.length - 1].innerText : '';
                }"""
            )

            if texto_assistente:
                minusculo = texto_assistente.lower()
                if "faça login" in minusculo or "sign in" in minusculo or "log in" in minusculo:
                    raise ChatGPTWebError("O ChatGPT pediu login de novo — a sessão deve ter expirado.")

            ainda_gerando = pagina.locator(_SELETOR_PARAR).count() > 0
            if texto_assistente and not ainda_gerando:
                return texto_assistente.strip()

        raise ChatGPTWebError("O ChatGPT demorou demais pra responder (timeout).")

    def fechar(self):
        if self._contexto:
            self._contexto.close()
        if self._playwright:
            self._playwright.stop()
