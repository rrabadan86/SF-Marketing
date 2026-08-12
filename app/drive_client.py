import os
import io

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
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


def get_drive_credentials():
    # Prioridade: OAuth da conta Google do usuário.
    if os.path.exists(OAUTH_TOKEN_FILE):
        credentials = Credentials.from_authorized_user_file(
            OAUTH_TOKEN_FILE,
            scopes=DRIVE_SCOPE,
        )

        print(
            "Google Drive autenticado via OAuth",
            flush=True,
        )

        return credentials

    # Fallback: Service Account.
    if os.path.exists(CREDENTIALS_FILE):
        credentials = (
            service_account.Credentials
            .from_service_account_file(
                CREDENTIALS_FILE,
                scopes=DRIVE_SCOPE,
            )
        )

        print(
            "Google Drive autenticado via Service Account",
            flush=True,
        )

        return credentials

    raise RuntimeError(
        "Nenhuma credencial Google encontrada."
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
