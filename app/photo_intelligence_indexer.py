import argparse
import base64
import json
import os
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from PIL import Image
from pillow_heif import register_heif_opener

from drive_client import baixar_arquivo
from openai_client import client, extrair_json

from photo_intelligence import (
    DB_FILE,
    VISUAL_INDEX_VERSION,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSIONS,
    ensure_photo_intelligence_schema,
    embedding_para_blob,
)


register_heif_opener()


PREVIEW_DIR = Path(
    "/app/cache/photo_previews"
)

PREVIEW_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# =========================================================
# PREVIEW
# =========================================================

def criar_preview(
    caminho_original,
    drive_file_id,
):
    destino = (
        PREVIEW_DIR
        / f"{drive_file_id}.jpg"
    )

    if destino.exists():
        return str(
            destino
        )

    imagem = Image.open(
        caminho_original
    ).convert(
        "RGB"
    )

    largura, altura = (
        imagem.size
    )

    max_dim = 512

    if max(
        largura,
        altura,
    ) > max_dim:
        proporcao = (
            max_dim
            / max(
                largura,
                altura,
            )
        )

        imagem = imagem.resize(
            (
                int(
                    largura
                    * proporcao
                ),
                int(
                    altura
                    * proporcao
                ),
            ),
            Image.Resampling.LANCZOS,
        )

    imagem.save(
        destino,
        "JPEG",
        quality=76,
        optimize=True,
    )

    return str(
        destino
    )


def imagem_para_base64(
    caminho,
):
    with open(
        caminho,
        "rb",
    ) as arquivo:
        return base64.b64encode(
            arquivo.read()
        ).decode(
            "utf-8"
        )


# =========================================================
# ANALISE VISUAL
# =========================================================

def analisar_lote(
    itens,
):
    conteudo = []

    prompt = """
Você está criando um ÍNDICE VISUAL GENÉRICO de fotografias
reais para futura busca em linguagem natural.

Não tente adivinhar campanhas futuras. Descreva o que está
VISIVELMENTE presente de forma ampla, reutilizável e objetiva.

Para cada imagem registre:
- quantidade aproximada de pessoas;
- se é individual, pequeno grupo ou grande grupo;
- ambiente/cenário;
- atividade;
- pose/comportamento;
- humor/clima visual;
- roupas e estilos de roupa;
- cores das roupas e proporção aproximada do grupo em cada cor;
- objetos relevantes;
- decoração;
- temas/eventos aparentes;
- sinais visuais de esportes, Brasil/seleção/copa, festa,
  elegância, celebração, treinamento, etc., somente quando
  houver evidência visual;
- uma descrição visual rica para busca semântica;
- 8 a 15 frases/termos de busca que uma pessoa poderia usar.

Não identifique pessoas.

IMPORTANTE SOBRE CORES:
clothing_color_ratios deve usar nomes normalizados em inglês:
black, white, yellow, green, blue, red, pink, purple, orange,
gray, beige, brown. Os valores vão de 0 a 1 e representam a
proporção aproximada de pessoas cuja roupa contém aquela cor
de forma visualmente relevante. As proporções podem se
sobrepor quando uma roupa tem mais de uma cor.

Retorne SOMENTE JSON válido:

{
  "images": [
    {
      "index": 1,
      "people_count_visual": 7,
      "group_type": "small_group",
      "scene": "fitness studio",
      "activity": "group celebration",
      "pose": "posed group",
      "mood": ["joyful", "energetic"],
      "clothing_styles": ["sportswear", "team shirt"],
      "clothing_color_ratios": {
        "yellow": 0.85,
        "green": 0.30,
        "black": 0.10
      },
      "objects": ["TRX straps"],
      "decorations": [],
      "themes": ["fitness", "team", "brazil", "sports"],
      "visual_description": "descrição visual detalhada",
      "search_phrases": [
        "grupo de mulheres de amarelo",
        "foto com clima de seleção",
        "equipe comemorando"
      ]
    }
  ]
}
"""

    conteudo.append({
        "type": "input_text",
        "text": prompt,
    })

    for indice, item in enumerate(
        itens,
        start=1,
    ):
        conteudo.append({
            "type": "input_text",
            "text": (
                f"IMAGEM {indice}\n"
                f"Arquivo: "
                f"{item.get('filename', '')}"
            ),
        })

        imagem_b64 = imagem_para_base64(
            item[
                "_preview_path"
            ]
        )

        conteudo.append({
            "type": "input_image",
            "image_url": (
                "data:image/jpeg;base64,"
                + imagem_b64
            ),
            "detail": "low",
        })

    modelo = os.getenv(
        "PHOTO_INDEX_VISION_MODEL",
        "gpt-5.6-terra",
    )

    resposta = client.responses.create(
        model=modelo,
        reasoning={
            "effort": "low"
        },
        input=[
            {
                "role": "user",
                "content": conteudo,
            }
        ],
    )

    texto = (
        resposta.output_text
        .strip()
    )

    if texto.startswith(
        "```json"
    ):
        texto = texto[7:]

    if texto.startswith(
        "```"
    ):
        texto = texto[3:]

    if texto.endswith(
        "```"
    ):
        texto = texto[:-3]

    dados = extrair_json(texto)

    return dados.get(
        "images",
        []
    )


def construir_semantic_text(
    meta,
):
    partes = []

    for chave in [
        "group_type",
        "scene",
        "activity",
        "pose",
        "visual_description",
    ]:
        valor = meta.get(
            chave
        )

        if valor:
            partes.append(
                str(
                    valor
                )
            )

    for chave in [
        "mood",
        "clothing_styles",
        "objects",
        "decorations",
        "themes",
        "search_phrases",
    ]:
        valor = meta.get(
            chave
        )

        if isinstance(
            valor,
            list,
        ):
            partes.extend(
                str(
                    item
                )
                for item in valor
                if item
            )

    cores = meta.get(
        "clothing_color_ratios",
        {}
    )

    if isinstance(
        cores,
        dict,
    ):
        for cor, ratio in (
            cores.items()
        ):
            try:
                ratio_float = float(
                    ratio
                )
            except Exception:
                ratio_float = 0.0

            if ratio_float >= 0.20:
                partes.append(
                    f"clothing color {cor}"
                )

            if ratio_float >= 0.55:
                partes.append(
                    f"majority wearing {cor}"
                )

            if ratio_float >= 0.85:
                partes.append(
                    f"almost everyone wearing {cor}"
                )

    return " | ".join(
        partes
    )


# =========================================================
# EMBEDDING EM LOTE
# =========================================================

def embeddings_lote(
    textos,
):
    resposta = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=textos,
        dimensions=EMBEDDING_DIMENSIONS,
    )

    return [
        item.embedding
        for item in resposta.data
    ]


# =========================================================
# DB
# =========================================================

def buscar_pendentes(
    limite=None,
    force=False,
):
    ensure_photo_intelligence_schema()

    conn = sqlite3.connect(
        DB_FILE
    )

    conn.row_factory = (
        sqlite3.Row
    )

    try:
        if force:
            sql = """
                SELECT *
                FROM photos
                WHERE indexed = 1
                ORDER BY filename
            """
            params = ()

        else:
            sql = """
                SELECT *
                FROM photos
                WHERE
                    indexed = 1
                    AND (
                        visual_index_version IS NULL
                        OR visual_index_version != ?
                        OR visual_embedding IS NULL
                    )
                ORDER BY filename
            """
            params = (
                VISUAL_INDEX_VERSION,
            )

        if limite is not None:
            sql += " LIMIT ?"
            params = (
                *params,
                int(
                    limite
                ),
            )

        return [
            dict(
                row
            )
            for row in conn.execute(
                sql,
                params,
            ).fetchall()
        ]

    finally:
        conn.close()


def salvar_resultado(
    foto,
    meta,
    semantic_text,
    embedding,
):
    conn = sqlite3.connect(
        DB_FILE
    )

    try:
        people_visual = meta.get(
            "people_count_visual"
        )

        conn.execute("""
            UPDATE photos
            SET
                visual_description = ?,
                visual_semantic_text = ?,
                visual_data_json = ?,
                visual_embedding = ?,
                visual_embedding_dim = ?,
                visual_index_version = ?,
                visual_indexed_at = ?,
                preview_path = ?,
                people_count = CASE
                    WHEN people_count IS NULL
                         OR people_count = 0
                    THEN ?
                    ELSE people_count
                END
            WHERE drive_file_id = ?
        """, (
            meta.get(
                "visual_description",
                "",
            ),
            semantic_text,
            json.dumps(
                meta,
                ensure_ascii=False,
                sort_keys=True,
            ),
            embedding_para_blob(
                embedding
            ),
            EMBEDDING_DIMENSIONS,
            VISUAL_INDEX_VERSION,
            datetime.now().isoformat(
                timespec="seconds"
            ),
            foto.get(
                "_preview_path"
            ),
            people_visual,
            foto.get(
                "drive_file_id"
            ),
        ))

        conn.commit()

    finally:
        conn.close()


# =========================================================
# EXECUÇÃO
# =========================================================

def preparar_preview(
    foto,
):
    sufixo = (
        os.path.splitext(
            foto.get(
                "filename",
                "",
            )
        )[1]
        or ".jpg"
    )

    temp = (
        tempfile.NamedTemporaryFile(
            suffix=sufixo,
            delete=False,
        )
    )

    original = temp.name
    temp.close()

    try:
        baixar_arquivo(
            foto[
                "drive_file_id"
            ],
            original,
        )

        preview = criar_preview(
            original,
            foto[
                "drive_file_id"
            ],
        )

        foto[
            "_preview_path"
        ] = preview

    finally:
        if os.path.exists(
            original
        ):
            try:
                os.remove(
                    original
                )
            except Exception:
                pass


def indexar(
    limite=None,
    force=False,
    batch_size=4,
):
    fotos = buscar_pendentes(
        limite=limite,
        force=force,
    )

    total = len(
        fotos
    )

    print(
        f"Fotos para indexar: {total}",
        flush=True,
    )

    processadas = 0
    erros = 0

    for inicio in range(
        0,
        total,
        batch_size,
    ):
        lote = fotos[
            inicio:
            inicio + batch_size
        ]

        lote_preparado = []

        for foto in lote:
            try:
                preparar_preview(
                    foto
                )

                lote_preparado.append(
                    foto
                )

            except Exception as exc:
                erros += 1

                print(
                    "Erro preview:",
                    foto.get(
                        "filename"
                    ),
                    type(
                        exc
                    ).__name__,
                    str(
                        exc
                    ),
                    flush=True,
                )

        if not lote_preparado:
            continue

        try:
            metas = analisar_lote(
                lote_preparado
            )

            por_indice = {}

            for meta in metas:
                try:
                    indice = int(
                        meta.get(
                            "index"
                        )
                    )
                except Exception:
                    continue

                por_indice[
                    indice
                ] = meta

            semantic_texts = []

            metas_ordenadas = []

            fotos_ordenadas = []

            for indice, foto in enumerate(
                lote_preparado,
                start=1,
            ):
                meta = por_indice.get(
                    indice
                )

                if not meta:
                    raise RuntimeError(
                        "Resposta visual sem metadados "
                        f"para imagem {indice}."
                    )

                semantic_text = (
                    construir_semantic_text(
                        meta
                    )
                )

                semantic_texts.append(
                    semantic_text
                )

                metas_ordenadas.append(
                    meta
                )

                fotos_ordenadas.append(
                    foto
                )

            embeddings = embeddings_lote(
                semantic_texts
            )

            for (
                foto,
                meta,
                semantic_text,
                embedding,
            ) in zip(
                fotos_ordenadas,
                metas_ordenadas,
                semantic_texts,
                embeddings,
            ):
                salvar_resultado(
                    foto,
                    meta,
                    semantic_text,
                    embedding,
                )

                processadas += 1

                print(
                    f"✅ {processadas}/{total} "
                    f"{foto.get('filename')}",
                    flush=True,
                )

        except Exception as exc:
            erros += len(
                lote_preparado
            )

            print(
                "Erro lote:",
                type(
                    exc
                ).__name__,
                str(
                    exc
                ),
                flush=True,
            )

    print(
        "Indexação finalizada.",
        flush=True,
    )

    print(
        f"Processadas: {processadas}",
        flush=True,
    )

    print(
        f"Erros: {erros}",
        flush=True,
    )


def mostrar_status():
    ensure_photo_intelligence_schema()

    conn = sqlite3.connect(
        DB_FILE
    )

    try:
        total = conn.execute("""
            SELECT COUNT(*)
            FROM photos
            WHERE indexed = 1
        """).fetchone()[0]

        prontos = conn.execute("""
            SELECT COUNT(*)
            FROM photos
            WHERE
                indexed = 1
                AND visual_index_version = ?
                AND visual_embedding IS NOT NULL
        """, (
            VISUAL_INDEX_VERSION,
        )).fetchone()[0]

        print(
            f"Total indexado no catálogo: {total}"
        )

        print(
            f"Photo Intelligence v{VISUAL_INDEX_VERSION}: "
            f"{prontos}/{total}"
        )

        print(
            f"Restantes: {max(0, total - prontos)}"
        )

    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=4,
    )

    parser.add_argument(
        "--force",
        action="store_true",
    )

    parser.add_argument(
        "--status",
        action="store_true",
    )

    args = parser.parse_args()

    if args.status:
        mostrar_status()

    else:
        indexar(
            limite=args.limit,
            force=args.force,
            batch_size=max(
                1,
                min(
                    8,
                    args.batch_size,
                ),
            ),
        )
