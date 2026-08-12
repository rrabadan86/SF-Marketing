import re
import unicodedata

from campaign_reference_search import (
    buscar_referencias,
    detectar_tipo_campanha,
)


# =========================================================
# PALETA
# =========================================================

BRAND_COLORS = {
    "TIFFANY": "#11ACB0",
    "CORAL": "#F37A73",
    "DARK_SILVER": "#707071",
    "CHARCOAL": "#2F2B30",
    "WHITE": "#FFFFFF",
    "OFF_WHITE": "#F4F4F2",
}


# =========================================================
# NORMALIZAÇÃO
# =========================================================

def normalizar_texto(texto):
    texto = str(
        texto or ""
    ).strip()

    texto = unicodedata.normalize(
        "NFKD",
        texto,
    )

    texto = "".join(
        c
        for c in texto
        if not unicodedata.combining(c)
    )

    return texto.lower()


def normalizar_cor(valor):
    texto = normalizar_texto(
        valor
    )

    if not texto:
        return None

    compacto = (
        texto
        .replace(" ", "")
        .upper()
    )

    mapa_hex = {
        "#11ACB0": "TIFFANY",
        "#F37A73": "CORAL",
        "#707071": "DARK_SILVER",
        "#2F2B30": "CHARCOAL",
        "#FFFFFF": "WHITE",
        "#F4F4F2": "OFF_WHITE",
    }

    if compacto in mapa_hex:
        return mapa_hex[
            compacto
        ]

    if any(
        termo in texto
        for termo in [
            "tiffany",
            "turquesa",
            "azul esverdeado",
        ]
    ):
        return "TIFFANY"

    if "coral" in texto:
        return "CORAL"

    if any(
        termo in texto
        for termo in [
            "dark silver",
            "cinza",
            "gray",
            "grey",
        ]
    ):
        return "DARK_SILVER"

    if any(
        termo in texto
        for termo in [
            "charcoal",
            "carvao",
            "grafite",
            "preto",
            "dark",
        ]
    ):
        return "CHARCOAL"

    if any(
        termo in texto
        for termo in [
            "off-white",
            "off white",
            "creme",
            "bege claro",
        ]
    ):
        return "OFF_WHITE"

    if any(
        termo in texto
        for termo in [
            "branco",
            "white",
        ]
    ):
        return "WHITE"

    if any(
        termo in texto
        for termo in [
            "amarelo",
            "yellow",
            "#ffd600",
            "#ffd400",
        ]
    ):
        return "CAMPAIGN_YELLOW"

    if any(
        termo in texto
        for termo in [
            "verde escuro",
            "#005a4e",
            "#004f43",
            "#005b4e",
            "#0b5e52",
            "#0a4c42",
        ]
    ):
        return "CAMPAIGN_GREEN"

    if re.match(
        r"^#[0-9a-f]{6}$",
        texto,
        flags=re.IGNORECASE,
    ):
        return "CAMPAIGN_CUSTOM"

    return None


# =========================================================
# ELEMENTOS VISUAIS
# =========================================================

def normalizar_elemento(valor):
    texto = normalizar_texto(
        valor
    )

    if not texto:
        return None

    regras = [
        (
            "CURVE",
            [
                "curve",
                "curva",
                "organic",
                "organico",
                "onda",
                "wave",
            ],
        ),
        (
            "LINE",
            [
                "line",
                "linha",
            ],
        ),
        (
            "BOTANICAL",
            [
                "botan",
                "folha",
                "floral",
                "planta",
            ],
        ),
        (
            "HEART",
            [
                "heart",
                "coracao",
            ],
        ),
        (
            "SPORT",
            [
                "sport",
                "esport",
                "medal",
                "estrela",
                "star",
                "trofeu",
                "numero",
            ],
        ),
        (
            "ICON",
            [
                "icon",
                "icone",
            ],
        ),
        (
            "BAND",
            [
                "band",
                "faixa",
            ],
        ),
        (
            "BADGE",
            [
                "badge",
                "selo",
                "serrilhado",
            ],
        ),
    ]

    for saida, termos in regras:
        if any(
            termo in texto
            for termo in termos
        ):
            return saida

    return None


# =========================================================
# CONTAGEM
# =========================================================

def incrementar(
    contador,
    chave,
    peso=1.0,
):
    if not chave:
        return

    contador[
        chave
    ] = (
        contador.get(
            chave,
            0.0,
        )
        + peso
    )


def ordenar_contagem(
    contador,
):
    return [
        chave
        for chave, _
        in sorted(
            contador.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ]


# =========================================================
# ARQUÉTIPO
# =========================================================

def detectar_arquetipo(
    campaign_type,
    referencias,
    estilos,
    foto,
):
    if campaign_type in {
        "DIA_DAS_MAES",
        "SAUDE",
        "DIA_DA_MULHER",
        "ATIVIDADE_FISICA",
        "OUTUBRO_ROSA",
    }:
        return "SEASONAL_CLEAN"

    if campaign_type in {
        "COPA_SLIM",
        "PASCOA",
    }:
        return "SEASONAL_PROMO"

    if campaign_type == "CIRCUITO_SLIM":
        return "SEASONAL_PHOTO"

    if (
        estilos.get(
            "promotional",
            0,
        )
        + estilos.get(
            "event",
            0,
        )
        >= 2
    ):
        return "SEASONAL_PROMO"

    foto_dominante = (
        foto.get(
            "dominant",
            0,
        )
        + foto.get(
            "high",
            0,
        )
    )

    foto_baixa = (
        foto.get(
            "none",
            0,
        )
        + foto.get(
            "low",
            0,
        )
    )

    if (
        foto_dominante
        > foto_baixa
    ):
        return "SEASONAL_PHOTO"

    return "SEASONAL_CLEAN"


# =========================================================
# REQUISITOS DA FOTO
# =========================================================

def requisitos_foto(
    campaign_type,
    archetype,
):
    requisitos = {
        "required": False,
        "min_people_count": None,
        "prefer_group": False,
        "prefer_action": False,
        "prefer_collective_class": False,
        "selection_mode": "normal",
    }

    # -----------------------------------------------------
    # CIRCUITO SLIM
    #
    # A proposta da aula é coletiva.
    # Não queremos imagens fechadas com poucas pessoas.
    #
    # O requisito é > 10 pessoas visíveis.
    # Portanto min_people_count = 11.
    # -----------------------------------------------------

    if (
        campaign_type
        == "CIRCUITO_SLIM"
    ):
        requisitos.update({
            "required": True,

            "min_people_count": 11,

            "prefer_group": True,

            "prefer_action": True,

            "prefer_collective_class": True,

            "selection_mode": (
                "large_group"
            ),
        })

        return requisitos

    # -----------------------------------------------------
    # Outros arquétipos fotográficos
    # -----------------------------------------------------

    if (
        archetype
        == "SEASONAL_PHOTO"
    ):
        requisitos.update({
            "required": True,

            "prefer_group": False,

            "prefer_action": True,

            "selection_mode": (
                "photo_campaign"
            ),
        })

    return requisitos


# =========================================================
# DIREÇÃO VISUAL
# =========================================================

def interpretar_referencias(
    pedido,
    limite=8,
):
    campaign_type = (
        detectar_tipo_campanha(
            pedido
        )
    )

    busca = buscar_referencias(
        pedido,
        limite=limite,
        campaign_type=campaign_type,
    )

    referencias = busca.get(
        "results",
        [],
    )

    estilos = {}
    fotos = {}
    tratamentos = {}
    densidades = {}
    posicoes = {}
    alinhamentos = {}
    cores = {}
    elementos = {}
    formas = {}

    date_emphasis = 0.0
    partner_logo = 0.0

    regras = []

    for item in referencias:
        qualidade = float(
            item.get(
                "reference_quality_score"
            )
            or 5
        )

        marca = float(
            item.get(
                "brand_fit_score"
            )
            or 5
        )

        peso = max(
            0.5,
            (
                qualidade
                + marca
            )
            / 20.0,
        )

        incrementar(
            estilos,
            item.get(
                "visual_style"
            ),
            peso,
        )

        incrementar(
            fotos,
            item.get(
                "photo_ratio"
            ),
            peso,
        )

        incrementar(
            tratamentos,
            item.get(
                "photo_treatment"
            ),
            peso,
        )

        incrementar(
            densidades,
            item.get(
                "text_density"
            ),
            peso,
        )

        incrementar(
            posicoes,
            item.get(
                "headline_position"
            ),
            peso,
        )

        incrementar(
            alinhamentos,
            item.get(
                "headline_alignment"
            ),
            peso,
        )

        incrementar(
            formas,
            item.get(
                "background_shape"
            ),
            peso,
        )

        if item.get(
            "date_emphasis"
        ):
            date_emphasis += peso

        if item.get(
            "partner_logo"
        ):
            partner_logo += peso

        for cor in item.get(
            "dominant_colors",
            []
        ):
            cor_normalizada = (
                normalizar_cor(
                    cor
                )
            )

            incrementar(
                cores,
                cor_normalizada,
                peso,
            )

        for elemento in item.get(
            "graphic_elements",
            []
        ):
            elemento_normalizado = (
                normalizar_elemento(
                    elemento
                )
            )

            incrementar(
                elementos,
                elemento_normalizado,
                peso,
            )

        for regra in item.get(
            "reusable_rules",
            []
        ):
            if (
                regra
                and regra not in regras
            ):
                regras.append(
                    regra
                )

    archetype = detectar_arquetipo(
        campaign_type,
        referencias,
        estilos,
        fotos,
    )

    photo_requirements = (
        requisitos_foto(
            campaign_type,
            archetype,
        )
    )

    total_peso = sum(
        max(
            0.5,
            (
                float(
                    item.get(
                        "reference_quality_score"
                    )
                    or 5
                )
                + float(
                    item.get(
                        "brand_fit_score"
                    )
                    or 5
                )
            )
            / 20.0,
        )
        for item in referencias
    )

    if total_peso:
        date_ratio = (
            date_emphasis
            / total_peso
        )

        partner_ratio = (
            partner_logo
            / total_peso
        )

    else:
        date_ratio = 0
        partner_ratio = 0

    preferred_colors = (
        ordenar_contagem(
            cores
        )
    )

    for padrao in [
        "TIFFANY",
        "CORAL",
        "CHARCOAL",
        "WHITE",
    ]:
        if (
            padrao
            not in preferred_colors
        ):
            preferred_colors.append(
                padrao
            )

    return {
        "campaign_type": campaign_type,

        "reference_count": len(
            referencias
        ),

        "archetype": archetype,

        "photo_requirements": (
            photo_requirements
        ),

        "preferred_styles": (
            ordenar_contagem(
                estilos
            )
        ),

        "photo_ratio": (
            ordenar_contagem(
                fotos
            )
        ),

        "photo_treatment": (
            ordenar_contagem(
                tratamentos
            )
        ),

        "text_density": (
            ordenar_contagem(
                densidades
            )
        ),

        "headline_position": (
            ordenar_contagem(
                posicoes
            )
        ),

        "headline_alignment": (
            ordenar_contagem(
                alinhamentos
            )
        ),

        "preferred_colors": (
            preferred_colors
        ),

        "preferred_shapes": (
            ordenar_contagem(
                formas
            )
        ),

        "graphic_elements": (
            ordenar_contagem(
                elementos
            )
        ),

        "date_emphasis": (
            date_ratio >= 0.50
        ),

        "partner_logo_expected": (
            partner_ratio >= 0.50
        ),

        "reusable_rules": (
            regras[:12]
        ),
    }


# =========================================================
# CLI
# =========================================================

if __name__ == "__main__":
    import json
    import sys

    pedido = " ".join(
        sys.argv[1:]
    )

    if not pedido:
        pedido = (
            "campanha sazonal SlimFit"
        )

    resultado = (
        interpretar_referencias(
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
