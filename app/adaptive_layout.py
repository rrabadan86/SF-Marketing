import os

from PIL import ImageFont


# Escada de fontes da marca: Nexa (oficial) com fallback DejaVu.
def _fonte_path(peso="regular"):
    if peso == "bold":
        candidatos = [
            "/app/assets/fonts/Nexa-Bold.otf",
            "/app/assets/fonts/Nexa-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    else:
        candidatos = [
            "/app/assets/fonts/Nexa-Regular.otf",
            "/app/assets/fonts/Nexa-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]

    for caminho in candidatos:
        if os.path.exists(caminho):
            return caminho

    return None


def fonte(tamanho, peso="regular"):
    caminho = _fonte_path(peso)

    if caminho:
        return ImageFont.truetype(
            caminho,
            int(tamanho),
        )

    return ImageFont.load_default()


def clamp(
    valor,
    minimo,
    maximo,
):
    return max(
        minimo,
        min(
            valor,
            maximo,
        ),
    )


# -------------------------------------------------------------
# Primitivas compartilhadas (antes duplicadas em cada renderer)
# -------------------------------------------------------------

def medir(draw, texto, font):
    """Largura e altura de um texto. Tolera None."""
    bbox = draw.textbbox(
        (0, 0),
        texto or "",
        font=font,
    )
    return (
        bbox[2] - bbox[0],
        bbox[3] - bbox[1],
    )


def hex_rgb(valor):
    """Converte '#RRGGBB' em (r, g, b). Tolera None/vazio (-> preto)."""
    valor = (
        valor
        or "#000000"
    ).lstrip("#")

    return tuple(
        int(valor[i:i + 2], 16)
        for i in (0, 2, 4)
    )


def quebrar(draw, texto, font, largura_max):
    """
    Quebra o texto em linhas que cabem em ``largura_max``. Palavra
    isolada maior que a largura fica sozinha na linha (não some).
    """
    palavras = (texto or "").split()

    if not palavras:
        return []

    linhas = []
    atual = []

    for palavra in palavras:
        tentativa = " ".join(atual + [palavra])
        largura, _ = medir(draw, tentativa, font)

        if largura <= largura_max or not atual:
            atual.append(palavra)
        else:
            linhas.append(" ".join(atual))
            atual = [palavra]

    if atual:
        linhas.append(" ".join(atual))

    return linhas


def altura_linhas(
    draw,
    texto,
    font,
    largura_max,
    quebrar_func,
    espacamento=7,
):
    """
    Calcula a altura REAL necessária para um texto,
    utilizando a mesma função de quebra usada no layout.
    """

    if not texto:
        return 0

    linhas = quebrar_func(
        draw,
        texto,
        font,
        largura_max,
    )

    if not linhas:
        return 0

    total = 0

    for indice, linha in enumerate(
        linhas
    ):
        bbox = draw.textbbox(
            (0, 0),
            linha,
            font=font,
        )

        altura = (
            bbox[3]
            - bbox[1]
        )

        total += altura

        if (
            indice
            < len(linhas) - 1
        ):
            total += espacamento

    return total


def calcular_bloco(
    *,
    headline_height,
    support_height=0,
    cta_height=0,
    meta_height=0,
    tag_height=0,
    padding_top=55,
    padding_bottom=65,
    gap_meta_headline=28,
    gap_headline_support=35,
    gap_support_cta=22,
    minimum_height=320,
    maximum_height=570,
):
    """
    Calcula a altura ideal da massa gráfica.

    Só reserva espaço para elementos que realmente existem.
    """

    altura = (
        padding_top
        + padding_bottom
    )

    if tag_height:
        altura += tag_height

    if meta_height:
        altura += meta_height

    if (
        (tag_height or meta_height)
        and headline_height
    ):
        altura += (
            gap_meta_headline
        )

    altura += (
        headline_height
    )

    if (
        support_height
        and headline_height
    ):
        altura += (
            gap_headline_support
        )

    altura += (
        support_height
    )

    if cta_height:
        if (
            support_height
            or headline_height
        ):
            altura += (
                gap_support_cta
            )

        altura += (
            cta_height
        )

    return int(
        clamp(
            altura,
            minimum_height,
            maximum_height,
        )
    )


def calcular_topo_por_rodape(
    altura_total,
    bloco_altura,
    margem_inferior,
):
    return int(
        altura_total
        - margem_inferior
        - bloco_altura
    )
