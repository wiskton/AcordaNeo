"""Cliente para modelos locais via Ollama (100% offline, gratuito e sem chave de API)."""

import json
import re
import urllib.error
import urllib.request
from typing import List

SYSTEM_PROMPT = (
    "Você é o Neo, um assistente de voz direto e seguro de si, ativado pela frase "
    "\"Acorda, Neo\". Responda SEMPRE em português do Brasil, de forma natural e "
    "conversacional — a resposta vai ser lida em voz alta, então evite listas, "
    "markdown, asteriscos, emojis ou qualquer formatação visual. Seja conciso: normalmente "
    "de 1 a 3 frases curtas, só se estenda se a pergunta realmente exigir. Só se "
    "apresente pelo nome quando fizer sentido — não repita 'sou o Neo' toda hora."
)


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, host: str = "http://localhost:11434", model: str = "llama3.2:3b"):
        self.host = host.rstrip("/")
        self.model = model
        self._historico = []

    def testar_conexao(self) -> bool:
        """Verifica se o servidor Ollama está acessível."""
        try:
            url = f"{self.host}/api/version"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def listar_modelos(self) -> List[str]:
        """Lista os modelos instalados no Ollama local."""
        try:
            url = f"{self.host}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                modelos = [m.get("name") for m in data.get("models", []) if m.get("name")]
                return modelos
        except Exception:
            return []

    def perguntar(self, pergunta: str) -> str:
        """Envia a pergunta ao modelo local do Ollama mantendo o histórico de conversa."""
        self._historico.append({"role": "user", "content": pergunta})

        mensagens = [{"role": "system", "content": SYSTEM_PROMPT}] + self._historico

        payload = {
            "model": self.model,
            "messages": mensagens,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 300,
            },
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            url = f"{self.host}/api/chat"
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60.0) as resp:
                resultado = json.loads(resp.read().decode("utf-8"))

            mensagem = resultado.get("message", {})
            texto = mensagem.get("content", "").strip()

            # Remove blocos de raciocínio de modelos com thinking (ex: DeepSeek-R1, Qwen3)
            if "<think>" in texto and "</think>" in texto:
                texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL).strip()

            self._historico.append({"role": "assistant", "content": texto})

            if len(self._historico) > 20:
                self._historico = self._historico[-20:]

            return texto
        except urllib.error.URLError as e:
            raise OllamaError(
                f"Não foi possível conectar ao Ollama em {self.host}. "
                "Verifique se o serviço está ativo (execute 'ollama serve')."
            ) from e
        except Exception as e:
            raise OllamaError(f"Erro ao consultar modelo {self.model}: {e}") from e

    def limpar_historico(self):
        self._historico = []
