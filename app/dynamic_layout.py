import os
import re
import tempfile

from PIL import Image, ImageDraw, ImageFont, ImageOps

from face_framing import detectar_foco_rosto


WIDTH = 1080
HEIGHT = 1350

COLORS = {
    "TIFFANY": "#11ACB0",
    "CORAL": "#F37A73",
    "DARK_SILVER": "#707071",
    "CHARCOAL": "#2F2B30",
    "WHITE": "#FFFFFF",
}


# -------------------------------------------------------------
# TEMAS DA ONDA (DYNAMIC)
# -------------------------------------------------------------
# Mesma composição, cores de fundo diferentes — todas da paleta
# oficial. O texto é sempre branco; "accent" é a cor de destaque do CTA,
# escolhida para contrastar com o fundo (nunca igual a ele).
WAVE_THEMES = {
    "coral": {
        "bg": (243, 122, 115, 224),
        "linha1": (17, 172, 176, 255),   # tiffany
        "linha2": (255, 255, 255, 245),  # branca
        "accent": "TIFFANY",
    },
    "tiffany": {
        "bg": (17, 172, 176, 224),
        "linha1": (243, 122, 115, 255),  # coral
        "linha2": (255, 255, 255, 245),
        "accent": "CORAL",
    },
    "escuro": {
        "bg": (47, 43, 48, 235),         # charcoal
        "linha1": (17, 172, 176, 255),   # tiffany
        "linha2": (255, 255, 255, 245),
        "accent": "TIFFANY",
    },
}


def _sem_acentos(texto):
    import unicodedata

    texto = unicodedata.normalize(
        "NFKD",
        str(texto or ""),
    )
    return "".join(
        c
        for c in texto
        if not unicodedata.combining(c)
    ).lower()


def detectar_tema_wave(pedido):
    """
    Escolhe o tema de fundo do Dynamic pela palavra-chave do pedido.
    Padrão: coral (comportamento histórico, sem regressão).
    """
    texto = _sem_acentos(pedido)

    if any(
        termo in texto
        for termo in [
            "fundo tiffany",
            "fundo azul",
            "fundo verde",
            "onda tiffany",
            "estilo tiffany",
            "versao tiffany",
        ]
    ):
        return "tiffany"

    if any(
        termo in texto
        for termo in [
            "fundo escuro",
            "fundo preto",
            "fundo dark",
            "fundo grafite",
            "estilo escuro",
            "versao escura",
            "onda escura",
        ]
    ):
        return "escuro"

    return "coral"


def fonte_path(peso="regular"):
    candidatos = []

    if peso == "bold":
        candidatos.extend([
            "/app/assets/fonts/Nexa-Bold.otf",
            "/app/assets/fonts/Nexa-Bold.ttf",
        ])
    else:
        candidatos.extend([
            "/app/assets/fonts/Nexa-Regular.otf",
            "/app/assets/fonts/Nexa-Regular.ttf",
        ])

    candidatos.extend([
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if peso == "bold"
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ])

    for caminho in candidatos:
        if os.path.exists(caminho):
            return caminho

    return None


def fonte(tamanho, peso="regular"):
    caminho = fonte_path(peso)

    if caminho:
        return ImageFont.truetype(
            caminho,
            int(tamanho),
        )

    return ImageFont.load_default()


def medir(draw, texto, font):
    bbox = draw.textbbox(
        (0, 0),
        texto or "",
        font=font,
    )

    return (
        bbox[2] - bbox[0],
        bbox[3] - bbox[1],
    )


def quebrar(draw, texto, font, largura_max):
    palavras = (
        texto
        or ""
    ).split()

    if not palavras:
        return []

    linhas = []
    atual = []

    for palavra in palavras:
        tentativa = " ".join(
            atual + [palavra]
        )

        largura, _ = medir(
            draw,
            tentativa,
            font,
        )

        if (
            largura <= largura_max
            or not atual
        ):
            atual.append(
                palavra
            )

        else:
            linhas.append(
                " ".join(
                    atual
                )
            )

            atual = [
                palavra
            ]

    if atual:
        linhas.append(
            " ".join(
                atual
            )
        )

    return linhas


def desenhar_multilinha(
    draw,
    texto,
    x,
    y,
    largura,
    tamanho,
    cor,
    peso="regular",
    espacamento=6,
    max_linhas=None,
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

    if max_linhas:
        linhas = linhas[
            :max_linhas
        ]

    atual_y = y

    for linha in linhas:
        _, h = medir(
            draw,
            linha,
            font,
        )

        draw.text(
            (
                x,
                atual_y,
            ),
            linha,
            font=font,
            fill=cor,
        )

        atual_y += (
            h
            + espacamento
        )

    return atual_y


def tamanho_headline(
    draw,
    texto,
    largura,
):
    for tamanho in range(
        62,
        43,
        -2,
    ):
        font = fonte(
            tamanho,
            "bold",
        )

        linhas = quebrar(
            draw,
            texto,
            font,
            largura,
        )

        if len(
            linhas
        ) <= 3:
            return tamanho

    return 44


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


def crop_foto(
    caminho_foto,
):
    foto = Image.open(
        caminho_foto
    ).convert(
        "RGB"
    )

    # Centraliza no(s) rosto(s) e protege a cabeça; sem rosto detectado,
    # usa o ponto fixo padrão.
    foco = detectar_foco_rosto(
        foto,
        default=(0.5, 0.37),
    )

    print(
        "Dynamic framing: foco=",
        foco,
        flush=True,
    )

    return ImageOps.fit(
        foto,
        (
            WIDTH,
            HEIGHT,
        ),
        method=(
            Image.Resampling.LANCZOS
        ),
        centering=foco,
    )


def pontos_wave(
    base_y,
    amplitude,
    offset=0,
):
    pontos = []

    for x in range(
        -40,
        WIDTH + 41,
        20,
    ):
        import math

        y = (
            base_y
            + amplitude
            * math.sin(
                (
                    x
                    + offset
                )
                / 180.0
            )
        )

        pontos.append(
            (
                x,
                int(
                    y
                ),
            )
        )

    return pontos


def desenhar_wave_overlay(
    canvas,
    tema=None,
):
    tema = tema or WAVE_THEMES["coral"]

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

    onda = pontos_wave(
        900,
        33,
        15,
    )

    poligono = (
        onda
        + [
            (
                WIDTH + 40,
                HEIGHT + 40,
            ),
            (
                -40,
                HEIGHT + 40,
            ),
        ]
    )

    draw.polygon(
        poligono,
        fill=tema["bg"],
    )

    # linhas finas acima da onda
    onda_tiffany = [
        (
            x,
            y - 27,
        )
        for x, y in pontos_wave(
            900,
            31,
            5,
        )
    ]

    onda_branca = [
        (
            x,
            y - 10,
        )
        for x, y in pontos_wave(
            900,
            29,
            40,
        )
    ]

    draw.line(
        onda_tiffany,
        fill=tema["linha1"],
        width=3,
    )

    draw.line(
        onda_branca,
        fill=(
            255,
            255,
            255,
            245,
        ),
        width=3,
    )

    canvas_rgba = canvas.convert(
        "RGBA"
    )

    return Image.alpha_composite(
        canvas_rgba,
        overlay,
    ).convert(
        "RGB"
    )



def altura_slot_badge(
    draw,
    texto="AULA EXPERIMENTAL",
):
    """
    Altura vertical exata que o badge ocupa no fluxo,
    incluindo o respiro posterior usado pelo renderer.
    """

    f = fonte(
        25,
        "bold",
    )

    _, h = medir(
        draw,
        texto,
        f,
    )

    pad_y = 9

    return (
        h
        + pad_y * 2
        + 24
    )


def desenhar_badge(
    draw,
    x,
    y,
    texto,
):
    f = fonte(
        25,
        "bold",
    )

    w, h = medir(
        draw,
        texto,
        f,
    )

    pad_x = 22
    pad_y = 9

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
        radius=21,
        fill=COLORS[
            "WHITE"
        ],
    )

    draw.text(
        (
            x + pad_x,
            y + pad_y - 2,
        ),
        texto,
        font=f,
        fill=COLORS[
            "CHARCOAL"
        ],
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
    emphasis=False,
    font_delta=0,
    accent="TIFFANY",
):
    if not texto:
        return y

    tamanho = max(
        23,
        min(
            34,
            25
            + int(
                font_delta
                or 0
            ),
        ),
    )

    f = fonte(
        tamanho,
        "bold",
    )

    w, h = medir(
        draw,
        texto,
        f,
    )

    # CTA sempre fica dentro do canvas.
    max_w = 650

    if w > max_w:
        tamanho = max(
            21,
            tamanho - 3,
        )

        f = fonte(
            tamanho,
            "bold",
        )

        w, h = medir(
            draw,
            texto,
            f,
        )

    if emphasis:
        pad_x = 22
        pad_y = 9

        draw.rounded_rectangle(
            (
                x,
                y,
                min(
                    WIDTH - 300,
                    x
                    + w
                    + pad_x * 2,
                ),
                y
                + h
                + pad_y * 2,
            ),
            radius=24,
            fill=COLORS[
                accent
            ],
            outline=COLORS[
                "WHITE"
            ],
            width=2,
        )

        draw.text(
            (
                x + pad_x,
                y + pad_y - 2,
            ),
            texto,
            font=f,
            fill=COLORS[
                "WHITE"
            ],
        )

        return (
            y
            + h
            + pad_y * 2
        )

    draw.text(
        (
            x,
            y,
        ),
        texto,
        font=f,
        fill=COLORS[
            accent
        ],
    )

    # underline discreto
    draw.line(
        (
            x,
            y + h + 5,
            x + min(
                w,
                280,
            ),
            y + h + 5,
        ),
        fill=COLORS[
            accent
        ],
        width=4,
    )

    return (
        y
        + h
        + 8
    )


def render_wave(
    caminho_foto,
    copy,
    pedido,
    render_overrides=None,
):
    overrides = (
        render_overrides
        or {}
    )

    tema_nome = (
        overrides.get("wave_theme")
        or detectar_tema_wave(pedido)
    )
    tema = WAVE_THEMES.get(
        tema_nome,
        WAVE_THEMES["coral"],
    )

    print(
        "Dynamic wave theme:",
        tema_nome,
        flush=True,
    )

    canvas = crop_foto(
        caminho_foto
    )

    canvas = desenhar_wave_overlay(
        canvas,
        tema,
    )

    draw = ImageDraw.Draw(
        canvas
    )

    ajuste_fino = bool(
        overrides.get(
            "layout_fine_tune"
        )
    )

    if ajuste_fino:
        # Um único eixo visual para headline, régua,
        # apoio e CTA.
        x = 66
        text_right = 770
        largura_texto = (
            text_right
            - x
        )

        # Mais respiro superior no bloco textual.
        y = 928

    else:
        x = 58
        text_right = 760
        largura_texto = (
            text_right
            - x
        )

        y = 920

    ocultar_badge = bool(
        overrides.get(
            "hide_badge"
        )
    )

    preservar_slot_badge = bool(
        overrides.get(
            "preserve_removed_space"
        )
        or overrides.get(
            "preserve_positions"
        )
    )

    mostrar_badge = (
        pedido_tem_aula_experimental(
            pedido
        )
        and not ocultar_badge
    )

    if mostrar_badge:
        y = desenhar_badge(
            draw,
            x,
            y,
            "AULA EXPERIMENTAL",
        )

        y += 24

    elif (
        ocultar_badge
        and preservar_slot_badge
    ):
        # Remoção realmente cirúrgica:
        # o badge desaparece, mas TODO o restante permanece
        # exatamente na mesma posição vertical.
        y += altura_slot_badge(
            draw,
            "AULA EXPERIMENTAL",
        )

    else:
        # Criação que originalmente não possui badge:
        # não reservamos um espaço fantasma.
        y += 16

    headline = (
        copy.get(
            "headline"
        )
        or ""
    )

    headline_size = tamanho_headline(
        draw,
        headline,
        largura_texto,
    )

    y = desenhar_multilinha(
        draw,
        headline,
        x,
        y,
        largura_texto,
        headline_size,
        COLORS[
            "WHITE"
        ],
        peso="bold",
        espacamento=0,
        max_linhas=3,
    )

    # assinatura horizontal
    linha_gap = (
        14
        if ajuste_fino
        else 11
    )

    draw.line(
        (
            x,
            y + linha_gap,
            x + 195,
            y + linha_gap,
        ),
        fill=COLORS[
            "WHITE"
        ],
        width=5,
    )

    y += (
        44
        if ajuste_fino
        else 38
    )

    apoio = (
        copy.get(
            "support"
        )
        or ""
    )

    support_size = 25

    if len(
        apoio
    ) > 82:
        support_size = 23

    y = desenhar_multilinha(
        draw,
        apoio,
        x,
        y,
        largura_texto,
        support_size,
        COLORS[
            "WHITE"
        ],
        peso="regular",
        espacamento=5,
        max_linhas=3,
    )

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

    # reservamos espaço inferior para não cortar CTA
    cta_y = min(
        y
        + (
            26
            if ajuste_fino
            else 18
        ),
        1280,
    )

    if (
        cta_y < 1320
        and cta
    ):
        desenhar_cta(
            draw,
            cta,
            x,
            cta_y,
            emphasis=bool(
                overrides.get(
                    "cta_emphasis"
                )
            ),
            font_delta=(
                overrides.get(
                    "cta_font_delta",
                    0,
                )
            ),
            accent=tema["accent"],
        )

    return canvas


def render_dynamic(
    caminho_foto,
    copy,
    pedido,
    foto,
    composition_override=None,
    background_override=None,
    render_overrides=None,
):
    """
    Renderer Dynamic oficial.

    A família Dynamic utiliza DYNAMIC_WAVE como composição
    padrão. Mantemos compatibilidade com composition_override,
    mas qualquer composição desconhecida cai de forma segura
    no DYNAMIC_WAVE.
    """

    composition = (
        composition_override
        or "DYNAMIC_WAVE"
    )

    if composition not in {
        "DYNAMIC_WAVE",
    }:
        composition = (
            "DYNAMIC_WAVE"
        )

    canvas = render_wave(
        caminho_foto,
        copy,
        pedido,
        render_overrides=(
            render_overrides
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
        "composition": composition,
        "family": (
            "SLIMFIT_DYNAMIC"
        ),
        "background_style": (
            background_override
            or composition
        ),
        "width": WIDTH,
        "height": HEIGHT,
    }
