import os
import re
import tempfile

from PIL import Image, ImageDraw, ImageFont, ImageOps

from face_framing import detectar_foco_rosto
from photo_style import tratar_foto
from seasonal_layout import ajustar_foto_na_moldura
from adaptive_layout import (
    medir,
    hex_rgb,
    fonte,
    quebrar,
    desenhar_multilinha,
    limpar_marcadores,
)


WIDTH = 1080
HEIGHT = 1350

# Registra se o último enquadramento de foto bateu no limite geométrico de
# zoom-out (foto horizontal numa moldura vertical não tem mais o que revelar).
# Processamento é sequencial por pedido, então o global reflete a última foto.
_ULTIMO_ZOOM_OUT_LIMITADO = False


def _ajuste_fonte(base, overrides, chave, minimo):
    """Aplica o delta de fonte pedido pelo usuário, com piso de segurança."""
    return max(
        minimo,
        base + int((overrides or {}).get(chave, 0) or 0),
    )


def _nota_zoom_out_limitado(overrides):
    """
    Devolve um aviso amigável quando o usuário pediu afastamento ("menos
    zoom"/"corpo inteiro") mas a geometria não permitiu revelar mais — em vez
    de mandar uma imagem visualmente idêntica sem explicação.
    """
    overrides = overrides or {}
    pediu_afastar = (
        float(overrides.get("photo_zoom", 1.0) or 1.0) < 1.0
        or bool(overrides.get("full_body"))
    )
    if pediu_afastar and _ULTIMO_ZOOM_OUT_LIMITADO:
        return (
            "ℹ️ Esta foto é horizontal e já está no afastamento máximo dentro "
            "do formato feed — afastar mais deixaria barras nas laterais. Para "
            "mostrar o corpo inteiro/todo o grupo sem cortar, posso gerar no "
            "formato Story (vertical): é só pedir \"gerar em story\"."
        )
    return None

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
    render_overrides=None,
):
    overrides = render_overrides or {}

    foto = tratar_foto(
        Image.open(caminho_foto)
    )

    # Foco: override explícito do usuário vence; senão o rosto detectado.
    face = detectar_foco_rosto(
        foto,
        default=(0.5, 0.37),
    )

    fx = overrides.get("photo_focus_x")
    fx = float(fx) if fx is not None else face[0]

    fy = overrides.get("photo_focus_y")
    fy = float(fy) if fy is not None else face[1]

    # "Sem cortar a cabeça" puxa o foco para o topo.
    if overrides.get("avoid_head_crop"):
        fy = min(fy, 0.12)

    # Nudge vertical relativo ("suba/desça a foto"): positivo mostra a
    # parte de baixo da foto (sobe o assunto no quadro).
    delta_fy = overrides.get("photo_focus_delta_y")
    if delta_fy is not None:
        fy = float(fy) + float(delta_fy)

    fy = max(0.0, min(1.0, float(fy)))

    # Zoom real (antes ignorado): usa o mesmo motor do Seasonal.
    zoom = float(
        overrides.get("photo_zoom", 1.0)
        or 1.0
    )

    foto_out, info = ajustar_foto_na_moldura(
        foto,
        WIDTH,
        HEIGHT,
        scale=zoom,
        focus_x=fx,
        focus_y=fy,
        modo="cover",
    )

    print(
        "Dynamic framing:",
        info,
        f"focus=({fx:.2f},{fy:.2f})",
        flush=True,
    )

    global _ULTIMO_ZOOM_OUT_LIMITADO
    _ULTIMO_ZOOM_OUT_LIMITADO = bool(
        info.get("zoom_out_limitado")
    )

    return foto_out


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
    # CTA/badge não renderiza ênfase inline — remove os marcadores.
    texto = limpar_marcadores(texto)
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

    texto = limpar_marcadores(texto)

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
        caminho_foto,
        overrides,
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
        y = 958

    else:
        x = 58
        text_right = 760
        largura_texto = (
            text_right
            - x
        )

        y = 950

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

    # Ajuste de fonte pedido pelo usuário ("aumente/diminua a fonte").
    headline_size = max(
        30,
        headline_size
        + int(
            overrides.get("headline_font_delta", 0)
            or 0
        ),
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
        60
        if ajuste_fino
        else 54
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

    support_size = max(
        16,
        support_size
        + int(
            overrides.get("support_font_delta", 0)
            or 0
        ),
    )

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
            42
            if ajuste_fino
            else 34
        ),
        1300,
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
            emphasis=True,
            font_delta=(
                overrides.get(
                    "cta_font_delta",
                    0,
                )
            ),
            accent=tema["accent"],
        )

    return canvas


# =============================================================
# COMPOSIÇÃO DYNAMIC_BOLD — foto full-bleed + degradê + texto
# =============================================================

def _degrade_inferior(
    canvas,
    altura_frac=0.55,
    cor=(28, 26, 30),
    alpha_max=236,
):
    """
    Aplica um degradê da cor sólida (base) até transparente (topo) na
    parte inferior da imagem, para o texto branco ficar legível sobre
    qualquer foto sem esconder a fotografia.
    """
    w, h = canvas.size
    inicio = int(h * (1 - altura_frac))

    mascara = Image.new("L", (1, h), 0)
    for y in range(inicio, h):
        t = (y - inicio) / max(1, (h - inicio))
        mascara.putpixel((0, y), int(alpha_max * (t ** 1.5)))
    mascara = mascara.resize((w, h))

    overlay = Image.new("RGB", (w, h), cor)
    return Image.composite(
        overlay,
        canvas.convert("RGB"),
        mascara,
    )


def _degrade_hero(canvas, cor, y_solido, fade=280):
    """
    Degradê da composição HERO: totalmente OPACO (cor sólida) a partir de
    ``y_solido`` para baixo — garantindo que o texto branco fique sobre
    fundo cheio, sem a foto vazar e apagar a leitura — e uma transição
    suave de ``fade`` px acima disso até a foto.
    """
    w, h = canvas.size
    y_solido = int(max(0, min(y_solido, h)))
    inicio = max(0, y_solido - fade)

    mascara = Image.new("L", (1, h), 0)
    for y in range(inicio, h):
        if y >= y_solido:
            alpha = 255
        else:
            alpha = int(255 * ((y - inicio) / max(1, fade)))
        mascara.putpixel((0, y), alpha)
    mascara = mascara.resize((w, h))

    overlay = Image.new("RGB", (w, h), cor)
    return Image.composite(
        overlay,
        canvas.convert("RGB"),
        mascara,
    )


def detectar_composicao(pedido):
    """
    Escolhe a composição do Dynamic pela palavra-chave. Padrão: a onda
    (DYNAMIC_WAVE), comportamento histórico.
    """
    texto = _sem_acentos(pedido)

    if any(
        termo in texto
        for termo in [
            "gradiente",
            "degrade",
            "estilo capa",
            "capa",
            "hero",
            "estilo hero",
            "estilo tema",
            "estilo rotina",
            "caixa de apoio",
        ]
    ):
        return "DYNAMIC_HERO"

    if any(
        termo in texto
        for termo in [
            "dividido",
            "split",
            "bloco de cor",
            "faixa de cor",
            "meio a meio",
            "foto em cima",
            "estilo limpo",
            "estilo corporativo",
        ]
    ):
        return "DYNAMIC_SPLIT"

    if any(
        termo in texto
        for termo in [
            "estilo foto",
            "foto em destaque",
            "destaque na foto",
            "texto sobre a foto",
            "sem onda",
            "tela cheia",
            "foto grande",
            "estilo bold",
            "estilo revista",
            "editorial",
        ]
    ):
        return "DYNAMIC_BOLD"

    return "DYNAMIC_WAVE"


def render_bold(
    caminho_foto,
    copy,
    pedido,
    render_overrides=None,
):
    overrides = render_overrides or {}

    tema = WAVE_THEMES.get(
        overrides.get("wave_theme")
        or detectar_tema_wave(pedido),
        WAVE_THEMES["coral"],
    )

    canvas = crop_foto(caminho_foto, overrides)
    # Degradê mais firme, garantindo leitura do texto branco mesmo em
    # fotos claras.
    canvas = _degrade_inferior(
        canvas,
        altura_frac=0.62,
        alpha_max=250,
    )

    draw = ImageDraw.Draw(canvas)

    x = 64
    largura = WIDTH - 128
    y = 890

    # Motivo de marca: traço curto tiffany (accent) acima da headline.
    draw.rectangle(
        (x, y - 26, x + 66, y - 19),
        fill=COLORS[tema["accent"]],
    )

    headline = copy.get("headline") or ""
    y = desenhar_multilinha(
        draw,
        headline,
        x,
        y,
        largura,
        _ajuste_fonte(58, overrides, "headline_font_delta", 34),
        COLORS["WHITE"],
        peso="bold",
        espacamento=2,
        max_linhas=3,
    )

    draw.line(
        (x, y + 14, x + 195, y + 14),
        fill=COLORS["WHITE"],
        width=5,
    )
    y += 54

    apoio = copy.get("support") or ""
    y = desenhar_multilinha(
        draw,
        apoio,
        x,
        y,
        largura,
        _ajuste_fonte(26, overrides, "support_font_delta", 16),
        COLORS["WHITE"],
        peso="regular",
        espacamento=5,
        max_linhas=3,
    )

    cta = copy.get("cta") or ""
    if cta and not overrides.get("hide_cta"):
        desenhar_cta(
            draw,
            cta,
            x,
            min(y + 36, 1300),
            emphasis=True,
            accent=tema["accent"],
        )

    return canvas


def render_hero(
    caminho_foto,
    copy,
    pedido,
    render_overrides=None,
):
    """
    Composição "capa": foto full-bleed, degradê na cor da marca (teal por
    padrão) subindo da base, headline centralizado (aceita **negrito** em
    trechos) e o apoio dentro de uma caixa arredondada com borda.
    """
    overrides = render_overrides or {}

    # Cor do degradê: TEAL (tiffany) por padrão — a identidade dessa
    # composição. Coral/escuro só quando o usuário pedir explicitamente.
    tema_nome = overrides.get("wave_theme")
    if not tema_nome:
        texto_pedido = _sem_acentos(pedido)
        if any(t in texto_pedido for t in ["coral", "rosa", "vermelho"]):
            tema_nome = "coral"
        elif any(t in texto_pedido for t in ["escuro", "preto", "dark"]):
            tema_nome = "escuro"
        else:
            tema_nome = "tiffany"

    # Teal um pouco mais fundo que o tiffany puro para o branco ter
    # contraste (branco sobre teal claro fica ilegível).
    def _fundo(cor, fator):
        return tuple(int(c * fator) for c in cor)

    if tema_nome == "coral":
        cor_grad = _fundo(hex_rgb(COLORS["CORAL"]), 0.9)
    elif tema_nome == "escuro":
        cor_grad = hex_rgb(COLORS["CHARCOAL"])
    else:
        cor_grad = _fundo(hex_rgb(COLORS["TIFFANY"]), 0.9)

    canvas = crop_foto(caminho_foto, overrides)

    # O degradê é aplicado DEPOIS de medir o texto, para ficar sólido
    # exatamente a partir do topo do bloco (ver abaixo).
    draw = ImageDraw.Draw(canvas)

    x = 70
    largura = WIDTH - 140

    headline = copy.get("headline") or ""
    apoio = copy.get("support") or ""

    # -------- Apoio dentro de caixa (medido primeiro p/ ancorar) -----
    apoio_size = _ajuste_fonte(24, overrides, "support_font_delta", 15)
    font_apoio = fonte(apoio_size, "regular")
    pad = 26
    box_larg = largura
    inner_larg = box_larg - pad * 2
    linhas_apoio = quebrar(draw, apoio, font_apoio, inner_larg) if apoio else []
    _, alt_linha = medir(draw, "Ay", font_apoio)
    esp_apoio = 8
    box_alt = (
        pad * 2
        + len(linhas_apoio) * alt_linha
        + max(0, len(linhas_apoio) - 1) * esp_apoio
        if linhas_apoio
        else 0
    )

    # -------- Headline centralizado ---------------------------------
    headline_size = _ajuste_fonte(40, overrides, "headline_font_delta", 26)
    font_head = fonte(headline_size, "regular")
    linhas_head = quebrar(
        draw,
        limpar_marcadores(headline),
        font_head,
        largura,
    ) if headline else []
    _, alt_head = medir(draw, "Ay", font_head)
    esp_head = 8
    alt_bloco_head = (
        len(linhas_head) * alt_head
        + max(0, len(linhas_head) - 1) * esp_head
    )

    # Ancora o conjunto (headline + caixa) na base, deixando o rodapé
    # livre para o logo (inferior_direito) — sem colisão com a caixa.
    gap_head_box = 22
    # Rodapé reservado para o logo (inferior_direito). O logo tem ~0.18 da
    # largura e a arte é alta; 220px garante folga sem colisão com a caixa.
    reserva_logo = 220
    base_y = HEIGHT - reserva_logo
    topo_box = base_y - box_alt
    topo_head = topo_box - gap_head_box - alt_bloco_head

    # Degradê CURTO: transição suave de ~120px logo acima do texto, para
    # revelar o máximo da foto (a faixa teal fica fina). O texto ainda cai
    # sobre teal cheio e legível.
    canvas = _degrade_hero(
        canvas,
        cor_grad,
        y_solido=topo_head - 16,
        fade=120,
    )
    draw = ImageDraw.Draw(canvas)

    if headline:
        desenhar_multilinha(
            draw,
            headline,
            x,
            topo_head,
            largura,
            headline_size,
            COLORS["WHITE"],
            peso="regular",
            espacamento=esp_head,
            alinhamento="center",
            max_linhas=4,
        )

    # Caixa de apoio com borda arredondada.
    if linhas_apoio:
        draw.rounded_rectangle(
            (
                x,
                topo_box,
                x + box_larg,
                topo_box + box_alt,
            ),
            radius=20,
            outline=(255, 255, 255, 235),
            width=2,
        )

        ay = topo_box + pad
        for linha in linhas_apoio:
            lw, _ = medir(draw, linha, font_apoio)
            lx = x + (box_larg - lw) / 2
            draw.text(
                (int(lx), int(ay)),
                linha,
                font=font_apoio,
                fill=COLORS["WHITE"],
            )
            ay += alt_linha + esp_apoio

    return canvas


def render_split(
    caminho_foto,
    copy,
    pedido,
    render_overrides=None,
):
    """
    Composição de bloco: foto no topo e um bloco de cor sólida (tema) na
    base com o texto. Visual limpo/corporativo, sem a onda.
    """
    overrides = render_overrides or {}

    tema = WAVE_THEMES.get(
        overrides.get("wave_theme")
        or detectar_tema_wave(pedido),
        WAVE_THEMES["coral"],
    )
    accent = COLORS[tema["accent"]]

    divisor = 852

    canvas = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        tuple(tema["bg"][:3]),
    )

    foto = tratar_foto(Image.open(caminho_foto))
    face = detectar_foco_rosto(foto, default=(0.5, 0.40))
    fx = overrides.get("photo_focus_x")
    fx = float(fx) if fx is not None else face[0]
    fy = overrides.get("photo_focus_y")
    fy = float(fy) if fy is not None else face[1]
    if overrides.get("avoid_head_crop"):
        fy = min(fy, 0.12)
    zoom = float(overrides.get("photo_zoom", 1.0) or 1.0)
    foto_area, _info_split = ajustar_foto_na_moldura(
        foto,
        WIDTH,
        divisor,
        scale=zoom,
        focus_x=fx,
        focus_y=fy,
        modo="cover",
    )
    global _ULTIMO_ZOOM_OUT_LIMITADO
    _ULTIMO_ZOOM_OUT_LIMITADO = bool(
        _info_split.get("zoom_out_limitado")
    )
    canvas.paste(foto_area, (0, 0))

    draw = ImageDraw.Draw(canvas)

    # Faixa de destaque no divisor.
    draw.rectangle(
        (0, divisor, WIDTH, divisor + 7),
        fill=accent,
    )

    x = 64
    largura = WIDTH - 128
    y = divisor + 54

    headline = copy.get("headline") or ""
    y = desenhar_multilinha(
        draw,
        headline,
        x,
        y,
        largura,
        _ajuste_fonte(52, overrides, "headline_font_delta", 32),
        COLORS["WHITE"],
        peso="bold",
        espacamento=2,
        max_linhas=3,
    )

    draw.line(
        (x, y + 13, x + 195, y + 13),
        fill=COLORS["WHITE"],
        width=5,
    )
    y += 52

    apoio = copy.get("support") or ""
    y = desenhar_multilinha(
        draw,
        apoio,
        x,
        y,
        largura,
        _ajuste_fonte(25, overrides, "support_font_delta", 16),
        COLORS["WHITE"],
        peso="regular",
        espacamento=5,
        max_linhas=2,
    )

    cta = copy.get("cta") or ""
    if cta and not overrides.get("hide_cta"):
        desenhar_cta(
            draw,
            cta,
            x,
            min(y + 32, 1300),
            emphasis=True,
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

    Duas composições: DYNAMIC_WAVE (onda, padrão) e DYNAMIC_BOLD (foto
    full-bleed com texto sobre a foto). A escolha vem do override ou da
    palavra-chave no pedido; composição desconhecida cai na onda.
    """

    global _ULTIMO_ZOOM_OUT_LIMITADO
    _ULTIMO_ZOOM_OUT_LIMITADO = False

    composition = (
        composition_override
        or detectar_composicao(pedido)
    )

    if composition not in {
        "DYNAMIC_WAVE",
        "DYNAMIC_BOLD",
        "DYNAMIC_SPLIT",
        "DYNAMIC_HERO",
    }:
        composition = (
            "DYNAMIC_WAVE"
        )

    if composition in {"DYNAMIC_BOLD", "DYNAMIC_SPLIT", "DYNAMIC_HERO"}:
        if composition == "DYNAMIC_BOLD":
            canvas = render_bold(
                caminho_foto,
                copy,
                pedido,
                render_overrides=render_overrides,
            )
        elif composition == "DYNAMIC_HERO":
            canvas = render_hero(
                caminho_foto,
                copy,
                pedido,
                render_overrides=render_overrides,
            )
        else:
            canvas = render_split(
                caminho_foto,
                copy,
                pedido,
                render_overrides=render_overrides,
            )

        temp = tempfile.NamedTemporaryFile(
            suffix=".png",
            delete=False,
        )
        caminho_saida = temp.name
        temp.close()
        canvas.save(caminho_saida, "PNG")

        return {
            "image_path": caminho_saida,
            "composition": composition,
            "family": "SLIMFIT_DYNAMIC",
            "background_style": (
                background_override
                or composition
            ),
            "width": WIDTH,
            "height": HEIGHT,
            "photo_note": _nota_zoom_out_limitado(
                render_overrides
            ),
        }

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
        "photo_note": _nota_zoom_out_limitado(
            render_overrides
        ),
    }
