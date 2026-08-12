import os
import json
import base64
import sqlite3
import tempfile
import unicodedata

from PIL import Image
from pillow_heif import register_heif_opener

from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from openai_client import client, extrair_json


register_heif_opener()


DB_FILE = "/app/data/creative_agent.db"

OAUTH_TOKEN_FILE = (
    "/app/secrets/google_token.json"
)

SERVICE_ACCOUNT_FILE = (
    "/app/secrets/google.json"
)

ROOT_FOLDER_ID = os.getenv(
    "CAMPAIGN_REFERENCES_FOLDER_ID",
    "1hmoTKN8c4zqmXneNqvoOIsCFznE3acot",
)


# =========================================================
# BANCO
# =========================================================

def conectar_db():
    conn = sqlite3.connect(
        DB_FILE
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS campaign_references (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            drive_file_id TEXT UNIQUE NOT NULL,
            filename TEXT NOT NULL,

            folder_id TEXT,
            folder_name TEXT,
            folder_path TEXT,

            campaign_type TEXT,

            description TEXT,
            visual_style TEXT,

            photo_ratio TEXT,
            photo_treatment TEXT,

            text_density TEXT,
            headline_position TEXT,
            headline_alignment TEXT,

            dominant_colors TEXT,

            background_shape TEXT,
            graphic_elements TEXT,

            date_emphasis INTEGER DEFAULT 0,
            partner_logo INTEGER DEFAULT 0,
            logo_position TEXT,

            composition_notes TEXT,
            reusable_rules TEXT,

            brand_fit_score REAL,
            reference_quality_score REAL,

            width INTEGER,
            height INTEGER,
            orientation TEXT,

            analysis_json TEXT,

            indexed INTEGER DEFAULT 0,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_campaign_references_campaign_type
        ON campaign_references (
            campaign_type
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_campaign_references_folder
        ON campaign_references (
            folder_name
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_campaign_references_indexed
        ON campaign_references (
            indexed
        )
    """)

    conn.commit()

    return conn


# =========================================================
# GOOGLE DRIVE
# =========================================================

def google_service():
    credentials = None

    # -----------------------------------------------------
    # OAUTH
    # -----------------------------------------------------
    #
    # O token já contém os scopes autorizados.
    #
    # Não informamos novos scopes aqui.
    #
    # IMPORTANTE:
    # /app/secrets está montado como read-only.
    # Portanto, renovamos o access token apenas em memória.
    # Não tentamos gravar google_token.json.
    # -----------------------------------------------------

    if os.path.exists(
        OAUTH_TOKEN_FILE
    ):
        credentials = (
            Credentials
            .from_authorized_user_file(
                OAUTH_TOKEN_FILE
            )
        )

        print(
            "Google Drive autenticado via OAuth",
            flush=True,
        )

        print(
            "Scopes OAuth:",
            credentials.scopes,
            flush=True,
        )

        if (
            credentials.expired
            and credentials.refresh_token
        ):
            print(
                "Atualizando token OAuth em memória...",
                flush=True,
            )

            credentials.refresh(
                Request()
            )

            print(
                "✅ Token OAuth atualizado em memória.",
                flush=True,
            )

        if not credentials.valid:
            raise RuntimeError(
                "Credencial OAuth Google inválida."
            )

    # -----------------------------------------------------
    # SERVICE ACCOUNT - FALLBACK
    # -----------------------------------------------------

    elif os.path.exists(
        SERVICE_ACCOUNT_FILE
    ):
        credentials = (
            service_account
            .Credentials
            .from_service_account_file(
                SERVICE_ACCOUNT_FILE,
                scopes=[
                    "https://www.googleapis.com/auth/drive.readonly"
                ],
            )
        )

        print(
            "Google Drive autenticado via Service Account",
            flush=True,
        )

    else:
        raise RuntimeError(
            "Nenhuma credencial Google encontrada."
        )

    return build(
        "drive",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )


# =========================================================
# DRIVE - LISTAGEM
# =========================================================

def listar_filhos(
    service,
    folder_id,
):
    itens = []

    page_token = None

    while True:
        response = (
            service.files()
            .list(
                q=(
                    f"'{folder_id}' in parents "
                    "and trashed = false"
                ),
                spaces="drive",
                fields=(
                    "nextPageToken,"
                    "files("
                    "id,"
                    "name,"
                    "mimeType,"
                    "parents,"
                    "createdTime,"
                    "modifiedTime"
                    ")"
                ),
                pageSize=1000,
                pageToken=page_token,
            )
            .execute()
        )

        itens.extend(
            response.get(
                "files",
                [],
            )
        )

        page_token = (
            response.get(
                "nextPageToken"
            )
        )

        if not page_token:
            break

    return itens


def extensao_imagem(
    nome,
):
    extensao = (
        os.path.splitext(
            nome
        )[1]
        .lower()
    )

    return extensao in {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".heic",
        ".heif",
    }


def varrer_recursivamente(
    service,
    folder_id,
    caminho="",
):
    resultados = []

    itens = listar_filhos(
        service,
        folder_id,
    )

    for item in itens:
        nome = item[
            "name"
        ]

        mime = item[
            "mimeType"
        ]

        if (
            mime
            == "application/vnd.google-apps.folder"
        ):
            novo_caminho = (
                f"{caminho}/{nome}"
                if caminho
                else nome
            )

            resultados.extend(
                varrer_recursivamente(
                    service,
                    item[
                        "id"
                    ],
                    novo_caminho,
                )
            )

            continue

        if (
            mime.startswith(
                "image/"
            )
            or extensao_imagem(
                nome
            )
        ):
            item[
                "folder_path"
            ] = caminho

            item[
                "folder_name"
            ] = (
                caminho.split("/")[-1]
                if caminho
                else ""
            )

            item[
                "folder_id"
            ] = folder_id

            resultados.append(
                item
            )

    return resultados


def baixar_drive(
    service,
    file_id,
    destino,
):
    request = (
        service.files()
        .get_media(
            fileId=file_id
        )
    )

    with open(
        destino,
        "wb",
    ) as arquivo:
        downloader = (
            MediaIoBaseDownload(
                arquivo,
                request,
            )
        )

        done = False

        while not done:
            _, done = (
                downloader.next_chunk()
            )


# =========================================================
# CLASSIFICAÇÃO DA PASTA
# =========================================================

def normalizar(
    texto,
):
    texto = (
        texto
        or ""
    ).strip()

    texto = unicodedata.normalize(
        "NFKD",
        texto,
    )

    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(
            caractere
        )
    )

    return texto.lower()


def inferir_campaign_type(
    folder_path,
):
    texto = normalizar(
        folder_path
    )

    if (
        "circuito slim"
        in texto
    ):
        return "CIRCUITO_SLIM"

    if (
        "atividade fisica"
        in texto
    ):
        return "ATIVIDADE_FISICA"

    if (
        "dia mundial da saude"
        in texto
        or "saude"
        in texto
    ):
        return "SAUDE"

    if (
        "dia das maes"
        in texto
    ):
        return "DIA_DAS_MAES"

    if (
        "copa slim"
        in texto
    ):
        return "COPA_SLIM"

    if (
        "pascoa"
        in texto
    ):
        return "PASCOA"

    if (
        "outubro rosa"
        in texto
    ):
        return "OUTUBRO_ROSA"

    if (
        "dia das mulheres"
        in texto
        or "dia da mulher"
        in texto
    ):
        return "DIA_DA_MULHER"

    return "OUTROS"


# =========================================================
# PREVIEW
# =========================================================

def preparar_preview(
    caminho_original,
):
    imagem = Image.open(
        caminho_original
    ).convert("RGB")

    width, height = (
        imagem.size
    )

    if height > width:
        orientation = (
            "portrait"
        )

    elif width > height:
        orientation = (
            "landscape"
        )

    else:
        orientation = (
            "square"
        )

    dimensoes = {
        "width": width,
        "height": height,
        "orientation": orientation,
    }

    max_dimension = 1400

    if max(
        width,
        height,
    ) > max_dimension:
        escala = (
            max_dimension
            / max(
                width,
                height,
            )
        )

        imagem = imagem.resize(
            (
                int(
                    width
                    * escala
                ),
                int(
                    height
                    * escala
                ),
            ),
            Image.Resampling.LANCZOS,
        )

    temp = (
        tempfile.NamedTemporaryFile(
            suffix=".jpg",
            delete=False,
        )
    )

    caminho_preview = (
        temp.name
    )

    temp.close()

    imagem.save(
        caminho_preview,
        "JPEG",
        quality=82,
        optimize=True,
    )

    return (
        caminho_preview,
        dimensoes,
    )


def base64_image(
    caminho,
):
    with open(
        caminho,
        "rb",
    ) as arquivo:
        return (
            base64
            .b64encode(
                arquivo.read()
            )
            .decode(
                "utf-8"
            )
        )


# =========================================================
# ANÁLISE VISUAL
# =========================================================

def analisar_referencia(
    caminho_preview,
    filename,
    folder_path,
    campaign_type,
):
    imagem_b64 = base64_image(
        caminho_preview
    )

    prompt = f"""
Você é Diretor de Arte e analista da identidade visual
da SlimFit Studio.

A imagem fornecida NÃO é uma fotografia para reutilização.

Ela é uma REFERÊNCIA VISUAL de uma campanha SlimFit.

Nosso objetivo é aprender a arquitetura da peça para
alimentar um sistema determinístico de composição.

Arquivo:
{filename}

Pasta:
{folder_path}

Tipo de campanha:
{campaign_type}

PALETA OFICIAL SLIMFIT:

Tiffany #11ACB0
Coral #F37A73
Dark Silver #707071
Charcoal #2F2B30
Branco e off-white

Analise:

1. proporção aproximada dedicada à fotografia;
2. tratamento da fotografia;
3. posição da headline;
4. alinhamento;
5. densidade de texto;
6. cores dominantes;
7. formato da massa gráfica;
8. curvas, linhas, ondas, faixas e outros grafismos;
9. importância visual da data;
10. presença de logos adicionais/parceiros;
11. posição do logo principal;
12. organização da composição;
13. regras visuais reutilizáveis;
14. qualidade da referência;
15. aderência à marca.

Não identifique pessoas.
Não descreva rostos.
Não sugira recriar pessoas.
Não tente copiar literalmente a arte.

Retorne SOMENTE JSON válido:

{{
  "description": "resumo objetivo",

  "visual_style":
    "editorial|emotional|institutional|energetic|minimal|promotional|event|other",

  "photo_ratio":
    "none|low|medium|high|dominant",

  "photo_treatment":
    "full_bleed|cropped|masked|overlay|gradient|split|background|other",

  "text_density":
    "low|medium|high",

  "headline_position":
    "top_left|top_center|top_right|center_left|center|center_right|bottom_left|bottom_center|bottom_right|mixed",

  "headline_alignment":
    "left|center|right|mixed",

  "dominant_colors": [],

  "background_shape":
    "none|rectangle|rounded_rectangle|wave|curve|diagonal|gradient|bands|mixed|other",

  "graphic_elements": [],

  "date_emphasis": true,

  "partner_logo": false,

  "logo_position":
    "top_left|top_center|top_right|bottom_left|bottom_center|bottom_right|other|unknown",

  "composition_notes":
    "descrição da estrutura",

  "reusable_rules": [
    "regra 1",
    "regra 2",
    "regra 3"
  ],

  "brand_fit_score": 0.0,

  "reference_quality_score": 0.0
}}

Os scores devem ficar entre 0 e 10.
"""

    response = (
        client.responses.create(
            model="gpt-5.6-terra",
            reasoning={
                "effort": "low",
            },
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
                                + imagem_b64
                            ),
                        },
                    ],
                }
            ],
        )
    )

    resposta = (
        response.output_text
        .strip()
    )

    if resposta.startswith(
        "```json"
    ):
        resposta = (
            resposta[7:]
        )

    elif resposta.startswith(
        "```"
    ):
        resposta = (
            resposta[3:]
        )

    if resposta.endswith(
        "```"
    ):
        resposta = (
            resposta[:-3]
        )

    return extrair_json(resposta)


# =========================================================
# SALVAR
# =========================================================

def salvar_referencia(
    conn,
    item,
    campaign_type,
    dimensoes,
    analise,
):
    dominant_colors = (
        json.dumps(
            analise.get(
                "dominant_colors",
                [],
            ),
            ensure_ascii=False,
        )
    )

    graphic_elements = (
        json.dumps(
            analise.get(
                "graphic_elements",
                [],
            ),
            ensure_ascii=False,
        )
    )

    reusable_rules = (
        json.dumps(
            analise.get(
                "reusable_rules",
                [],
            ),
            ensure_ascii=False,
        )
    )

    analysis_json = (
        json.dumps(
            analise,
            ensure_ascii=False,
        )
    )

    conn.execute("""
        INSERT INTO campaign_references (
            drive_file_id,
            filename,

            folder_id,
            folder_name,
            folder_path,

            campaign_type,

            description,
            visual_style,

            photo_ratio,
            photo_treatment,

            text_density,
            headline_position,
            headline_alignment,

            dominant_colors,

            background_shape,
            graphic_elements,

            date_emphasis,
            partner_logo,
            logo_position,

            composition_notes,
            reusable_rules,

            brand_fit_score,
            reference_quality_score,

            width,
            height,
            orientation,

            analysis_json,

            indexed,
            updated_at
        )
        VALUES (
            ?, ?,
            ?, ?, ?,
            ?,
            ?, ?,
            ?, ?,
            ?, ?, ?,
            ?,
            ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?,
            ?, ?, ?,
            ?,
            1,
            CURRENT_TIMESTAMP
        )

        ON CONFLICT(drive_file_id)
        DO UPDATE SET

            filename =
                excluded.filename,

            folder_id =
                excluded.folder_id,

            folder_name =
                excluded.folder_name,

            folder_path =
                excluded.folder_path,

            campaign_type =
                excluded.campaign_type,

            description =
                excluded.description,

            visual_style =
                excluded.visual_style,

            photo_ratio =
                excluded.photo_ratio,

            photo_treatment =
                excluded.photo_treatment,

            text_density =
                excluded.text_density,

            headline_position =
                excluded.headline_position,

            headline_alignment =
                excluded.headline_alignment,

            dominant_colors =
                excluded.dominant_colors,

            background_shape =
                excluded.background_shape,

            graphic_elements =
                excluded.graphic_elements,

            date_emphasis =
                excluded.date_emphasis,

            partner_logo =
                excluded.partner_logo,

            logo_position =
                excluded.logo_position,

            composition_notes =
                excluded.composition_notes,

            reusable_rules =
                excluded.reusable_rules,

            brand_fit_score =
                excluded.brand_fit_score,

            reference_quality_score =
                excluded.reference_quality_score,

            width =
                excluded.width,

            height =
                excluded.height,

            orientation =
                excluded.orientation,

            analysis_json =
                excluded.analysis_json,

            indexed = 1,

            updated_at =
                CURRENT_TIMESTAMP
    """, (
        item[
            "id"
        ],

        item[
            "name"
        ],

        item.get(
            "folder_id"
        ),

        item.get(
            "folder_name"
        ),

        item.get(
            "folder_path"
        ),

        campaign_type,

        analise.get(
            "description"
        ),

        analise.get(
            "visual_style"
        ),

        analise.get(
            "photo_ratio"
        ),

        analise.get(
            "photo_treatment"
        ),

        analise.get(
            "text_density"
        ),

        analise.get(
            "headline_position"
        ),

        analise.get(
            "headline_alignment"
        ),

        dominant_colors,

        analise.get(
            "background_shape"
        ),

        graphic_elements,

        1
        if analise.get(
            "date_emphasis"
        )
        else 0,

        1
        if analise.get(
            "partner_logo"
        )
        else 0,

        analise.get(
            "logo_position"
        ),

        analise.get(
            "composition_notes"
        ),

        reusable_rules,

        analise.get(
            "brand_fit_score"
        ),

        analise.get(
            "reference_quality_score"
        ),

        dimensoes[
            "width"
        ],

        dimensoes[
            "height"
        ],

        dimensoes[
            "orientation"
        ],

        analysis_json,
    ))

    conn.commit()


# =========================================================
# INDEXAÇÃO
# =========================================================

def referencias_ja_indexadas(
    conn,
):
    rows = conn.execute("""
        SELECT drive_file_id
        FROM campaign_references
        WHERE indexed = 1
    """).fetchall()

    return {
        row[0]
        for row in rows
    }


def indexar_referencias(
    limite=20,
    reanalisar=False,
):
    service = (
        google_service()
    )

    conn = conectar_db()

    print(
        "",
        flush=True,
    )

    print(
        "🔎 Varrendo referências sazonais...",
        flush=True,
    )

    arquivos = (
        varrer_recursivamente(
            service,
            ROOT_FOLDER_ID,
        )
    )

    print(
        f"🖼 Referências encontradas: "
        f"{len(arquivos)}",
        flush=True,
    )

    indexadas = (
        set()
        if reanalisar
        else referencias_ja_indexadas(
            conn
        )
    )

    pendentes_total = [
        item
        for item in arquivos
        if item[
            "id"
        ] not in indexadas
    ]

    print(
        f"✅ Já indexadas: "
        f"{len(arquivos) - len(pendentes_total)}",
        flush=True,
    )

    print(
        f"⏳ Pendentes: "
        f"{len(pendentes_total)}",
        flush=True,
    )

    pendentes = (
        pendentes_total
    )

    if limite:
        pendentes = (
            pendentes[
                :limite
            ]
        )

    if not pendentes:
        print(
            "",
            flush=True,
        )

        print(
            "✅ Nenhuma nova referência para indexar.",
            flush=True,
        )

        conn.close()

        return {
            "found": len(
                arquivos
            ),
            "processed": 0,
            "errors": 0,
            "pending": 0,
        }

    processadas = 0
    erros = 0

    for indice, item in enumerate(
        pendentes,
        start=1,
    ):
        original = None
        preview = None

        try:
            print(
                "",
                flush=True,
            )

            print(
                f"[{indice}/{len(pendentes)}] "
                f"{item['folder_path']} / "
                f"{item['name']}",
                flush=True,
            )

            extensao = (
                os.path.splitext(
                    item[
                        "name"
                    ]
                )[1]
                or ".jpg"
            )

            temp = (
                tempfile.NamedTemporaryFile(
                    suffix=extensao,
                    delete=False,
                )
            )

            original = (
                temp.name
            )

            temp.close()

            baixar_drive(
                service,
                item[
                    "id"
                ],
                original,
            )

            (
                preview,
                dimensoes,
            ) = preparar_preview(
                original
            )

            campaign_type = (
                inferir_campaign_type(
                    item[
                        "folder_path"
                    ]
                )
            )

            print(
                f"   Campanha: "
                f"{campaign_type}",
                flush=True,
            )

            analise = (
                analisar_referencia(
                    preview,
                    item[
                        "name"
                    ],
                    item[
                        "folder_path"
                    ],
                    campaign_type,
                )
            )

            salvar_referencia(
                conn,
                item,
                campaign_type,
                dimensoes,
                analise,
            )

            processadas += 1

            print(
                f"   ✅ "
                f"{analise.get('visual_style')} | "
                f"foto={analise.get('photo_ratio')} | "
                f"fundo={analise.get('background_shape')} | "
                f"qualidade="
                f"{analise.get('reference_quality_score')} | "
                f"marca="
                f"{analise.get('brand_fit_score')}",
                flush=True,
            )

        except Exception as erro:
            erros += 1

            print(
                "   ❌",
                type(
                    erro
                ).__name__,
                str(
                    erro
                ),
                flush=True,
            )

        finally:
            for caminho in [
                original,
                preview,
            ]:
                if (
                    caminho
                    and os.path.exists(
                        caminho
                    )
                ):
                    try:
                        os.remove(
                            caminho
                        )
                    except Exception:
                        pass

    conn.close()

    restantes = (
        len(
            pendentes_total
        )
        - processadas
    )

    print(
        "",
        flush=True,
    )

    print(
        "======================================",
        flush=True,
    )

    print(
        "INDEXAÇÃO DE REFERÊNCIAS CONCLUÍDA",
        flush=True,
    )

    print(
        f"✅ Processadas: "
        f"{processadas}",
        flush=True,
    )

    print(
        f"❌ Erros: "
        f"{erros}",
        flush=True,
    )

    print(
        f"⏳ Ainda pendentes: "
        f"{max(0, restantes)}",
        flush=True,
    )

    print(
        "======================================",
        flush=True,
    )

    return {
        "found": len(
            arquivos
        ),
        "processed": (
            processadas
        ),
        "errors": erros,
        "pending": max(
            0,
            restantes,
        ),
    }


# =========================================================
# CLI
# =========================================================

if __name__ == "__main__":
    import argparse

    parser = (
        argparse.ArgumentParser()
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=20,
    )

    parser.add_argument(
        "--reanalyze",
        action="store_true",
    )

    args = (
        parser.parse_args()
    )

    indexar_referencias(
        limite=args.limit,
        reanalisar=args.reanalyze,
    )
