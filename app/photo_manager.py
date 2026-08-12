import os
import json

from drive_client import (
    ROOT_FOLDER_ID,
    listar_pasta,
    localizar_subpasta,
)

DATA_DIR = "/app/data"
PHOTO_INVENTORY_FILE = os.path.join(DATA_DIR, "photos_inventory.json")


def listar_subpastas(folder_id):
    arquivos = listar_pasta(folder_id)

    return [
        arquivo for arquivo in arquivos
        if arquivo["mimeType"] == "application/vnd.google-apps.folder"
    ]


def listar_imagens(folder_id):
    arquivos = listar_pasta(folder_id)

    imagens = []

    for arquivo in arquivos:
        mime = arquivo.get("mimeType", "")
        if mime.startswith("image/"):
            imagens.append(arquivo)

    return imagens


def inventariar_pasta(folder_id, caminho_atual=""):
    arquivos = listar_pasta(folder_id)

    resultado = {
        "path": caminho_atual,
        "folders": [],
        "images": [],
        "image_count": 0,
    }

    for arquivo in arquivos:
        nome = arquivo["name"]
        mime = arquivo["mimeType"]

        if mime == "application/vnd.google-apps.folder":
            sub_caminho = f"{caminho_atual}/{nome}" if caminho_atual else nome
            sub_resultado = inventariar_pasta(arquivo["id"], sub_caminho)
            resultado["folders"].append(sub_resultado)
            resultado["image_count"] += sub_resultado["image_count"]

        elif mime.startswith("image/"):
            resultado["images"].append({
                "id": arquivo["id"],
                "name": nome,
                "mimeType": mime,
                "path": caminho_atual,
            })
            resultado["image_count"] += 1

    return resultado


def gerar_inventario_fotos():
    pasta_fotos = localizar_subpasta(ROOT_FOLDER_ID, "02_FOTOS")

    if not pasta_fotos:
        raise RuntimeError("Pasta 02_FOTOS não encontrada.")

    inventario = inventariar_pasta(
        pasta_fotos["id"],
        "02_FOTOS",
    )

    os.makedirs(DATA_DIR, exist_ok=True)

    with open(
        PHOTO_INVENTORY_FILE,
        "w",
        encoding="utf-8",
    ) as arquivo:
        json.dump(
            inventario,
            arquivo,
            ensure_ascii=False,
            indent=2,
        )

    return inventario
