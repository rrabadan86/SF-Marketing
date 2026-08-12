import json
import math
import re
import sqlite3
import struct
import unicodedata

from openai_client import client


DB_FILE = "/app/data/creative_agent.db"

VISUAL_INDEX_VERSION = 2
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 256


# =========================================================
# SCHEMA
# =========================================================

def ensure_photo_intelligence_schema():
    conn = sqlite3.connect(
        DB_FILE
    )

    try:
        existentes = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(photos)"
            ).fetchall()
        }

        novas_colunas = {
            "visual_description": "TEXT",
            "visual_semantic_text": "TEXT",
            "visual_data_json": "TEXT",
            "visual_embedding": "BLOB",
            "visual_embedding_dim": "INTEGER",
            "visual_index_version": "INTEGER",
            "visual_indexed_at": "TEXT",
            "preview_path": "TEXT",
        }

        for nome, tipo in novas_colunas.items():
            if nome not in existentes:
                conn.execute(
                    f"""
                    ALTER TABLE photos
                    ADD COLUMN {nome} {tipo}
                    """
                )

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_photos_visual_index_version
            ON photos(
                visual_index_version
            )
        """)

        conn.commit()

    finally:
        conn.close()


# =========================================================
# EMBEDDINGS
# =========================================================

def embedding_para_blob(
    valores,
):
    valores = [
        float(
            valor
        )
        for valor in valores
    ]

    return struct.pack(
        f"<{len(valores)}f",
        *valores,
    )


def blob_para_embedding(
    blob,
    dimensao,
):
    if (
        not blob
        or not dimensao
    ):
        return None

    try:
        return list(
            struct.unpack(
                f"<{int(dimensao)}f",
                blob,
            )
        )

    except Exception:
        return None


def obter_embedding(
    texto,
):
    texto = (
        texto
        or ""
    ).strip()

    if not texto:
        return None

    resposta = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texto,
        dimensions=EMBEDDING_DIMENSIONS,
    )

    return resposta.data[
        0
    ].embedding


def similaridade_cosseno(
    a,
    b,
):
    if (
        not a
        or not b
        or len(
            a
        ) != len(
            b
        )
    ):
        return 0.0

    produto = 0.0
    norma_a = 0.0
    norma_b = 0.0

    for x, y in zip(
        a,
        b,
    ):
        produto += (
            x
            * y
        )

        norma_a += (
            x
            * x
        )

        norma_b += (
            y
            * y
        )

    if (
        norma_a <= 0
        or norma_b <= 0
    ):
        return 0.0

    return (
        produto
        / math.sqrt(
            norma_a
            * norma_b
        )
    )


# =========================================================
# NORMALIZAÇÃO
# =========================================================

def normalizar_texto(
    texto,
):
    texto = (
        texto
        or ""
    ).lower()

    texto = unicodedata.normalize(
        "NFD",
        texto,
    )

    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(
            caractere
        ) != "Mn"
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto,
    )

    return texto.strip()


MAPA_CORES = {
    "preto": "black",
    "preta": "black",
    "pretas": "black",
    "pretos": "black",
    "black": "black",

    "amarelo": "yellow",
    "amarela": "yellow",
    "amarelas": "yellow",
    "amarelos": "yellow",
    "yellow": "yellow",

    "branco": "white",
    "branca": "white",
    "brancas": "white",
    "brancos": "white",
    "white": "white",

    "verde": "green",
    "verdes": "green",
    "green": "green",

    "azul": "blue",
    "azuis": "blue",
    "blue": "blue",

    "vermelho": "red",
    "vermelha": "red",
    "vermelhas": "red",
    "vermelhos": "red",
    "red": "red",

    "rosa": "pink",
    "pink": "pink",

    "roxo": "purple",
    "roxa": "purple",
    "purple": "purple",

    "laranja": "orange",
    "orange": "orange",

    "cinza": "gray",
    "gray": "gray",
    "grey": "gray",

    "bege": "beige",
    "beige": "beige",

    "marrom": "brown",
    "brown": "brown",
}


def interpretar_filtros_locais(
    consulta,
):
    """
    Extrai apenas regras objetivas e muito seguras.
    Todo o restante continua sendo resolvido semanticamente.

    Assim não precisamos prever "festa junina", "elegante",
    "com balões", "com flores", etc.
    """

    texto = normalizar_texto(
        consulta
    )

    cor = None

    for termo, cor_normalizada in (
        MAPA_CORES.items()
    ):
        if re.search(
            r"\b"
            + re.escape(
                termo
            )
            + r"\b",
            texto,
        ):
            cor = cor_normalizada
            break

    min_ratio = None

    if cor:
        if any(
            frase in texto
            for frase in [
                "todas de ",
                "todos de ",
                "todas as mulheres de ",
                "todo mundo de ",
                "100%",
            ]
        ):
            min_ratio = 0.88

        elif any(
            frase in texto
            for frase in [
                "quase todas",
                "quase a totalidade",
                "grande maioria",
            ]
        ):
            min_ratio = 0.72

        elif any(
            frase in texto
            for frase in [
                "maioria",
                "predominantemente",
                "predominio",
            ]
        ):
            min_ratio = 0.55

        elif any(
            frase in texto
            for frase in [
                "varias",
                "várias",
            ]
        ):
            min_ratio = 0.25

    min_people = None

    if any(
        termo in texto
        for termo in [
            "grupo",
            "varias mulheres",
            "várias mulheres",
            "muitas mulheres",
        ]
    ):
        min_people = 3

    return {
        "preferred_color": cor,
        "min_color_ratio": min_ratio,
        "min_people_count": min_people,
    }


# =========================================================
# VISUAL DATA
# =========================================================

def carregar_visual_data(
    valor,
):
    if not valor:
        return {}

    try:
        return json.loads(
            valor
        )

    except Exception:
        return {}


def color_ratio(
    visual_data,
    color_name,
):
    if not color_name:
        return 0.0

    ratios = visual_data.get(
        "clothing_color_ratios",
        {},
    )

    if not isinstance(
        ratios,
        dict,
    ):
        return 0.0

    try:
        return float(
            ratios.get(
                color_name,
                0,
            )
            or 0
        )

    except Exception:
        return 0.0


def photo_intelligence_status():
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

        return {
            "total": int(
                total
            ),
            "ready": int(
                prontos
            ),
            "remaining": int(
                max(
                    0,
                    total - prontos,
                )
            ),
        }

    finally:
        conn.close()


# =========================================================
# SHORTLIST INTELIGENTE
# =========================================================

def buscar_candidatos_inteligentes(
    consulta,
    limite=12,
    excluir_ids=None,
):
    """
    Busca sem baixar nenhuma imagem.

    Passos:
    1. embedding do pedido;
    2. similaridade com metadados visuais pré-indexados;
    3. bônus/filtro estruturado quando o pedido contém algo
       objetivo, como cor predominante;
    4. retorna apenas uma shortlist pequena para visão final.
    """

    ensure_photo_intelligence_schema()

    excluir_ids = set(
        excluir_ids
        or []
    )

    consulta_embedding = obter_embedding(
        consulta
    )

    filtros = interpretar_filtros_locais(
        consulta
    )

    conn = sqlite3.connect(
        DB_FILE
    )

    conn.row_factory = (
        sqlite3.Row
    )

    try:
        rows = conn.execute("""
            SELECT
                drive_file_id,
                filename,
                folder,
                description,
                tags,
                orientation,
                people_count,
                text_space,
                quality_score,
                brand_fit_score,
                visual_description,
                visual_semantic_text,
                visual_data_json,
                visual_embedding,
                visual_embedding_dim,
                preview_path
            FROM photos
            WHERE
                indexed = 1
                AND visual_index_version = ?
                AND visual_embedding IS NOT NULL
        """, (
            VISUAL_INDEX_VERSION,
        )).fetchall()

    finally:
        conn.close()

    resultados = []

    for row in rows:
        foto = dict(
            row
        )

        drive_id = foto.get(
            "drive_file_id"
        )

        if (
            not drive_id
            or drive_id in excluir_ids
        ):
            continue

        try:
            pessoas = int(
                foto.get(
                    "people_count"
                )
                or 0
            )

        except Exception:
            pessoas = 0

        min_people = filtros.get(
            "min_people_count"
        )

        if (
            min_people is not None
            and pessoas < min_people
        ):
            continue

        embedding_foto = (
            blob_para_embedding(
                foto.get(
                    "visual_embedding"
                ),
                foto.get(
                    "visual_embedding_dim"
                ),
            )
        )

        semantica = (
            similaridade_cosseno(
                consulta_embedding,
                embedding_foto,
            )
        )

        visual_data = carregar_visual_data(
            foto.get(
                "visual_data_json"
            )
        )

        cor = filtros.get(
            "preferred_color"
        )

        ratio = color_ratio(
            visual_data,
            cor,
        )

        min_ratio = filtros.get(
            "min_color_ratio"
        )

        # Quando o usuário expressa uma regra quantitativa de
        # cor ("maioria de preto", "quase todas de amarelo",
        # "todas de branco"), isso vira um filtro forte.
        #
        # Mantemos apenas uma pequena tolerância porque os ratios
        # são estimativas visuais do indexador, não medições exatas.
        required_ratio = None

        if (
            cor
            and min_ratio is not None
        ):
            required_ratio = max(
                0.0,
                float(min_ratio) - 0.05,
            )

            if ratio < required_ratio:
                continue

        quality = float(
            foto.get(
                "quality_score"
            )
            or 0
        ) / 10.0

        brand = float(
            foto.get(
                "brand_fit_score"
            )
            or 0
        ) / 10.0

        score = (
            semantica
            * 0.72
            + ratio
            * 0.18
            + quality
            * 0.05
            + brand
            * 0.05
        )

        foto[
            "_semantic_similarity"
        ] = semantica

        foto[
            "_structured_color_ratio"
        ] = ratio

        foto[
            "_required_color_ratio"
        ] = required_ratio

        foto[
            "_preferred_color"
        ] = cor

        foto[
            "_smart_score"
        ] = score

        resultados.append(
            foto
        )

    # Para pedidos quantitativos de cor, a proporção objetiva
    # pesa mais que a similaridade semântica. Para buscas livres,
    # o score semântico continua sendo o principal sinal.
    if (
        filtros.get("preferred_color")
        and filtros.get("min_color_ratio") is not None
    ):
        resultados.sort(
            key=lambda foto: (
                float(
                    foto.get(
                        "_structured_color_ratio",
                        0,
                    )
                    or 0
                ),
                float(
                    foto.get(
                        "_smart_score",
                        0,
                    )
                    or 0
                ),
                float(
                    foto.get(
                        "_semantic_similarity",
                        0,
                    )
                    or 0
                ),
                int(
                    foto.get(
                        "people_count",
                        0,
                    )
                    or 0
                ),
            ),
            reverse=True,
        )

    else:
        resultados.sort(
            key=lambda foto: (
                float(
                    foto.get(
                        "_smart_score",
                        0,
                    )
                    or 0
                ),
                float(
                    foto.get(
                        "_structured_color_ratio",
                        0,
                    )
                    or 0
                ),
                int(
                    foto.get(
                        "people_count",
                        0,
                    )
                    or 0
                ),
            ),
            reverse=True,
        )

    return {
        "results": resultados[
            :int(
                limite
            )
        ],
        "filters": filtros,
        "indexed_count": len(
            rows
        ),
    }
