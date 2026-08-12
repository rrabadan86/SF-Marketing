import hashlib
import unicodedata


STYLES = {
    "DARK_PREMIUM": {
        "background": "#2F2B30",
        "surface": "#2F2B30",
        "primary_text": "#FFFFFF",
        "secondary_text": "#F4F4F2",
        "accent": "#11ACB0",
        "secondary_accent": "#F37A73",
        "cta_fill": "#F37A73",
        "cta_text": "#FFFFFF",
        "tag_fill": "#11ACB0",
        "tag_text": "#2F2B30",
    },

    "LIGHT_CLEAN": {
        "background": "#F4F4F2",
        "surface": "#F4F4F2",
        "primary_text": "#2F2B30",
        "secondary_text": "#5A565B",
        "accent": "#11ACB0",
        "secondary_accent": "#F37A73",
        "cta_fill": "#11ACB0",
        "cta_text": "#FFFFFF",
        "tag_fill": "#2F2B30",
        "tag_text": "#FFFFFF",
    },

    "TIFFANY_FOCUS": {
        "background": "#11ACB0",
        "surface": "#11ACB0",
        "primary_text": "#FFFFFF",
        "secondary_text": "#F4F4F2",
        "accent": "#FFFFFF",
        "secondary_accent": "#F37A73",
        "cta_fill": "#2F2B30",
        "cta_text": "#FFFFFF",
        "tag_fill": "#FFFFFF",
        "tag_text": "#2F2B30",
    },

    "CORAL_ACCENT": {
        "background": "#2F2B30",
        "surface": "#2F2B30",
        "primary_text": "#FFFFFF",
        "secondary_text": "#F4F4F2",
        "accent": "#F37A73",
        "secondary_accent": "#11ACB0",
        "cta_fill": "#11ACB0",
        "cta_text": "#FFFFFF",
        "tag_fill": "#F37A73",
        "tag_text": "#FFFFFF",
    },

    "PHOTO_FIRST": {
        "background": "#2F2B30",
        "surface": "#2F2B30",
        "primary_text": "#FFFFFF",
        "secondary_text": "#F4F4F2",
        "accent": "#11ACB0",
        "secondary_accent": "#F37A73",
        "cta_fill": "#F37A73",
        "cta_text": "#FFFFFF",
        "tag_fill": "#11ACB0",
        "tag_text": "#2F2B30",
    },
}


def normalizar(texto):
    if not texto:
        return ""

    texto = unicodedata.normalize(
        "NFKD",
        texto,
    )

    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )

    return texto.lower()


def escolher_estilo(
    template,
    pedido,
    foto,
):
    pedido = normalizar(
        pedido
    )

    # Pedido explícito tem prioridade.
    if any(
        termo in pedido
        for termo in [
            "claro",
            "clean",
            "leve",
            "minimalista claro",
            "fundo claro",
        ]
    ):
        estilo = "LIGHT_CLEAN"

    elif any(
        termo in pedido
        for termo in [
            "premium",
            "sofisticado",
            "elegante",
            "escuro",
            "luxo",
        ]
    ):
        estilo = "DARK_PREMIUM"

    elif any(
        termo in pedido
        for termo in [
            "tiffany",
            "turquesa",
            "azul",
            "identidade forte",
        ]
    ):
        estilo = "TIFFANY_FOCUS"

    elif any(
        termo in pedido
        for termo in [
            "coral",
            "quente",
            "vibrante",
            "energético",
            "energia",
        ]
    ):
        estilo = "CORAL_ACCENT"

    elif any(
        termo in pedido
        for termo in [
            "foto cheia",
            "foto ocupando",
            "fotografia dominante",
            "visual",
            "fotográfico",
        ]
    ):
        estilo = "PHOTO_FIRST"

    else:
        # Preferências por template.
        preferencias = {
            "A": [
                "DARK_PREMIUM",
                "LIGHT_CLEAN",
                "CORAL_ACCENT",
            ],
            "B": [
                "DARK_PREMIUM",
                "PHOTO_FIRST",
                "LIGHT_CLEAN",
            ],
            "C": [
                "PHOTO_FIRST",
                "TIFFANY_FOCUS",
                "DARK_PREMIUM",
            ],
        }

        opcoes = preferencias.get(
            template,
            [
                "DARK_PREMIUM",
                "LIGHT_CLEAN",
            ],
        )

        # Variação determinística:
        # o mesmo pedido tende a manter consistência,
        # pedidos/fotos diferentes podem variar.
        chave = (
            f"{pedido}|"
            f"{foto.get('filename')}|"
            f"{template}"
        )

        hash_value = int(
            hashlib.sha256(
                chave.encode(
                    "utf-8"
                )
            ).hexdigest(),
            16,
        )

        estilo = opcoes[
            hash_value
            % len(opcoes)
        ]

    return {
        "style": estilo,
        "colors": STYLES[
            estilo
        ],
    }
