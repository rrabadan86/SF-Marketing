import os
import re
import time
import unicodedata
import requests

from creative_generator import (
    gerar_criativo,
)

from publisher import (
    finalizar_e_publicar,
)

from openai_client import (
    criar_briefing,
)

from history_manager import (
    registrar_criativo,
    buscar_criativo,
    atualizar_status,
    listar_ultimos,
)


TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN"
)

ALLOWED_CHAT_ID = str(
    os.getenv(
        "TELEGRAM_ALLOWED_CHAT_ID",
        "",
    )
)

if not TOKEN:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN não configurado"
    )


BASE_URL = (
    f"https://api.telegram.org/"
    f"bot{TOKEN}"
)


print(
    "Creative Agent iniciado com sucesso",
    flush=True,
)

print(
    "Telegram polling iniciado",
    flush=True,
)

print(
    "Motor SlimFit Dynamic iniciado",
    flush=True,
)

print(
    "Família SlimFit Event habilitada",
    flush=True,
)

print(
    "Família SlimFit Seasonal habilitada",
    flush=True,
)

print(
    "Histórico visual integrado",
    flush=True,
)

print(
    "Refazer inteligente habilitado",
    flush=True,
)

print(
    "Cooldown de fotos aprovadas habilitado",
    flush=True,
)

print(
    "Trocarfoto com design congelado habilitado",
    flush=True,
)

print(
    "Logo contextual por composição habilitada",
    flush=True,
)


offset = None


# =========================================================
# TELEGRAM
# =========================================================

def send_message(
    chat_id,
    text,
):
    response = requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
        },
        timeout=30,
    )

    response.raise_for_status()


def send_photo(
    chat_id,
    caminho,
    legenda=None,
):
    with open(
        caminho,
        "rb",
    ) as arquivo:
        response = requests.post(
            f"{BASE_URL}/sendPhoto",
            data={
                "chat_id": chat_id,
                "caption": (
                    legenda
                    or ""
                ),
            },
            files={
                "photo": (
                    "criativo.jpg",
                    arquivo,
                    "image/jpeg",
                ),
            },
            timeout=120,
        )

    response.raise_for_status()


# =========================================================
# /REFAZER
# =========================================================

def interpretar_refazer(
    texto,
):
    conteudo = texto[
        len(
            "/refazer"
        ):
    ].strip()

    if not conteudo:
        return (
            None,
            None,
        )

    partes = conteudo.split(
        maxsplit=1
    )

    codigo = (
        partes[
            0
        ]
        .strip()
        .upper()
    )

    instrucao = None

    if len(
        partes
    ) > 1:
        instrucao = (
            partes[
                1
            ].strip()
        )

    return (
        codigo,
        instrucao,
    )


def montar_pedido_refazer(
    item,
    instrucao=None,
):
    pedido_original = (
        item.get(
            "request"
        )
        or ""
    ).strip()

    if instrucao:
        return (
            pedido_original
            + "\n\n"
            + "INSTRUÇÃO DE REVISÃO DO USUÁRIO:\n"
            + instrucao
            + "\n\n"
            + "Mantenha o objetivo principal do "
            + "criativo anterior, mas a instrução "
            + "de revisão acima tem prioridade para "
            + "composição, estilo, cor, quantidade "
            + "de texto e copy."
        )

    return (
        pedido_original
        + "\n\n"
        + "Crie uma nova variação de headline, "
        + "texto de apoio e tratamento visual, "
        + "mantendo o mesmo objetivo."
    )


# =========================================================
# INTELIGÊNCIA DO /REFAZER
# =========================================================

def normalizar_instrucao(
    texto,
):
    texto = (
        texto
        or ""
    ).lower()

    texto = unicodedata.normalize(
        "NFD",
        texto,
    )

    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(
            caractere
        ) != "Mn"
    )

    return texto


def detectar_substituicao_literal(
    instrucao,
):
    """
    Detecta substituições literais com pequenas variações
    naturais de linguagem.

    Exemplos aceitos:
    - troque a frase "X" por "Y"
    - troque apenas a frase "X" por "Y"
    - substitua somente "X" por "Y"
    - substituir o texto "X" por "Y"
    - altere apenas a frase "X" para "Y"

    Aceita aspas normais e curvas.
    """

    if not instrucao:
        return None

    # Normaliza apenas espaços; preserva acentos e conteúdo
    # dentro das aspas.
    texto = re.sub(
        r"\s+",
        " ",
        instrucao,
    ).strip()

    verbo = (
        r"(?:troque|trocar|substitua|substituir|"
        r"altere|alterar|mude|mudar)"
    )

    modificador = (
        r"(?:\s+(?:apenas|somente|só|so))?"
    )

    alvo = (
        r"(?:\s+(?:a\s+frase|o\s+texto|a\s+mensagem|"
        r"o\s+cta|cta))?"
    )

    aspas_abre = r'["“”]'
    aspas_fecha = r'["“”]'

    ligacao = r"\s+(?:por|para)\s+"

    padrao = (
        verbo
        + modificador
        + alvo
        + r"\s*"
        + aspas_abre
        + r"(.+?)"
        + aspas_fecha
        + ligacao
        + aspas_abre
        + r"(.+?)"
        + aspas_fecha
    )

    match = re.search(
        padrao,
        texto,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    antigo = (
        match.group(
            1
        )
        .strip()
    )

    novo = (
        match.group(
            2
        )
        .strip()
    )

    if not antigo:
        return None

    return (
        antigo,
        novo,
    )



def detectar_copy_exata(
    instrucao,
):
    """
    Detecta pedidos do tipo:

    altere a copy para: TEXTO...
    mude a copy para: TEXTO...
    substitua a copy por: TEXTO...

    Nesse modo o texto informado pelo usuário vira o texto
    de apoio EXATAMENTE, sem reescrita por IA.
    """

    if not instrucao:
        return None

    texto = re.sub(
        r"\s+",
        " ",
        instrucao,
    ).strip()

    padrao = (
        r"(?:altere|alterar|mude|mudar|troque|trocar|"
        r"substitua|substituir)"
        r"(?:\s+(?:apenas|somente|só|so))?"
        r"\s+(?:a\s+)?copy"
        r"\s+(?:para|por)\s*:?\s*"
        r"(.+)$"
    )

    match = re.search(
        padrao,
        texto,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    copy_texto = (
        match.group(1)
        .strip()
    )

    # Remove somente instruções finais de controle.
    # Inclui o erro comum "apens".
    copy_texto = re.sub(
        r"\s*(?:faça|faca)\s+"
        r"(?:apenas|apens|somente|só|so)\s+"
        r"(?:isso|o\s+que\s+solicitei)"
        r"[!.]*\s*$",
        "",
        copy_texto,
        flags=re.IGNORECASE,
    ).strip()

    copy_texto = re.sub(
        r"\s*não\s+altere\s+mais\s+nada"
        r"[!.]*\s*$",
        "",
        copy_texto,
        flags=re.IGNORECASE,
    ).strip()

    if not copy_texto:
        return None

    return copy_texto


def detectar_ajuste_tipografia(
    instrucao,
):
    """
    Detecta ajustes de tamanho de fonte sem tratar isso como
    alteração de conteúdo da copy.

    Exemplos:
    - aumente um pouco a fonte da copy
    - aumente a fonte do texto de apoio
    - diminua um pouco a fonte da copy
    - aumente bastante a fonte da headline
    """

    if not instrucao:
        return None

    texto = normalizar_instrucao(
        instrucao
    )

    if (
        "fonte"
        not in texto
        and "letra"
        not in texto
    ):
        return None

    alvo = "support"

    if (
        "headline" in texto
        or "titulo" in texto
    ):
        alvo = "headline"

    elif (
        "cta" in texto
        or "botao" in texto
        or "chamada" in texto
    ):
        alvo = "cta"

    elif (
        "copy" in texto
        or "texto de apoio" in texto
        or "texto" in texto
    ):
        alvo = "support"

    direcao = None

    if any(
        termo in texto
        for termo in [
            "aumente",
            "aumentar",
            "maior",
            "mais grande",
        ]
    ):
        direcao = 1

    elif any(
        termo in texto
        for termo in [
            "diminua",
            "diminuir",
            "reduza",
            "reduzir",
            "menor",
        ]
    ):
        direcao = -1

    if direcao is None:
        return None

    intensidade = 2

    if any(
        termo in texto
        for termo in [
            "bastante",
            "bem mais",
            "muito",
            "consideravelmente",
        ]
    ):
        intensidade = 4

    elif any(
        termo in texto
        for termo in [
            "um pouco",
            "pouco",
            "levemente",
            "ligeiramente",
        ]
    ):
        intensidade = 2

    return {
        "target": alvo,
        "delta": (
            direcao
            * intensidade
        ),
    }


def somar_ajustes_tipografia(
    texto,
):
    """
    Soma os ajustes de fonte presentes no histórico acumulado
    do request. Assim um /refazer posterior continua herdando
    o tamanho de fonte já ajustado.
    """

    if not texto:
        return {}

    normalizado = normalizar_instrucao(
        texto
    )

    resultados = {
        "support_font_delta": 0,
        "headline_font_delta": 0,
        "cta_font_delta": 0,
    }

    # Divide o histórico em frases/blocos para não confundir
    # instruções diferentes.
    partes = re.split(
        r"[\n.!?]+",
        normalizado,
    )

    for parte in partes:
        ajuste = detectar_ajuste_tipografia(
            parte
        )

        if not ajuste:
            continue

        chave = (
            ajuste[
                "target"
            ]
            + "_font_delta"
        )

        resultados[
            chave
        ] += ajuste[
            "delta"
        ]

    # Limites para evitar tamanhos absurdos após muitas revisões.
    for chave in list(
        resultados.keys()
    ):
        resultados[
            chave
        ] = max(
            -8,
            min(
                8,
                resultados[
                    chave
                ],
            ),
        )

    return {
        chave: valor
        for chave, valor
        in resultados.items()
        if valor
    }

def instrucao_modo_estrito(
    instrucao,
):
    texto = normalizar_instrucao(
        instrucao
    )

    marcadores = [
        "faca apenas isso",
        "faca apens isso",
        "faca somente isso",
        "apenas o que solicitei",
        "somente o que solicitei",
        "nao altere mais nada",
        "nao mude mais nada",
        "mantenha exatamente",
        "altere apenas",
        "substitua apenas",
        "troque apenas",
    ]

    return any(
        marcador in texto
        for marcador in marcadores
    )


def instrucao_preserva_copy(
    instrucao,
):
    """
    Detecta instruções de PRESERVAÇÃO de texto/copy.

    Exemplos:
    - não altere os textos
    - preserve os textos
    - mantenha os textos atuais
    - sem mudar a copy

    Essas frases NÃO significam pedido de edição textual.
    Elas significam que o usuário quer alterar outra dimensão
    (foto/layout/elemento visual) mantendo a copy congelada.
    """

    texto = normalizar_instrucao(
        instrucao
    )

    padroes_preservacao = [
        "nao altere os textos",
        "não altere os textos",
        "nao altere nenhum texto",
        "não altere nenhum texto",
        "nao altere o texto",
        "não altere o texto",
        "nao mude os textos",
        "não mude os textos",
        "nao mude o texto",
        "não mude o texto",
        "mantenha os textos",
        "mantenha o texto",
        "mantenha a copy",
        "preserve os textos",
        "preserve o texto",
        "preserve a copy",
        "sem alterar os textos",
        "sem alterar o texto",
        "sem mudar os textos",
        "sem mudar o texto",
        "sem mexer nos textos",
        "sem mexer no texto",
        "nao altere os textos restantes",
        "não altere os textos restantes",
        "nao altere os demais textos",
        "não altere os demais textos",
        "preserve os textos restantes",
        "preserve os demais textos",
    ]

    return any(
        padrao in texto
        for padrao in padroes_preservacao
    )


def instrucao_pede_mudanca_explicita_copy(
    instrucao,
):
    """
    Detecta apenas pedidos inequívocos de ALTERAÇÃO de conteúdo.
    Isso evita que frases de preservação como
    'não altere os textos' sejam confundidas com edição de copy.
    """

    texto = normalizar_instrucao(
        instrucao
    )

    sinais = [
        "reescreva",
        "reformule",
        "novo texto",
        "nova frase",
        "nova headline",
        "troque o texto",
        "troque a frase",
        "troque a headline",
        "troque a copy",
        "substitua o texto",
        "substitua a frase",
        "substitua a headline",
        "substitua a copy",
        "altere o texto para",
        "mude o texto para",
        "headline para",
        "cta para",
        "escreva",
    ]

    return any(
        sinal in texto
        for sinal in sinais
    )


def instrucao_pede_copy(
    instrucao,
):
    texto = normalizar_instrucao(
        instrucao
    )

    # Frases como "não altere os textos" são ordens de
    # PRESERVAÇÃO, não pedidos de edição textual.
    if (
        instrucao_preserva_copy(
            instrucao
        )
        and not instrucao_pede_mudanca_explicita_copy(
            instrucao
        )
    ):
        return False

    # "aumente o destaque do CTA", "mude a cor do CTA",
    # "destaque o CTA" etc. são alterações VISUAIS do CTA,
    # não alterações do conteúdo textual.
    cta_visual = (
        "cta" in texto
        and any(
            termo in texto
            for termo in [
                "destaque",
                "cor",
                "fonte",
                "tamanho",
                "maior",
                "menor",
                "botao",
                "botão",
                "contraste",
                "peso",
            ]
        )
        and not any(
            termo in texto
            for termo in [
                "troque o cta",
                "substitua o cta",
                "reescreva o cta",
                "altere o texto do cta",
                "mude o texto do cta",
                "cta para",
                "cta:",
            ]
        )
    )

    # Criação de selo/badge com um texto específico deve ser
    # tratada como ajuste visual, não como reescrita de copy.
    badge_visual = (
        any(
            termo in texto
            for termo in [
                "selo",
                "badge",
                "faixa",
            ]
        )
        and any(
            termo in texto
            for termo in [
                "com o texto",
                "texto no selo",
                "texto do selo",
                "texto no badge",
                "texto do badge",
                "destaque visual",
            ]
        )
        and not any(
            termo in texto
            for termo in [
                "headline",
                "copy",
                "texto de apoio",
                "cta",
                "troque a headline",
                "substitua a headline",
                "troque a copy",
                "substitua a copy",
                "troque o texto de apoio",
                "substitua o texto de apoio",
            ]
        )
    )

    if badge_visual:
        return False

    termos = [
        "headline",
        "copy",
        "texto",
        "frase",
        "mensagem",
        "chamada",
        "titulo",
        "palavra",
        "escreva",
        "reescreva",
        "reformule",
        "troque",
        "substitua",
        "motivacional",
    ]

    if any(
        termo in texto
        for termo in termos
    ):
        return True

    if (
        "cta" in texto
        and not cta_visual
    ):
        return True

    return False


def instrucao_pede_visual(
    instrucao,
):
    texto = normalizar_instrucao(
        instrucao
    )

    termos = [
        "layout",
        "composicao",
        "espaco",
        "areas vazias",
        "area vazia",
        "foto maior",
        "foto menor",
        "aumente a foto",
        "reduza a foto",
        "fundo",
        "cor",
        "cores",
        "posicao",
        "tamanho",
        "margem",
        "respiro",
        "caixa",
        "bloco",
        "badge",
        "selo",
        "grafismo",
        "elemento",
        "hierarquia",
        "zoom",
        "enquadramento",
        "moldura",
        "cabeca",
        "cabeça",
        "medalha",
        "trofeu",
        "troféu",
        "aproxime",
        "aproximar",
        "afaste",
        "afastar",
        "centralize",
        "centralizar",
        "centro da foto",
        "no centro da foto",
        "enquadre",
        "enquadrar",
    ]

    return any(
        termo in texto
        for termo in termos
    )




def detectar_ajuste_layout(
    instrucao,
):
    """
    Detecta pedidos que são exclusivamente de organização
    visual do bloco textual, sem alteração de conteúdo.

    Exemplos:
    - ajuste apenas o layout
    - realinhe headline, apoio e CTA
    - dê mais respiro
    - reorganize o bloco textual
    - mantenha os mesmos textos
    """

    texto = normalizar_instrucao(
        instrucao
    )

    termos_layout = [
        "ajuste de layout",
        "ajuste fino",
        "apenas ajuste de layout",
        "realinhe",
        "realinhar",
        "alinhe",
        "alinhar",
        "reorganize",
        "reorganizar",
        "reposicione",
        "reposicionar",
        "bloco textual",
        "bloco de texto",
        "mesmo eixo",
        "alinhados entre si",
        "mais respiro",
        "espacamento",
        "espaçamento",
        "melhor distribuicao",
        "melhor distribuição",
        "mais organizado visualmente",
        "organize visualmente",
    ]

    detectado = any(
        termo in texto
        for termo in termos_layout
    )

    if not detectado:
        return False

    # Se a própria instrução diz para preservar textos/copy,
    # tratamos como layout-only mesmo que apareçam as palavras
    # "texto", "copy", "headline" ou "CTA".
    preservar_copy = any(
        termo in texto
        for termo in [
            "mesma copy",
            "mesmos textos",
            "mantenha exatamente os mesmos textos",
            "mantenha os mesmos textos",
            "nao substitua nenhum texto",
            "não substitua nenhum texto",
            "sem alterar o texto",
            "sem alterar os textos",
            "preserve exatamente a mesma copy",
            "mantenha a mesma copy",
        ]
    )

    return bool(
        detectado
        and preservar_copy
    )



def extrair_elementos_para_ocultar(
    instrucao,
):
    """
    Extrai elementos que o usuário pediu para NÃO exibir.

    A saída é genérica e pode ser consumida por qualquer renderer.
    Reconhece tanto remoção de algo já existente quanto pedidos de
    criação do tipo "não coloque X", "não mostre X" ou "sem X".
    """

    if not instrucao:
        return []

    bruto = normalizar_espacos_comando(
        instrucao
    )

    alvos = []

    conhecidos = [
        "AULA EXPERIMENTAL",
        "EDIÇÃO ESPECIAL",
        "MAIS MOVIMENTO",
        "MAIS CONEXÃO",
        "MAIS SLIMFIT",
    ]

    # --------------------------------------------------
    # 1. REMOÇÃO EXPLÍCITA
    # --------------------------------------------------
    padrao_remocao = re.compile(
        r'(?i)(?:remova|retire|exclua|tire|remover|retirar|excluir)'
        r'[^.!?\n]{0,240}'
    )

    # --------------------------------------------------
    # 2. NÃO INCLUIR / NÃO MOSTRAR
    # --------------------------------------------------
    # Importante para /criarfoto, em que o elemento ainda nem
    # existe no histórico. Ex.:
    #   "Não coloque MAIS MOVIMENTO..."
    # --------------------------------------------------
    padrao_nao_incluir = re.compile(
        r'(?i)(?:'
        r'n[aã]o\s+(?:coloque|inclua|mostre|exiba|adicione|use)|'
        r'omita|sem\s+'
        r')'
        r'[^.!?\n]{0,240}'
    )

    trechos = []

    trechos.extend(
        padrao_remocao.findall(
            bruto
        )
    )

    trechos.extend(
        padrao_nao_incluir.findall(
            bruto
        )
    )

    # Conteúdo entre aspas só vira alvo quando aparece dentro
    # de uma oração de remoção/não inclusão.
    for trecho in trechos:
        for alvo in re.findall(
            r'["“”]([^"“”]{2,120})["“”]',
            trecho,
        ):
            alvo = alvo.strip()

            if alvo:
                alvos.append(
                    alvo
                )

    # Elementos estruturais conhecidos podem ser citados sem aspas.
    for trecho in trechos:
        trecho_norm = normalizar_instrucao(
            trecho
        )

        for conhecido in conhecidos:
            if normalizar_instrucao(
                conhecido
            ) in trecho_norm:
                alvos.append(
                    conhecido
                )

    # Caso comum: "sem MAIS MOVIMENTO, MAIS CONEXÃO...".
    texto_norm = normalizar_instrucao(
        instrucao
    )

    for conhecido in conhecidos:
        conhecido_norm = normalizar_instrucao(
            conhecido
        )

        if re.search(
            rf'\bsem\b[^.!?\n]{{0,180}}{re.escape(conhecido_norm)}',
            texto_norm,
        ):
            alvos.append(
                conhecido
            )

    resultado = []
    vistos = set()

    for alvo in alvos:
        chave = normalizar_instrucao(
            alvo
        )

        if not chave or chave in vistos:
            continue

        vistos.add(
            chave
        )

        resultado.append(
            alvo
        )

    return resultado

def pedido_preserva_enquadramento(
    instrucao,
):
    """
    Detecta preservação EXPLÍCITA do enquadramento da foto.

    A regra antiga cruzava palavras distantes no pedido inteiro.
    Exemplo problemático:

      "Dê menos zoom na foto... Preserve o estilo atual da composição."

    Como existiam "preserve" e "foto" em pontos diferentes,
    o parser concluía incorretamente que o usuário queria preservar
    o enquadramento.

    Agora a preservação só é ativada quando o verbo e o objeto
    fotográfico aparecem na mesma frase/segmento.
    """

    texto = normalizar_instrucao(
        instrucao
    )

    if not texto:
        return False

    segmentos = re.split(
        r'[\n\.!?;]+',
        texto,
    )

    verbos_preservar = [
        "preserve",
        "preservar",
        "mantenha",
        "manter",
        "nao mude",
        "não mude",
        "nao altere",
        "não altere",
    ]

    objetos_fotograficos = [
        "enquadramento",
        "zoom da foto",
        "zoom atual",
        "foto como esta",
        "foto como está",
        "fotografia como esta",
        "fotografia como está",
        "imagem como esta",
        "imagem como está",
        "posicao da foto",
        "posição da foto",
        "recorte da foto",
        "crop da foto",
        "framing da foto",
    ]

    for segmento in segmentos:
        segmento = segmento.strip()

        if not segmento:
            continue

        tem_verbo = any(
            verbo in segmento
            for verbo in verbos_preservar
        )

        if not tem_verbo:
            continue

        if any(
            objeto in segmento
            for objeto in objetos_fotograficos
        ):
            return True

        # Forma direta muito comum:
        # "preserve exatamente a foto" / "mantenha a foto".
        if re.search(
            r'\b(preserve|preservar|mantenha|manter)\b.{0,28}\b(foto|fotografia|imagem)\b',
            segmento,
        ):
            return True

    return False


def pedido_pede_centralizar_assunto(
    instrucao,
):
    """
    Detecta pedidos objetivos de centralização do sujeito na foto.

    Exemplos:
      - centralize a aluna
      - enquadre a aluna no centro da foto
      - deixe a pessoa mais no centro
    """

    texto = normalizar_instrucao(
        instrucao
    )

    if not texto:
        return False

    termos_centro = [
        "centralize",
        "centralizar",
        "centro da foto",
        "no centro da foto",
        "mais no centro",
        "enquadre a aluna no centro",
        "enquadre no centro",
        "aluna no centro",
        "pessoa no centro",
        "sujeito no centro",
    ]

    return any(
        termo in texto
        for termo in termos_centro
    )


def pedido_pede_menos_zoom(
    instrucao,
):
    """
    Detecta pedidos explícitos de afastamento/mais área visível.
    """

    texto = normalizar_instrucao(
        instrucao
    )

    if not texto:
        return None

    expressoes_zoom_out = [
        "menos zoom",
        "menos de zoom",
        "de menos zoom",
        "dê menos zoom",
        "de um pouco menos de zoom",
        "dê um pouco menos de zoom",
        "um pouco menos de zoom",
        "um pouco menos zoom",
        "reduza o zoom",
        "reduzir o zoom",
        "diminua o zoom",
        "diminuir o zoom",
        "afaste a foto",
        "afaste a fotografia",
        "afaste a imagem",
        "deixe a foto mais afastada",
        "deixe a aluna mais afastada",
        "mostrar mais",
        "mostre mais",
        "quero ver mais",
        "corpo inteiro",
        "corpo todo",
        "de corpo inteiro",
        "mostrar o corpo todo",
        "mostrar as pernas",
        "ver as pernas",
        "as pernas",
    ]

    detectou_zoom_out = any(
        termo in texto
        for termo in expressoes_zoom_out
    )

    # Regra estrutural: qualquer pedido afirmativo que contenha
    # "zoom" + ideia de redução/afastamento também é zoom-out.
    # Isso evita depender de cada variação linguística possível.
    if (
        "zoom" in texto
        and any(
            termo in texto
            for termo in [
                "menos",
                "reduza",
                "reduzir",
                "diminua",
                "diminuir",
                "afaste",
                "afastar",
            ]
        )
    ):
        detectou_zoom_out = True

    if not detectou_zoom_out:
        return None

    zoom = 0.92
    zoom_delta = -0.08
    strength = 0.78

    if any(
        termo in texto
        for termo in [
            "um pouco menos de zoom",
            "um pouco menos zoom",
            "de um pouco menos de zoom",
            "dê um pouco menos de zoom",
        ]
    ):
        zoom = 0.95
        zoom_delta = -0.05
        strength = 0.62

    if any(
        termo in texto
        for termo in [
            "bem menos zoom",
            "muito menos zoom",
            "mais afastada",
            "mais afastado",
            "mostrar o trofeu",
            "mostrar o troféu",
            "mostrar a medalha",
            "ver o trofeu",
            "ver o troféu",
            "ver a medalha",
            "aparece pouco",
            "aparecendo pouco",
            "corpo inteiro",
            "corpo todo",
            "de corpo inteiro",
            "mostrar as pernas",
            "ver as pernas",
            "as pernas",
        ]
    ):
        zoom = 0.88
        zoom_delta = -0.12
        strength = 0.92

    return {
        "intent": "zoom_out_subject",
        "strength": strength,
        "zoom": zoom,
        "zoom_delta": zoom_delta,
    }


def pedido_quer_corpo_inteiro(
    instrucao,
):
    """
    Detecta o pedido explícito de "corpo inteiro / pernas".

    Numa moldura de feed (horizontal) isso é geometricamente impossível
    sem cortar; o formato certo é o Story (vertical). O chamador usa isto
    para converter o /refazer em geração de Story.
    """

    texto = normalizar_instrucao(
        instrucao
    )

    if not texto:
        return False

    return any(
        termo in texto
        for termo in [
            "corpo inteiro",
            "corpo todo",
            "de corpo inteiro",
            "mostrar o corpo todo",
            "mostrar as pernas",
            "ver as pernas",
            "as pernas",
        ]
    )


def pedido_pede_mais_headroom(
    instrucao,
):
    """
    Interpreta "menos zoom porque cortou a cabeça" como pedido de
    mais folga no topo, sem obrigar o renderer a usar contain.
    """

    texto = normalizar_instrucao(
        instrucao
    )

    menciona_cabeca = (
        "cabeca" in texto
        or "cabeça" in texto
    )

    problema_corte = any(
        termo in texto
        for termo in [
            "cortada",
            "cortado",
            "corte",
            "cortar",
            "cortando",
            "sem cortar",
            "nao corte",
            "não corte",
            "saiu cortada",
            "ficou cortada",
        ]
    )

    pede_menos_zoom = any(
        termo in texto
        for termo in [
            "menos zoom",
            "de menos zoom",
            "dê menos zoom",
            "reduza o zoom",
            "diminua o zoom",
            "afaste a foto",
            "mais afastada",
        ]
    )

    return bool(
        menciona_cabeca
        and problema_corte
        and pede_menos_zoom
    )


def pedido_pede_mostrar_mais_parte_inferior(
    instrucao,
):
    """
    Detecta pedidos como:
      - "dê menos zoom, o troféu aparece pouco"
      - "mostre melhor a medalha"
      - "quero ver mais o prêmio"

    Em molduras horizontais, reduzir o zoom de verdade exigiria
    letterbox/laterais. A intenção visual correta é deslocar o crop
    para baixo, preservando o preenchimento integral da moldura.
    """

    texto = normalizar_instrucao(
        instrucao
    )

    pede_menos_zoom = any(
        termo in texto
        for termo in [
            "menos zoom",
            "de menos zoom",
            "dê menos zoom",
            "reduza o zoom",
            "diminua o zoom",
            "afaste a foto",
            "mais afastada",
            "mostre mais",
        ]
    )

    objetos_inferiores = any(
        termo in texto
        for termo in [
            "trofeu",
            "troféu",
            "medalha",
            "premio",
            "prêmio",
            "placa",
            "certificado",
            "objeto",
            "tronco",
            "corpo",
        ]
    )

    pouca_visibilidade = any(
        termo in texto
        for termo in [
            "aparece pouco",
            "aparecendo pouco",
            "aparecendopouco",
            "esta aparecendo pouco",
            "está aparecendo pouco",
            "quase nao aparece",
            "quase não aparece",
            "mais visivel",
            "mais visível",
            "melhor visivel",
            "melhor visível",
        ]
    )

    return bool(
        objetos_inferiores
        and (
            pede_menos_zoom
            or pouca_visibilidade
        )
    )



def pedido_pede_mais_zoom(
    instrucao,
):
    """
    Detecta pedido explícito para APROXIMAR a fotografia.

    Este intent é separado de ``safe_subject`` porque simplesmente
    alterar o foco do crop não aumenta o tamanho visual da pessoa.
    O renderer recebe ``photo_zoom`` > 1.0 e aplica zoom real dentro
    da moldura, preservando o estilo/crop base.
    """

    texto = normalizar_instrucao(
        instrucao
    )

    expressoes_zoom = [
        "mais zoom",
        "de mais zoom",
        "dê mais zoom",
        "aumente o zoom",
        "aumentar o zoom",
        "aproxime a foto",
        "aproxime a fotografia",
        "aproxime a imagem",
        "deixe a foto mais proxima",
        "deixe a foto mais próxima",
        "deixe ela mais proxima",
        "deixe ela mais próxima",
        "deixe a aluna mais proxima",
        "deixe a aluna mais próxima",
        "deixe a pessoa maior",
        "deixe a aluna maior",
        "amplie a foto",
        "amplie a fotografia",
        "aproxime a aluna",
    ]

    if not any(
        termo in texto
        for termo in expressoes_zoom
    ):
        return None

    # Intensidade padrão moderada: suficiente para ser visualmente
    # perceptível sem transformar um /refazer em novo enquadramento.
    zoom = 1.14
    strength = 0.72

    if any(
        termo in texto
        for termo in [
            "bem mais zoom",
            "muito mais zoom",
            "bem mais proxima",
            "bem mais próxima",
            "mais proximo do quadro",
            "mais próximo do quadro",
            "mais proxima do quadro",
            "mais próxima do quadro",
            "no limite da medalha",
            "ate a medalha",
            "até a medalha",
        ]
    ):
        zoom = 1.18
        strength = 0.9

    return {
        "intent": "zoom_in_subject",
        "strength": strength,
        "zoom": zoom,
        "zoom_delta": round(
            zoom - 1.0,
            3,
        ),
    }

def detectar_ajustes_visuais_cirurgicos(
    instrucao,
):
    """
    Interpreta alterações visuais objetivas que não exigem
    substituição literal de texto.

    Exemplos:
    - remova apenas o selo "AULA EXPERIMENTAL"
    - aumente um pouco o destaque do CTA
    - não altere mais nada
    """

    texto = normalizar_instrucao(
        instrucao
    )

    ajustes = {}

    # Se o usuário pedir explicitamente para manter os
    # espaçamentos/posições, a remoção do elemento deve deixar
    # um "slot invisível" no mesmo lugar. Assim nada abaixo sobe.
    preservar_espacamentos = any(
        termo in texto
        for termo in [
            "mantenha todos os espacamentos",
            "mantenha todos os espaçamentos",
            "mantenha os espacamentos",
            "mantenha os espaçamentos",
            "mantenha os espacos",
            "mantenha os espaços",
            "mantenha os espacos que ja existem",
            "mantenha os espaços que já existem",
            "preserve todos os espacamentos",
            "preserve todos os espaçamentos",
            "preserve os espacamentos",
            "preserve os espaçamentos",
            "sem alterar os espacamentos",
            "sem alterar os espaçamentos",
            "nao altere os espacamentos",
            "não altere os espaçamentos",
            "mantenha exatamente as posicoes",
            "mantenha exatamente as posições",
            "preserve as posicoes",
            "preserve as posições",
        ]
    )

    if preservar_espacamentos:
        ajustes[
            "preserve_removed_space"
        ] = True

        ajustes[
            "preserve_positions"
        ] = True

    if detectar_ajuste_layout(
        instrucao
    ):
        ajustes[
            "layout_fine_tune"
        ] = True

        ajustes[
            "text_block_align_left"
        ] = True

        ajustes[
            "text_spacing_balanced"
        ] = True


    verbos_remocao = [
        "remova",
        "retire",
        "exclua",
        "tire",
        "remover",
        "retirar",
        "excluir",
    ]

    pediu_remocao = any(
        termo in texto
        for termo in verbos_remocao
    )

    # --------------------------------------------------
    # ELEMENTOS VISUAIS GENÉRICOS
    # --------------------------------------------------

    hide_elements = extrair_elementos_para_ocultar(
        instrucao
    )

    if hide_elements:
        ajustes[
            "hide_elements"
        ] = hide_elements

    hide_norm = {
        normalizar_instrucao(
            alvo
        )
        for alvo in hide_elements
    }

    # Compatibilidade com layouts existentes: só oculta o badge
    # de campanha se ele próprio foi alvo da remoção.
    if (
        "aula experimental" in hide_norm
        or "edicao especial" in hide_norm
        or "edição especial" in hide_norm
    ):
        ajustes[
            "hide_badge"
        ] = True

    if (
        "cta" in texto
        and (
            pediu_remocao
            or "sem cta" in texto
        )
    ):
        ajustes[
            "hide_cta"
        ] = True

    pilares_norm = {
        "mais movimento",
        "mais conexao",
        "mais conexão",
        "mais slimfit",
    }

    if any(
        alvo in pilares_norm
        for alvo in hide_norm
    ):
        ajustes[
            "hide_campaign_pillars"
        ] = True

    if (
        ajustes.get(
            "hide_campaign_pillars"
        )
        and any(
            termo in texto
            for termo in [
                "diminua os espacos vazios",
                "diminua os espaços vazios",
                "reduza os espacos vazios",
                "reduza os espaços vazios",
                "reorganize o espaco vazio",
                "reorganize o espaço vazio",
                "compacte o rodape",
                "compacte o rodapé",
                "diminua o espaco vazio",
                "diminua o espaço vazio",
                "apos a exclusao",
                "após a exclusão",
            ]
        )
    ):
        ajustes[
            "compact_footer_space"
        ] = True

    if (
        "cta" in texto
        and any(
            termo in texto
            for termo in [
                "destaque",
                "destacar",
                "mais destaque",
                "contraste",
                "mais visivel",
                "mais visível",
            ]
        )
    ):
        ajustes[
            "cta_emphasis"
        ] = True

    if (
        "cta" in texto
        and any(
            termo in texto
            for termo in [
                "aumente",
                "maior",
                "aumentar",
            ]
        )
    ):
        ajustes[
            "cta_font_delta"
        ] = 3


    # --------------------------------------------------
    # ENQUADRAMENTO / FOTO - INTENÇÕES GENÉRICAS
    # --------------------------------------------------

    preservar_enquadramento = pedido_preserva_enquadramento(
        instrucao
    )

    if preservar_enquadramento:
        ajustes[
            "preserve_photo_framing"
        ] = True

    zoom_in_request = (
        None
        if preservar_enquadramento
        else pedido_pede_mais_zoom(
            instrucao
        )
    )

    zoom_out_request = (
        None
        if preservar_enquadramento or zoom_in_request
        else pedido_pede_menos_zoom(
            instrucao
        )
    )

    centralizar_assunto = (
        False
        if preservar_enquadramento
        else pedido_pede_centralizar_assunto(
            instrucao
        )
    )

    if zoom_in_request:
        ajustes[
            "photo_reframe"
        ] = {
            "intent": "zoom_in_subject",
            "strength": zoom_in_request[
                "strength"
            ],
        }

        ajustes[
            "preserve_photo_framing"
        ] = False

        ajustes[
            "photo_mode"
        ] = "safe_cover"

        ajustes[
            "photo_zoom"
        ] = zoom_in_request[
            "zoom"
        ]

        ajustes[
            "photo_zoom_delta"
        ] = zoom_in_request.get(
            "zoom_delta",
            zoom_in_request["zoom"] - 1.0,
        )

        ajustes[
            "photo_focus_x"
        ] = 0.5

        if any(
            termo in texto
            for termo in [
                "medalha",
                "trofeu",
                "troféu",
                "premio",
                "prêmio",
            ]
        ):
            ajustes[
                "photo_safe_focus_y"
            ] = 0.16
            ajustes[
                "photo_zoom_focus_y"
            ] = 0.58
        else:
            ajustes[
                "photo_safe_focus_y"
            ] = 0.12
            ajustes[
                "photo_zoom_focus_y"
            ] = 0.46

    elif zoom_out_request:
        ajustes[
            "photo_reframe"
        ] = {
            "intent": "zoom_out_subject",
            "strength": zoom_out_request[
                "strength"
            ],
        }

        ajustes[
            "preserve_photo_framing"
        ] = False

        # "Menos zoom" é aplicado pelo enquadramento unificado
        # (ajustar_foto_na_moldura), que preenche sempre a moldura e
        # trata o afastamento de forma contínua, sem a antiga tira
        # flutuante sobre fundo borrado do modo smart_contain.
        ajustes[
            "photo_mode"
        ] = "cover"

        ajustes[
            "photo_zoom"
        ] = zoom_out_request[
            "zoom"
        ]

        ajustes[
            "photo_zoom_delta"
        ] = zoom_out_request.get(
            "zoom_delta",
            zoom_out_request["zoom"] - 1.0,
        )

        ajustes[
            "photo_focus_x"
        ] = 0.5

        if pedido_pede_mais_headroom(
            instrucao
        ):
            ajustes[
                "avoid_head_crop"
            ] = True
            ajustes[
                "photo_focus_y"
            ] = 0.20

        elif pedido_pede_mostrar_mais_parte_inferior(
            instrucao
        ):
            ajustes[
                "photo_focus_y"
            ] = 0.38

        else:
            ajustes[
                "photo_focus_y"
            ] = 0.30

        if centralizar_assunto:
            ajustes[
                "photo_focus_x"
            ] = 0.5

    elif (
        not preservar_enquadramento
        and pedido_pede_mais_headroom(
            instrucao
        )
    ):
        ajustes[
            "photo_reframe"
        ] = {
            "intent": "more_headroom",
            "strength": 0.95,
        }

        ajustes[
            "preserve_photo_framing"
        ] = False

        ajustes[
            "avoid_head_crop"
        ] = True

        ajustes[
            "photo_mode"
        ] = "safe_cover"

        ajustes[
            "photo_safe_focus_y"
        ] = 0.0

    elif (
        not preservar_enquadramento
        and pedido_pede_mostrar_mais_parte_inferior(
            instrucao
        )
    ):
        ajustes[
            "photo_reframe"
        ] = {
            "intent": "show_lower_subject",
            "strength": 0.8,
        }

        ajustes[
            "preserve_photo_framing"
        ] = False

        ajustes[
            "photo_mode"
        ] = "safe_cover"

        ajustes[
            "photo_safe_focus_y"
        ] = 0.24

    elif centralizar_assunto:
        ajustes[
            "photo_reframe"
        ] = {
            "intent": "center_subject",
            "strength": 0.7,
        }

        ajustes[
            "preserve_photo_framing"
        ] = False

        ajustes[
            "photo_focus_x"
        ] = 0.5

        ajustes[
            "photo_mode"
        ] = "safe_cover"

        ajustes.setdefault(
            "photo_safe_focus_y",
            0.12,
        )

    elif (
        not preservar_enquadramento
        and any(
            termo in texto
            for termo in [
                "enquadramento",
                "moldura superior",
                "moldura",
                "zoom",
                "cabeca",
                "cabeça",
                "medalha",
                "trofeu",
                "troféu",
                "apareca inteira",
                "apareça inteira",
                "sem cortar",
                "nao fique cortada",
                "não fique cortada",
            ]
        )
    ):
        ajustes[
            "photo_reframe"
        ] = {
            "intent": "safe_subject",
            "strength": 0.6,
        }

        ajustes[
            "preserve_photo_framing"
        ] = False

    if (
        not preservar_enquadramento
        and any(
            termo in texto
            for termo in [
                "cabeca nao fique cortada",
                "cabeça nao fique cortada",
                "cabeça não fique cortada",
                "cabeca da aluna nao seja cortada",
                "cabeça da aluna nao seja cortada",
                "cabeça da aluna não seja cortada",
                "nao corte a cabeca",
                "não corte a cabeça",
                "sem cortar a cabeca",
                "sem cortar a cabeça",
                "garanta que a cabeca",
                "garanta que a cabeça",
            ]
        )
    ):
        ajustes[
            "avoid_head_crop"
        ] = True

        # IMPORTANTE: esta é uma proteção de cabeça, não uma ordem
        # para trocar o modo de enquadramento. Se o pedido explícito
        # já escolheu smart_contain/contain (ex.: "menos zoom"),
        # preservar esse modo tem prioridade. Antes, este bloco
        # sobrescrevia smart_contain por safe_cover e anulava o pedido.
        modo_foto_atual = ajustes.get(
            "photo_mode"
        )

        if modo_foto_atual not in {
            "smart_contain",
            "contain",
        }:
            ajustes[
                "photo_mode"
            ] = "safe_cover"

            ajustes.setdefault(
                "photo_safe_focus_y",
                0.12,
            )
        else:
            # Em contain/smart_contain, proteger a cabeça significa
            # ancorar discretamente a foto mais para cima, sem mudar
            # o modo solicitado pelo usuário.
            ajustes[
                "photo_focus_y"
            ] = min(
                float(
                    ajustes.get(
                        "photo_focus_y",
                        0.24,
                    )
                    or 0.24
                ),
                0.24,
            )

    if (
        not preservar_enquadramento
        and any(
            termo in texto
            for termo in [
                "medalha apareca",
                "medalha apareça",
                "medalha bem visivel",
                "medalha bem visível",
                "mantenha a medalha visivel",
                "mantenha a medalha visível",
                "preserve a medalha",
            ]
        )
    ):
        ajustes[
            "photo_focus_y"
        ] = 0.22

    if preservar_enquadramento:
        for chave in [
            "photo_mode",
            "photo_zoom",
            "photo_focus_x",
            "photo_focus_y",
            "photo_safe_focus_y",
            "photo_zoom_focus_x",
            "photo_zoom_focus_y",
            "photo_zoom_delta",
            "avoid_head_crop",
            "photo_reframe",
        ]:
            ajustes.pop(
                chave,
                None,
            )

    badge_conquista = extrair_badge_conquista(
        instrucao
    )

    if badge_conquista and any(
        termo in texto
        for termo in [
            "selo",
            "badge",
            "faixa",
            "destaque",
            "lugar",
        ]
    ):
        ajustes[
            "achievement_badge_text"
        ] = badge_conquista

        ajustes[
            "achievement_badge_style"
        ] = "yellow"

        ajustes[
            "achievement_badge_priority"
        ] = True

    return ajustes



def remocao_visual_preserva_copy(
    instrucao,
    visual_overrides,
):
    """
    Decide quando uma instrução como:
      - Retire a frase "Aula Experimental"
      - Apenas retire o CTA
    deve congelar a copy em vez de pedir uma nova geração.

    "Aula Experimental" é badge do layout e CTA pode ser
    ocultado diretamente pelo renderer.
    """

    if not visual_overrides:
        return False

    possui_remocao = any(
        visual_overrides.get(
            chave
        )
        for chave in [
            "hide_badge",
            "hide_cta",
            "hide_campaign_pillars",
            "hide_elements",
        ]
    )

    if not possui_remocao:
        return False

    texto = normalizar_instrucao(
        instrucao
    )

    # Se houver pedido inequívoco de NOVO conteúdo textual,
    # não congelamos a copy.
    sinais_nova_copy = [
        "reescreva",
        "reformule",
        "novo texto",
        "nova frase",
        "nova headline",
        "troque por",
        "substitua por",
        "altere o texto para",
        "mude o texto para",
        "cta para",
        "headline para",
    ]

    if any(
        sinal in texto
        for sinal in sinais_nova_copy
    ):
        return False

    return True


def analisar_refazer(
    instrucao,
):
    literal = detectar_substituicao_literal(
        instrucao
    )

    exact_copy = detectar_copy_exata(
        instrucao
    )

    typography = detectar_ajuste_tipografia(
        instrucao
    )

    estrito = instrucao_modo_estrito(
        instrucao
    )

    copy = instrucao_pede_copy(
        instrucao
    )

    preserve_existing_copy = (
        instrucao_preserva_copy(
            instrucao
        )
    )

    visual = instrucao_pede_visual(
        instrucao
    )

    layout_only = (
        detectar_ajuste_layout(
            instrucao
        )
    )

    visual_overrides = (
        detectar_ajustes_visuais_cirurgicos(
            instrucao
        )
    )

    if visual_overrides.get(
        "photo_reframe"
    ):
        print(
            "Framing parser:",
            f"intent={visual_overrides.get('photo_reframe')}",
            f"mode={visual_overrides.get('photo_mode')}",
            f"zoom={visual_overrides.get('photo_zoom')}",
            f"focus=({visual_overrides.get('photo_focus_x')}, {visual_overrides.get('photo_focus_y')})",
            f"avoid_head_crop={visual_overrides.get('avoid_head_crop')}",
            flush=True,
        )

    if layout_only:
        estrito = True
        copy = False
        visual = True

    if visual_overrides:
        estrito = True
        visual = True

    # Uma ordem explícita para preservar a copy deve impedir
    # que a mera presença da palavra "texto" ative copy_change.
    # Só mantemos copy=True se houver pedido inequívoco de
    # alteração textual (troque/substitua/reescreva etc.).
    if (
        preserve_existing_copy
        and not literal
        and not exact_copy
        and not instrucao_pede_mudanca_explicita_copy(
            instrucao
        )
    ):
        copy = False

    if remocao_visual_preserva_copy(
        instrucao,
        visual_overrides,
    ):
        estrito = True
        copy = False
        visual = True

    if literal:
        estrito = True
        copy = True

    if exact_copy:
        estrito = True
        copy = True
        visual = False

    # Alterar tamanho de fonte NÃO é alterar o conteúdo da copy.
    # Nesse caso preservamos integralmente os textos.
    if typography:
        estrito = True
        copy = False
        visual = True

    return {
        "literal_replace": literal,
        "exact_copy": exact_copy,
        "typography_adjustment": typography,
        "strict_only": estrito,
        "copy_change": copy,
        "preserve_existing_copy": preserve_existing_copy,
        "visual_change": visual,
        "visual_overrides": visual_overrides,
        "layout_adjustment": layout_only,
    }


def copy_estruturada_do_item(
    item,
):
    """
    Retorna a copy realmente renderizada quando ela já existe
    no histórico novo.

    Para criativos antigos, retorna None e o gerador usa o
    briefing como fallback apenas nessa primeira revisão.
    """

    if not item:
        return None

    headline = item.get(
        "headline"
    )

    support = item.get(
        "support_text"
    )

    cta = item.get(
        "cta_text"
    )

    if (
        headline is None
        and support is None
        and cta is None
    ):
        return None

    return {
        "headline": (
            headline
            or ""
        ),
        "support": (
            support
            or ""
        ),
        "cta": (
            cta
            or ""
        ),
    }


def render_overrides_do_item(
    item,
):
    if not item:
        return {}

    valor = item.get(
        "render_overrides"
    )

    if isinstance(
        valor,
        dict,
    ):
        return dict(
            valor
        )

    return {}


def extrair_badge_conquista(
    texto,
):
    """
    Extrai textos de badge/selos do tipo:
      - "POLY • 5º LUGAR"
      - Poly ficou em 5º lugar
      - destaque informando que ela foi a 5º lugar

    Retorna um texto pronto para renderização quando houver
    evidência suficiente de nome + colocação.
    """

    if not texto:
        return None

    bruto = normalizar_espacos_comando(
        texto
    )

    normalizado = normalizar_instrucao(
        texto
    )

    # 1) Prioriza conteúdo explícito entre aspas.
    citacoes = re.findall(
        r'["“”]([^"“”]{3,80})["“”]',
        bruto,
    )

    for citacao in citacoes:
        citacao_norm = normalizar_instrucao(
            citacao
        )

        if (
            "lugar" in citacao_norm
            or "top" in citacao_norm
            or "podio" in citacao_norm
            or "pódio" in citacao_norm
        ):
            return citacao.strip()

    # 2) Busca nome + colocação no corpo do pedido.
    match_lugar = re.search(
        r'(\d{1,2}\s*[ºª°oa]?\s*lugar)',
        bruto,
        flags=re.IGNORECASE,
    )

    if not match_lugar:
        return None

    lugar = (
        match_lugar.group(1)
        .strip()
        .upper()
    )

    nomes_candidatos = re.findall(
        r'\b([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÁ-ÿ]{2,})\b',
        bruto,
    )

    ignorar = {
        'Crie', 'Ajuste', 'Além', 'Preserve', 'Mantenha',
        'Garanta', 'Arte', 'Campanha', 'Copa', 'Slim',
        'Story', 'Feed', 'Google', 'Drive', 'Publisher',
        'Use', 'Não', 'Nao', 'Foto', 'Imagem', 'CTA',
        'Badge', 'Selo', 'Faixa', 'Destaque', 'Lugar',
        'Ela', 'Aluna', 'Mais', 'Mundo', 'SlimFit',
    }

    nome = None

    for candidato in nomes_candidatos:
        if candidato in ignorar:
            continue

        candidato_norm = normalizar_instrucao(
            candidato
        )

        if candidato_norm in {
            'copa', 'slim', 'slimfit', 'lugar', 'edicao', 'especial'
        }:
            continue

        nome = candidato.upper()
        break

    if not nome:
        return None

    return f"{nome} • {lugar}"


def detectar_overrides_criacao_visual(
    pedido,
):
    """
    Reaproveita a mesma inteligência de ajustes visuais no
    fluxo /criarfoto e /criarstoryfoto.
    """

    overrides = detectar_ajustes_visuais_cirurgicos(
        pedido
    )

    return overrides or None


# =========================================================
# NORMALIZAÇÃO DE COMANDOS
# =========================================================

def normalizar_espacos_comando(
    texto,
):
    """
    Telegram/WhatsApp/cópia e cola podem inserir NBSP e outros
    espaços Unicode. Convertemos tudo para espaço comum sem
    destruir quebras de linha úteis do pedido.
    """

    texto = (
        texto
        or ""
    )

    substituicoes = {
        "\u00A0": " ",  # NBSP
        "\u2007": " ",  # figure space
        "\u202F": " ",  # narrow no-break space
        "\u2009": " ",  # thin space
        "\u200A": " ",  # hair space
    }

    for antigo, novo in substituicoes.items():
        texto = texto.replace(
            antigo,
            novo,
        )

    return texto.strip()


# =========================================================
# COPY OBRIGATÓRIA NO /CRIAR
# =========================================================

def detectar_copy_obrigatoria_criar(
    pedido,
):
    """
    Detecta pedidos como:

    A copy deve ser: TEXTO...
    A copy é: TEXTO...
    Use exatamente esta copy: TEXTO...

    Retorna somente o texto que deve ser renderizado como
    texto de apoio. Instruções visuais posteriores são
    removidas quando aparecem em nova linha ou após marcadores
    claramente visuais.
    """

    if not pedido:
        return None

    texto = normalizar_espacos_comando(
        pedido
    )

    padroes_inicio = [
        r"\ba\s+copy\s+deve\s+ser\s*:\s*",
        r"\ba\s+copy\s+é\s*:\s*",
        r"\ba\s+copy\s+e\s*:\s*",
        r"\buse\s+exatamente\s+esta\s+copy\s*:\s*",
        r"\buse\s+esta\s+copy\s*:\s*",
    ]

    inicio = None

    for padrao in padroes_inicio:
        match = re.search(
            padrao,
            texto,
            flags=re.IGNORECASE,
        )

        if match:
            inicio = match.end()
            break

    if inicio is None:
        return None

    restante = texto[
        inicio:
    ].strip()

    # Cortes seguros para instruções visuais que vêm depois
    # da copy. Priorizamos quebras de linha e frases claramente
    # imperativas de layout.
    cortes = [
        r"\n\s*(?:reduza|reduzir|aumente|aumentar|"
        r"mantenha|manter|use|utilize|deixe|deixar|"
        r"fundo|layout|composição|composicao|"
        r"foto|imagem|cores?|paleta)\b",

        r"\s+(?=(?:reduza|reduzir)\s+as?\s+áreas?\s+vazias?)",

        r"\s+(?=(?:mantenha|manter)\s+a\s+identidade\b)",
    ]

    fim = len(
        restante
    )

    for padrao in cortes:
        match = re.search(
            padrao,
            restante,
            flags=re.IGNORECASE,
        )

        if match:
            fim = min(
                fim,
                match.start(),
            )

    copy_texto = restante[
        :fim
    ].strip()

    if not copy_texto:
        return None

    return copy_texto


def pedido_sem_copy_obrigatoria(
    pedido,
):
    """
    Mantém o pedido completo para briefing/roteamento.
    Esta função existe para deixar explícito que não apagamos
    contexto de campanha; a copy exata é aplicada por override.
    """

    return normalizar_espacos_comando(
        pedido
    )


# =========================================================
# /TROCARFOTO COM INSTRUÇÃO
# =========================================================

def interpretar_trocarfoto(
    texto,
):
    """
    Aceita:

    /trocarfoto CRIATIVO-0086

    e também:

    /trocarfoto CRIATIVO-0086 procure uma foto com várias
    mulheres de amarelo
    """

    conteudo = normalizar_espacos_comando(
        texto[
            len(
                "/trocarfoto"
            ):
        ]
    )

    if not conteudo:
        return (
            None,
            None,
        )

    partes = conteudo.split(
        maxsplit=1
    )

    codigo = (
        partes[0]
        .strip()
        .upper()
    )

    instrucao = None

    if len(
        partes
    ) > 1:
        instrucao = (
            partes[1]
            .strip()
        )

    return (
        codigo,
        instrucao,
    )



def sanitizar_nome_foto(
    nome,
):
    """
    Defesa em profundidade contra path traversal.

    O nome vem do texto cru do usuário e é usado como chave de busca de
    fotos. Reduzimos ao basename, o que neutraliza tentativas de
    ``../../`` sem afetar nomes legítimos (nomes de arquivo do Drive não
    contêm separadores de caminho).
    """

    if not nome:
        return nome

    return os.path.basename(
        str(nome)
    ).strip()


def interpretar_foto_e_pedido(
    conteudo,
):
    """
    Formas aceitas:
      IMG_5882.JPG Quero divulgar...
      "Tezza-6077 (1).jpeg" Quero divulgar...
      IMG_5882.JPG | Quero divulgar...
    """

    conteudo = normalizar_espacos_comando(
        conteudo
    )

    if not conteudo:
        return None, None

    if conteudo.startswith(
        '"'
    ):
        match = re.match(
            r'^"([^"]+)"\s*(?:\|\s*)?(.*)$',
            conteudo,
            flags=re.DOTALL,
        )

        if not match:
            return None, None

        foto = sanitizar_nome_foto(match.group(1))
        pedido = match.group(2).strip()

        return foto, pedido

    if "|" in conteudo:
        esquerda, direita = conteudo.split(
            "|",
            1,
        )

        return (
            sanitizar_nome_foto(esquerda),
            direita.strip(),
        )

    partes = conteudo.split(
        maxsplit=1
    )

    if len(partes) == 1:
        return (
            sanitizar_nome_foto(partes[0]),
            "",
        )

    return (
        sanitizar_nome_foto(partes[0]),
        partes[1].strip(),
    )


def extrair_foto_exata_trocarfoto(
    instrucao,
):
    if not instrucao:
        return None

    texto = normalizar_espacos_comando(
        instrucao
    )

    padroes = [
        r'^\s*usar?\s+exatamente\s+a\s+foto\s+(.+?)\s*$',
        r'^\s*use\s+exatamente\s+a\s+foto\s+(.+?)\s*$',
        r'^\s*usar?\s+a\s+foto\s+exata\s+(.+?)\s*$',
        r'^\s*foto\s+exata\s*:\s*(.+?)\s*$',
    ]

    for padrao in padroes:
        match = re.match(
            padrao,
            texto,
            flags=re.IGNORECASE,
        )

        if match:
            referencia = (
                match.group(1)
                .strip()
                .strip('"')
            )

            return referencia

    return None


def output_format_do_item(
    item,
):
    if not item:
        return "FEED"

    layout = str(
        item.get(
            "layout"
        )
        or ""
    )

    if layout.startswith(
        "STORY_"
    ):
        return "STORY"

    overrides = (
        item.get(
            "render_overrides"
        )
        or {}
    )

    if isinstance(
        overrides,
        dict,
    ):
        formato = str(
            overrides.get(
                "output_format"
            )
            or ""
        ).upper()

        if formato == "STORY":
            return "STORY"

    return "FEED"


# =========================================================
# CRIAÇÃO
# =========================================================

def executar_criacao(
    chat_id,
    pedido,
    parent_code=None,
    revision_type="ORIGINAL",
    foto_fixa_id=None,
    excluir_foto_id=None,
    briefing_fixo=None,
    family_fixa=None,
    layout_fixo=None,
    background_style_fixo=None,
    literal_replace=None,
    render_request_fixo=None,
    copy_override=None,
    render_overrides=None,
    copy_fixa=None,
    photo_selection_request=None,
    foto_fixa_nome=None,
    output_format="FEED",
):
    caminho_bruto = None
    caminho_final = None

    print(
        "CHK 1 - entrou em executar_criacao",
        "| revision_type:",
        revision_type,
        "| output_format:",
        output_format,
        "| foto_fixa_nome:",
        foto_fixa_nome,
        "| foto_fixa_id:",
        foto_fixa_id,
        flush=True,
    )

    if (
        revision_type
        == "NEW_PHOTO"
    ):
        mensagem_inicio = (
            "🖼 Trocando somente a fotografia...\n\n"
            "1/5 Design anterior\n"
            "2/5 Nova foto\n"
            "3/5 Mesma composição\n"
            "4/5 Marca oficial\n"
            "5/5 Google Drive"
        )

    elif (
        str(output_format)
        .strip()
        .upper()
        == "STORY"
        or revision_type == "STORY"
    ):
        mensagem_inicio = (
            "📱 Criando seu Story...\n\n"
            "1/5 Briefing\n"
            "2/5 Foto\n"
            "3/5 Composição 9:16\n"
            "4/5 Marca oficial\n"
            "5/5 Google Drive"
        )

    else:
        mensagem_inicio = (
            "🎨 Criando seu criativo...\n\n"
            "1/5 Briefing\n"
            "2/5 Foto\n"
            "3/5 Composição\n"
            "4/5 Marca oficial\n"
            "5/5 Google Drive"
        )

    try:
        # ================================================
        # TELEGRAM - MENSAGEM INICIAL
        # ================================================

        print(
            "CHK 2 - antes do send_message inicial",
            flush=True,
        )

        send_message(
            chat_id,
            mensagem_inicio,
        )

        print(
            "CHK 3 - depois do send_message inicial",
            flush=True,
        )

        # ================================================
        # GERADOR
        # ================================================

        print(
            "CHK 4 - antes do gerar_criativo",
            flush=True,
        )

        resultado = gerar_criativo(
            pedido,

            foto_fixa_id=(
                foto_fixa_id
            ),

            excluir_foto_id=(
                excluir_foto_id
            ),

            briefing_fixo=(
                briefing_fixo
            ),

            family_fixa=(
                family_fixa
            ),

            layout_fixo=(
                layout_fixo
            ),

            background_style_fixo=(
                background_style_fixo
            ),

            literal_replace=(
                literal_replace
            ),

            render_request_fixo=(
                render_request_fixo
            ),

            copy_override=(
                copy_override
            ),

            render_overrides=(
                render_overrides
            ),

            copy_fixa=(
                copy_fixa
            ),

            photo_selection_request=(
                photo_selection_request
            ),

            foto_fixa_nome=(
                foto_fixa_nome
            ),

            output_format=(
                output_format
            ),
        )

        print(
            "CHK 5 - depois do gerar_criativo",
            "| family:",
            resultado.get(
                "family"
            ),
            "| layout:",
            resultado.get(
                "layout"
            ),
            "| output_format:",
            resultado.get(
                "output_format"
            ),
            "| size:",
            f"{resultado.get('width', 1080)}x"
            f"{resultado.get('height', 1350)}",
            flush=True,
        )

        caminho_bruto = (
            resultado[
                "image_path"
            ]
        )

        foto = (
            resultado[
                "photo"
            ]
        )

        briefing = (
            resultado[
                "briefing"
            ]
        )

        family = resultado.get(
            "family"
        )

        layout = resultado.get(
            "layout"
        )

        background_style = (
            resultado.get(
                "background_style"
            )
        )

        copy_final = (
            resultado.get(
                "copy"
            )
            or {}
        )

        render_overrides_final = (
            resultado.get(
                "render_overrides"
            )
            or {}
        )

        # ================================================
        # FINALIZAÇÃO / LOGO / DRIVE
        # ================================================

        publisher_layout = (
            resultado.get(
                "publisher_layout"
            )
            or layout
        )

        print(
            "CHK 6 - antes do finalizar_e_publicar",
            "| publisher_layout:",
            publisher_layout,
            flush=True,
        )

        publicacao = (
            finalizar_e_publicar(
                caminho_bruto,
                family=family,
                layout=publisher_layout,
            )
        )

        print(
            "CHK 7 - depois do finalizar_e_publicar",
            "| logo:",
            publicacao.get(
                "logo_name"
            ),
            "| posição:",
            publicacao.get(
                "logo_position"
            ),
            flush=True,
        )

        caminho_final = (
            publicacao[
                "image_path"
            ]
        )

        # ================================================
        # HISTÓRICO
        # ================================================

        print(
            "CHK 8 - antes do registrar_criativo",
            flush=True,
        )

        codigo = registrar_criativo(
            request=pedido,
            briefing=briefing,
            photo=foto,
            publication=publicacao,
            family=family,
            layout=layout,
            background_style=(
                background_style
            ),
            parent_code=(
                parent_code
            ),
            revision_type=(
                revision_type
            ),

            copy=(
                copy_final
            ),

            render_overrides=(
                render_overrides_final
            ),
        )

        print(
            "CHK 9 - depois do registrar_criativo",
            "| código:",
            codigo,
            flush=True,
        )

        drive_link = (
            publicacao[
                "drive_file"
            ].get(
                "webViewLink"
            )
            or ""
        )

        design_status = ""

        if (
            revision_type
            == "NEW_PHOTO"
        ):
            design_status = (
                "\n🔒 Design anterior mantido"
            )

        legenda = (
            "✅  Criativo gerado\n\n"
            f"🆔 {codigo}\n"
            f"🔁 Tipo: {revision_type}\n"
            f"👨‍🎨 Família: {family}\n"
            f"🧩 Composição: {layout}\n"
            f"🎨 Fundo: {background_style}\n"
            f"📷 Foto: {foto['filename']}\n"
            f"⭐  Qualidade: "
            f"{foto['quality_score']}/10\n"
            f"🎯 Marca: "
            f"{foto['brand_fit_score']}/10\n"
            f"🏷 Logo: "
            f"{publicacao['logo_name']}\n"
            f"📍 Logo: "
            f"{publicacao['logo_position']}\n"
            f"📐 {resultado.get('width', 1080)}x"
            f"{resultado.get('height', 1350)}"
            f"{design_status}\n\n"
            "Status: PENDENTE"
        )

        print(
            "CHK 10 - antes do send_photo",
            flush=True,
        )

        send_photo(
            chat_id,
            caminho_final,
            legenda,
        )

        print(
            "CHK 11 - depois do send_photo",
            flush=True,
        )

        if drive_link:
            print(
                "CHK 12 - antes do send_message com link",
                flush=True,
            )

            send_message(
                chat_id,
                f"☁️ {drive_link}\n\n"
                f"/aprovar {codigo}\n"
                f"/refazer {codigo}\n"
                f"/trocarfoto {codigo}",
            )

            print(
                "CHK 13 - depois do send_message com link",
                flush=True,
            )

        # Nota de enquadramento: o renderizador sinaliza quando um pedido
        # de afastamento não pôde ser atendido por limite geométrico e
        # sugere o formato Story. Enviada por último para não competir
        # com a imagem/links.
        photo_note = resultado.get(
            "photo_note"
        )
        if photo_note:
            send_message(
                chat_id,
                photo_note,
            )

        return codigo

    except Exception as e:
        print(
            "Erro criação:",
            type(
                e
            ).__name__,
            str(
                e
            ),
            flush=True,
        )

        mensagem_erro = str(
            e
        )

        try:
            if mensagem_erro.startswith(
                "EDIÇÃO LITERAL:"
            ):
                send_message(
                    chat_id,
                    "❌  "
                    + mensagem_erro.replace(
                        "EDIÇÃO LITERAL: ",
                        "",
                        1,
                    ),
                )

            elif mensagem_erro.startswith(
                "FOTO ESPECÍFICA:"
            ):
                send_message(
                    chat_id,
                    "📷 "
                    + mensagem_erro.replace(
                        "FOTO ESPECÍFICA:",
                        "",
                        1,
                    ).strip(),
                )

            elif (
                "Nenhuma das fotos finalistas atende "
                "visualmente ao critério solicitado:"
                in mensagem_erro
            ):
                criterio_nao_encontrado = (
                    mensagem_erro.split(
                        "critério solicitado:",
                        1,
                    )[-1]
                    .strip()
                    .rstrip(".")
                )

                send_message(
                    chat_id,
                    "🔎 Não encontrei no acervo uma foto que "
                    "atenda suficientemente ao critério pedido."
                    "\n\n"
                    f"🎯 Critério: {criterio_nao_encontrado}"
                    "\n\n"
                    "Nenhuma fotografia foi alterada. "
                    "Você pode tentar descrever o que procura "
                    "de outra forma ou usar outro critério.",
                )

            elif mensagem_erro.startswith(
                "Não encontrei no índice visual uma fotografia "
                "com aderência suficiente ao critério:"
            ):
                criterio_nao_encontrado = (
                    mensagem_erro.split(
                        "critério:",
                        1,
                    )[-1]
                    .strip()
                    .rstrip(".")
                )

                send_message(
                    chat_id,
                    "🔎 Não encontrei no acervo uma foto que "
                    "atenda suficientemente ao critério pedido."
                    "\n\n"
                    f"🎯 Critério: {criterio_nao_encontrado}"
                    "\n\n"
                    "Nenhuma fotografia foi alterada.",
                )

            elif (
                "invalid_grant" in mensagem_erro
                or "Token has been expired or revoked" in mensagem_erro
                or "credencial Google" in mensagem_erro
                or "RefreshError" in type(e).__name__
            ):
                send_message(
                    chat_id,
                    "🔐 Falha de acesso ao Google Drive: a credencial "
                    "expirou ou foi revogada.\n\n"
                    "É preciso renovar o acesso no servidor "
                    "(Service Account em /app/secrets/google.json, com as "
                    "pastas do Drive compartilhadas com o e-mail dela). "
                    "Nenhum criativo foi alterado.",
                )

            else:
                send_message(
                    chat_id,
                    "❌ Não consegui gerar o criativo.\n\n"
                    "O erro foi registrado no log do servidor "
                    "para diagnóstico.",
                )

        except Exception as erro_telegram:
            print(
                "Erro ao enviar mensagem de falha ao Telegram:",
                type(
                    erro_telegram
                ).__name__,
                str(
                    erro_telegram
                ),
                flush=True,
            )

        return None

    finally:
        for caminho in [
            caminho_bruto,
            caminho_final,
        ]:
            if (
                caminho
                and os.path.exists(
                    caminho
                )
            ):
                try:
                    os.remove(
                        caminho
                    )

                except Exception:
                    pass


# =========================================================
# POLLING
# =========================================================

while True:
    try:
        params = {
            "timeout": 30,
        }

        if offset is not None:
            params[
                "offset"
            ] = offset

        response = requests.get(
            f"{BASE_URL}/getUpdates",
            params=params,
            timeout=40,
        )

        response.raise_for_status()

        data = (
            response.json()
        )

        for update in data.get(
            "result",
            [],
        ):
            offset = (
                update[
                    "update_id"
                ]
                + 1
            )

            try:
                message = update.get(
                    "message"
                )

                if not message:
                    continue

                chat_id = str(
                    message[
                        "chat"
                    ][
                        "id"
                    ]
                )

                if (
                    chat_id
                    != ALLOWED_CHAT_ID
                ):
                    continue

                text = normalizar_espacos_comando(
                    message.get(
                        "text",
                        "",
                    )
                )

                if not text:
                    continue

                lower = text.lower()

                print(
                    "Pedido recebido:",
                    text,
                    flush=True,
                )

                # =============================================
                # CRIAR STORY COM FOTO ESPECÍFICA
                # =============================================

                if (
                    lower == "/criarstoryfoto"
                    or lower.startswith(
                        "/criarstoryfoto "
                    )
                    or lower == "/criarfotostory"
                    or lower.startswith(
                        "/criarfotostory "
                    )
                ):
                    comando_story_foto = (
                        "/criarfotostory"
                        if lower.startswith(
                            "/criarfotostory"
                        )
                        else "/criarstoryfoto"
                    )

                    conteudo = normalizar_espacos_comando(
                        text[
                            len(
                                comando_story_foto
                            ):
                        ]
                    )

                    foto_nome, pedido = (
                        interpretar_foto_e_pedido(
                            conteudo
                        )
                    )

                    if (
                        not foto_nome
                        or not pedido
                    ):
                        send_message(
                            chat_id,
                            "Use:\n"
                            '/criarstoryfoto IMG_5882.JPG '
                            'descreva o story\n'
                            'ou:\n'
                            '/criarfotostory IMG_5882.JPG '
                            'descreva o story\n\n'
                            'Para nomes com espaços:\n'
                            '/criarstoryfoto "Tezza-6077 (1).jpeg" '
                            'descreva o story',
                        )
                        continue

                    copy_obrigatoria = (
                        detectar_copy_obrigatoria_criar(
                            pedido
                        )
                    )

                    copy_override_criar = (
                        {
                            "support": copy_obrigatoria
                        }
                        if copy_obrigatoria
                        else None
                    )

                    executar_criacao(
                        chat_id,
                        pedido_sem_copy_obrigatoria(
                            pedido
                        ),
                        foto_fixa_nome=(
                            foto_nome
                        ),
                        output_format="STORY",
                        copy_override=(
                            copy_override_criar
                        ),
                        render_overrides=(
                            detectar_overrides_criacao_visual(
                                pedido
                            )
                        ),
                    )

                    continue

                # =============================================
                # CRIAR COM FOTO ESPECÍFICA
                # =============================================

                if (
                    lower == "/criarfoto"
                    or lower.startswith(
                        "/criarfoto "
                    )
                ):
                    conteudo = normalizar_espacos_comando(
                        text[
                            len(
                                "/criarfoto"
                            ):
                        ]
                    )

                    foto_nome, pedido = (
                        interpretar_foto_e_pedido(
                            conteudo
                        )
                    )

                    if (
                        not foto_nome
                        or not pedido
                    ):
                        send_message(
                            chat_id,
                            "Use:\n"
                            '/criarfoto IMG_5882.JPG '
                            'descreva o criativo\n\n'
                            'Para nomes com espaços:\n'
                            '/criarfoto "Tezza-6077 (1).jpeg" '
                            'descreva o criativo',
                        )
                        continue

                    copy_obrigatoria = (
                        detectar_copy_obrigatoria_criar(
                            pedido
                        )
                    )

                    copy_override_criar = (
                        {
                            "support": copy_obrigatoria
                        }
                        if copy_obrigatoria
                        else None
                    )

                    executar_criacao(
                        chat_id,
                        pedido_sem_copy_obrigatoria(
                            pedido
                        ),
                        foto_fixa_nome=(
                            foto_nome
                        ),
                        output_format="FEED",
                        copy_override=(
                            copy_override_criar
                        ),
                        render_overrides=(
                            detectar_overrides_criacao_visual(
                                pedido
                            )
                        ),
                    )

                    continue

                # =============================================
                # CRIAR STORY
                # =============================================

                if (
                    lower == "/criarstory"
                    or lower.startswith(
                        "/criarstory "
                    )
                ):
                    pedido = normalizar_espacos_comando(
                        text[
                            len(
                                "/criarstory"
                            ):
                        ]
                    )

                    if not pedido:
                        send_message(
                            chat_id,
                            "Use:\n"
                            "/criarstory descreva o story que você quer.",
                        )
                        continue

                    copy_obrigatoria = (
                        detectar_copy_obrigatoria_criar(
                            pedido
                        )
                    )

                    copy_override_criar = (
                        {
                            "support": copy_obrigatoria
                        }
                        if copy_obrigatoria
                        else None
                    )

                    executar_criacao(
                        chat_id,
                        pedido_sem_copy_obrigatoria(
                            pedido
                        ),
                        output_format="STORY",
                        copy_override=(
                            copy_override_criar
                        ),
                    )

                    continue

                # =============================================
                # CONVERTER CRIATIVO EXISTENTE PARA STORY
                # =============================================

                if (
                    lower == "/story"
                    or lower.startswith(
                        "/story "
                    )
                ):
                    codigo = (
                        text[
                            len(
                                "/story"
                            ):
                        ]
                        .strip()
                        .upper()
                    )

                    if not codigo:
                        send_message(
                            chat_id,
                            "Use:\n"
                            "/story CRIATIVO-0094",
                        )
                        continue

                    item = buscar_criativo(
                        codigo
                    )

                    if not item:
                        send_message(
                            chat_id,
                            "❌  Criativo não encontrado.",
                        )
                        continue

                    send_message(
                        chat_id,
                        f"📱 Convertendo {codigo} para Story "
                        "1080x1920...\n\n"
                        "📷 Mesma foto\n"
                        "✏️ Mesma copy\n"
                        "🎨 Identidade preservada",
                    )

                    executar_criacao(
                        chat_id,
                        item.get(
                            "request"
                        )
                        or "",
                        parent_code=(
                            codigo
                        ),
                        revision_type="STORY",
                        foto_fixa_id=(
                            item.get(
                                "source_photo_id"
                            )
                        ),
                        briefing_fixo=(
                            item.get(
                                "briefing"
                            )
                        ),
                        family_fixa=(
                            item.get(
                                "family"
                            )
                        ),
                        layout_fixo=(
                            str(
                                item.get(
                                    "layout"
                                )
                                or ""
                            ).replace(
                                "STORY_",
                                "",
                                1,
                            )
                        ),
                        background_style_fixo=(
                            item.get(
                                "background_style"
                            )
                        ),
                        render_request_fixo=(
                            item.get(
                                "request"
                            )
                        ),
                        copy_fixa=(
                            copy_estruturada_do_item(
                                item
                            )
                        ),
                        render_overrides=(
                            render_overrides_do_item(
                                item
                            )
                        ),
                        output_format="STORY",
                    )

                    continue

                # =============================================
                # CRIAR
                # =============================================

                if (
                    lower == "/criar"
                    or lower.startswith(
                        "/criar "
                    )
                ):
                    pedido = normalizar_espacos_comando(
                        text[
                            len(
                                "/criar"
                            ):
                        ]
                    )

                    if not pedido:
                        send_message(
                            chat_id,
                            "Use:\n"
                            "/criar descreva o criativo que você quer.",
                        )

                        continue

                    copy_obrigatoria = (
                        detectar_copy_obrigatoria_criar(
                            pedido
                        )
                    )

                    copy_override_criar = None

                    if copy_obrigatoria:
                        copy_override_criar = {
                            "support": copy_obrigatoria
                        }

                        print(
                            "Copy obrigatória detectada no /criar:",
                            copy_obrigatoria,
                            flush=True,
                        )

                    executar_criacao(
                        chat_id,
                        pedido_sem_copy_obrigatoria(
                            pedido
                        ),
                        copy_override=(
                            copy_override_criar
                        ),
                    )

                    continue

                # =============================================
                # APROVAR
                # =============================================

                if lower.startswith(
                    "/aprovar "
                ):
                    codigo = (
                        text[
                            len(
                                "/aprovar "
                            ):
                        ]
                        .strip()
                        .upper()
                    )

                    item = buscar_criativo(
                        codigo
                    )

                    if not item:
                        send_message(
                            chat_id,
                            "❌  Criativo não encontrado.",
                        )

                        continue

                    atualizar_status(
                        codigo,
                        "APPROVED",
                    )

                    send_message(
                        chat_id,
                        f"✅  {codigo} aprovado.\n\n"
                        "📷 A foto entrou no cooldown "
                        "das próximas 40 gerações normais.\n\n"
                        f"👨‍🎨 {item.get('family')}\n"
                        f"🧩 {item.get('layout')}\n"
                        f"🎨 {item.get('background_style')}",
                    )

                    continue

                # =============================================
                # REFAZER
                # =============================================

                if lower.startswith(
                    "/refazer"
                ):
                    (
                        codigo,
                        instrucao,
                    ) = interpretar_refazer(
                        text
                    )

                    if not codigo:
                        send_message(
                            chat_id,
                            "Use:\n"
                            "/refazer CRIATIVO-0037\n\n"
                            "ou:\n"
                            "/refazer CRIATIVO-0037 "
                            "quero outro fundo e "
                            "headline mais curta",
                        )

                        continue

                    item = buscar_criativo(
                        codigo
                    )

                    if not item:
                        send_message(
                            chat_id,
                            "❌  Criativo não encontrado.",
                        )

                        continue

                    # Pedido de "corpo inteiro" num feed horizontal: em vez
                    # de gerar uma arte que não mostra o corpo todo, converte
                    # para Story (vertical), onde o corpo cabe. Espelha o
                    # caminho do comando /story.
                    if (
                        instrucao
                        and pedido_quer_corpo_inteiro(instrucao)
                        and output_format_do_item(item) == "FEED"
                    ):
                        send_message(
                            chat_id,
                            "📱 Você pediu o corpo inteiro. Numa arte de "
                            "feed (horizontal) não dá para mostrar o corpo "
                            "todo sem cortar, então vou gerar em Story "
                            "(vertical), onde ele cabe.",
                        )

                        executar_criacao(
                            chat_id,
                            item.get("request") or "",
                            parent_code=codigo,
                            revision_type="STORY",
                            foto_fixa_id=item.get(
                                "source_photo_id"
                            ),
                            briefing_fixo=item.get(
                                "briefing"
                            ),
                            family_fixa=item.get(
                                "family"
                            ),
                            layout_fixo=str(
                                item.get("layout") or ""
                            ).replace(
                                "STORY_",
                                "",
                                1,
                            ),
                            background_style_fixo=item.get(
                                "background_style"
                            ),
                            render_request_fixo=item.get(
                                "request"
                            ),
                            copy_fixa=copy_estruturada_do_item(
                                item
                            ),
                            render_overrides=render_overrides_do_item(
                                item
                            ),
                            output_format="STORY",
                        )

                        continue

                    novo_pedido = (
                        montar_pedido_refazer(
                            item,
                            instrucao,
                        )
                    )

                    if instrucao:
                        revision_type = (
                            "CUSTOM_REMAKE"
                        )

                        send_message(
                            chat_id,
                            f"🔄 Revisando {codigo}\n\n"
                            "📷 Mesma foto\n"
                            f"✏️ Ajuste: {instrucao}",
                        )

                    else:
                        revision_type = (
                            "REMAKE"
                        )

                        send_message(
                            chat_id,
                            f"🔄 Refazendo {codigo} "
                            f"com a mesma foto...",
                        )

                    analise_refazer = analisar_refazer(
                        instrucao
                    )

                    parametros_refazer = {
                        "briefing_fixo": None,
                        "family_fixa": None,
                        "layout_fixo": None,
                        "background_style_fixo": None,
                        "literal_replace": None,
                        "render_request_fixo": None,
                        "copy_override": None,
                        "render_overrides": None,
                        "copy_fixa": None,
                        "output_format": (
                            output_format_do_item(
                                item
                            )
                        ),
                    }

                    if instrucao:
                        print(
                            "Modo /refazer:",
                            analise_refazer,
                            flush=True,
                        )
                        # -----------------------------------------
                        # 1. AJUSTE SOMENTE DE TIPOGRAFIA
                        # -----------------------------------------
                        if (
                            analise_refazer[
                                "typography_adjustment"
                            ]
                        ):
                            # Texto, foto e estrutura ficam congelados.
                            parametros_refazer[
                                "briefing_fixo"
                            ] = item.get(
                                "briefing"
                            )

                            parametros_refazer[
                                "copy_fixa"
                            ] = copy_estruturada_do_item(
                                item
                            )

                            parametros_refazer[
                                "family_fixa"
                            ] = item.get(
                                "family"
                            )

                            parametros_refazer[
                                "layout_fixo"
                            ] = item.get(
                                "layout"
                            )

                            parametros_refazer[
                                "background_style_fixo"
                            ] = item.get(
                                "background_style"
                            )

                            # Preserva o contexto visual anterior.
                            parametros_refazer[
                                "render_request_fixo"
                            ] = item.get(
                                "request"
                            )

                            # O banco é a fonte da verdade para os
                            # ajustes já aplicados. Para criativos antigos,
                            # ainda aceitamos o request como fallback.
                            overrides_anteriores = (
                                render_overrides_do_item(
                                    item
                                )
                            )

                            if not overrides_anteriores:
                                overrides_anteriores = (
                                    somar_ajustes_tipografia(
                                        item.get(
                                            "request"
                                        )
                                        or ""
                                    )
                                )

                            ajuste_atual = analise_refazer[
                                "typography_adjustment"
                            ]

                            chave_delta = (
                                ajuste_atual[
                                    "target"
                                ]
                                + "_font_delta"
                            )

                            overrides_anteriores[
                                chave_delta
                            ] = (
                                int(
                                    overrides_anteriores.get(
                                        chave_delta,
                                        0,
                                    )
                                    or 0
                                )
                                + int(
                                    ajuste_atual[
                                        "delta"
                                    ]
                                )
                            )

                            overrides_anteriores[
                                chave_delta
                            ] = max(
                                -8,
                                min(
                                    8,
                                    overrides_anteriores[
                                        chave_delta
                                    ],
                                ),
                            )

                            parametros_refazer[
                                "render_overrides"
                            ] = overrides_anteriores

                        # -----------------------------------------
                        # 2. COPY EXATA / "ALTERE A COPY PARA:"
                        # -----------------------------------------
                        elif (
                            analise_refazer[
                                "exact_copy"
                            ]
                        ):
                            parametros_refazer[
                                "briefing_fixo"
                            ] = item.get(
                                "briefing"
                            )

                            parametros_refazer[
                                "copy_fixa"
                            ] = copy_estruturada_do_item(
                                item
                            )

                            parametros_refazer[
                                "family_fixa"
                            ] = item.get(
                                "family"
                            )

                            parametros_refazer[
                                "layout_fixo"
                            ] = item.get(
                                "layout"
                            )

                            parametros_refazer[
                                "background_style_fixo"
                            ] = item.get(
                                "background_style"
                            )

                            parametros_refazer[
                                "render_request_fixo"
                            ] = item.get(
                                "request"
                            )

                            parametros_refazer[
                                "copy_override"
                            ] = {
                                "support": analise_refazer[
                                    "exact_copy"
                                ]
                            }

                            parametros_refazer[
                                "render_overrides"
                            ] = somar_ajustes_tipografia(
                                item.get(
                                    "request"
                                )
                                or ""
                            )

                        # -----------------------------------------
                        # 2. EDIÇÃO LITERAL / "FAÇA APENAS ISSO"
                        # -----------------------------------------
                        elif (
                            analise_refazer[
                                "literal_replace"
                            ]
                        ):
                            parametros_refazer[
                                "briefing_fixo"
                            ] = item.get(
                                "briefing"
                            )

                            parametros_refazer[
                                "copy_fixa"
                            ] = copy_estruturada_do_item(
                                item
                            )

                            parametros_refazer[
                                "family_fixa"
                            ] = item.get(
                                "family"
                            )

                            parametros_refazer[
                                "layout_fixo"
                            ] = item.get(
                                "layout"
                            )

                            parametros_refazer[
                                "background_style_fixo"
                            ] = item.get(
                                "background_style"
                            )

                            parametros_refazer[
                                "literal_replace"
                            ] = analise_refazer[
                                "literal_replace"
                            ]

                            # O renderer recebe o pedido exatamente
                            # da versão anterior. Assim badge,
                            # contexto temporal e demais detalhes
                            # visuais não são reinterpretados.
                            parametros_refazer[
                                "render_request_fixo"
                            ] = item.get(
                                "request"
                            )

                            parametros_refazer[
                                "render_overrides"
                            ] = somar_ajustes_tipografia(
                                item.get(
                                    "request"
                                )
                                or ""
                            )

                        # -----------------------------------------
                        # AJUSTE SOMENTE VISUAL
                        # -----------------------------------------
                        elif (
                            analise_refazer[
                                "visual_change"
                            ]
                            and not analise_refazer[
                                "copy_change"
                            ]
                        ):
                            # Preserva automaticamente headline,
                            # apoio e CTA.
                            parametros_refazer[
                                "briefing_fixo"
                            ] = item.get(
                                "briefing"
                            )

                            parametros_refazer[
                                "copy_fixa"
                            ] = copy_estruturada_do_item(
                                item
                            )

                            parametros_refazer[
                                "family_fixa"
                            ] = item.get(
                                "family"
                            )

                            # Alteração cirúrgica visual: mantém a
                            # composição e o fundo atuais.
                            parametros_refazer[
                                "layout_fixo"
                            ] = item.get(
                                "layout"
                            )

                            parametros_refazer[
                                "background_style_fixo"
                            ] = item.get(
                                "background_style"
                            )

                            # Mantemos o pedido original como contexto.
                            parametros_refazer[
                                "render_request_fixo"
                            ] = item.get(
                                "request"
                            )

                            overrides_anteriores = (
                                render_overrides_do_item(
                                    item
                                )
                            )

                            overrides_novos = (
                                analise_refazer.get(
                                    "visual_overrides"
                                )
                                or {}
                            )

                            # ---------------------------------
                            # NORMALIZAÇÃO DE OVERRIDES DE FOTO
                            # ---------------------------------
                            # Um novo pedido explícito de framing deve
                            # substituir o framing herdado da revisão
                            # anterior. Antes, flags antigas como
                            # avoid_head_crop mantinham SAFE_COVER ativo
                            # mesmo quando o novo pedido dizia
                            # photo_mode=smart_contain.
                            framing_novo = any(
                                chave in overrides_novos
                                for chave in [
                                    "photo_reframe",
                                    "photo_mode",
                                    "photo_zoom",
                                    "photo_zoom_delta",
                                    "photo_focus_x",
                                    "photo_focus_y",
                                    "photo_safe_focus_y",
                                    "preserve_photo_framing",
                                ]
                            )

                            if framing_novo:
                                preservar_foto = bool(
                                    overrides_novos.get(
                                        "preserve_photo_framing"
                                    )
                                )

                                if not preservar_foto:
                                    for chave_antiga in [
                                        "photo_mode",
                                        "photo_zoom",
                                        "photo_zoom_delta",
                                        "photo_focus_x",
                                        "photo_focus_y",
                                        "photo_safe_focus_y",
                                        "photo_zoom_focus_x",
                                        "photo_zoom_focus_y",
                                        "avoid_head_crop",
                                        "photo_reframe",
                                        "preserve_photo_framing",
                                    ]:
                                        overrides_anteriores.pop(
                                            chave_antiga,
                                            None,
                                        )

                            # Zoom é relativo entre revisões. Se a versão
                            # anterior já estava em 0.88 e o usuário pede
                            # "um pouco menos", aplicamos novo delta sobre
                            # 0.88 em vez de resetar para um valor absoluto.
                            zoom_delta_novo = overrides_novos.get(
                                "photo_zoom_delta"
                            )

                            if zoom_delta_novo is not None:
                                zoom_base = float(
                                    render_overrides_do_item(
                                        item
                                    ).get(
                                        "photo_zoom",
                                        1.0,
                                    )
                                    or 1.0
                                )

                                zoom_calculado = max(
                                    0.82,
                                    min(
                                        1.20,
                                        zoom_base
                                        + float(
                                            zoom_delta_novo
                                        ),
                                    ),
                                )

                                overrides_novos[
                                    "photo_zoom"
                                ] = round(
                                    zoom_calculado,
                                    3,
                                )

                            for chave, valor in (
                                overrides_novos.items()
                            ):
                                if chave == "photo_zoom_delta":
                                    continue

                                if (
                                    chave.endswith(
                                        "_font_delta"
                                    )
                                    and chave
                                    in overrides_anteriores
                                ):
                                    overrides_anteriores[
                                        chave
                                    ] = max(
                                        -8,
                                        min(
                                            8,
                                            int(
                                                overrides_anteriores.get(
                                                    chave,
                                                    0,
                                                )
                                                or 0
                                            )
                                            + int(
                                                valor
                                            ),
                                        ),
                                    )
                                else:
                                    overrides_anteriores[
                                        chave
                                    ] = valor

                            if overrides_novos.get(
                                "preserve_photo_framing"
                            ):
                                overrides_anteriores[
                                    "preserve_photo_framing"
                                ] = True

                            parametros_refazer[
                                "render_overrides"
                            ] = overrides_anteriores

                        # -----------------------------------------
                        # 3. AJUSTE SOMENTE DE COPY
                        # -----------------------------------------
                        elif (
                            analise_refazer[
                                "copy_change"
                            ]
                            and not analise_refazer[
                                "visual_change"
                            ]
                        ):
                            # Mantém estrutura visual; a copy pode
                            # ser recriada conforme a instrução.
                            parametros_refazer[
                                "family_fixa"
                            ] = item.get(
                                "family"
                            )

                            parametros_refazer[
                                "layout_fixo"
                            ] = item.get(
                                "layout"
                            )

                            parametros_refazer[
                                "background_style_fixo"
                            ] = item.get(
                                "background_style"
                            )

                        # -----------------------------------------
                        # 4. MODO ESTRITO NÃO INTERPRETADO
                        # -----------------------------------------
                        elif analise_refazer[
                            "strict_only"
                        ]:
                            # Se o usuário pediu "não altere mais
                            # nada" mas não conseguimos identificar
                            # com segurança uma edição literal,
                            # NÃO regeneramos o criativo inteiro.
                            send_message(
                                chat_id,
                                "⚠️ Entendi que você quer uma "
                                "alteração cirúrgica, mas não "
                                "consegui identificar com segurança "
                                "o trecho exato a substituir.\n\n"
                                "Use, por exemplo:\n"
                                '/refazer '
                                + codigo
                                + ' substitua apenas a frase '
                                '"texto atual" por "texto novo".'
                            )

                            continue

                    executar_criacao(
                        chat_id,
                        novo_pedido,
                        parent_code=codigo,
                        revision_type=(
                            revision_type
                        ),
                        foto_fixa_id=(
                            item[
                                "source_photo_id"
                            ]
                        ),
                        briefing_fixo=(
                            parametros_refazer[
                                "briefing_fixo"
                            ]
                        ),
                        family_fixa=(
                            parametros_refazer[
                                "family_fixa"
                            ]
                        ),
                        layout_fixo=(
                            parametros_refazer[
                                "layout_fixo"
                            ]
                        ),
                        background_style_fixo=(
                            parametros_refazer[
                                "background_style_fixo"
                            ]
                        ),
                        literal_replace=(
                            parametros_refazer[
                                "literal_replace"
                            ]
                        ),
                        render_request_fixo=(
                            parametros_refazer[
                                "render_request_fixo"
                            ]
                        ),
                        copy_override=(
                            parametros_refazer[
                                "copy_override"
                            ]
                        ),
                        render_overrides=(
                            parametros_refazer[
                                "render_overrides"
                            ]
                        ),
                        copy_fixa=(
                            parametros_refazer[
                                "copy_fixa"
                            ]
                        ),
                        output_format=(
                            parametros_refazer[
                                "output_format"
                            ]
                        ),
                    )

                    continue

                # =============================================
                # TROCAR FOTO
                # =============================================

                if (
                    lower == "/trocarfoto"
                    or lower.startswith(
                        "/trocarfoto "
                    )
                ):
                    (
                        codigo,
                        instrucao_foto,
                    ) = interpretar_trocarfoto(
                        text
                    )

                    if not codigo:
                        send_message(
                            chat_id,
                            "Use:\n"
                            "/trocarfoto CRIATIVO-0086\n\n"
                            "ou:\n"
                            "/trocarfoto CRIATIVO-0086 "
                            "procure uma foto com várias mulheres "
                            "de amarelo",
                        )

                        continue

                    item = buscar_criativo(
                        codigo
                    )

                    if not item:
                        send_message(
                            chat_id,
                            "❌  Criativo não encontrado.",
                        )

                        continue

                    copy_anterior = (
                        copy_estruturada_do_item(
                            item
                        )
                    )

                    overrides_anteriores = (
                        render_overrides_do_item(
                            item
                        )
                    )

                    foto_exata = (
                        extrair_foto_exata_trocarfoto(
                            instrucao_foto
                        )
                    )

                    if foto_exata:
                        criterio = (
                            "usar exatamente a foto "
                            + foto_exata
                        )

                        mensagem_criterio = (
                            "\n📌 Foto específica: "
                            + foto_exata
                        )

                        pedido_selecao_foto = None

                    elif instrucao_foto:
                        criterio = (
                            instrucao_foto
                        )

                        mensagem_criterio = (
                            "\n🎯 Critério da nova foto: "
                            + criterio
                        )

                        pedido_selecao_foto = (
                            (
                                item.get(
                                    "request"
                                )
                                or ""
                            )
                            + "\n\n"
                            + "INSTRUÇÃO EXCLUSIVA PARA A NOVA FOTO:\n"
                            + criterio
                            + "\n\n"
                            + "Use esta instrução somente para "
                            + "selecionar a fotografia. Não altere "
                            + "copy, layout, cores ou composição."
                        )

                    else:
                        mensagem_criterio = ""
                        pedido_selecao_foto = (
                            item.get(
                                "request"
                            )
                            or ""
                        )

                    send_message(
                        chat_id,
                        f"🖼 Trocando a foto de {codigo}...\n\n"
                        "🔒 Serão mantidos:\n"
                        f"• família: {item.get('family')}\n"
                        f"• composição: {item.get('layout')}\n"
                        f"• fundo: {item.get('background_style')}\n"
                        "• headline\n"
                        "• texto de apoio\n"
                        "• CTA\n"
                        "• ajustes de fonte\n"
                        f"{mensagem_criterio}\n\n"
                        "Apenas a fotografia será substituída.",
                    )

                    executar_criacao(
                        chat_id,

                        item.get(
                            "request"
                        )
                        or "",

                        parent_code=codigo,

                        revision_type=(
                            "NEW_PHOTO"
                        ),

                        excluir_foto_id=(
                            None
                            if foto_exata
                            else item[
                                "source_photo_id"
                            ]
                        ),

                        foto_fixa_nome=(
                            foto_exata
                        ),

                        briefing_fixo=(
                            item[
                                "briefing"
                            ]
                        ),

                        family_fixa=(
                            item[
                                "family"
                            ]
                        ),

                        layout_fixo=(
                            item[
                                "layout"
                            ]
                        ),

                        background_style_fixo=(
                            item[
                                "background_style"
                            ]
                        ),

                        # Mantém o contexto visual original.
                        render_request_fixo=(
                            item.get(
                                "request"
                            )
                            or ""
                        ),

                        # Mantém a copy efetivamente renderizada.
                        copy_fixa=(
                            copy_anterior
                        ),

                        # Mantém ajustes tipográficos anteriores.
                        render_overrides=(
                            overrides_anteriores
                        ),

                        # Só esta instrução influencia a busca.
                        photo_selection_request=(
                            pedido_selecao_foto
                        ),

                        output_format=(
                            output_format_do_item(
                                item
                            )
                        ),
                    )

                    continue

                # =============================================
                # HISTÓRICO
                # =============================================

                if lower == "/historico":
                    itens = listar_ultimos(
                        10
                    )

                    if not itens:
                        send_message(
                            chat_id,
                            "Nenhum criativo registrado.",
                        )

                        continue

                    linhas = [
                        "📚 ÚLTIMOS CRIATIVOS",
                        "",
                    ]

                    for item in itens:
                        linhas.append(
                            f"{item['creative_code']} "
                            f"| {item['status']}"
                        )

                        linhas.append(
                            f"👨‍🎨 "
                            f"{item.get('family')}"
                        )

                        linhas.append(
                            f"🧩 "
                            f"{item.get('layout')}"
                        )

                        linhas.append(
                            f"🎨 "
                            f"{item.get('background_style')}"
                        )

                        linhas.append(
                            f"📷 "
                            f"{item.get('source_photo_name')}"
                        )

                        if item.get(
                            "parent_code"
                        ):
                            linhas.append(
                                f"↳ origem: "
                                f"{item['parent_code']}"
                            )

                        linhas.append(
                            ""
                        )

                    send_message(
                        chat_id,
                        "\n".join(
                            linhas
                        ),
                    )

                    continue

                # =============================================
                # TEXTO NORMAL
                # =============================================

                send_message(
                    chat_id,
                    "🎨 Analisando seu pedido...",
                )

                try:
                    briefing = (
                        criar_briefing(
                            text
                        )
                    )

                    send_message(
                        chat_id,
                        briefing,
                    )

                except Exception as e:
                    print(
                        "Erro OpenAI:",
                        type(
                            e
                        ).__name__,
                        str(
                            e
                        ),
                        flush=True,
                    )

                    send_message(
                        chat_id,
                        "❌  Não consegui processar.",
                    )
            except Exception as erro_update:
                print(
                    "Erro no processamento do update:",
                    type(erro_update).__name__,
                    str(erro_update),
                    flush=True,
                )
                continue

    except Exception as e:
        print(
            "Erro polling:",
            type(
                e
            ).__name__,
            str(
                e
            ),
            flush=True,
        )

        time.sleep(
            5
        )
