import os
import tempfile
import unicodedata

from PIL import Image, ImageStat

from drive_client import (
    ROOT_FOLDER_ID,
    localizar_subpasta,
    listar_pasta,
    baixar_arquivo,
)


# =========================================================
# UTILIDADES
# =========================================================

def normalizar_nome(texto):
    texto = unicodedata.normalize(
        "NFKD",
        texto,
    )

    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )

    return texto.lower()


def classificar_tipo_logo(nome):
    nome = normalizar_nome(nome)

    if "principal" in nome:
        return "principal"

    if (
        "branca" in nome
        or "branco" in nome
        or "white" in nome
    ):
        return "branca"

    if (
        "preta" in nome
        or "preto" in nome
        or "black" in nome
    ):
        return "preta"

    return "outra"


# =========================================================
# LOCALIZAÇÃO DAS LOGOS NO DRIVE
# =========================================================

def localizar_logos():
    pasta = localizar_subpasta(
        ROOT_FOLDER_ID,
        "01_LOGOS",
    )

    if not pasta:
        raise RuntimeError(
            "Pasta 01_LOGOS não encontrada."
        )

    arquivos = listar_pasta(
        pasta["id"]
    )

    logos = []

    for arquivo in arquivos:
        mime = arquivo.get(
            "mimeType",
            "",
        )

        if not mime.startswith(
            "image/"
        ):
            continue

        logos.append({
            "arquivo": arquivo,
            "tipo": classificar_tipo_logo(
                arquivo["name"]
            ),
        })

    if not logos:
        raise RuntimeError(
            "Nenhuma logo encontrada em 01_LOGOS."
        )

    return logos


# =========================================================
# VALIDAÇÃO DA COR REAL DA LOGO
# =========================================================

def analisar_cor_logo(caminho):
    imagem = Image.open(
        caminho
    ).convert("RGBA")

    pixels = []

    for r, g, b, a in imagem.getdata():
        # Ignora pixels transparentes.
        if a < 30:
            continue

        pixels.append(
            (r, g, b)
        )

    if not pixels:
        return {
            "r": 0,
            "g": 0,
            "b": 0,
            "luminancia": 0,
        }

    r = sum(
        p[0] for p in pixels
    ) / len(pixels)

    g = sum(
        p[1] for p in pixels
    ) / len(pixels)

    b = sum(
        p[2] for p in pixels
    ) / len(pixels)

    luminancia = (
        0.2126 * r
        + 0.7152 * g
        + 0.0722 * b
    )

    return {
        "r": r,
        "g": g,
        "b": b,
        "luminancia": luminancia,
    }


def validar_tipo_logo(
    caminho,
    tipo,
    nome,
):
    cor = analisar_cor_logo(
        caminho
    )

    lum = cor[
        "luminancia"
    ]

    if tipo == "branca":
        if lum < 180:
            print(
                f"⚠️ AVISO: {nome} está classificada "
                f"como branca, mas luminância média={lum:.1f}.",
                flush=True,
            )

    elif tipo == "preta":
        if lum > 100:
            print(
                f"⚠️ AVISO: {nome} está classificada "
                f"como preta, mas luminância média={lum:.1f}.",
                flush=True,
            )

    return cor


# =========================================================
# DOWNLOAD DA LOGO ESCOLHIDA
# =========================================================

def baixar_logo_por_tipo(
    tipo_preferido,
):
    logos = localizar_logos()

    candidatas = [
        item
        for item in logos
        if item["tipo"]
        == tipo_preferido
    ]

    if not candidatas:
        raise RuntimeError(
            f"Nenhuma logo do tipo "
            f"'{tipo_preferido}' encontrada "
            f"em 01_LOGOS."
        )

    # Priorizamos arquivos com "oficial".
    candidatas.sort(
        key=lambda item: (
            0
            if "oficial"
            in normalizar_nome(
                item["arquivo"]["name"]
            )
            else 1,
            item["arquivo"]["name"],
        )
    )

    escolhida = candidatas[0]

    arquivo = escolhida[
        "arquivo"
    ]

    sufixo = os.path.splitext(
        arquivo["name"]
    )[1] or ".png"

    temp = tempfile.NamedTemporaryFile(
        suffix=sufixo,
        delete=False,
    )

    caminho = temp.name
    temp.close()

    baixar_arquivo(
        arquivo["id"],
        caminho,
    )

    cor = validar_tipo_logo(
        caminho,
        escolhida["tipo"],
        arquivo["name"],
    )

    return (
        caminho,
        arquivo,
        escolhida["tipo"],
        cor,
    )


# =========================================================
# ANÁLISE DO FUNDO
# =========================================================

def luminancia_media(imagem):
    imagem = imagem.convert(
        "RGB"
    )

    stat = ImageStat.Stat(
        imagem
    )

    r, g, b = stat.mean

    return (
        0.2126 * r
        + 0.7152 * g
        + 0.0722 * b
    )


def variacao_visual(imagem):
    imagem = imagem.convert(
        "L"
    )

    stat = ImageStat.Stat(
        imagem
    )

    return stat.stddev[0]


# =========================================================
# FORMATO / SAFE AREA DE MARCA
# =========================================================

def eh_story(
    largura,
    altura,
):
    """
    Detecta canvas 9:16 com pequena tolerância.

    Feed continua exatamente com o comportamento anterior.
    """

    if (
        largura <= 0
        or altura <= 0
    ):
        return False

    proporcao = (
        largura
        / altura
    )

    return abs(
        proporcao
        - (
            9
            / 16
        )
    ) <= 0.015


def margem_vertical_logo(
    largura,
    altura,
    posicao,
):
    """
    No feed usamos a margem histórica de 4,5% da largura.

    No Story, elevamos a marca para fora das zonas mais
    disputadas pela interface do Instagram:
      - topo: aproximadamente 7,5% da altura;
      - rodapé: aproximadamente 10% da altura.

    Isso altera SOMENTE o posicionamento da marca em 9:16.
    """

    margem_padrao = int(
        largura
        * 0.045
    )

    if not eh_story(
        largura,
        altura,
    ):
        return margem_padrao

    if (
        posicao
        == "inferior_direito"
    ):
        return max(
            margem_padrao,
            int(
                altura
                * 0.10
            ),
        )

    if (
        posicao
        == "superior_direito"
    ):
        return max(
            margem_padrao,
            int(
                altura
                * 0.075
            ),
        )

    return margem_padrao


# =========================================================
# POSICIONAMENTO
# =========================================================

def calcular_area(
    largura,
    altura,
    largura_logo,
    altura_logo,
    margem,
    posicao,
):
    margem_y = margem_vertical_logo(
        largura,
        altura,
        posicao,
    )

    if posicao == "superior_direito":
        x = (
            largura
            - largura_logo
            - margem
        )

        y = margem_y

    elif posicao == "inferior_direito":
        x = (
            largura
            - largura_logo
            - margem
        )

        y = (
            altura
            - altura_logo
            - margem_y
        )

    else:
        raise ValueError(
            f"Posição inválida: {posicao}"
        )

    return (
        x,
        y,
        x + largura_logo,
        y + altura_logo,
    )


def escolher_posicao_logo(
    caminho_criativo,
    largura_logo_ratio=0.18,
):
    imagem = Image.open(
        caminho_criativo
    ).convert("RGB")

    largura, altura = (
        imagem.size
    )

    largura_logo = int(
        largura
        * largura_logo_ratio
    )

    altura_logo = int(
        largura_logo / 3
    )

    margem = int(
        largura * 0.045
    )

    resultados = []

    for posicao in [
        "inferior_direito",
        "superior_direito",
    ]:
        area = calcular_area(
            largura,
            altura,
            largura_logo,
            altura_logo,
            margem,
            posicao,
        )

        recorte = imagem.crop(
            area
        )

        lum = luminancia_media(
            recorte
        )

        variacao = variacao_visual(
            recorte
        )

        # Quanto menor a variação,
        # mais limpa a região.
        limpeza = max(
            0,
            35 - variacao
        )

        # Queremos priorizar inferior direito,
        # mas sem forçar quando estiver muito ruim.
        if (
            posicao
            == "inferior_direito"
        ):
            bonus_posicao = 12
        else:
            bonus_posicao = 3

        score = (
            limpeza
            + bonus_posicao
        )

        resultados.append({
            "posicao": posicao,
            "luminancia": lum,
            "variacao": variacao,
            "score": score,
        })

    resultados.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    melhor = resultados[0]

    # =====================================================
    # ESCOLHA DA COR DA LOGO
    # =====================================================

    # Fundo escuro/intermediário:
    # branco costuma ser mais elegante e legível.
    if (
        melhor["luminancia"]
        < 155
    ):
        tipo_logo = "branca"

    else:
        tipo_logo = "preta"

    return {
        "posicao": melhor[
            "posicao"
        ],
        "tipo_logo": tipo_logo,
        "diagnostico": resultados,
    }


# =========================================================
# APLICAÇÃO DA LOGO
# =========================================================

def aplicar_logo(
    caminho_criativo,
    caminho_logo,
    caminho_saida,
    posicao,
):
    criativo = Image.open(
        caminho_criativo
    ).convert("RGBA")

    logo = Image.open(
        caminho_logo
    ).convert("RGBA")

    largura, altura = (
        criativo.size
    )

    largura_logo = int(
        largura * 0.18
    )

    proporcao = (
        largura_logo
        / logo.width
    )

    altura_logo = int(
        logo.height
        * proporcao
    )

    logo = logo.resize(
        (
            largura_logo,
            altura_logo,
        ),
        Image.LANCZOS,
    )

    margem = int(
        largura * 0.045
    )

    area = calcular_area(
        largura,
        altura,
        largura_logo,
        altura_logo,
        margem,
        posicao,
    )

    x = area[0]
    y = area[1]

    if eh_story(
        largura,
        altura,
    ):
        print(
            "Logo Story safe-area:",
            f"posição={posicao}",
            f"x={x}",
            f"y={y}",
            f"canvas={largura}x{altura}",
            f"margem_vertical="
            f"{margem_vertical_logo(largura, altura, posicao)}",
            flush=True,
        )

    criativo.alpha_composite(
        logo,
        dest=(x, y),
    )

    criativo = criativo.convert(
        "RGB"
    )

    criativo.save(
        caminho_saida,
        "JPEG",
        quality=95,
        optimize=True,
    )

    return caminho_saida
