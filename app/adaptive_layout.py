import os
import re

from PIL import ImageFont


# -------------------------------------------------------------
# Destaque de trecho: o texto pode conter **trecho** para marcar
# ênfase (negrito + sublinhado). Os marcadores nunca são desenhados
# literalmente — medir/quebrar os removem e desenhar_multilinha os
# interpreta.
# -------------------------------------------------------------

_MARCADOR = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)


def limpar_marcadores(texto):
    """Remove os marcadores ** deixando só o texto."""
    if not texto:
        return texto
    return _MARCADOR.sub(r"\1", texto)


def segmentar_enfase(texto):
    """
    Divide ``texto`` em segmentos (trecho, enfase_bool) na ordem em que
    aparecem. '**A** B' -> [('A', True), (' B', False)].
    """
    segmentos = []
    pos = 0
    for match in _MARCADOR.finditer(texto or ""):
        if match.start() > pos:
            segmentos.append(
                (texto[pos:match.start()], False)
            )
        segmentos.append((match.group(1), True))
        pos = match.end()
    if pos < len(texto or ""):
        segmentos.append((texto[pos:], False))
    return segmentos


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
    """Largura e altura de um texto. Tolera None e ignora marcadores **."""
    bbox = draw.textbbox(
        (0, 0),
        limpar_marcadores(texto) or "",
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
    Marcadores de ênfase ** são removidos.
    """
    palavras = (limpar_marcadores(texto) or "").split()

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


def desenhar_multilinha(
    draw,
    texto,
    x,
    y,
    largura,
    tamanho,
    cor,
    peso="regular",
    espacamento=7,
    max_linhas=None,
    alinhamento="left",
):
    """
    Desenha texto quebrado em linhas e devolve o y final.

    Superset das versões antes duplicadas nos renderizadores:
    - ``max_linhas`` trunca (Dynamic/Story);
    - ``alinhamento`` 'left'/'center'/'right' (Seasonal).
    Texto vazio devolve ``y`` sem desenhar.
    """
    if not texto:
        return y

    # Caminho rico: há trecho marcado com ** para ênfase (negrito +
    # sublinhado). Faz a quebra ciente dos segmentos e desenha palavra
    # a palavra.
    if "**" in texto:
        return _desenhar_multilinha_rico(
            draw,
            texto,
            x,
            y,
            largura,
            tamanho,
            cor,
            peso=peso,
            espacamento=espacamento,
            max_linhas=max_linhas,
            alinhamento=alinhamento,
        )

    font = fonte(tamanho, peso)
    linhas = quebrar(draw, texto, font, largura)

    if max_linhas:
        linhas = linhas[:max_linhas]

    atual_y = y

    for linha in linhas:
        largura_linha, altura = medir(draw, linha, font)

        if alinhamento == "center":
            linha_x = x + (largura - largura_linha) / 2
        elif alinhamento == "right":
            linha_x = x + largura - largura_linha
        else:
            linha_x = x

        draw.text(
            (int(linha_x), int(atual_y)),
            linha,
            font=font,
            fill=cor,
        )
        atual_y += altura + espacamento

    return atual_y


def _desenhar_multilinha_rico(
    draw,
    texto,
    x,
    y,
    largura,
    tamanho,
    cor,
    peso="regular",
    espacamento=7,
    max_linhas=None,
    alinhamento="left",
):
    """
    Versão de ``desenhar_multilinha`` que respeita trechos marcados com
    ** — desenha-os em negrito e com sublinhado contínuo, mantendo o
    mesmo tamanho de fonte (baseline alinhado).
    """
    font_base = fonte(tamanho, peso)
    font_enf = fonte(tamanho, "bold")

    def larg(palavra, fnt):
        return draw.textlength(palavra, font=fnt)

    espaco_w = larg(" ", font_base)

    # Texto plano + ênfase por caractere (evita espaços artificiais
    # junto à pontuação nas bordas dos trechos marcados).
    plano = []
    enfase_char = []
    for seg_texto, enfase in segmentar_enfase(texto):
        plano.append(seg_texto)
        enfase_char.extend([enfase] * len(seg_texto))
    plano = "".join(plano)

    # (palavra, enfase, largura, fonte) — quebra por espaços do texto
    # plano; a ênfase da palavra vem do seu primeiro caractere.
    palavras = []
    i = 0
    n = len(plano)
    while i < n:
        if plano[i].isspace():
            i += 1
            continue
        j = i
        while j < n and not plano[j].isspace():
            j += 1
        palavra = plano[i:j]
        enfase = enfase_char[i]
        fnt = font_enf if enfase else font_base
        palavras.append(
            (palavra, enfase, larg(palavra, fnt), fnt)
        )
        i = j

    # Quebra em linhas respeitando a largura.
    linhas = []
    atual = []
    atual_w = 0
    for item in palavras:
        add = item[2] if not atual else espaco_w + item[2]
        if atual and atual_w + add > largura:
            linhas.append(atual)
            atual = [item]
            atual_w = item[2]
        else:
            atual.append(item)
            atual_w += add
    if atual:
        linhas.append(atual)

    if max_linhas:
        linhas = linhas[:max_linhas]

    # Altura de linha uniforme (fonte base) para não desalinhar.
    _, altura = medir(draw, "Ay", font_base)
    espessura = max(2, int(tamanho / 14))

    atual_y = y
    for linha in linhas:
        largura_linha = (
            sum(it[2] for it in linha)
            + espaco_w * (len(linha) - 1)
        )
        if alinhamento == "center":
            xx = x + (largura - largura_linha) / 2
        elif alinhamento == "right":
            xx = x + largura - largura_linha
        else:
            xx = x

        # Desenha palavras e registra posições para o sublinhado.
        posicoes = []
        for palavra, enfase, w, fnt in linha:
            draw.text(
                (int(xx), int(atual_y)),
                palavra,
                font=fnt,
                fill=cor,
            )
            posicoes.append((xx, xx + w, enfase))
            xx += w + espaco_w

        # Sublinhado contínuo sobre sequências de palavras enfatizadas.
        y_sub = atual_y + altura + max(2, int(tamanho / 12))
        run_ini = None
        run_fim = None
        for x0, x1, enfase in posicoes:
            if enfase:
                if run_ini is None:
                    run_ini = x0
                run_fim = x1
            elif run_ini is not None:
                draw.line(
                    (int(run_ini), int(y_sub), int(run_fim), int(y_sub)),
                    fill=cor,
                    width=espessura,
                )
                run_ini = None
        if run_ini is not None:
            draw.line(
                (int(run_ini), int(y_sub), int(run_fim), int(y_sub)),
                fill=cor,
                width=espessura,
            )

        atual_y += altura + espacamento

    return atual_y


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
