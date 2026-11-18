import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm

from app.database import get_db
from app.schemas.usuario import UsuarioCriacao
from app.services.autenticacao import criar_usuario, autenticar_usuario

from app.utils.seguranca import criar_access_token

from app.services.dois_fatores import criar_token_2fa, verificar_codigo_2fa
from app.services.email import EmailEnvioError
from app.schemas.dois_fatores import Verificar2FARequest


# Uso PROVISÓRIO: defina DOIS_FATORES_DESATIVADO=true no ambiente para
# pular o 2FA (por exemplo, enquanto o envio de e-mail não está configurado).
# Deixe em false (ou sem definir) para manter o 2FA ativo.
DOIS_FATORES_DESATIVADO = (
    os.getenv("DOIS_FATORES_DESATIVADO", "false").strip().lower() == "true"
)


router = APIRouter(
    prefix="/auth",
    tags=["Autenticação"]
)


@router.post("/cadastro")
def cadastro(
    usuario: UsuarioCriacao,
    db: Session = Depends(get_db)
):

    novo_usuario = criar_usuario(db, usuario)

    if novo_usuario is None:
        raise HTTPException(
            status_code=400,
            detail="Email já cadastrado."
        )

    return {
        "mensagem": "Usuário criado com sucesso!",
        "id_usuario": novo_usuario.id_usuario
    }


@router.post("/login")
def login(
    dados: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    usuario = autenticar_usuario(
        email=dados.username,
        senha=dados.password,
        db=db
    )

    # Verifica se o usuário possui 2FA ativo
    if usuario.dois_fatores_ativo and not DOIS_FATORES_DESATIVADO:

        try:
            criar_token_2fa(db, usuario)

        except EmailEnvioError:
            # Em vez de um erro 500 genérico, devolve uma mensagem clara
            raise HTTPException(
                status_code=503,
                detail=(
                    "Não foi possível enviar o código de verificação "
                    "por e-mail. Tente novamente em instantes."
                )
            )

        return {
            "status": "2fa",
            "mensagem": "Enviamos um código de verificação para seu e-mail.",
            "email": usuario.email
        }

    token = criar_access_token(
        {
            "sub": str(usuario.id_usuario)
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }


@router.post("/verificar-2fa")
def verificar_2fa(
    dados: Verificar2FARequest,
    db: Session = Depends(get_db)
):

    access_token = verificar_codigo_2fa(
        db=db,
        email=dados.email,
        codigo=dados.codigo
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }