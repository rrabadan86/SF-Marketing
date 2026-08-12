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
