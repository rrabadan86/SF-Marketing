import math
import os
import re
import tempfile

from PIL import (
    Image,
    ImageDraw,
    ImageFont,
    ImageOps,
    ImageFilter,
)

from adaptive_layout import (
    altura_linhas,
    calcular_bloco,
)


WIDTH = 1080
HEIGHT = 1350


COLORS = {
    "TIFFANY": "#11ACB0",
    "CORAL": "#F37A73",
    "DARK_SILVER": "#707071",
    "CHARCOAL": "#2F2B30",
    "WHITE": "#FFFFFF",
    "OFF_WHITE": "#F4F4F2",

    "CAMPAIGN_YELLOW": "#FFD600",
    "CAMPAIGN_GREEN": "#005A4E",
}


VALID_ARCHETYPES = {
    "SEASONAL_CLEAN",
    "SEASONAL_PHOTO",
    "SEASONAL_PROMO",
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
# TEXTO
# =========================================================

def medir(
    draw,
    texto,
    font,
):
    bbox = draw.textbbox(
        (0, 0),
        texto,
        font=font,
    )

    return (
        bbox[2] - bbox[0],
        bbox[3] - bbox[1],
    )


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
    alinhamento="left",
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
        largura, altura = medir(
            draw,
            linha,
            font,
        )

        if alinhamento == "center":
            linha_x = (
                x
                + (
                    largura_max
                    - largura
                )
                / 2
            )

        elif alinhamento == "right":
            linha_x = (
                x
                + largura_max
                - largura
            )

        else:
            linha_x = x

        draw.text(
            (
                int(
                    linha_x
                ),
                int(
                    atual_y
                ),
            ),
            linha,
            font=font,
            fill=cor,
        )

        atual_y += (
            altura
            + espacamento
        )

    return atual_y


def desenhar_multilinha_destaque(
    draw,
    texto,
    x,
    y,
    largura_max,
    tamanho,
    cor_base,
    cor_destaque,
    peso="bold",
    alinhamento="center",
    espacamento=4,
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

    palavras = (
        texto
        or ""
    ).split()

    destaque = ""

    ignorar = {
        "a",
        "o",
        "as",
        "os",
        "de",
        "da",
        "do",
        "das",
        "dos",
        "e",
        "em",
        "para",
        "por",
        "um",
        "uma",
        "no",
        "na",
        "nos",
        "nas",
    }

    for palavra in reversed(
        palavras
    ):
        limpa = (
            palavra
            .strip(
                ".,!?;:"
            )
            .lower()
        )

        if (
            limpa
            and limpa
            not in ignorar
        ):
            destaque = limpa
            break

    atual_y = y

    for linha in linhas:
        palavras_linha = (
            linha.split()
        )

        larguras = []

        for palavra in palavras_linha:
            largura, _ = medir(
                draw,
                palavra + " ",
                font,
            )

            larguras.append(
                largura
            )

        largura_linha = sum(
            larguras
        )

        if alinhamento == "center":
            atual_x = (
                x
                + (
                    largura_max
                    - largura_linha
                )
                / 2
            )

        elif alinhamento == "right":
            atual_x = (
                x
                + largura_max
                - largura_linha
            )

        else:
            atual_x = x

        altura_linha = 0

        for palavra, largura in zip(
            palavras_linha,
            larguras,
        ):
            limpa = (
                palavra
                .strip(
                    ".,!?;:"
                )
                .lower()
            )

            cor = (
                cor_destaque
                if (
                    destaque
                    and limpa
                    == destaque
                )
                else cor_base
            )

            draw.text(
                (
                    int(
                        atual_x
                    ),
                    int(
                        atual_y
                    ),
                ),
                palavra,
                font=font,
                fill=cor,
            )

            _, altura = medir(
                draw,
                palavra,
                font,
            )

            altura_linha = max(
                altura_linha,
                altura,
            )

            atual_x += largura

        atual_y += (
            altura_linha
            + espacamento
        )

    return atual_y


# =========================================================
# CORES
# =========================================================

def hex_rgb(
    hexadecimal,
):
    hexadecimal = (
        hexadecimal
        .lstrip("#")
    )

    return tuple(
        int(
            hexadecimal[
                i:i + 2
            ],
            16,
        )
        for i in (
            0,
            2,
            4,
        )
    )


def limitar(
    valor,
    minimo,
    maximo,
):
    return max(
        minimo,
        min(
            maximo,
            valor,
        ),
    )


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
        (
            "segunda",
            "SEGUNDA",
        ),
        (
            "terça",
            "TERÇA",
        ),
        (
            "terca",
            "TERÇA",
        ),
        (
            "quarta",
            "QUARTA",
        ),
        (
            "quinta",
            "QUINTA",
        ),
        (
            "sexta",
            "SEXTA",
        ),
        (
            "sábado",
            "SÁBADO",
        ),
        (
            "sabado",
            "SÁBADO",
        ),
        (
            "domingo",
            "DOMINGO",
        ),
    ]

    for termo, saida in mapa:
        if termo in texto:
            return saida

    return ""


def metadata_evento(
    pedido,
):
    partes = []

    dia = extrair_dia_semana(
        pedido
    )

    data = extrair_data(
        pedido
    )

    horario = extrair_horario(
        pedido
    )

    if dia:
        partes.append(
            dia
        )

    if data:
        partes.append(
            data.upper()
        )

    if horario:
        partes.append(
            horario.upper()
        )

    return " • ".join(
        partes
    )


# =========================================================
# PALETA
# =========================================================

def definir_paleta(
    direction,
    archetype,
):
    cores = direction.get(
        "preferred_colors",
        [],
    )

    if (
        archetype
        == "SEASONAL_PROMO"
    ):
        if (
            "CAMPAIGN_GREEN"
            in cores
        ):
            fundo = COLORS[
                "CAMPAIGN_GREEN"
            ]

        else:
            fundo = COLORS[
                "CHARCOAL"
            ]

        destaque = (
            COLORS[
                "CAMPAIGN_YELLOW"
            ]
            if (
                "CAMPAIGN_YELLOW"
                in cores
            )
            else COLORS[
                "TIFFANY"
            ]
        )

        return {
            "background": fundo,
            "surface": COLORS[
                "WHITE"
            ],
            "headline": COLORS[
                "WHITE"
            ],
            "support": COLORS[
                "WHITE"
            ],
            "accent": destaque,
            "second": COLORS[
                "CORAL"
            ],
            "dark_text": COLORS[
                "CHARCOAL"
            ],
        }

    if (
        archetype
        == "SEASONAL_PHOTO"
    ):
        return {
            "background": COLORS[
                "TIFFANY"
            ],
            "surface": COLORS[
                "OFF_WHITE"
            ],
            "headline": COLORS[
                "DARK_SILVER"
            ],
            "support": COLORS[
                "DARK_SILVER"
            ],
            "accent": COLORS[
                "TIFFANY"
            ],
            "second": COLORS[
                "CORAL"
            ],
            "dark_text": COLORS[
                "CHARCOAL"
            ],
        }

    return {
        "background": COLORS[
            "OFF_WHITE"
        ],
        "surface": COLORS[
            "WHITE"
        ],
        "headline": COLORS[
            "DARK_SILVER"
        ],
        "support": COLORS[
            "DARK_SILVER"
        ],
        "accent": COLORS[
            "TIFFANY"
        ],
        "second": COLORS[
            "CORAL"
        ],
        "dark_text": COLORS[
            "CHARCOAL"
        ],
    }


# =========================================================
# MEDIÇÃO ADAPTATIVA
# =========================================================

def medir_copy(
    draw,
    copy,
    headline_size,
    headline_width,
    support_width,
):
    headline_font = fonte(
        headline_size,
        "bold",
    )

    support_font = fonte(
        27,
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
        headline_width,
        quebrar,
        espacamento=4,
    )

    support_height = altura_linhas(
        draw,
        copy.get(
            "support"
        ),
        support_font,
        support_width,
        quebrar,
        espacamento=8,
    )

    cta_height = altura_linhas(
        draw,
        copy.get(
            "cta"
        ),
        cta_font,
        support_width,
        quebrar,
        espacamento=5,
    )

    return {
        "headline": (
            headline_height
        ),

        "support": (
            support_height
        ),

        "cta": (
            cta_height
        ),
    }


# =========================================================
# GRAFISMOS
# =========================================================

def desenhar_curvas_laterais(
    draw,
    cor1,
    cor2,
):
    draw.arc(
        (
            -330,
            100,
            410,
            930,
        ),
        start=275,
        end=80,
        fill=cor1,
        width=4,
    )

    draw.arc(
        (
            -290,
            150,
            460,
            1010,
        ),
        start=275,
        end=80,
        fill=cor2,
        width=3,
    )

    draw.arc(
        (
            790,
            560,
            1340,
            1310,
        ),
        start=95,
        end=260,
        fill=cor1,
        width=4,
    )


def desenhar_coracoes(
    draw,
    cor,
):
    pontos = [
        (
            135,
            330,
            18,
        ),
        (
            925,
            420,
            14,
        ),
        (
            165,
            1025,
            12,
        ),
    ]

    for x, y, tamanho in pontos:
        r = tamanho

        draw.ellipse(
            (
                x,
                y,
                x + r,
                y + r,
            ),
            fill=cor,
        )

        draw.ellipse(
            (
                x + r - 2,
                y,
                x + r * 2 - 2,
                y + r,
            ),
            fill=cor,
        )

        draw.polygon(
            [
                (
                    x,
                    y + r // 2,
                ),
                (
                    x + r * 2 - 2,
                    y + r // 2,
                ),
                (
                    x + r - 1,
                    y + r * 2,
                ),
            ],
            fill=cor,
        )


def desenhar_estrelas(
    draw,
    cor,
):
    pontos = [
        (
            110,
            320,
            14,
        ),
        (
            920,
            350,
            11,
        ),
        (
            870,
            1040,
            16,
        ),
        (
            165,
            1110,
            10,
        ),
    ]

    for cx, cy, raio in pontos:
        coords = []

        for i in range(
            10
        ):
            angulo = (
                -math.pi / 2
                + i * math.pi / 5
            )

            r = (
                raio
                if i % 2 == 0
                else raio * 0.42
            )

            coords.append(
                (
                    cx
                    + math.cos(
                        angulo
                    ) * r,

                    cy
                    + math.sin(
                        angulo
                    ) * r,
                )
            )

        draw.polygon(
            coords,
            fill=cor,
        )


# =========================================================
# CLEAN
# =========================================================

def render_clean(
    copy,
    pedido,
    direction,
):
    paleta = definir_paleta(
        direction,
        "SEASONAL_CLEAN",
    )

    canvas = Image.new(
        "RGB",
        (
            WIDTH,
            HEIGHT,
        ),
        paleta[
            "background"
        ],
    )

    draw = ImageDraw.Draw(
        canvas
    )

    elementos = set(
        direction.get(
            "graphic_elements",
            [],
        )
    )

    desenhar_curvas_laterais(
        draw,
        paleta[
            "accent"
        ],
        paleta[
            "second"
        ],
    )

    if (
        "HEART"
        in elementos
    ):
        desenhar_coracoes(
            draw,
            paleta[
                "accent"
            ],
        )

    if (
        "BOTANICAL"
        in elementos
    ):
        for deslocamento in range(
            0,
            5,
        ):
            draw.arc(
                (
                    40
                    + deslocamento * 18,

                    155
                    + deslocamento * 24,

                    330
                    + deslocamento * 24,

                    650
                    + deslocamento * 30,
                ),
                start=110,
                end=225,
                fill=COLORS[
                    "DARK_SILVER"
                ],
                width=2,
            )

        for deslocamento in range(
            0,
            4,
        ):
            draw.arc(
                (
                    760
                    - deslocamento * 20,

                    770
                    - deslocamento * 25,

                    1080
                    - deslocamento * 20,

                    1300
                    - deslocamento * 10,
                ),
                start=285,
                end=65,
                fill=COLORS[
                    "DARK_SILVER"
                ],
                width=2,
            )

    caixa_x = 135
    caixa_w = 810

    medidas = medir_copy(
        draw,
        copy,
        headline_size=68,
        headline_width=760,
        support_width=660,
    )

    meta = metadata_evento(
        pedido
    )

    meta_h = (
        46
        if meta
        else 0
    )

    bloco_h = calcular_bloco(
        headline_height=(
            medidas[
                "headline"
            ]
        ),
        support_height=(
            medidas[
                "support"
            ]
        ),
        cta_height=(
            medidas[
                "cta"
            ]
        ),
        meta_height=meta_h,
        padding_top=65,
        padding_bottom=65,
        gap_meta_headline=30,
        gap_headline_support=34,
        gap_support_cta=24,
        minimum_height=430,
        maximum_height=690,
    )

    caixa_y = int(
        (
            HEIGHT
            - bloco_h
        )
        / 2
    )

    draw.rounded_rectangle(
        (
            caixa_x,
            caixa_y,
            caixa_x + caixa_w,
            caixa_y + bloco_h,
        ),
        radius=58,
        fill=paleta[
            "surface"
        ],
    )

    y = (
        caixa_y
        + 58
    )

    if meta:
        meta_font = fonte(
            23,
            "bold",
        )

        meta_w, meta_text_h = medir(
            draw,
            meta,
            meta_font,
        )

        draw.rounded_rectangle(
            (
                WIDTH / 2
                - meta_w / 2
                - 20,

                y,

                WIDTH / 2
                + meta_w / 2
                + 20,

                y
                + meta_text_h
                + 18,
            ),
            radius=20,
            fill=paleta[
                "accent"
            ],
        )

        draw.text(
            (
                WIDTH / 2
                - meta_w / 2,

                y + 7,
            ),
            meta,
            font=meta_font,
            fill=COLORS[
                "WHITE"
            ],
        )

        y += (
            meta_text_h
            + 48
        )

    y = desenhar_multilinha_destaque(
        draw,
        copy.get(
            "headline",
            ""
        ),
        160,
        y,
        760,
        68,
        paleta[
            "headline"
        ],
        paleta[
            "accent"
        ],
        peso="bold",
        alinhamento="center",
        espacamento=4,
    )

    draw.line(
        (
            430,
            y + 22,
            650,
            y + 22,
        ),
        fill=paleta[
            "accent"
        ],
        width=4,
    )

    y += 52

    if copy.get(
        "support"
    ):
        y = desenhar_multilinha(
            draw,
            copy[
                "support"
            ],
            210,
            y,
            660,
            27,
            paleta[
                "support"
            ],
            alinhamento="center",
            espacamento=8,
        )

    if copy.get(
        "cta"
    ):
        desenhar_multilinha(
            draw,
            copy[
                "cta"
            ],
            250,
            y + 25,
            580,
            25,
            paleta[
                "accent"
            ],
            peso="bold",
            alinhamento="center",
        )

    return canvas


# =========================================================
# PHOTO
# =========================================================

def render_photo(
    caminho_foto,
    copy,
    pedido,
    direction,
):
    if not caminho_foto:
        raise ValueError(
            "SEASONAL_PHOTO requer fotografia."
        )

    paleta = definir_paleta(
        direction,
        "SEASONAL_PHOTO",
    )

    # -----------------------------------------------------
    # FUNDO TIFFANY
    # -----------------------------------------------------
    #
    # Tiffany funciona como moldura estrutural. A altura do
    # cartão é determinada pela copy e NÃO por um rodapé
    # fixo até 1300px.
    # -----------------------------------------------------

    canvas = Image.new(
        "RGB",
        (
            WIDTH,
            HEIGHT,
        ),
        paleta[
            "background"
        ],
    )

    # -----------------------------------------------------
    # FOTO DOMINANTE
    # -----------------------------------------------------
    #
    # Mantemos a fotografia grande, com margens externas
    # Tiffany. O cartão toca levemente a foto, sem esconder
    # uma faixa relevante da imagem.
    # -----------------------------------------------------

    foto_original = Image.open(
        caminho_foto
    ).convert(
        "RGB"
    )

    foto_x = 45
    foto_y = 42
    foto_w = 990
    foto_h = 970

    foto = ImageOps.fit(
        foto_original,
        (
            foto_w,
            foto_h,
        ),
        method=Image.Resampling.LANCZOS,
        centering=(
            0.5,
            0.43,
        ),
    )

    mascara = Image.new(
        "L",
        (
            foto_w,
            foto_h,
        ),
        0,
    )

    draw_mask = ImageDraw.Draw(
        mascara
    )

    draw_mask.rounded_rectangle(
        (
            0,
            0,
            foto_w,
            foto_h,
        ),
        radius=54,
        fill=255,
    )

    canvas.paste(
        foto,
        (
            foto_x,
            foto_y,
        ),
        mascara,
    )

    draw = ImageDraw.Draw(
        canvas
    )

    # -----------------------------------------------------
    # MEDIÇÃO REAL DO CONTEÚDO
    # -----------------------------------------------------

    medidas = medir_copy(
        draw,
        copy,
        headline_size=56,
        headline_width=820,
        support_width=760,
    )

    meta = metadata_evento(
        pedido
    )

    meta_h = (
        40
        if meta
        else 0
    )

    # -----------------------------------------------------
    # ALTURA REAL DO CARTÃO
    # -----------------------------------------------------
    #
    # A correção principal desta versão é aqui:
    # painel_h é respeitado como altura final do cartão.
    # O cartão não é mais esticado artificialmente porque
    # seu fundo ficava preso em y=1300.
    # -----------------------------------------------------

    painel_h = calcular_bloco(
        headline_height=(
            medidas[
                "headline"
            ]
        ),
        support_height=(
            medidas[
                "support"
            ]
        ),
        cta_height=(
            medidas[
                "cta"
            ]
        ),
        meta_height=(
            meta_h
        ),
        padding_top=20,
        padding_bottom=22,
        gap_meta_headline=14,
        gap_headline_support=12,
        gap_support_cta=10,
        minimum_height=205,
        maximum_height=350,
    )

    foto_bottom = (
        foto_y
        + foto_h
    )

    # O cartão fica um pouco abaixo da fotografia.
    # Isso evita a sensação de que o branco invade a imagem
    # e cria um respiro Tiffany mais elegante entre os blocos.
    espaco_entre_foto_e_cartao = 28

    painel_top = (
        foto_bottom
        + espaco_entre_foto_e_cartao
    )

    painel_bottom = (
        painel_top
        + painel_h
    )

    # Mantém margem Tiffany inferior mínima de 42px.
    margem_inferior = 42
    limite_bottom = (
        HEIGHT
        - margem_inferior
    )

    if painel_bottom > limite_bottom:
        excesso = (
            painel_bottom
            - limite_bottom
        )

        painel_top -= excesso
        painel_bottom -= excesso

    # Mantém o cartão sempre abaixo da fotografia.
    painel_top = max(
        foto_bottom + 20,
        painel_top,
    )

    painel_bottom = (
        painel_top
        + painel_h
    )

    # -----------------------------------------------------
    # CARTÃO
    # -----------------------------------------------------

    painel_x1 = 70
    painel_x2 = 1010

    draw.rounded_rectangle(
        (
            painel_x1,
            painel_top,
            painel_x2,
            painel_bottom,
        ),
        radius=46,
        fill=paleta[
            "surface"
        ],
    )

    # -----------------------------------------------------
    # CURVAS ORGÂNICAS
    # -----------------------------------------------------
    #
    # As linhas ficam imediatamente acima da transição e
    # nunca atravessam o cartão ou a área de leitura.
    # -----------------------------------------------------

    curva_y = (
        painel_top
        - 22
    )

    draw.arc(
        (
            -105,
            curva_y - 95,
            550,
            curva_y + 220,
        ),
        start=205,
        end=323,
        fill=COLORS[
            "CORAL"
        ],
        width=3,
    )

    draw.arc(
        (
            -88,
            curva_y - 78,
            585,
            curva_y + 240,
        ),
        start=205,
        end=323,
        fill=COLORS[
            "WHITE"
        ],
        width=3,
    )

    # -----------------------------------------------------
    # CONTEÚDO
    # -----------------------------------------------------

    y = (
        painel_top
        + 17
    )

    # DATA / HORÁRIO
    if meta:
        meta_font = fonte(
            20,
            "bold",
        )

        meta_w, meta_text_h = medir(
            draw,
            meta,
            meta_font,
        )

        chip_pad_x = 18
        chip_pad_y = 6

        chip_x1 = (
            WIDTH / 2
            - meta_w / 2
            - chip_pad_x
        )

        chip_x2 = (
            WIDTH / 2
            + meta_w / 2
            + chip_pad_x
        )

        draw.rounded_rectangle(
            (
                chip_x1,
                y,
                chip_x2,
                y
                + meta_text_h
                + chip_pad_y * 2,
            ),
            radius=17,
            fill=paleta[
                "accent"
            ],
        )

        draw.text(
            (
                WIDTH / 2
                - meta_w / 2,
                y + chip_pad_y - 1,
            ),
            meta,
            font=meta_font,
            fill=COLORS[
                "WHITE"
            ],
        )

        y += (
            meta_text_h
            + chip_pad_y * 2
            + 13
        )

    # HEADLINE
    y = desenhar_multilinha_destaque(
        draw,
        copy.get(
            "headline",
            ""
        ),
        130,
        y,
        820,
        56,
        paleta[
            "headline"
        ],
        paleta[
            "accent"
        ],
        alinhamento="center",
        espacamento=2,
    )

    # APOIO
    if copy.get(
        "support"
    ):
        y = desenhar_multilinha(
            draw,
            copy[
                "support"
            ],
            160,
            y + 10,
            760,
            25,
            paleta[
                "support"
            ],
            alinhamento="center",
            espacamento=5,
        )

    # CTA
    if copy.get(
        "cta"
    ):
        desenhar_multilinha(
            draw,
            copy[
                "cta"
            ],
            245,
            y + 8,
            590,
            22,
            paleta[
                "accent"
            ],
            peso="bold",
            alinhamento="center",
            espacamento=4,
        )

    return canvas


def badge_promocional(
    pedido,
    campaign_type=None,
):
    """
    Define o badge pelo contexto. Nunca força 'VEM AÍ!'
    quando o pedido indica campanha passada ou solicita
    explicitamente sua retirada.
    """

    texto = (
        pedido
        or ""
    ).lower()

    # Pedidos explícitos de remoção têm prioridade.
    if (
        (
            "retire"
            in texto
            or "remova"
            in texto
            or "sem"
            in texto
        )
        and (
            "vem aí"
            in texto
            or "vem ai"
            in texto
        )
    ):
        return ""

    # Campanha concluída / retrospectiva.
    passado = [
        "foi uma campanha",
        "foi bastante",
        "campanha concluída",
        "campanha concluida",
        "já aconteceu",
        "ja aconteceu",
        "foi desafiadora",
        "foi desafiador",
    ]

    if any(
        termo in texto
        for termo in passado
    ):
        return ""

    # Futuro explícito.
    futuro = [
        "vem aí",
        "vem ai",
        "em breve",
        "vai acontecer",
        "próxima edição",
        "proxima edicao",
        "prepare-se",
        "prepare se",
    ]

    if any(
        termo in texto
        for termo in futuro
    ):
        return "VEM AÍ!"

    # Default atemporal para peças promocionais.
    if campaign_type == "COPA_SLIM":
        return "EDIÇÃO ESPECIAL"

    return ""


# =========================================================
# PROMO
# =========================================================

def render_promo(
    caminho_foto,
    copy,
    pedido,
    direction,
    render_overrides=None,
):
    """
    SEASONAL_PROMO v2

    Direção:
    - mais impacto promocional;
    - fotografia grande e dominante;
    - título muito maior;
    - menos espaço vazio;
    - badge / selo;
    - grafismos esportivos;
    - reserva de área segura no canto inferior direito
      para o logo oficial aplicado pelo publisher.
    """

    render_overrides = (
        render_overrides
        or {}
    )

    paleta = definir_paleta(
        direction,
        "SEASONAL_PROMO",
    )

    canvas = Image.new(
        "RGB",
        (
            WIDTH,
            HEIGHT,
        ),
        paleta[
            "background"
        ],
    )

    draw = ImageDraw.Draw(
        canvas
    )

    hide_badge = bool(
        render_overrides.get(
            "hide_badge"
        )
    )

    hide_cta = bool(
        render_overrides.get(
            "hide_cta"
        )
    )

    hide_campaign_pillars = bool(
        render_overrides.get(
            "hide_campaign_pillars"
        )
    )

    compact_footer_space = bool(
        render_overrides.get(
            "compact_footer_space"
        )
    )

    preserve_removed_space = bool(
        render_overrides.get(
            "preserve_removed_space"
        )
    )


    hide_elements = (
        render_overrides.get(
            "hide_elements"
        )
        or []
    )

    if not isinstance(
        hide_elements,
        list,
    ):
        hide_elements = []

    def _norm_elemento(valor):
        return (
            str(valor)
            .strip()
            .lower()
            .replace("ã", "a")
            .replace("ç", "c")
            .replace("é", "e")
            .replace("í", "i")
            .replace("ó", "o")
            .replace("ú", "u")
        )

    hide_elements_norm = {
        _norm_elemento(
            item
        )
        for item in hide_elements
        if str(item).strip()
    }

    if any(
        item in hide_elements_norm
        for item in [
            "mais movimento",
            "mais conexao",
            "mais slimfit",
        ]
    ):
        hide_campaign_pillars = True


    # -----------------------------------------------------
    # FUNDO DINÂMICO
    # -----------------------------------------------------

    fundo_rgb = hex_rgb(
        paleta[
            "background"
        ]
    )

    tom_escuro = tuple(
        max(
            0,
            componente - 20,
        )
        for componente
        in fundo_rgb
    )

    tom_claro = tuple(
        min(
            255,
            componente + 12,
        )
        for componente
        in fundo_rgb
    )

    # Massa diagonal principal.
    draw.polygon(
        [
            (0, 0),
            (690, 0),
            (385, HEIGHT),
            (0, HEIGHT),
        ],
        fill=tom_escuro,
    )

    # Massa diagonal secundária.
    draw.polygon(
        [
            (760, 0),
            (WIDTH, 0),
            (WIDTH, 780),
            (915, 870),
            (650, 670),
        ],
        fill=tom_claro,
    )

    # Linhas esportivas laterais.
    for deslocamento in range(
        0,
        4,
    ):
        draw.arc(
            (
                -360 + deslocamento * 18,
                650 + deslocamento * 20,
                470 + deslocamento * 35,
                1450 + deslocamento * 20,
            ),
            start=205,
            end=320,
            fill=(
                paleta["accent"]
                if deslocamento % 2 == 0
                else COLORS["TIFFANY"]
            ),
            width=3,
        )

    # -----------------------------------------------------
    # FOTO GRANDE
    # -----------------------------------------------------

    if caminho_foto:
        foto_original = Image.open(
            caminho_foto
        ).convert(
            "RGB"
        )

        foto_x = 82
        foto_y = 92
        foto_w = 916
        foto_h = 545

        photo_mode = str(
            render_overrides.get(
                "photo_mode",
                "cover",
            )
            or "cover"
        ).lower()

        photo_zoom = float(
            render_overrides.get(
                "photo_zoom",
                1.0,
            )
            or 1.0
        )

        photo_zoom = limitar(
            photo_zoom,
            0.82,
            1.20,
        )

        photo_focus_x = float(
            render_overrides.get(
                "photo_focus_x",
                0.5,
            )
            or 0.5
        )

        photo_focus_y = float(
            render_overrides.get(
                "photo_focus_y",
                0.42,
            )
            or 0.42
        )

        photo_focus_x = limitar(
            photo_focus_x,
            0.0,
            1.0,
        )

        photo_focus_y = limitar(
            photo_focus_y,
            0.0,
            1.0,
        )

        avoid_head_crop = bool(
            render_overrides.get(
                "avoid_head_crop"
            )
        )

        mascara = Image.new(
            "L",
            (
                foto_w,
                foto_h,
            ),
            0,
        )

        draw_mask = ImageDraw.Draw(
            mascara
        )

        draw_mask.rounded_rectangle(
            (
                0,
                0,
                foto_w,
                foto_h,
            ),
            radius=52,
            fill=255,
        )

        origem_w, origem_h = (
            foto_original.size
        )

        origem_ratio = (
            origem_w / origem_h
            if origem_h
            else 1.0
        )

        destino_ratio = (
            foto_w / foto_h
        )

        # -------------------------------------------------
        # SAFE COVER PARA RETRATO EM MOLDURA HORIZONTAL
        # -------------------------------------------------
        #
        # O "contain" puro preservava o corpo inteiro, porém
        # criava grandes laterais desfocadas. Para a Copa Slim
        # isso deixava a fotografia pequena e com aparência de
        # montagem.
        #
        # Quando o usuário pede "não cortar a cabeça" em uma
        # foto vertical, usamos cover real, mas ancorado perto
        # do topo. Assim:
        # - a moldura é totalmente preenchida;
        # - não aparecem laterais artificiais;
        # - rosto/cabeça permanecem visíveis;
        # - medalha e tronco ganham protagonismo.
        # -------------------------------------------------

        retrato_em_moldura_horizontal = (
            origem_ratio
            < destino_ratio
        )

        photo_reframe = (
            render_overrides.get(
                "photo_reframe"
            )
            or {}
        )

        if not isinstance(
            photo_reframe,
            dict,
        ):
            photo_reframe = {}

        more_headroom = (
            photo_reframe.get(
                "intent"
            )
            == "more_headroom"
        )

        show_lower_subject = (
            photo_reframe.get(
                "intent"
            )
            == "show_lower_subject"
        )

        zoom_out_subject = (
            photo_reframe.get(
                "intent"
            )
            == "zoom_out_subject"
        )

        center_subject = (
            photo_reframe.get(
                "intent"
            )
            == "center_subject"
        )

        if photo_reframe or render_overrides.get(
            "preserve_photo_framing"
        ) is not None:
            print(
                "Seasonal Promo framing:",
                f"preserve={render_overrides.get('preserve_photo_framing')}",
                f"reframe={photo_reframe}",
                f"mode={photo_mode}",
                f"zoom={photo_zoom:.2f}",
                f"focus=({photo_focus_x:.2f},{photo_focus_y:.2f})",
                f"avoid_head_crop={avoid_head_crop}",
                flush=True,
            )

        if photo_mode == "smart_contain":
            # "Menos zoom" em retratos verticais dentro de uma moldura
            # horizontal precisa mostrar mais da foto original.
            # Para evitar um resultado sem diferença visual, usamos
            # fundo preenchido + foto contida em primeiro plano.
            fundo_foto = ImageOps.fit(
                foto_original,
                (
                    foto_w,
                    foto_h,
                ),
                method=Image.Resampling.LANCZOS,
                centering=(
                    photo_focus_x,
                    0.18 if avoid_head_crop else 0.22,
                ),
            )

            fundo_foto = fundo_foto.filter(
                ImageFilter.GaussianBlur(
                    radius=20
                )
            )

            foto = fundo_foto.copy()

            # photo_zoom < 1 representa afastamento real.
            # Limitamos apenas o tamanho mínimo para manter presença
            # visual dentro da campanha sem voltar ao crop agressivo.
            smart_zoom = limitar(
                photo_zoom,
                0.82,
                1.0,
            )

            inner_w = int(
                foto_w * smart_zoom
            )
            inner_h = int(
                foto_h * smart_zoom
            )

            foto_contida = ImageOps.contain(
                foto_original,
                (
                    inner_w,
                    inner_h,
                ),
                method=Image.Resampling.LANCZOS,
            )

            sobra_x = max(
                0,
                foto_w - foto_contida.width,
            )

            sobra_y = max(
                0,
                foto_h - foto_contida.height,
            )

            inner_x = int(
                round(
                    sobra_x * photo_focus_x
                )
            )

            inner_y = int(
                round(
                    sobra_y * photo_focus_y
                )
            )

            inner_x = int(
                limitar(
                    inner_x,
                    0,
                    sobra_x,
                )
            )

            inner_y = int(
                limitar(
                    inner_y,
                    0,
                    sobra_y,
                )
            )

            fg_mask = Image.new(
                "L",
                (
                    foto_contida.width,
                    foto_contida.height,
                ),
                0,
            )

            fg_draw = ImageDraw.Draw(
                fg_mask
            )

            fg_draw.rounded_rectangle(
                (
                    0,
                    0,
                    foto_contida.width,
                    foto_contida.height,
                ),
                radius=26,
                fill=235,
            )

            sombra = Image.new(
                "RGBA",
                (
                    foto_contida.width + 16,
                    foto_contida.height + 16,
                ),
                (0, 0, 0, 0),
            )

            sombra_mask = Image.new(
                "L",
                (
                    foto_contida.width,
                    foto_contida.height,
                ),
                0,
            )

            sombra_draw = ImageDraw.Draw(
                sombra_mask
            )

            sombra_draw.rounded_rectangle(
                (
                    0,
                    0,
                    foto_contida.width,
                    foto_contida.height,
                ),
                radius=26,
                fill=120,
            )

            sombra.paste(
                (0, 0, 0, 110),
                (8, 8),
                sombra_mask.filter(
                    ImageFilter.GaussianBlur(
                        radius=10
                    )
                ),
            )

            foto = foto.convert(
                "RGBA"
            )
            foto.alpha_composite(
                sombra,
                (
                    max(0, inner_x - 8),
                    max(0, inner_y - 8),
                ),
            )

            camada_fg = Image.new(
                "RGBA",
                foto.size,
                (0, 0, 0, 0),
            )
            camada_fg.paste(
                foto_contida.convert(
                    "RGBA"
                ),
                (
                    inner_x,
                    inner_y,
                ),
                fg_mask,
            )
            foto.alpha_composite(
                camada_fg
            )
            foto = foto.convert(
                "RGB"
            )

            print(
                "Seasonal Promo photo:",
                "SMART_CONTAIN",
                f"source={origem_w}x{origem_h}",
                f"target={foto_w}x{foto_h}",
                f"zoom={smart_zoom:.2f}",
                f"place=({inner_x},{inner_y})",
                flush=True,
            )


        elif (
            (
                avoid_head_crop
                or more_headroom
                or show_lower_subject
                or photo_mode == "safe_cover"
            )
            and retrato_em_moldura_horizontal
        ):
            if more_headroom:
                safe_focus_default = 0.0

            elif show_lower_subject:
                safe_focus_default = 0.24

            elif center_subject:
                safe_focus_default = 0.12

            else:
                safe_focus_default = 0.12

            safe_focus_y = float(
                render_overrides.get(
                    "photo_safe_focus_y",
                    safe_focus_default,
                )
                or safe_focus_default
            )

            safe_focus_y = limitar(
                safe_focus_y,
                0.0,
                0.28,
            )

            foto = ImageOps.fit(
                foto_original,
                (
                    foto_w,
                    foto_h,
                ),
                method=Image.Resampling.LANCZOS,
                centering=(
                    photo_focus_x,
                    safe_focus_y,
                ),
            )

            # ---------------------------------------------
            # ZOOM REAL DENTRO DO SAFE_COVER
            # ---------------------------------------------
            # Antes desta versão, ``photo_zoom`` era lido mas
            # ignorado neste branch. Por isso pedidos como
            # "dê mais zoom" produziam pixels idênticos.
            #
            # Agora ampliamos o frame já enquadrado e recortamos
            # novamente para 916x545. Isso mantém a moldura cheia,
            # não cria barras laterais e torna o zoom perceptível.
            # ---------------------------------------------

            if photo_zoom > 1.001:
                zoom_w = int(
                    round(
                        foto_w
                        * photo_zoom
                    )
                )

                zoom_h = int(
                    round(
                        foto_h
                        * photo_zoom
                    )
                )

                foto_zoomed = foto.resize(
                    (
                        zoom_w,
                        zoom_h,
                    ),
                    Image.Resampling.LANCZOS,
                )

                # Zoom ao redor do centro visual. O foco horizontal
                # pode ser controlado pelo override existente.
                zoom_focus_x = limitar(
                    float(
                        render_overrides.get(
                            "photo_zoom_focus_x",
                            0.5,
                        )
                        or 0.5
                    ),
                    0.0,
                    1.0,
                )

                zoom_focus_y = limitar(
                    float(
                        render_overrides.get(
                            "photo_zoom_focus_y",
                            0.5,
                        )
                        or 0.5
                    ),
                    0.0,
                    1.0,
                )

                excesso_x = max(
                    0,
                    zoom_w - foto_w,
                )

                excesso_y = max(
                    0,
                    zoom_h - foto_h,
                )

                crop_x = int(
                    round(
                        excesso_x
                        * zoom_focus_x
                    )
                )

                crop_y = int(
                    round(
                        excesso_y
                        * zoom_focus_y
                    )
                )

                crop_x = int(
                    limitar(
                        crop_x,
                        0,
                        excesso_x,
                    )
                )

                crop_y = int(
                    limitar(
                        crop_y,
                        0,
                        excesso_y,
                    )
                )

                foto = foto_zoomed.crop(
                    (
                        crop_x,
                        crop_y,
                        crop_x + foto_w,
                        crop_y + foto_h,
                    )
                )

                print(
                    "Seasonal Promo zoom:",
                    f"zoom={photo_zoom:.2f}",
                    f"focus=({zoom_focus_x:.2f},{zoom_focus_y:.2f})",
                    f"crop=({crop_x},{crop_y})",
                    flush=True,
                )

            print(
                "Seasonal Promo photo:",
                "SAFE_COVER",
                f"source={origem_w}x{origem_h}",
                f"target={foto_w}x{foto_h}",
                f"focus_y={safe_focus_y:.2f}",
                f"zoom={photo_zoom:.2f}",
                flush=True,
            )

        elif photo_mode == "contain":
            # Contain continua disponível para pedidos em que
            # mostrar a fotografia integralmente seja realmente
            # mais importante do que preencher toda a moldura.
            fundo_foto = ImageOps.fit(
                foto_original,
                (
                    foto_w,
                    foto_h,
                ),
                method=Image.Resampling.LANCZOS,
                centering=(
                    photo_focus_x,
                    photo_focus_y,
                ),
            )

            fundo_foto = fundo_foto.filter(
                ImageFilter.GaussianBlur(
                    radius=18
                )
            )

            foto = fundo_foto.copy()

            inner_w = int(
                foto_w * photo_zoom
            )
            inner_h = int(
                foto_h * photo_zoom
            )

            foto_contida = ImageOps.contain(
                foto_original,
                (
                    inner_w,
                    inner_h,
                ),
                method=Image.Resampling.LANCZOS,
            )

            inner_x = int(
                (foto_w - foto_contida.width) / 2
            )

            inner_y = int(
                (foto_h - foto_contida.height) / 2
            )

            foto.paste(
                foto_contida,
                (
                    inner_x,
                    inner_y,
                ),
            )

        else:
            foto = ImageOps.fit(
                foto_original,
                (
                    foto_w,
                    foto_h,
                ),
                method=Image.Resampling.LANCZOS,
                centering=(
                    photo_focus_x,
                    photo_focus_y,
                ),
            )

        canvas.paste(
            foto,
            (
                foto_x,
                foto_y,
            ),
            mascara,
        )

        draw = ImageDraw.Draw(
            canvas
        )

        # Moldura de energia em amarelo.
        draw.rounded_rectangle(
            (
                foto_x - 5,
                foto_y - 5,
                foto_x + foto_w + 5,
                foto_y + foto_h + 5,
            ),
            radius=57,
            outline=paleta[
                "accent"
            ],
            width=5,
        )

    # -----------------------------------------------------
    # SELO / BADGE
    # -----------------------------------------------------

    badge_text = badge_promocional(
        pedido,
        direction.get(
            "campaign_type"
        ),
    )

    campaign_badge_norm = (
        _norm_elemento(
            badge_text
        )
        if badge_text
        else ""
    )

    hide_campaign_badge = (
        hide_badge
        or (
            campaign_badge_norm
            and campaign_badge_norm
            in hide_elements_norm
        )
    )

    if badge_text and not hide_campaign_badge:
        badge_x = 74
        badge_y = 55

        badge_font = fonte(
            25,
            "bold",
        )

        badge_tw, badge_th = medir(
            draw,
            badge_text,
            badge_font,
        )

        badge_w = max(
            195,
            badge_tw + 48,
        )

        badge_h = 82

        draw.rounded_rectangle(
            (
                badge_x,
                badge_y,
                badge_x + badge_w,
                badge_y + badge_h,
            ),
            radius=28,
            fill=paleta[
                "accent"
            ],
        )

        draw.text(
            (
                badge_x
                + (
                    badge_w
                    - badge_tw
                ) / 2,

                badge_y
                + (
                    badge_h
                    - badge_th
                ) / 2
                - 2,
            ),
            badge_text,
            font=badge_font,
            fill=paleta[
                "dark_text"
            ],
        )

    # -----------------------------------------------------
    # TÍTULO
    # -----------------------------------------------------

    titulo = (
        copy.get(
            "headline"
        )
        or "Copa Slim"
    ).strip()

    # Em Copa Slim, força uma hierarquia esportiva:
    # COPA em branco + SLIM em amarelo.
    if (
        direction.get(
            "campaign_type"
        )
        == "COPA_SLIM"
    ):
        linha1 = "COPA"
        linha2 = "SLIM"

    else:
        palavras = titulo.split(
            maxsplit=1
        )

        linha1 = (
            palavras[0].upper()
            if palavras
            else "CAMPANHA"
        )

        linha2 = (
            palavras[1].upper()
            if len(
                palavras
            ) > 1
            else ""
        )

    titulo_x = 78
    titulo_y = 665

    font_copa = fonte(
        108,
        "bold",
    )

    font_slim = fonte(
        134,
        "bold",
    )

    draw.text(
        (
            titulo_x,
            titulo_y,
        ),
        linha1,
        font=font_copa,
        fill=COLORS[
            "WHITE"
        ],
    )

    linha1_w, linha1_h = medir(
        draw,
        linha1,
        font_copa,
    )

    if linha2:
        draw.text(
            (
                titulo_x + 45,
                titulo_y
                + linha1_h
                + 4,
            ),
            linha2,
            font=font_slim,
            fill=paleta[
                "accent"
            ],
        )

        _, linha2_h = medir(
            draw,
            linha2,
            font_slim,
        )

        titulo_bottom = (
            titulo_y
            + linha1_h
            + 4
            + linha2_h
        )

    else:
        titulo_bottom = (
            titulo_y
            + linha1_h
        )

    # Estrelas de competição.
    for sx, sy, r in [
        (760, 695, 15),
        (810, 675, 11),
        (850, 705, 9),
    ]:
        pontos = []

        for i in range(
            10
        ):
            angulo = (
                -math.pi / 2
                + i * math.pi / 5
            )

            raio = (
                r
                if i % 2 == 0
                else r * 0.42
            )

            pontos.append(
                (
                    sx
                    + math.cos(
                        angulo
                    ) * raio,

                    sy
                    + math.sin(
                        angulo
                    ) * raio,
                )
            )

        draw.polygon(
            pontos,
            fill=paleta[
                "accent"
            ],
        )

    # -----------------------------------------------------
    # APOIO
    # -----------------------------------------------------

    support = (
        copy.get(
            "support"
        )
        or ""
    )

    support_y = (
        titulo_bottom
        + 28
    )

    if support:
        support_inicio_y = (
            support_y
        )

        # Copy exata pode ser maior que a copy promocional
        # padrão. Ajustamos apenas o tamanho da fonte para
        # preservar a composição e caber com legibilidade.
        tamanho_support = 27

        if len(
            support
        ) > 280:
            tamanho_support = 19

        elif len(
            support
        ) > 210:
            tamanho_support = 20

        elif len(
            support
        ) > 150:
            tamanho_support = 22

        elif len(
            support
        ) > 110:
            tamanho_support = 24

        tamanho_support += int(
            render_overrides.get(
                "support_font_delta",
                0,
            )
            or 0
        )

        # Mantém legibilidade e evita estouro do layout.
        tamanho_support = max(
            17,
            min(
                29,
                tamanho_support,
            ),
        )

        support_y = desenhar_multilinha(
            draw,
            support,
            112,
            support_y,
            720,
            tamanho_support,
            COLORS[
                "WHITE"
            ],
            peso="regular",
            espacamento=6,
            alinhamento="left",
        )

        altura_linha = max(
            80,
            support_y
            - support_inicio_y
            - 4,
        )

        draw.rounded_rectangle(
            (
                82,
                support_inicio_y + 5,
                89,
                support_inicio_y
                + altura_linha,
            ),
            radius=4,
            fill=paleta[
                "accent"
            ],
        )

    # -----------------------------------------------------
    # BARRA PROMOCIONAL
    # -----------------------------------------------------

    bar_y = min(
        max(
            support_y + 38,
            1130,
        ),
        1210,
    )

    bar_x1 = 86
    bar_x2 = 820
    bar_h = 92

    bar_enabled = not hide_campaign_pillars

    if bar_enabled:
        draw.rounded_rectangle(
            (
                bar_x1,
                bar_y,
                bar_x2,
                bar_y + bar_h,
            ),
            radius=26,
            outline=COLORS[
                "TIFFANY"
            ],
            width=3,
        )

        bloco_font = fonte(
            20,
            "bold",
        )

        frases = [
            "MAIS MOVIMENTO",
            "MAIS CONEXÃO",
            "MAIS SLIMFIT",
        ]

        largura_bloco = (
            bar_x2
            - bar_x1
        ) / 3

        for indice, frase in enumerate(
            frases
        ):
            bx = (
                bar_x1
                + largura_bloco
                * indice
            )

            if indice > 0:
                draw.line(
                    (
                        bx,
                        bar_y + 20,
                        bx,
                        bar_y + bar_h - 20,
                    ),
                    fill=COLORS[
                        "WHITE"
                    ],
                    width=2,
                )

            tw, th = medir(
                draw,
                frase,
                bloco_font,
            )

            draw.text(
                (
                    bx
                    + (
                        largura_bloco
                        - tw
                    ) / 2,
                    bar_y
                    + (
                        bar_h
                        - th
                    ) / 2
                    - 2,
                ),
                frase,
                font=bloco_font,
                fill=(
                    paleta["accent"]
                    if indice == 0
                    else COLORS["WHITE"]
                ),
            )

    # -----------------------------------------------------
    # CTA / BADGE DE CONQUISTA
    # -----------------------------------------------------

    badge_conquista = (
        render_overrides.get(
            "achievement_badge_text"
        )
        or ""
    ).strip()

    achievement_norm = (
        _norm_elemento(
            badge_conquista
        )
        if badge_conquista
        else ""
    )

    if (
        achievement_norm
        and achievement_norm
        in hide_elements_norm
    ):
        badge_conquista = ""

    cta_texto = (
        copy.get(
            "cta"
        )
        or ""
    )

    if (
        not hide_cta
        and (
            badge_conquista
            or cta_texto
        )
    ):
        cta_font = fonte(
            22,
            "bold",
        )

        cta_texto_final = (
            badge_conquista
            or cta_texto
        )

        cta_w, cta_h = medir(
            draw,
            cta_texto_final,
            cta_font,
        )

        cta_x = 88

        if bar_enabled:
            cta_y = min(
                bar_y - cta_h - 28,
                1085,
            )

        elif preserve_removed_space and not compact_footer_space:
            cta_y = 1085

        elif compact_footer_space:
            # Sem a barra, o selo sobe para perto do texto de apoio.
            # Isso elimina o grande vazio que aparecia no teste 0128.
            cta_y = min(
                support_y + 34,
                1035,
            )

        else:
            cta_y = min(
                support_y + 52,
                1060,
            )

        draw.rounded_rectangle(
            (
                cta_x,
                cta_y,
                cta_x + cta_w + 42,
                cta_y + cta_h + 22,
            ),
            radius=20,
            fill=paleta[
                "accent"
            ],
        )

        draw.text(
            (
                cta_x + 21,
                cta_y + 8,
            ),
            cta_texto_final,
            font=cta_font,
            fill=paleta[
                "dark_text"
            ],
        )

        if (
            hide_campaign_pillars
            and compact_footer_space
        ):
            print(
                "Seasonal Promo footer:",
                "PILLARS_HIDDEN",
                f"badge_y={cta_y}",
                f"support_end={support_y}",
                flush=True,
            )

    # -----------------------------------------------------
    # SAFE ZONE DO LOGO
    # -----------------------------------------------------
    #
    # O publisher insere o logo depois. Por isso deixamos
    # o canto inferior direito sem texto ou foto.
    # -----------------------------------------------------

    return canvas


# =========================================================
# RENDER PÚBLICO
# =========================================================

def render_seasonal(
    caminho_foto,
    copy,
    pedido,
    foto,
    direction,
    archetype_override=None,
    render_overrides=None,
):
    archetype = (
        archetype_override
        or direction.get(
            "archetype"
        )
        or "SEASONAL_CLEAN"
    )

    if (
        archetype
        not in VALID_ARCHETYPES
    ):
        archetype = (
            "SEASONAL_CLEAN"
        )

    if (
        archetype
        == "SEASONAL_PHOTO"
    ):
        canvas = render_photo(
            caminho_foto,
            copy,
            pedido,
            direction,
        )

    elif (
        archetype
        == "SEASONAL_PROMO"
    ):
        canvas = render_promo(
            caminho_foto,
            copy,
            pedido,
            direction,
            render_overrides=(
                render_overrides
                or {}
            ),
        )

    else:
        canvas = render_clean(
            copy,
            pedido,
            direction,
        )

    temp = (
        tempfile.NamedTemporaryFile(
            suffix=".png",
            delete=False,
        )
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
        "image_path": (
            caminho_saida
        ),

        "composition": (
            archetype
        ),

        "family": (
            "SLIMFIT_SEASONAL"
        ),

        "background_style": (
            archetype
        ),

        "campaign_type": (
            direction.get(
                "campaign_type"
            )
        ),

        "reference_count": (
            direction.get(
                "reference_count",
                0,
            )
        ),

        "photo_requirements": (
            direction.get(
                "photo_requirements",
                {},
            )
        ),

        # Informação para integração futura
        # com o logo_manager.
        "preferred_logo_position": (
            "top_right"
            if archetype
            == "SEASONAL_PHOTO"
            else None
        ),

        "preferred_logo_type": (
            "white"
            if archetype
            == "SEASONAL_PHOTO"
            else None
        ),
    }
