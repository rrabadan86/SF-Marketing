import os
import io

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import (
    MediaIoBaseDownload,
    MediaFileUpload,
)


CREDENTIALS_FILE = os.getenv(
    "GOOGLE_CREDENTIALS_FILE",
    "/app/secrets/google.json",
)

OAUTH_TOKEN_FILE = "/app/secrets/google_token.json"

ROOT_FOLDER_ID = os.getenv("DRIVE_ROOT_FOLDER_ID")

DRIVE_SCOPE = [
    "https://www.googleapis.com/auth/drive"
]


def _carregar_oauth():
    """
    Carrega o token OAuth do usuário e, se necessário, faz o refresh de
    forma proativa. Se o refresh token estiver expirado/revogado
    (invalid_grant), a exceção sobe para o chamador decidir o fallback —
    em vez de estourar mais tarde, no meio de uma chamada à API.
    """

    if not os.path.exists(OAUTH_TOKEN_FILE):
        return None

    credentials = Credentials.from_authorized_user_file(
        OAUTH_TOKEN_FILE,
        scopes=DRIVE_SCOPE,
    )

    if not credentials.valid:
        if (
            credentials.expired
            and credentials.refresh_token
        ):
            # Pode levantar RefreshError (invalid_grant) — proposital:
            # queremos detectar o token morto aqui e cair para a SA.
            credentials.refresh(Request())
        else:
            return None

    return credentials


def _carregar_service_account():
    if not os.path.exists(CREDENTIALS_FILE):
        return None

    return (
        service_account.Credentials
        .from_service_account_file(
            CREDENTIALS_FILE,
            scopes=DRIVE_SCOPE,
        )
    )


def get_drive_credentials():
    # 1) Tenta OAuth da conta Google do usuário.
    try:
        credentials = _carregar_oauth()

        if credentials:
            print(
                "Google Drive autenticado via OAuth",
                flush=True,
            )

            return credentials

    except Exception as erro:
        # Token OAuth morto (invalid_grant) ou arquivo inválido: em vez
        # de derrubar a geração, caímos para a Service Account.
        print(
            "OAuth do Drive indisponível "
            f"({type(erro).__name__}: {erro}); "
            "tentando Service Account.",
            flush=True,
        )

    # 2) Fallback: Service Account (não expira — ideal para servidor).
    conta_servico = _carregar_service_account()

    if conta_servico:
        print(
            "Google Drive autenticado via Service Account",
            flush=True,
        )

        return conta_servico

    raise RuntimeError(
        "Nenhuma credencial Google válida: o token OAuth falhou "
        "(expirado/revogado) e não há Service Account em "
        f"{CREDENTIALS_FILE}. Configure a Service Account e compartilhe "
        "as pastas do Drive com o e-mail dela."
    )


def get_drive_service():
    credentials = get_drive_credentials()

    return build(
        "drive",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )


def listar_pasta(folder_id):
    service = get_drive_service()

    query = (
        f"'{folder_id}' in parents "
        "and trashed = false"
    )

    result = service.files().list(
        q=query,
        fields=(
            "files("
            "id,"
            "name,"
            "mimeType,"
            "size,"
            "modifiedTime"
            ")"
        ),
        orderBy="name",
        pageSize=1000,
    ).execute()

    return result.get("files", [])


def localizar_subpasta(parent_id, nome):
    arquivos = listar_pasta(parent_id)

    for arquivo in arquivos:
        if (
            arquivo["name"] == nome
            and arquivo["mimeType"]
            == "application/vnd.google-apps.folder"
        ):
            return arquivo

    return None


def baixar_arquivo(file_id, destino):
    service = get_drive_service()

    request = service.files().get_media(
        fileId=file_id,
    )

    with io.FileIO(destino, "wb") as arquivo_local:
        downloader = MediaIoBaseDownload(
            arquivo_local,
            request,
        )

        concluido = False

        while not concluido:
            _, concluido = downloader.next_chunk()

    return destino


def upload_arquivo(
    caminho_local,
    nome_arquivo,
    folder_id,
    mime_type="image/jpeg",
):
    service = get_drive_service()

    metadata = {
        "name": nome_arquivo,
        "parents": [folder_id],
    }

    media = MediaFileUpload(
        caminho_local,
        mimetype=mime_type,
        resumable=False,
    )

    arquivo = service.files().create(
        body=metadata,
        media_body=media,
        fields="id,name,webViewLink",
    ).execute()

    return arquivo


def localizar_pasta_gerados():
    pasta = localizar_subpasta(
        ROOT_FOLDER_ID,
        "04_GERADOS",
    )

    if not pasta:
        raise RuntimeError(
            "Pasta 04_GERADOS não encontrada."
        )

    return pasta


def testar_drive():
    if not ROOT_FOLDER_ID:
        raise RuntimeError(
            "DRIVE_ROOT_FOLDER_ID não configurado"
        )

    return listar_pasta(ROOT_FOLDER_ID)
