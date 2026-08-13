import hashlib
import os
import re
import tempfile

from PIL import (
    Image,
    ImageDraw,
    ImageFont,
    ImageOps,
)

from face_framing import detectar_foco_rosto
from photo_style import tratar_foto

from adaptive_layout import (
    altura_linhas,
    calcular_bloco,
    calcular_topo_por_rodape,
    medir,
    hex_rgb,
)


WIDTH = 1080
HEIGHT = 1350


COLORS = {
    "tiffany": "#11ACB0",
    "coral": "#F37A73",
    "charcoal": "#2F2B30",
    "dark": "#232125",
    "white": "#FFFFFF",
    "off_white": "#F4F4F2",
}


EVENT_STYLES = {
    "EVENT_CHARCOAL": {
        "surface": "#232125",
        "headline": "#FFFFFF",
        "support": "#F4F4F2",
        "accent": "#11ACB0",
        "second": "#F37A73",
    },

    "EVENT_TIFFANY": {
        "surface": "#087F82",
        "headline": "#FFFFFF",
        "support": "#FFFFFF",
        "accent": "#FFFFFF",
        "second": "#F37A73",
    },

    "EVENT_CORAL": {
        "surface": "#C85F59",
        "headline": "#FFFFFF",
        "support": "#FFFFFF",
        "accent": "#FFFFFF",
        "second": "#11ACB0",
    },
}


VALID_EVENT_LAYOUTS = {
    "EVENT_CENTER",
    "EVENT_EDITORIAL",
}


# =========================================================
# FONTES
# =========================================================

def localizar_fonte(
    peso="regular",
):
    if peso == "bold":
        candidatos = [
            "/app/assets/fonts/Nexa-Bold.ttf",
            "/app/assets/fonts/Nexa-Bold.otf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    else:
        candidatos = [
            "/app/assets/fonts/Nexa-Regular.ttf",
            "/app/assets/fonts/Nexa-Regular.otf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]

    for caminho in candidatos:
        if os.path.exists(
            caminho
        ):
            return caminho

    return None


def fonte(
    tamanho,
    peso="regular",
):
    caminho = localizar_fonte(
        peso
    )

    if caminho:
        return ImageFont.truetype(
            caminho,
            tamanho,
        )

    return ImageFont.load_default()


# =========================================================
# FOTO
# =========================================================

def preparar_foto(
    caminho,
    centering=(0.5, 0.40),
):
    imagem = tratar_foto(
        Image.open(caminho)
    )

    # Centraliza no(s) rosto(s) e protege a cabeça; sem rosto, usa o
    # centering padrão do layout como fallback.
    foco = detectar_foco_rosto(
        imagem,
        default=centering,
    )

    print(
        "Event framing: foco=",
        foco,
        flush=True,
    )

    return ImageOps.fit(
        imagem,
        (
            WIDTH,
            HEIGHT,
        ),
        method=Image.Resampling.LANCZOS,
        centering=foco,
    )


# =========================================================
# COR
# =========================================================

# =========================================================
# TEXTO
# =========================================================

def quebrar(
    draw,
    texto,
    font,
    largura_max,
):
    palavras = (
        texto
        or ""
    ).split()

    linhas = []
    atual = ""

    for palavra in palavras:
        teste = (
            palavra
            if not atual
            else f"{atual} {palavra}"
        )

        largura, _ = medir(
            draw,
            teste,
            font,
        )

        if largura <= largura_max:
            atual = teste

        else:
            if atual:
                linhas.append(
                    atual
                )

            atual = palavra

    if atual:
        linhas.append(
            atual
        )

    return linhas


def desenhar_multilinha(
    draw,
    texto,
    x,
    y,
    largura_max,
    tamanho,
    cor,
    peso="regular",
    espacamento=7,
):
    if not texto:
        return y

    font = fonte(
        tamanho,
        peso,
    )

    linhas = quebrar(
        draw,
        texto,
        font,
        largura_max,
    )

    atual_y = y

    for linha in linhas:
        draw.text(
            (
                x,
                atual_y,
            ),
            linha,
            font=font,
            fill=cor,
        )

        _, altura = medir(
            draw,
            linha,
            font,
        )

        atual_y += (
            altura
            + espacamento
        )

    return atual_y


# =========================================================
# DATA / HORÁRIO
# =========================================================

MESES = (
    "janeiro|fevereiro|março|marco|abril|maio|junho|"
    "julho|agosto|setembro|outubro|novembro|dezembro"
)


def extrair_data(
    pedido,
):
    texto = (
        pedido
        or ""
    )

    padroes = [
        r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b",
        rf"\b\d{{1,2}}\s+de\s+(?:{MESES})\b",
    ]

    for padrao in padroes:
        match = re.search(
            padrao,
            texto,
            flags=re.IGNORECASE,
        )

        if match:
            return (
                match
                .group(0)
                .strip()
            )

    return ""


def extrair_horario(
    pedido,
):
    texto = (
        pedido
        or ""
    )

    padroes = [
        r"\b\d{1,2}:\d{2}\b",
        r"\b\d{1,2}h\d{0,2}\b",
        r"\b(?:às|as)\s+\d{1,2}(?::\d{2})?\b",
    ]

    for padrao in padroes:
        match = re.search(
            padrao,
            texto,
            flags=re.IGNORECASE,
        )

        if match:
            valor = (
                match
                .group(0)
                .strip()
            )

            return re.sub(
                r"^(às|as)\s+",
                "",
                valor,
                flags=re.IGNORECASE,
            )

    return ""


def extrair_dia_semana(
    pedido,
):
    texto = (
        pedido
        or ""
    ).lower()

    mapa = [
        ("segunda", "SEGUNDA"),
        ("terça", "TERÇA"),
        ("terca", "TERÇA"),
        ("quarta", "QUARTA"),
        ("quinta", "QUINTA"),
        ("sexta", "SEXTA"),
        ("sábado", "SÁBADO"),
        ("sabado", "SÁBADO"),
        ("domingo", "DOMINGO"),
    ]

    for termo, saida in mapa:
        if termo in texto:
            return saida

    return ""


def metadata_evento(
    pedido,
):
    return {
        "date": extrair_data(
            pedido
        ),
        "time": extrair_horario(
            pedido
        ),
        "weekday": extrair_dia_semana(
            pedido
        ),
    }


def texto_metadata(
    meta,
):
    partes = []

    if meta.get(
        "weekday"
    ):
        partes.append(
            meta[
                "weekday"
            ]
        )

    if meta.get(
        "date"
    ):
        partes.append(
            meta[
                "date"
            ].upper()
        )

    if meta.get(
        "time"
    ):
        partes.append(
            meta[
                "time"
            ].upper()
        )

    return "  •  ".join(
        partes
    )


# =========================================================
# ESCOLHAS
# =========================================================

def escolher_layout(
    pedido,
    layout_override=None,
):
    if (
        layout_override
        in VALID_EVENT_LAYOUTS
    ):
        return layout_override

    texto = (
        pedido
        or ""
    ).lower()

    if any(
        termo in texto
        for termo in [
            "editorial",
            "sofisticado",
            "sofisticada",
            "premium",
            "elegante",
        ]
    ):
        return "EVENT_EDITORIAL"

    return "EVENT_CENTER"


def escolher_estilo(
    pedido,
    foto,
    style_override=None,
):
    if (
        style_override
        in EVENT_STYLES
    ):
        return style_override

    texto = (
        pedido
        or ""
    ).lower()

    if any(
        termo in texto
        for termo in [
            "tiffany",
            "turquesa",
        ]
    ):
        return "EVENT_TIFFANY"

    if any(
        termo in texto
        for termo in [
            "coral",
            "quente",
            "vibrante",
        ]
    ):
        return "EVENT_CORAL"

    chave = (
        f"{pedido}|"
        f"{foto.get('filename')}"
    )

    valor = int(
        hashlib.sha256(
            chave.encode(
                "utf-8"
            )
        ).hexdigest(),
        16,
    )

    opcoes = [
        "EVENT_CHARCOAL",
        "EVENT_CHARCOAL",
        "EVENT_TIFFANY",
        "EVENT_CORAL",
    ]

    return opcoes[
        valor % len(opcoes)
    ]


# =========================================================
# MEDIÇÃO ADAPTATIVA
# =========================================================

def medir_conteudo_evento(
    draw,
    copy,
    meta,
):
    headline_font = fonte(
        61,
        "bold",
    )

    support_font = fonte(
        26,
        "regular",
    )

    cta_font = fonte(
        25,
        "bold",
    )

    headline_height = altura_linhas(
        draw,
        copy.get(
            "headline"
        ),
        headline_font,
        820,
        quebrar,
        espacamento=2,
    )

    support_height = altura_linhas(
        draw,
        copy.get(
            "support"
        ),
        support_font,
        790,
        quebrar,
        espacamento=6,
    )

    cta_height = altura_linhas(
        draw,
        copy.get(
            "cta"
        ),
        cta_font,
        620,
        quebrar,
        espacamento=4,
    )

    meta_text = texto_metadata(
        meta
    )

    meta_height = 0

    if meta_text:
        meta_font = fonte(
            25,
            "bold",
        )

        _, texto_h = medir(
            draw,
            meta_text,
            meta_font,
        )

        # altura do chip completo
        meta_height = (
            texto_h
            + 24
        )

    bloco_altura = calcular_bloco(
        headline_height=(
            headline_height
        ),
        support_height=(
            support_height
        ),
        cta_height=(
            cta_height
        ),
        meta_height=(
            meta_height
        ),
        padding_top=48,
        padding_bottom=52,
        gap_meta_headline=27,
        gap_headline_support=32,
        gap_support_cta=18,

        # ~25% a ~42% do post.
        minimum_height=335,
        maximum_height=565,
    )

    return {
        "headline_height": (
            headline_height
        ),
        "support_height": (
            support_height
        ),
        "cta_height": (
            cta_height
        ),
        "meta_height": (
            meta_height
        ),
        "block_height": (
            bloco_altura
        ),
    }


# =========================================================
# CHIP DATA
# =========================================================

def desenhar_data_box(
    draw,
    x,
    y,
    meta,
    estilo,
):
    texto = texto_metadata(
        meta
    )

    if not texto:
        return y

    font = fonte(
        25,
        "bold",
    )

    largura, altura = medir(
        draw,
        texto,
        font,
    )

    pad_x = 22
    pad_y = 12

    draw.rounded_rectangle(
        (
            x,
            y,
            x + largura + pad_x * 2,
            y + altura + pad_y * 2,
        ),
        radius=22,
        fill=estilo[
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
        fill=COLORS[
            "charcoal"
        ],
    )

    return (
        y
        + altura
        + pad_y * 2
    )


# =========================================================
# EVENT CENTER
# =========================================================

def render_center(
    caminho_foto,
    copy,
    pedido,
    estilo,
):
    foto = preparar_foto(
        caminho_foto,
        centering=(
            0.5,
            0.38,
        ),
    )

    canvas = foto.convert(
        "RGBA"
    )

    # Canvas temporário só para medir.
    draw_medida = ImageDraw.Draw(
        canvas
    )

    meta = metadata_evento(
        pedido
    )

    medidas = medir_conteudo_evento(
        draw_medida,
        copy,
        meta,
    )

    bloco_altura = medidas[
        "block_height"
    ]

    # Fundo termina antes do fim do arquivo para
    # manter respiro e não parecer um rodapé gigante.
    painel_bottom = 1245

    painel_top = calcular_topo_por_rodape(
        HEIGHT,
        bloco_altura,
        HEIGHT - painel_bottom,
    )

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

    draw_overlay = ImageDraw.Draw(
        overlay
    )

    # Proteção global mínima.
    draw_overlay.rectangle(
        (
            0,
            0,
            WIDTH,
            HEIGHT,
        ),
        fill=(
            18,
            18,
            20,
            16,
        ),
    )

    r, g, b = hex_rgb(
        estilo[
            "surface"
        ]
    )

    draw_overlay.rounded_rectangle(
        (
            42,
            painel_top,
            1038,
            painel_bottom,
        ),
        radius=48,
        fill=(
            r,
            g,
            b,
            218,
        ),
    )

    canvas.alpha_composite(
        overlay
    )

    draw = ImageDraw.Draw(
        canvas
    )

    margem = 72

    y = (
        painel_top
        + 38
    )

    # Acento curto, proporcional.
    draw.line(
        (
            margem,
            y,
            margem + 145,
            y,
        ),
        fill=estilo[
            "second"
        ],
        width=5,
    )

    y += 28

    if texto_metadata(
        meta
    ):
        y = desenhar_data_box(
            draw,
            margem,
            y,
            meta,
            estilo,
        )

        y += 27

    y = desenhar_multilinha(
        draw,
        copy[
            "headline"
        ],
        margem,
        y,
        820,
        61,
        estilo[
            "headline"
        ],
        peso="bold",
        espacamento=2,
    )

    draw.line(
        (
            margem,
            y + 11,
            margem + 160,
            y + 11,
        ),
        fill=estilo[
            "accent"
        ],
        width=5,
    )

    if copy.get(
        "support"
    ):
        y = desenhar_multilinha(
            draw,
            copy[
                "support"
            ],
            margem,
            y + 34,
            790,
            26,
            estilo[
                "support"
            ],
            peso="regular",
            espacamento=6,
        )

    if copy.get(
        "cta"
    ):
        desenhar_multilinha(
            draw,
            copy[
                "cta"
            ],
            margem,
            y + 18,
            620,
            25,
            estilo[
                "second"
            ],
            peso="bold",
            espacamento=4,
        )

    # Arco acompanha a dimensão real do bloco.
    arco_size = min(
        360,
        bloco_altura
    )

    draw.arc(
        (
            810,
            painel_bottom - arco_size + 35,
            1175,
            painel_bottom + 35,
        ),
        start=125,
        end=287,
        fill=estilo[
            "accent"
        ],
        width=3,
    )

    return canvas.convert(
        "RGB"
    )


# =========================================================
# EVENT EDITORIAL
# =========================================================

def render_editorial(
    caminho_foto,
    copy,
    pedido,
    estilo,
):
    foto = preparar_foto(
        caminho_foto,
        centering=(
            0.5,
            0.37,
        ),
    )

    canvas = foto.convert(
        "RGBA"
    )

    draw_medida = ImageDraw.Draw(
        canvas
    )

    meta = metadata_evento(
        pedido
    )

    medidas = medir_conteudo_evento(
        draw_medida,
        copy,
        meta,
    )

    bloco_altura = medidas[
        "block_height"
    ]

    painel_bottom = HEIGHT

    base_top = calcular_topo_por_rodape(
        HEIGHT,
        bloco_altura,
        0,
    )

    # Editorial inclina sem transformar uma copy curta
    # em metade do post.
    left_top = max(
        710,
        base_top - 25,
    )

    right_top = max(
        675,
        base_top - 80,
    )

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

    draw_overlay = ImageDraw.Draw(
        overlay
    )

    r, g, b = hex_rgb(
        estilo[
            "surface"
        ]
    )

    draw_overlay.polygon(
        [
            (
                0,
                left_top,
            ),
            (
                WIDTH,
                right_top,
            ),
            (
                WIDTH,
                painel_bottom,
            ),
            (
                0,
                painel_bottom,
            ),
        ],
        fill=(
            r,
            g,
            b,
            230,
        ),
    )

    canvas.alpha_composite(
        overlay
    )

    draw = ImageDraw.Draw(
        canvas
    )

    margem = 68

    y = max(
        left_top,
        right_top,
    ) + 42

    if texto_metadata(
        meta
    ):
        y = desenhar_data_box(
            draw,
            margem,
            y,
            meta,
            estilo,
        )

        y += 28

    y = desenhar_multilinha(
        draw,
        copy[
            "headline"
        ],
        margem,
        y,
        820,
        61,
        estilo[
            "headline"
        ],
        peso="bold",
        espacamento=2,
    )

    draw.line(
        (
            margem,
            y + 11,
            margem + 160,
            y + 11,
        ),
        fill=estilo[
            "accent"
        ],
        width=5,
    )

    if copy.get(
        "support"
    ):
        y = desenhar_multilinha(
            draw,
            copy[
                "support"
            ],
            margem,
            y + 34,
            760,
            26,
            estilo[
                "support"
            ],
        )

    if copy.get(
        "cta"
    ):
        desenhar_multilinha(
            draw,
            copy[
                "cta"
            ],
            margem,
            y + 18,
            620,
            25,
            estilo[
                "second"
            ],
            peso="bold",
        )

    # Grafismos proporcionais à área ocupada.
    draw.arc(
        (
            -260,
            right_top - 120,
            830,
            1360,
        ),
        start=205,
        end=330,
        fill=estilo[
            "accent"
        ],
        width=4,
    )

    draw.arc(
        (
            -300,
            right_top - 95,
            870,
            1390,
        ),
        start=205,
        end=330,
        fill=estilo[
            "second"
        ],
        width=3,
    )

    return canvas.convert(
        "RGB"
    )


# =========================================================
# RENDER
# =========================================================

def render_event(
    caminho_foto,
    copy,
    pedido,
    foto,
    layout_override=None,
    background_override=None,
):
    layout = escolher_layout(
        pedido,
        layout_override=(
            layout_override
        ),
    )

    background_style = escolher_estilo(
        pedido,
        foto,
        style_override=(
            background_override
        ),
    )

    estilo = EVENT_STYLES[
        background_style
    ]

    if (
        layout
        == "EVENT_EDITORIAL"
    ):
        canvas = render_editorial(
            caminho_foto,
            copy,
            pedido,
            estilo,
        )

    else:
        canvas = render_center(
            caminho_foto,
            copy,
            pedido,
            estilo,
        )

    temp = tempfile.NamedTemporaryFile(
        suffix=".png",
        delete=False,
    )

    caminho_saida = temp.name
    temp.close()

    canvas.save(
        caminho_saida,
        "PNG",
    )

    return {
        "image_path": caminho_saida,
        "composition": layout,
        "family": "SLIMFIT_EVENT",
        "background_style": (
            background_style
        ),
        "event_meta": metadata_evento(
            pedido
        ),
    }
