import math
import os
import tempfile

from PIL import Image, ImageDraw, ImageFont, ImageOps

from face_framing import detectar_foco_rosto
from photo_style import tratar_foto
from dynamic_layout import detectar_tema_wave
from adaptive_layout import medir, hex_rgb, fonte, quebrar, desenhar_multilinha


WIDTH = 1080
HEIGHT = 1920

COLORS = {
    "TIFFANY": "#11ACB0",
    "CORAL": "#F37A73",
    "DARK_SILVER": "#707071",
    "CHARCOAL": "#2F2B30",
    "WHITE": "#FFFFFF",
    "CAMPAIGN_YELLOW": "#FFD600",
    "CAMPAIGN_GREEN": "#005A4E",
}


def tamanho_automatico(
    draw,
    texto,
    largura,
    max_size,
    min_size,
    max_linhas,
    peso="bold",
):
    for tamanho in range(
        int(max_size),
        int(min_size) - 1,
        -2,
    ):
        font = fonte(
            tamanho,
            peso,
        )

        linhas = quebrar(
            draw,
            texto,
            font,
            largura,
        )

        if len(
            linhas
        ) <= max_linhas:
            return tamanho

    return int(
        min_size
    )


def pedido_tem_aula_experimental(
    pedido,
):
    texto = (
        pedido
        or ""
    ).lower()

    return any(
        termo in texto
        for termo in [
            "aula experimental",
            "experimental",
            "primeira aula",
            "aula teste",
            "aula de teste",
        ]
    )


# Temas de cor do Story para a família Dynamic (espelham os temas da
# onda do feed). Texto sempre branco; accent/CTA contrastam com o painel.
STORY_THEMES = {
    "coral": {
        "panel": "CORAL",
        "accent": "TIFFANY",
        "cta_fill": "TIFFANY",
    },
    "tiffany": {
        "panel": "TIFFANY",
        "accent": "CORAL",
        "cta_fill": "CORAL",
    },
    "escuro": {
        "panel": "CHARCOAL",
        "accent": "TIFFANY",
        "cta_fill": "TIFFANY",
    },
}


def paleta_story(
    family,
    base_layout,
    seasonal_direction=None,
    tema="coral",
):
    campaign_type = (
        seasonal_direction
        or {}
    ).get(
        "campaign_type"
    )

    if (
        family
        == "SLIMFIT_SEASONAL"
        and (
            "PROMO"
            in str(
                base_layout
                or ""
            )
            or campaign_type
            == "COPA_SLIM"
        )
    ):
        return {
            "panel": COLORS[
                "CAMPAIGN_GREEN"
            ],
            "accent": COLORS[
                "CAMPAIGN_YELLOW"
            ],
            "headline": COLORS[
                "WHITE"
            ],
            "support": COLORS[
                "WHITE"
            ],
            "cta_fill": COLORS[
                "CAMPAIGN_YELLOW"
            ],
            "cta_text": COLORS[
                "CHARCOAL"
            ],
            "panel_alpha": 238,
        }

    if family == "SLIMFIT_EVENT":
        return {
            "panel": COLORS[
                "CHARCOAL"
            ],
            "accent": COLORS[
                "CORAL"
            ],
            "headline": COLORS[
                "WHITE"
            ],
            "support": COLORS[
                "WHITE"
            ],
            "cta_fill": COLORS[
                "CORAL"
            ],
            "cta_text": COLORS[
                "WHITE"
            ],
            "panel_alpha": 238,
        }

    cores_tema = STORY_THEMES.get(
        tema,
        STORY_THEMES["coral"],
    )

    return {
        "panel": COLORS[
            cores_tema["panel"]
        ],
        "accent": COLORS[
            cores_tema["accent"]
        ],
        "headline": COLORS[
            "WHITE"
        ],
        "support": COLORS[
            "WHITE"
        ],
        "cta_fill": COLORS[
            cores_tema["cta_fill"]
        ],
        "cta_text": COLORS[
            "WHITE"
        ],
        "panel_alpha": 225,
    }


def criar_base_foto(
    caminho_foto,
):
    original = tratar_foto(
        Image.open(caminho_foto)
    )

    # Enquadramento centrado no(s) rosto(s), com a cabeça protegida.
    # Se não houver detecção/rosto, cai no ponto fixo padrão (0.5, 0.32).
    foco = detectar_foco_rosto(
        original,
        default=(0.5, 0.32),
    )

    print(
        "Story framing: foco=",
        foco,
        flush=True,
    )

    # Fundo full-bleed para evitar faixas.
    fundo = ImageOps.fit(
        original,
        (
            WIDTH,
            HEIGHT,
        ),
        method=Image.Resampling.LANCZOS,
        centering=foco,
    )

    # A parte visualmente importante recebe um crop menos
    # agressivo, preservando mais pessoas.
    topo_h = 1270

    topo = ImageOps.fit(
        original,
        (
            WIDTH,
            topo_h,
        ),
        method=Image.Resampling.LANCZOS,
        centering=foco,
    )

    fundo.paste(
        topo,
        (
            0,
            0,
        ),
    )

    return fundo


def pontos_onda(
    base_y,
    amplitude,
    fase=0,
):
    pontos = []

    for x in range(
        -50,
        WIDTH + 51,
        18,
    ):
        y = (
            base_y
            + amplitude
            * math.sin(
                (
                    x
                    + fase
                )
                / 175.0
            )
        )

        pontos.append(
            (
                x,
                int(y),
            )
        )

    return pontos


def aplicar_painel(
    canvas,
    paleta,
):
    overlay = Image.new(
        "RGBA",
        (
            WIDTH,
            HEIGHT,
        ),
        (
            0,
            0,
            0,
            0,
        ),
    )

    draw = ImageDraw.Draw(
        overlay
    )

    onda_base = pontos_onda(
        1110,
        34,
        15,
    )

    rgb = hex_rgb(
        paleta[
            "panel"
        ]
    )

    poligono = (
        onda_base
        + [
            (
                WIDTH + 50,
                HEIGHT + 50,
            ),
            (
                -50,
                HEIGHT + 50,
            ),
        ]
    )

    draw.polygon(
        poligono,
        fill=(
            rgb[0],
            rgb[1],
            rgb[2],
            int(
                paleta[
                    "panel_alpha"
                ]
            ),
        ),
    )

    onda_accent = [
        (
            x,
            y - 37,
        )
        for x, y
        in pontos_onda(
            1110,
            31,
            0,
        )
    ]

    onda_branca = [
        (
            x,
            y - 14,
        )
        for x, y
        in pontos_onda(
            1110,
            29,
            42,
        )
    ]

    draw.line(
        onda_accent,
        fill=hex_rgb(
            paleta[
                "accent"
            ]
        )
        + (255,),
        width=4,
    )

    draw.line(
        onda_branca,
        fill=(
            255,
            255,
            255,
            245,
        ),
        width=4,
    )

    return Image.alpha_composite(
        canvas.convert(
            "RGBA"
        ),
        overlay,
    ).convert(
        "RGB"
    )


def desenhar_badge(
    draw,
    texto,
    x,
    y,
    paleta,
):
    font = fonte(
        29,
        "bold",
    )

    w, h = medir(
        draw,
        texto,
        font,
    )

    pad_x = 24
    pad_y = 11

    draw.rounded_rectangle(
        (
            x,
            y,
            x
            + w
            + pad_x * 2,
            y
            + h
            + pad_y * 2,
        ),
        radius=24,
        fill=paleta[
            "accent"
        ],
    )

    draw.text(
        (
            x + pad_x,
            y + pad_y - 2,
        ),
        texto,
        font=font,
        fill=(
            COLORS[
                "CHARCOAL"
            ]
            if paleta[
                "accent"
            ]
            == COLORS[
                "CAMPAIGN_YELLOW"
            ]
            else COLORS[
                "WHITE"
            ]
        ),
    )

    return (
        y
        + h
        + pad_y * 2
    )


def desenhar_cta(
    draw,
    texto,
    x,
    y,
    paleta,
    font_delta=0,
):
    if not texto:
        return y

    tamanho = max(
        29,
        min(
            41,
            34
            + int(
                font_delta
                or 0
            ),
        ),
    )

    font = fonte(
        tamanho,
        "bold",
    )

    w, h = medir(
        draw,
        texto,
        font,
    )

    max_button_w = 760

    if (
        w + 64
        > max_button_w
    ):
        tamanho = max(
            27,
            tamanho - 4,
        )

        font = fonte(
            tamanho,
            "bold",
        )

        w, h = medir(
            draw,
            texto,
            font,
        )

    button_w = min(
        max_button_w,
        w + 64,
    )

    button_h = (
        h + 32
    )

    draw.rounded_rectangle(
        (
            x,
            y,
            x + button_w,
            y + button_h,
        ),
        radius=(
            button_h // 2
        ),
        fill=paleta[
            "cta_fill"
        ],
        outline=COLORS[
            "WHITE"
        ],
        width=3,
    )

    draw.text(
        (
            x + 32,
            y + 14,
        ),
        texto,
        font=font,
        fill=paleta[
            "cta_text"
        ],
    )

    return (
        y + button_h
    )



def eh_copa_slim_story(
    family,
    seasonal_direction,
):
    return bool(
        family
        == "SLIMFIT_SEASONAL"
        and (
            (
                seasonal_direction
                or {}
            ).get(
                "campaign_type"
            )
            == "COPA_SLIM"
        )
    )


def desenhar_titulo_copa_story(
    draw,
    x,
    y,
    paleta,
):
    """
    Assinatura estrutural da campanha.

    COPA não depende da headline gerada pela IA.
    SLIM permanece amarelo para preservar a identidade
    consolidada da campanha.
    """

    font_copa = fonte(
        66,
        "bold",
    )

    font_slim = fonte(
        78,
        "bold",
    )

    draw.text(
        (
            x,
            y,
        ),
        "COPA",
        font=font_copa,
        fill=COLORS[
            "WHITE"
        ],
    )

    _, copa_h = medir(
        draw,
        "COPA",
        font_copa,
    )

    slim_y = (
        y
        + copa_h
        - 4
    )

    draw.text(
        (
            x + 28,
            slim_y,
        ),
        "SLIM",
        font=font_slim,
        fill=paleta[
            "accent"
        ],
    )

    _, slim_h = medir(
        draw,
        "SLIM",
        font_slim,
    )

    return (
        slim_y
        + slim_h
    )


def desenhar_badge_conquista_story(
    draw,
    texto,
    x,
    y,
    paleta,
):
    if not texto:
        return y

    tamanho = 34

    font = fonte(
        tamanho,
        "bold",
    )

    w, h = medir(
        draw,
        texto,
        font,
    )

    max_w = 720

    if (
        w + 58
        > max_w
    ):
        tamanho = 30

        font = fonte(
            tamanho,
            "bold",
        )

        w, h = medir(
            draw,
            texto,
            font,
        )

    button_w = min(
        max_w,
        w + 58,
    )

    button_h = (
        h + 28
    )

    draw.rounded_rectangle(
        (
            x,
            y,
            x + button_w,
            y + button_h,
        ),
        radius=(
            button_h // 2
        ),
        fill=paleta[
            "accent"
        ],
    )

    draw.text(
        (
            x + 29,
            y + 12,
        ),
        texto,
        font=font,
        fill=COLORS[
            "CHARCOAL"
        ],
    )

    return (
        y
        + button_h
    )


def render_story(
    caminho_foto,
    copy,
    pedido,
    foto_meta,
    family,
    base_layout,
    seasonal_direction=None,
    render_overrides=None,
):
    """
    Renderer Story nativo 1080x1920.

    Não redimensiona o feed.
    Recompõe a foto e o conteúdo para 9:16.
    """

    overrides = (
        render_overrides
        or {}
    )

    tema_story = (
        overrides.get("wave_theme")
        or detectar_tema_wave(pedido)
    )

    paleta = paleta_story(
        family,
        base_layout,
        seasonal_direction=(
            seasonal_direction
        ),
        tema=tema_story,
    )

    print(
        "Story layout v3:",
        "wave_y=1110",
        "| headline_max=76",
        "| crop_y=0.32",
        flush=True,
    )

    canvas = criar_base_foto(
        caminho_foto
    )

    canvas = aplicar_painel(
        canvas,
        paleta,
    )

    draw = ImageDraw.Draw(
        canvas
    )

    text_x = 74
    text_w = 860
    # Um respiro a mais entre a onda (wave_y=1110) e o topo do texto.
    y = 1190

    copa_story = eh_copa_slim_story(
        family,
        seasonal_direction,
    )

    # ====================================================
    # COPA SLIM - STORY SEASONAL ESPECÍFICO
    # ====================================================
    #
    # COPA SLIM é identidade estrutural da campanha.
    # A colocação da aluna é um elemento independente.
    # Isso impede que "POLY • 5º LUGAR" substitua o nome
    # visual da campanha.
    # ====================================================

    if copa_story:
        print(
            "Story Seasonal Copa:",
            "titulo=COPA_SLIM",
            "| achievement=",
            (
                overrides.get(
                    "achievement_badge_text"
                )
                or copy.get(
                    "headline"
                )
                or ""
            ),
            flush=True,
        )

        # Selo de edição.
        if not bool(
            overrides.get(
                "hide_badge"
            )
        ):
            y = desenhar_badge(
                draw,
                "EDIÇÃO ESPECIAL",
                text_x,
                y,
                paleta,
            )

            y += 22

        # Título estrutural fixo.
        y = desenhar_titulo_copa_story(
            draw,
            text_x,
            y,
            paleta,
        )

        y += 28

        # Resultado / colocação.
        achievement = (
            overrides.get(
                "achievement_badge_text"
            )
            or copy.get(
                "headline"
            )
            or ""
        ).strip()

        if achievement:
            y = desenhar_badge_conquista_story(
                draw,
                achievement,
                text_x,
                y,
                paleta,
            )

            y += 34

        # Texto de apoio.
        support = (
            copy.get(
                "support"
            )
            or ""
        )

        support_delta = int(
            overrides.get(
                "support_font_delta",
                0,
            )
            or 0
        )

        support_size = max(
            25,
            min(
                32,
                28 + support_delta,
            ),
        )

        if support:
            y = desenhar_multilinha(
                draw,
                support,
                text_x,
                y,
                700,
                support_size,
                COLORS[
                    "WHITE"
                ],
                peso="regular",
                espacamento=8,
                max_linhas=3,
            )

        # CTA permanece complementar à conquista.
        cta = (
            copy.get(
                "cta"
            )
            or ""
        )

        if bool(
            overrides.get(
                "hide_cta"
            )
        ):
            cta = ""

        if cta:
            cta_y = min(
                y + 34,
                1680,
            )

            desenhar_cta(
                draw,
                cta,
                text_x,
                cta_y,
                paleta,
                font_delta=(
                    overrides.get(
                        "cta_font_delta",
                        0,
                    )
                ),
            )

        temp = tempfile.NamedTemporaryFile(
            suffix=".png",
            delete=False,
        )

        caminho_saida = (
            temp.name
        )

        temp.close()

        canvas.save(
            caminho_saida,
            "PNG",
        )

        return {
            "image_path": caminho_saida,
            "composition": (
                "STORY_SEASONAL_PROMO"
            ),
            "publisher_layout": (
                "SEASONAL_PROMO"
            ),
            "family": family,
            "background_style": (
                "STORY_SEASONAL_PROMO"
            ),
            "format": "STORY",
            "width": WIDTH,
            "height": HEIGHT,
        }

    # ----------------------------------------------------
    # BADGE
    # ----------------------------------------------------

    hide_badge = bool(
        overrides.get(
            "hide_badge"
        )
    )

    badge = None

    if (
        family
        == "SLIMFIT_SEASONAL"
        and (
            (
                seasonal_direction
                or {}
            ).get(
                "campaign_type"
            )
            == "COPA_SLIM"
        )
    ):
        badge = (
            "EDIÇÃO ESPECIAL"
        )

    elif (
        family
        == "SLIMFIT_DYNAMIC"
        and pedido_tem_aula_experimental(
            pedido
        )
    ):
        badge = (
            "AULA EXPERIMENTAL"
        )

    if (
        badge
        and not hide_badge
    ):
        y = desenhar_badge(
            draw,
            badge,
            text_x,
            y,
            paleta,
        )

        y += 28

    # ----------------------------------------------------
    # HEADLINE
    # ----------------------------------------------------

    headline = (
        copy.get(
            "headline"
        )
        or ""
    )

    headline_size = tamanho_automatico(
        draw,
        headline,
        text_w,
        max_size=76,
        min_size=54,
        max_linhas=3,
        peso="bold",
    )

    y = desenhar_multilinha(
        draw,
        headline,
        text_x,
        y,
        text_w,
        headline_size,
        paleta[
            "headline"
        ],
        peso="bold",
        espacamento=3,
        max_linhas=3,
    )

    # ----------------------------------------------------
    # RÉGUA
    # ----------------------------------------------------

    line_y = y + 22

    draw.rounded_rectangle(
        (
            text_x,
            line_y,
            text_x + 205,
            line_y + 7,
        ),
        radius=4,
        fill=COLORS[
            "WHITE"
        ],
    )

    y = (
        line_y + 64
    )

    # ----------------------------------------------------
    # APOIO
    # ----------------------------------------------------

    support = (
        copy.get(
            "support"
        )
        or ""
    )

    support_delta = int(
        overrides.get(
            "support_font_delta",
            0,
        )
        or 0
    )

    support_size = (
        30 + support_delta
    )

    if len(
        support
    ) > 120:
        support_size -= 3

    support_size = max(
        25,
        min(
            36,
            support_size,
        ),
    )

    if support:
        y = desenhar_multilinha(
            draw,
            support,
            text_x,
            y,
            820,
            support_size,
            paleta[
                "support"
            ],
            peso="regular",
            espacamento=8,
            max_linhas=4,
        )

    # ----------------------------------------------------
    # CTA
    # ----------------------------------------------------

    cta = (
        copy.get(
            "cta"
        )
        or ""
    )

    if bool(
        overrides.get(
            "hide_cta"
        )
    ):
        cta = ""

    if cta:
        cta_y = min(
            y + 54,
            1675,
        )

        desenhar_cta(
            draw,
            cta,
            text_x,
            cta_y,
            paleta,
            font_delta=(
                overrides.get(
                    "cta_font_delta",
                    0,
                )
            ),
        )

    # ----------------------------------------------------
    # ÁREA SEGURA
    # ----------------------------------------------------
    # Não desenhamos elementos de copy nos últimos ~180 px.
    # O publisher aplica a marca oficial no lower-right.

    temp = tempfile.NamedTemporaryFile(
        suffix=".png",
        delete=False,
    )

    caminho_saida = (
        temp.name
    )

    temp.close()

    canvas.save(
        caminho_saida,
        "PNG",
    )

    return {
        "image_path": caminho_saida,
        "composition": (
            "STORY_"
            + str(
                base_layout
                or "DYNAMIC_WAVE"
            ).replace(
                "STORY_",
                "",
                1,
            )
        ),
        "publisher_layout": (
            str(
                base_layout
                or "DYNAMIC_WAVE"
            ).replace(
                "STORY_",
                "",
                1,
            )
        ),
        "family": family,
        "background_style": (
            "STORY_"
            + str(
                base_layout
                or "DYNAMIC_WAVE"
            ).replace(
                "STORY_",
                "",
                1,
            )
        ),
        "format": "STORY",
        "width": WIDTH,
        "height": HEIGHT,
    }
