import os
import json
import sqlite3
import tempfile
import base64

from PIL import Image
from pillow_heif import register_heif_opener

register_heif_opener()

from drive_client import baixar_arquivo
from openai_client import client
from photo_manager import gerar_inventario_fotos


DB_FILE = "/app/data/creative_agent.db"


def get_db():
    conn = sqlite3.connect(DB_FILE)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS photos (
            drive_file_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            folder TEXT,
            mime_type TEXT,
            indexed INTEGER DEFAULT 0,
            description TEXT,
            tags TEXT,
            orientation TEXT,
            people_count INTEGER,
            text_space TEXT,
            quality_score REAL,
            brand_fit_score REAL
        )
    """)

    conn.commit()
    return conn


def flatten_images(node):
    imagens = list(node.get("images", []))

    for pasta in node.get("folders", []):
        imagens.extend(flatten_images(pasta))

    return imagens


def sincronizar_inventario():
    inventario = gerar_inventario_fotos()
    imagens = flatten_images(inventario)

    conn = get_db()

    for imagem in imagens:
        conn.execute("""
            INSERT OR IGNORE INTO photos (
                drive_file_id,
                filename,
                folder,
                mime_type
            )
            VALUES (?, ?, ?, ?)
        """, (
            imagem["id"],
            imagem["name"],
            imagem.get("path"),
            imagem.get("mimeType"),
        ))

    conn.commit()
    conn.close()

    return len(imagens)


def criar_preview(caminho_original):
    imagem = Image.open(caminho_original)
    imagem = imagem.convert("RGB")

    largura, altura = imagem.size

    max_dim = 1200

    if max(largura, altura) > max_dim:
        proporcao = max_dim / max(largura, altura)

        novo_tamanho = (
            int(largura * proporcao),
            int(altura * proporcao),
        )

        imagem = imagem.resize(novo_tamanho)

    temp = tempfile.NamedTemporaryFile(
        suffix=".jpg",
        delete=False,
    )

    caminho_preview = temp.name
    temp.close()

    imagem.save(
        caminho_preview,
        format="JPEG",
        quality=82,
        optimize=True,
    )

    return caminho_preview


def analisar_foto(caminho_preview, filename, folder):
    with open(caminho_preview, "rb") as arquivo:
        imagem_base64 = base64.b64encode(
            arquivo.read()
        ).decode("utf-8")

    prompt = f"""
Analise esta fotografia como curador visual
da marca SlimFit Studio.

Arquivo:
{filename}

Pasta de origem:
{folder}

Sua função é avaliar se esta foto é útil para
criativos de Instagram.

Retorne SOMENTE JSON válido nesta estrutura:

{{
  "description": "descrição objetiva da fotografia",
  "tags": [
    "tag1",
    "tag2"
  ],
  "orientation": "vertical|horizontal|quadrada",
  "people_count": 0,
  "text_space": "superior|inferior|esquerda|direita|centro|nenhum",
  "quality_score": 0,
  "brand_fit_score": 0
}}

Regras:

- quality_score deve ser de 0 a 10.
- brand_fit_score deve ser de 0 a 10.
- considere iluminação, enquadramento,
  nitidez, composição e utilidade para publicidade.
- considere aderência à marca SlimFit Studio:
  mulheres reais, treino, energia, elegância,
  boa postura, ambiente profissional e ausência
  de marcas concorrentes em destaque.
- não identifique pessoas pelo nome.
- não invente informações que não sejam visíveis.
"""

    response = client.responses.create(
        model="gpt-5.6-terra",
        reasoning={"effort": "low"},
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": prompt,
                    },
                    {
                        "type": "input_image",
                        "image_url": (
                            "data:image/jpeg;base64,"
                            + imagem_base64
                        ),
                    },
                ],
            }
        ],
    )

    resposta = response.output_text.strip()

    if resposta.startswith("```json"):
        resposta = resposta[7:]

    if resposta.startswith("```"):
        resposta = resposta[3:]

    if resposta.endswith("```"):
        resposta = resposta[:-3]

    return json.loads(resposta.strip())


def indexar_fotos(limite=5):
    sincronizar_inventario()

    conn = get_db()

    cursor = conn.execute("""
        SELECT
            drive_file_id,
            filename,
            folder
        FROM photos
        WHERE indexed = 0
        ORDER BY folder, filename
        LIMIT ?
    """, (limite,))

    fotos = cursor.fetchall()

    if not fotos:
        print("Nenhuma foto pendente de indexação.")
        conn.close()
        return

    print(
        f"Fotos a indexar neste lote: {len(fotos)}",
        flush=True,
    )

    for indice, foto in enumerate(fotos, start=1):
        file_id, filename, folder = foto

        print(
            f"[{indice}/{len(fotos)}] {folder}/{filename}",
            flush=True,
        )

        temp_original = tempfile.NamedTemporaryFile(
            suffix=os.path.splitext(filename)[1] or ".jpg",
            delete=False,
        )

        caminho_original = temp_original.name
        temp_original.close()

        caminho_preview = None

        try:
            baixar_arquivo(
                file_id,
                caminho_original,
            )

            caminho_preview = criar_preview(
                caminho_original,
            )

            analise = analisar_foto(
                caminho_preview,
                filename,
                folder,
            )

            conn.execute("""
                UPDATE photos
                SET
                    indexed = 1,
                    description = ?,
                    tags = ?,
                    orientation = ?,
                    people_count = ?,
                    text_space = ?,
                    quality_score = ?,
                    brand_fit_score = ?
                WHERE drive_file_id = ?
            """, (
                analise.get("description"),
                json.dumps(
                    analise.get("tags", []),
                    ensure_ascii=False,
                ),
                analise.get("orientation"),
                analise.get("people_count"),
                analise.get("text_space"),
                analise.get("quality_score"),
                analise.get("brand_fit_score"),
                file_id,
            ))

            conn.commit()

            print(
                f"  OK | qualidade={analise.get('quality_score')} "
                f"| marca={analise.get('brand_fit_score')}",
                flush=True,
            )

        except Exception as e:
            print(
                f"  ERRO: {e}",
                flush=True,
            )

        finally:
            if os.path.exists(caminho_original):
                os.remove(caminho_original)

            if (
                caminho_preview
                and os.path.exists(caminho_preview)
            ):
                os.remove(caminho_preview)

    conn.close()
