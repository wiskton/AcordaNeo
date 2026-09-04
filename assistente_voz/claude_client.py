"""Wrapper fino sobre a API da Anthropic (Claude) para o assistente de voz."""

from anthropic import Anthropic

SYSTEM_PROMPT = (
    "Você é um assistente de voz sábio e direto, com o tom calmo e confiante de "
    "um mentor. Responda SEMPRE em português do Brasil, de forma natural e "
    "conversacional — a resposta vai ser lida em voz alta, então evite listas, "
    "markdown, emojis ou qualquer formatação visual. Seja conciso: normalmente "
    "de 1 a 4 frases, só se estenda se a pergunta realmente exigir."
)


class ClaudeClient:
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ValueError("Chave da API da Anthropic não configurada.")
        self._client = Anthropic(api_key=api_key)
        self._model = model
        self._historico = []

    def perguntar(self, pergunta: str) -> str:
        """Envia a pergunta (com o histórico da conversa) e devolve a resposta em texto."""
        self._historico.append({"role": "user", "content": pergunta})

        resposta = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=self._historico,
        )

        texto = "".join(bloco.text for bloco in resposta.content if bloco.type == "text").strip()
        self._historico.append({"role": "assistant", "content": texto})

        # Mantém só as últimas ~10 trocas pra não deixar o contexto (e o custo) crescer sem limite
        if len(self._historico) > 20:
            self._historico = self._historico[-20:]

        return texto

    def limpar_historico(self):
        self._historico = []
