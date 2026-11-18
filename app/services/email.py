import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

# Tempo máximo (segundos) esperando a resposta do serviço de e-mail
TIMEOUT_SEGUNDOS = 15


class EmailEnvioError(Exception):
    """Falha ao enviar e-mail."""


def _post_json(url: str, headers: dict, payload: dict) -> None:
    """Faz um POST JSON usando só a biblioteca padrão (sem dependências novas)."""

    dados = json.dumps(payload).encode("utf-8")

    # O User-Agent é necessário: alguns serviços bloqueiam o padrão do urllib
    cabecalhos = {
        "Content-Type": "application/json",
        "User-Agent": "VALID/1.0",
        **headers,
    }

    requisicao = urllib.request.Request(
        url,
        data=dados,
        headers=cabecalhos,
        method="POST",
    )

    try:
        with urllib.request.urlopen(requisicao, timeout=TIMEOUT_SEGUNDOS) as resposta:
            resposta.read()

    except urllib.error.HTTPError as erro:
        corpo = erro.read().decode("utf-8", errors="replace")
        logger.error("Serviço de e-mail recusou o envio (%s): %s", erro.code, corpo)
        raise EmailEnvioError("O serviço de e-mail recusou o envio.") from erro

    except (urllib.error.URLError, TimeoutError, OSError) as erro:
        logger.error("Não foi possível conectar ao serviço de e-mail: %s", erro)
        raise EmailEnvioError("Não foi possível conectar ao serviço de e-mail.") from erro


def _enviar_resend(destinatario, assunto, mensagem, remetente, nome, api_key):
    _post_json(
        "https://api.resend.com/emails",
        {"Authorization": f"Bearer {api_key}"},
        {
            "from": f"{nome} <{remetente}>",
            "to": [destinatario],
            "subject": assunto,
            "text": mensagem,
        },
    )


def _enviar_brevo(destinatario, assunto, mensagem, remetente, nome, api_key):
    _post_json(
        "https://api.brevo.com/v3/smtp/email",
        {"api-key": api_key, "accept": "application/json"},
        {
            "sender": {"name": nome, "email": remetente},
            "to": [{"email": destinatario}],
            "subject": assunto,
            "textContent": mensagem,
        },
    )


def enviar_email(
    destinatario: str,
    assunto: str,
    mensagem: str
):
    """
    Envia e-mail por API HTTPS (a Render bloqueia SMTP nos planos gratuitos).

    Variáveis de ambiente:
      EMAIL_PROVIDER   -> "resend" (padrão) ou "brevo"
      EMAIL_API_KEY    -> chave da API do provedor
      EMAIL_FROM       -> e-mail remetente (precisa estar autorizado no provedor)
      EMAIL_FROM_NAME  -> nome exibido (padrão "VALID")
    """

    provedor = os.getenv("EMAIL_PROVIDER", "resend").strip().lower()
    api_key = os.getenv("EMAIL_API_KEY", "").strip()
    remetente = (os.getenv("EMAIL_FROM") or os.getenv("EMAIL_USER") or "").strip()
    nome = os.getenv("EMAIL_FROM_NAME", "VALID").strip()

    if not api_key or not remetente:
        logger.error("EMAIL_API_KEY ou EMAIL_FROM não configurados.")
        raise EmailEnvioError("Serviço de e-mail não configurado.")

    if provedor == "resend":
        _enviar_resend(destinatario, assunto, mensagem, remetente, nome, api_key)
    elif provedor == "brevo":
        _enviar_brevo(destinatario, assunto, mensagem, remetente, nome, api_key)
    else:
        raise EmailEnvioError(f"Provedor de e-mail desconhecido: {provedor}")