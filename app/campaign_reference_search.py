import json
import sqlite3
import unicodedata


DB_FILE = (
    "/app/data/creative_agent.db"
)


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


def detectar_tipo_campanha(
    pedido,
):
    texto = normalizar(
        pedido
    )

    regras = [
        (
            "OUTUBRO_ROSA",
            [
                "outubro rosa",
            ],
        ),

        (
            "DIA_DA_MULHER",
            [
                "dia da mulher",
                "dia das mulheres",
            ],
        ),

        (
            "DIA_DAS_MAES",
            [
                "dia das maes",
                "maes",
            ],
        ),

        (
            "ATIVIDADE_FISICA",
            [
                "atividade fisica",
                "dia mundial da atividade fisica",
            ],
        ),

        (
            "SAUDE",
            [
                "dia mundial da saude",
                "saude",
            ],
        ),

        (
            "COPA_SLIM",
            [
                "copa slim",
                "copa",
            ],
        ),

        (
            "PASCOA",
            [
                "pascoa",
                "desafio de pascoa",
            ],
        ),

        (
            "CIRCUITO_SLIM",
            [
                "circuito slim",
            ],
        ),
    ]

    for tipo, termos in regras:
        for termo in termos:
            if termo in texto:
                return tipo

    return None


def desserializar(
    valor,
    default=None,
):
    if not valor:
        return (
            default
            if default is not None
            else []
        )

    try:
        return json.loads(
            valor
        )
    except Exception:
        return (
            default
            if default is not None
            else []
        )


def buscar_referencias(
    pedido,
    limite=5,
    campaign_type=None,
):
    if campaign_type is None:
        campaign_type = (
            detectar_tipo_campanha(
                pedido
            )
        )

    conn = sqlite3.connect(
        DB_FILE
    )

    conn.row_factory = (
        sqlite3.Row
    )

    if campaign_type:
        rows = conn.execute("""
            SELECT *
            FROM campaign_references
            WHERE
                indexed = 1
                AND campaign_type = ?
            ORDER BY
                reference_quality_score DESC,
                brand_fit_score DESC,
                id DESC
            LIMIT ?
        """, (
            campaign_type,
            limite,
        )).fetchall()

    else:
        rows = conn.execute("""
            SELECT *
            FROM campaign_references
            WHERE indexed = 1
            ORDER BY
                reference_quality_score DESC,
                brand_fit_score DESC,
                id DESC
            LIMIT ?
        """, (
            limite,
        )).fetchall()

    conn.close()

    resultados = []

    for row in rows:
        item = dict(
            row
        )

        item[
            "dominant_colors"
        ] = desserializar(
            item.get(
                "dominant_colors"
            )
        )

        item[
            "graphic_elements"
        ] = desserializar(
            item.get(
                "graphic_elements"
            )
        )

        item[
            "reusable_rules"
        ] = desserializar(
            item.get(
                "reusable_rules"
            )
        )

        item[
            "analysis"
        ] = desserializar(
            item.get(
                "analysis_json"
            ),
            {},
        )

        resultados.append(
            item
        )

    return {
        "campaign_type": (
            campaign_type
        ),
        "count": len(
            resultados
        ),
        "results": resultados,
    }


def resumir_referencias(
    pedido,
    limite=5,
):
    busca = buscar_referencias(
        pedido,
        limite=limite,
    )

    referencias = busca[
        "results"
    ]

    if not referencias:
        return {
            "campaign_type": (
                busca[
                    "campaign_type"
                ]
            ),
            "reference_count": 0,
            "preferred_styles": [],
            "preferred_shapes": [],
            "preferred_colors": [],
            "reusable_rules": [],
        }

    estilos = {}
    formas = {}
    cores = {}
    regras = []

    for item in referencias:
        visual_style = item.get(
            "visual_style"
        )

        background_shape = (
            item.get(
                "background_shape"
            )
        )

        if visual_style:
            estilos[
                visual_style
            ] = (
                estilos.get(
                    visual_style,
                    0,
                )
                + 1
            )

        if background_shape:
            formas[
                background_shape
            ] = (
                formas.get(
                    background_shape,
                    0,
                )
                + 1
            )

        for cor in item.get(
            "dominant_colors",
            [],
        ):
            cores[
                cor
            ] = (
                cores.get(
                    cor,
                    0,
                )
                + 1
            )

        for regra in item.get(
            "reusable_rules",
            [],
        ):
            if (
                regra
                and regra not in regras
            ):
                regras.append(
                    regra
                )

    ordenar = lambda d: [
        chave
        for chave, _
        in sorted(
            d.items(),
            key=lambda x: x[1],
            reverse=True,
        )
    ]

    return {
        "campaign_type": (
            busca[
                "campaign_type"
            ]
        ),

        "reference_count": len(
            referencias
        ),

        "preferred_styles": (
            ordenar(
                estilos
            )
        ),

        "preferred_shapes": (
            ordenar(
                formas
            )
        ),

        "preferred_colors": (
            ordenar(
                cores
            )
        ),

        "reusable_rules": regras[
            :12
        ],
    }


if __name__ == "__main__":
    import sys

    pedido = " ".join(
        sys.argv[1:]
    )

    if not pedido:
        pedido = (
            "campanha sazonal SlimFit"
        )

    resultado = (
        resumir_referencias(
            pedido
        )
    )

    print(
        json.dumps(
            resultado,
            ensure_ascii=False,
            indent=2,
        )
    )
