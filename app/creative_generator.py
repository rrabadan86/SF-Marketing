import os
import re
import sqlite3
import tempfile

from openai_client import (
    criar_briefing,
)

from photo_selector import (
    selecionar_melhor_foto,
)

from drive_client import (
    baixar_arquivo,
)

from campaign_router import (
    escolher_familia,
    FAMILY_DYNAMIC,
    FAMILY_EVENT,
    FAMILY_SEASONAL,
)

from dynamic_layout import (
    render_dynamic,
)

from event_layout import (
    render_event,
)

from seasonal_layout import (
    render_seasonal,
)

from story_layout import (
    render_story,
)

from seasonal_reference_interpreter import (
    interpretar_referencias,
)


DB_FILE = (
    "/app/data/creative_agent.db"
)


# =========================================================
# FOTO FIXA
# =========================================================

def buscar_foto_por_id(
    drive_file_id,
):
    conn = sqlite3.connect(
        DB_FILE
    )

    conn.row_factory = (
        sqlite3.Row
    )

    row = conn.execute("""
        SELECT
            drive_file_id,
            filename,
            folder,
            description,
            tags,
            orientation,
            people_count,
            text_space,
            quality_score,
            brand_fit_score
        FROM photos
        WHERE drive_file_id = ?
          AND indexed = 1
    """, (
        drive_file_id,
    )).fetchone()

    conn.close()

    if not row:
        raise RuntimeError(
            "Foto não encontrada no banco."
        )

    return dict(
        row
    )



def buscar_foto_especifica(
    referencia,
):
    """
    Resolve uma fotografia exata pelo drive_file_id ou filename.

    Regras:
    - ID do Drive tem prioridade;
    - filename exato case-insensitive;
    - se houver nomes duplicados, exige referência mais específica.
    """

    referencia = (
        referencia
        or ""
    ).strip()

    if not referencia:
        raise RuntimeError(
            "FOTO ESPECÍFICA: informe o nome do arquivo "
            "ou drive_file_id."
        )

    conn = sqlite3.connect(
        DB_FILE
    )

    conn.row_factory = (
        sqlite3.Row
    )

    try:
        row = conn.execute("""
            SELECT
                drive_file_id,
                filename,
                folder,
                description,
                tags,
                orientation,
                people_count,
                text_space,
                quality_score,
                brand_fit_score
            FROM photos
            WHERE drive_file_id = ?
              AND indexed = 1
            LIMIT 1
        """, (
            referencia,
        )).fetchone()

        if row:
            return dict(row)

        rows = conn.execute("""
            SELECT
                drive_file_id,
                filename,
                folder,
                description,
                tags,
                orientation,
                people_count,
                text_space,
                quality_score,
                brand_fit_score
            FROM photos
            WHERE LOWER(filename) = LOWER(?)
              AND indexed = 1
        """, (
            referencia,
        )).fetchall()

    finally:
        conn.close()

    if not rows:
        raise RuntimeError(
            "FOTO ESPECÍFICA: não encontrei no acervo o arquivo "
            f"'{referencia}'."
        )

    if len(rows) > 1:
        pastas = sorted(
            {
                str(row["folder"] or "")
                for row in rows
            }
        )

        detalhe = ", ".join(
            pasta
            for pasta in pastas
            if pasta
        )

        raise RuntimeError(
            "FOTO ESPECÍFICA: há mais de uma foto com o nome "
            f"'{referencia}'. "
            + (
                f"Pastas: {detalhe}. "
                if detalhe
                else ""
            )
            + "Use o drive_file_id para escolher sem ambiguidade."
        )

    return dict(
        rows[0]
    )


# =========================================================
# BRIEFING
# =========================================================

def extrair_secao(
    briefing,
    titulo,
    proximos,
):
    match = re.search(
        re.escape(
            titulo
        ),
        briefing,
        flags=re.IGNORECASE,
    )

    if not match:
        return ""

    resto = briefing[
        match.end():
    ]

    fim = len(
        resto
    )

    for proximo in proximos:
        proximo_match = re.search(
            re.escape(
                proximo
            ),
            resto,
            flags=re.IGNORECASE,
        )

        if (
            proximo_match
            and proximo_match.start()
            < fim
        ):
            fim = (
                proximo_match.start()
            )

    resultado = (
        resto[:fim]
    )

    resultado = re.sub(
        r"\*\*",
        "",
        resultado,
    )

    resultado = re.sub(
        r"\s+",
        " ",
        resultado,
    )

    return resultado.strip()


def limitar(
    texto,
    limite,
):
    texto = (
        texto
        or ""
    ).strip()

    if len(
        texto
    ) <= limite:
        return texto

    parcial = (
        texto[:limite]
    )

    if " " in parcial:
        parcial = (
            parcial.rsplit(
                " ",
                1,
            )[0]
        )

    return (
        parcial.rstrip(
            ".,;:-"
        )
        + "."
    )


# =========================================================
# REVISÃO DO /REFAZER
# =========================================================

REVISAO_MARKER = "INSTRUÇÃO DE REVISÃO DO USUÁRIO:"


def extrair_instrucao_revisao(
    pedido,
):
    texto = (
        pedido
        or ""
    )

    if REVISAO_MARKER not in texto:
        return ""

    instrucao = texto.split(
        REVISAO_MARKER,
        1,
    )[1]

    # Remove a orientação técnica que o main acrescenta
    # depois da instrução real do usuário.
    corte = (
        "Mantenha o objetivo principal do "
        "criativo anterior"
    )

    if corte in instrucao:
        instrucao = instrucao.split(
            corte,
            1,
        )[0]

    return instrucao.strip()


def pedido_base_sem_revisao(
    pedido,
):
    texto = (
        pedido
        or ""
    )

    if REVISAO_MARKER in texto:
        return (
            texto.split(
                REVISAO_MARKER,
                1,
            )[0]
            .strip()
        )

    return texto.strip()


def preparar_pedido_para_briefing(
    pedido,
):
    """
    Em /refazer com instrução, não enviamos ao gerador de
    briefing um pedido "misturado". A revisão recebe
    prioridade explícita e o objetivo anterior vira contexto.
    """

    instrucao = extrair_instrucao_revisao(
        pedido
    )

    if not instrucao:
        return (
            "CRIE O BRIEFING COM FIDELIDADE MÁXIMA AO PEDIDO DO "
            "USUÁRIO.\n\n"
            "REGRA CRÍTICA DE COPY:\n"
            "- A headline e o texto de apoio devem comunicar "
            "explicitamente a ideia central pedida pelo usuário.\n"
            "- Não substitua o conceito pedido por frases genéricas "
            "de academia, transformação, treino ou aula experimental.\n"
            "- Se o usuário mencionar acolhimento, amizade, "
            "pertencimento, bem-estar, comunidade, exclusividade, "
            "confiança, constância ou outro atributo, esse atributo "
            "deve aparecer claramente na mensagem final.\n"
            "- O texto precisa combinar com a intenção emocional e "
            "comercial do pedido, não apenas com o segmento fitness.\n"
            "- Evite clichês como 'Sua transformação pode começar "
            "hoje' quando isso não for o objetivo solicitado.\n"
            "- Retorne normalmente todas as seções do briefing, "
            "incluindo exatamente os cabeçalhos 📝 HEADLINE, "
            "💬 TEXTO DE APOIO e 👉 CTA.\n\n"
            "PEDIDO ORIGINAL DO USUÁRIO:\n"
            + pedido
        )

    base = pedido_base_sem_revisao(
        pedido
    )

    return (
        "REVISÃO DE UM CRIATIVO EXISTENTE.\n\n"
        "OBJETIVO ORIGINAL:\n"
        + base
        + "\n\n"
        "INSTRUÇÃO ATUAL DO USUÁRIO — PRIORIDADE MÁXIMA:\n"
        + instrucao
        + "\n\n"
        "Gere um novo briefing completo obedecendo a "
        "instrução atual. Se ela pedir para retirar, trocar "
        "ou reformular uma frase, a versão anterior NÃO "
        "deve permanecer. A copy final deve refletir "
        "explicitamente a revisão solicitada."
    )


def aplicar_instrucao_revisao_sazonal(
    copy,
    pedido,
):
    """
    Camada de segurança para instruções textuais explícitas.
    O briefing continua sendo a principal fonte da copy, mas
    pedidos objetivos como 'informe que...' não podem cair no
    texto genérico de fallback.
    """

    instrucao = extrair_instrucao_revisao(
        pedido
    )

    if not instrucao:
        return copy

    texto = instrucao.strip()
    texto_lower = texto.lower()

    # "Informe que ..." vira uma base factual para o apoio.
    match = re.search(
        r"\binforme\s+que\s+(.+?)(?:\.\s|$)",
        texto,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if match:
        fato = re.sub(
            r"\s+",
            " ",
            match.group(1),
        ).strip()

        if fato:
            fato = (
                fato[0].upper()
                + fato[1:]
            )

            if not fato.endswith(
                (".", "!", "?")
            ):
                fato += "."

            copy[
                "support"
            ] = limitar(
                fato,
                100,
            )

    # Quando o usuário pede tom motivacional sem exageros,
    # evitamos slogans excessivos e usamos uma conclusão curta.
    if (
        "motivacional"
        in texto_lower
        and (
            "sem exager"
            in texto_lower
            or "sem exageros"
            in texto_lower
        )
    ):
        support = (
            copy.get(
                "support"
            )
            or ""
        ).strip()

        complemento = (
            " Cada treino realizado contou nessa jornada."
        )

        if (
            complemento.strip().lower()
            not in support.lower()
        ):
            copy[
                "support"
            ] = limitar(
                (
                    support
                    + complemento
                ).strip(),
                100,
            )

    return copy


# =========================================================
# EDIÇÃO CIRÚRGICA DE COPY
# =========================================================

def substituir_case_insensitive(
    texto,
    antigo,
    novo,
):
    texto = (
        texto
        or ""
    )

    antigo = (
        antigo
        or ""
    )

    if not antigo:
        return texto, False

    # Primeiro tenta a substituição literal exata.
    if antigo in texto:
        return (
            texto.replace(
                antigo,
                novo,
                1,
            ),
            True,
        )

    # Depois tenta ignorando maiúsculas/minúsculas.
    match = re.search(
        re.escape(
            antigo
        ),
        texto,
        flags=re.IGNORECASE,
    )

    if not match:
        return texto, False

    return (
        texto[
            :match.start()
        ]
        + novo
        + texto[
            match.end():
        ],
        True,
    )


def aplicar_substituicao_literal(
    copy,
    substituicao,
):
    """
    Troca uma frase somente onde ela realmente existe.
    Não pede nova copy à IA e não altera outros campos.
    """

    if not substituicao:
        return copy

    antigo, novo = substituicao

    encontrou = False

    for campo in (
        "headline",
        "support",
        "cta",
    ):
        valor = (
            copy.get(
                campo
            )
            or ""
        )

        valor_novo, alterou = (
            substituir_case_insensitive(
                valor,
                antigo,
                novo,
            )
        )

        if alterou:
            copy[
                campo
            ] = valor_novo

            encontrou = True

            # A instrução é "substitua a frase X por Y".
            # Alteramos apenas a primeira ocorrência encontrada.
            break

    if not encontrou:
        raise ValueError(
            "EDIÇÃO LITERAL: não encontrei a frase "
            f'"{antigo}" no headline, texto de apoio ou CTA '
            "do criativo anterior."
        )

    return copy


def substituir_conteudo_secao(
    briefing,
    titulo,
    proximos,
    novo_conteudo,
):
    """
    Mantém o briefing histórico coerente com a copy renderizada.
    Isso é importante para que um próximo /refazer preserve
    exatamente a versão mais recente, inclusive após uma
    substituição literal.
    """

    briefing = (
        briefing
        or ""
    )

    inicio = re.search(
        re.escape(
            titulo
        ),
        briefing,
        flags=re.IGNORECASE,
    )

    if not inicio:
        return briefing

    conteudo_inicio = (
        inicio.end()
    )

    fim = len(
        briefing
    )

    trecho_restante = briefing[
        conteudo_inicio:
    ]

    for proximo in proximos:
        match = re.search(
            re.escape(
                proximo
            ),
            trecho_restante,
            flags=re.IGNORECASE,
        )

        if match:
            candidato = (
                conteudo_inicio
                + match.start()
            )

            if candidato < fim:
                fim = candidato

    prefixo = briefing[
        :conteudo_inicio
    ]

    sufixo = briefing[
        fim:
    ]

    conteudo = (
        "\n"
        + (
            novo_conteudo
            or ""
        ).strip()
        + "\n\n"
    )

    return (
        prefixo
        + conteudo
        + sufixo.lstrip(
            "\n"
        )
    )


def sincronizar_briefing_com_copy(
    briefing,
    copy,
):
    briefing = substituir_conteudo_secao(
        briefing,
        "📝 HEADLINE",
        [
            "💬 TEXTO DE APOIO",
            "👉 CTA",
            "📷 FOTO IDEAL",
            "🎨 DIREÇÃO VISUAL",
        ],
        copy.get(
            "headline"
        )
        or "",
    )

    briefing = substituir_conteudo_secao(
        briefing,
        "💬 TEXTO DE APOIO",
        [
            "👉 CTA",
            "📷 FOTO IDEAL",
            "🎨 DIREÇÃO VISUAL",
        ],
        copy.get(
            "support"
        )
        or "",
    )

    briefing = substituir_conteudo_secao(
        briefing,
        "👉 CTA",
        [
            "📷 FOTO IDEAL",
            "🎨 DIREÇÃO VISUAL",
        ],
        copy.get(
            "cta"
        )
        or "",
    )

    return briefing


# =========================================================
# NOMES DE CAMPANHAS
# =========================================================

def detectar_nome_evento(
    pedido,
):
    texto = (
        pedido
        or ""
    ).lower()

    if (
        "aulão"
        in texto
        or "aulao"
        in texto
    ):
        if (
            "especial"
            in texto
        ):
            return (
                "Aulão especial SlimFit"
            )

        return (
            "Aulão SlimFit"
        )

    if (
        "confraternização"
        in texto
        or "confraternizacao"
        in texto
    ):
        return (
            "Confraternização SlimFit"
        )

    if (
        "aniversário"
        in texto
        or "aniversario"
        in texto
    ):
        return (
            "Aniversário SlimFit"
        )

    if "workshop" in texto:
        return (
            "Workshop SlimFit"
        )

    if "evento" in texto:
        return (
            "Evento especial SlimFit"
        )

    return ""


def detectar_nome_sazonal(
    pedido,
):
    texto = (
        pedido
        or ""
    ).lower()

    if (
        "circuito slim"
        in texto
    ):
        return "Circuito Slim"

    if (
        "dia das mães"
        in texto
        or "dia das maes"
        in texto
    ):
        return "Dia das Mães"

    if (
        "dia das mulheres"
        in texto
        or "dia da mulher"
        in texto
    ):
        return "Dia das Mulheres"

    if (
        "dia mundial da saúde"
        in texto
        or "dia mundial da saude"
        in texto
    ):
        return "Dia Mundial da Saúde"

    if (
        "dia mundial da atividade física"
        in texto
        or "dia mundial da atividade fisica"
        in texto
    ):
        return (
            "Dia Mundial da Atividade Física"
        )

    if "outubro rosa" in texto:
        return "Outubro Rosa"

    if "copa slim" in texto:
        return "Copa Slim"

    if (
        "páscoa"
        in texto
        or "pascoa"
        in texto
    ):
        return "Desafio de Páscoa"

    return ""


# =========================================================
# COPY EVENTO
# =========================================================

def headline_evento_generica(
    headline,
):
    texto = (
        headline
        or ""
    ).lower()

    frases_genericas = [
        "um encontro especial",
        "espera por você",
        "espera por voce",
        "viva uma experiência",
        "viva uma experiencia",
        "momento especial",
        "uma experiência especial",
        "uma experiencia especial",
        "venha viver",
    ]

    return any(
        frase in texto
        for frase in frases_genericas
    )


def adaptar_copy_evento(
    pedido,
    headline,
    apoio,
    cta,
):
    nome_evento = (
        detectar_nome_evento(
            pedido
        )
    )

    if nome_evento:
        if (
            not headline
            or headline_evento_generica(
                headline
            )
        ):
            headline = (
                nome_evento
            )

    if not headline:
        headline = (
            "Um evento especial no SlimFit."
        )

    if not apoio:
        apoio = (
            "Uma experiência de movimento, "
            "energia e conexão entre mulheres."
        )

    if cta:
        if (
            cta.strip().lower()
            == headline.strip().lower()
        ):
            cta = (
                "Participe com a gente."
            )

    return {
        "headline": limitar(
            headline,
            48,
        ),

        "support": limitar(
            apoio,
            82,
        ),

        "cta": (
            limitar(
                cta,
                30,
            )
            if cta
            else ""
        ),
    }


# =========================================================
# COPY SEASONAL
# =========================================================

def headline_sazonal_generica(
    headline,
):
    texto = (
        headline
        or ""
    ).lower()

    frases = [
        "um momento especial",
        "uma data especial",
        "celebre com a gente",
        "celebre conosco",
        "movimento que transforma",
        "juntas somos mais fortes",
        "uma experiência especial",
        "uma experiencia especial",
        "vem aí",
        "vem ai",
    ]

    return any(
        frase in texto
        for frase in frases
    )


def adaptar_copy_sazonal(
    pedido,
    headline,
    apoio,
    cta,
):
    nome = (
        detectar_nome_sazonal(
            pedido
        )
    )

    # Para campanhas com nome próprio, evitamos
    # headlines genéricas que escondem a campanha.
    if nome:
        if (
            not headline
            or headline_sazonal_generica(
                headline
            )
        ):
            headline = nome

    if not headline:
        headline = (
            nome
            or "Uma campanha especial SlimFit"
        )

    if not apoio:
        if nome == "Circuito Slim":
            apoio = (
                "Movimento, energia e conexão "
                "em uma experiência coletiva."
            )

        elif nome:
            apoio = (
                "Uma mensagem especial da SlimFit "
                "para celebrar esta campanha."
            )

        else:
            apoio = (
                "Uma campanha criada para informar, "
                "inspirar e conectar."
            )

    if (
        cta
        and cta.strip().lower()
        == headline.strip().lower()
    ):
        cta = ""

    return {
        "headline": limitar(
            headline,
            54,
        ),

        "support": limitar(
            apoio,
            100,
        ),

        "cta": (
            limitar(
                cta,
                34,
            )
            if cta
            else ""
        ),
    }



# =========================================================
# FIDELIDADE DE COPY - DYNAMIC
# =========================================================

def normalizar_sem_acento(
    texto,
):
    import unicodedata

    texto = (
        texto
        or ""
    ).lower()

    texto = unicodedata.normalize(
        "NFD",
        texto,
    )

    return "".join(
        caractere
        for caractere in texto
        if unicodedata.category(
            caractere
        ) != "Mn"
    )


def copy_dynamic_generica(
    headline,
    apoio,
):
    """
    Detecta os fallbacks/clichês que podem mascarar o pedido
    real do usuário.
    """

    combinado = normalizar_sem_acento(
        (
            headline
            or ""
        )
        + " "
        + (
            apoio
            or ""
        )
    )

    frases_genericas = [
        "sua transformacao pode comecar hoje",
        "conheca uma experiencia de treino",
        "pensada para mulheres reais",
        "comece sua transformacao",
        "venha treinar com a gente",
        "aula experimental",
    ]

    return any(
        frase in combinado
        for frase in frases_genericas
    )


def detectar_tema_dynamic(
    pedido,
):
    """
    Camada determinística de segurança.

    O OpenAI continua sendo a fonte principal do briefing.
    Esta função só impede que um pedido semanticamente claro
    termine em fallback genérico caso a extração do briefing
    falhe ou retorne copy desalinhada.
    """

    texto = normalizar_sem_acento(
        pedido
    )

    temas = [
        {
            "nome": "ACOLHIMENTO_COMUNIDADE",
            "termos": [
                "acolhedor",
                "acolhimento",
                "amizade",
                "amigas",
                "pertencimento",
                "comunidade",
                "conexao",
                "bem-estar",
                "bem estar",
                "ambiente diferente",
                "diferente de qualquer academia",
            ],
            "headline": (
                "Mais que treino. Um lugar para pertencer."
            ),
            "support": (
                "No SlimFit, acolhimento, amizade e bem-estar "
                "fazem parte de cada encontro."
            ),
            "cta": (
                "Venha viver o SlimFit."
            ),
        },
        {
            "nome": "CONSTANCIA_ROTINA",
            "termos": [
                "constancia",
                "consistencia",
                "rotina",
                "frequencia",
                "habito",
                "assiduidade",
            ],
            "headline": (
                "Constância que vira conquista."
            ),
            "support": (
                "Uma rotina de movimento, cuidado e evolução "
                "construída um treino de cada vez."
            ),
            "cta": (
                "Continue com a gente."
            ),
        },
        {
            "nome": "FORCA_CONFIANCA",
            "termos": [
                "forca",
                "forte",
                "confianca",
                "autoconfianca",
                "seguranca",
                "superacao",
            ],
            "headline": (
                "Força que você leva para a vida."
            ),
            "support": (
                "Treinar também é construir confiança, autonomia "
                "e disposição para viver melhor."
            ),
            "cta": (
                "Descubra sua força."
            ),
        },
        {
            "nome": "SAUDE_BEM_ESTAR",
            "termos": [
                "saude",
                "qualidade de vida",
                "bem-estar",
                "bem estar",
                "disposicao",
                "energia",
                "cuidado",
            ],
            "headline": (
                "Seu bem-estar também é prioridade."
            ),
            "support": (
                "Movimento, cuidado e energia em uma experiência "
                "pensada para fazer bem por inteiro."
            ),
            "cta": (
                "Cuide de você com a gente."
            ),
        },
        {
            "nome": "EXPERIENCIA_PREMIUM",
            "termos": [
                "premium",
                "exclusivo",
                "exclusividade",
                "personalizado",
                "atendimento",
                "experiencia diferenciada",
                "diferenciado",
            ],
            "headline": (
                "Treino com atenção de verdade."
            ),
            "support": (
                "Uma experiência mais próxima, personalizada e "
                "cuidadosa em cada detalhe."
            ),
            "cta": (
                "Conheça o SlimFit."
            ),
        },
        {
            "nome": "GRUPO_CONEXAO",
            "termos": [
                "grupo",
                "juntas",
                "conexao",
                "amizade",
                "companhia",
                "coletivo",
            ],
            "headline": (
                "Juntas, o treino ganha outro sentido."
            ),
            "support": (
                "Movimento, conexão e incentivo em um espaço onde "
                "cada mulher faz parte."
            ),
            "cta": (
                "Venha fazer parte."
            ),
        },
    ]

    melhor = None
    melhor_score = 0

    for tema in temas:
        score = sum(
            1
            for termo in tema[
                "termos"
            ]
            if termo in texto
        )

        if score > melhor_score:
            melhor = tema
            melhor_score = score

    if melhor_score <= 0:
        return None

    return {
        **melhor,
        "score": melhor_score,
    }


def adaptar_copy_dynamic(
    pedido,
    headline,
    apoio,
    cta,
):
    """
    Garante aderência ao objetivo explícito do usuário.

    Não sobrescreve uma copy boa sem necessidade.
    Atua quando:
    - a copy caiu no fallback genérico; ou
    - o pedido contém vários sinais claros de um tema e a copy
      gerada não menciona nenhum desses conceitos.
    """

    tema = detectar_tema_dynamic(
        pedido
    )

    if not tema:
        return {
            "headline": headline,
            "support": apoio,
            "cta": cta,
            "theme": None,
            "changed": False,
        }

    generica = copy_dynamic_generica(
        headline,
        apoio,
    )

    pedido_norm = normalizar_sem_acento(
        pedido
    )

    copy_norm = normalizar_sem_acento(
        (
            headline
            or ""
        )
        + " "
        + (
            apoio
            or ""
        )
    )

    termos_relevantes = [
        termo
        for termo in tema[
            "termos"
        ]
        if termo in pedido_norm
    ]

    # Quantos conceitos realmente pedidos aparecem na copy.
    hits_copy = sum(
        1
        for termo in termos_relevantes
        if termo in copy_norm
    )

    desalinhada = (
        generica
        or (
            tema[
                "score"
            ] >= 2
            and hits_copy == 0
        )
    )

    if not desalinhada:
        return {
            "headline": headline,
            "support": apoio,
            "cta": cta,
            "theme": tema[
                "nome"
            ],
            "changed": False,
        }

    return {
        "headline": tema[
            "headline"
        ],
        "support": tema[
            "support"
        ],
        "cta": (
            cta
            or tema[
                "cta"
            ]
        ),
        "theme": tema[
            "nome"
        ],
        "changed": True,
    }



# =========================================================
# ORÇAMENTO DE TEXTO - DYNAMIC
# =========================================================

def compactar_copy_dynamic_para_layout(
    pedido,
    headline,
    apoio,
    cta,
):
    """
    Evita overflow vertical no DYNAMIC_WAVE e composições
    similares.

    Estratégia:
    - se o pedido possui um tema claro;
    - e a soma da copy ficou grande demais para o bloco;
    - usamos a versão temática curta e coesa já definida no
      gerador.

    Isso evita CTA órfão/cortado no rodapé e mantém a ideia
    principal do usuário.
    """

    tema = detectar_tema_dynamic(
        pedido
    )

    headline = (
        headline
        or ""
    ).strip()

    apoio = (
        apoio
        or ""
    ).strip()

    cta = (
        cta
        or ""
    ).strip()

    if not tema:
        return {
            "headline": headline,
            "support": apoio,
            "cta": cta,
            "changed": False,
            "reason": None,
        }

    # Estimativa simples e conservadora para o bloco Dynamic.
    # Headline longa + apoio longo + CTA é a combinação que
    # mais tende a empurrar a última linha para fora do canvas.
    carga = (
        len(headline)
        + len(apoio)
        + len(cta)
    )

    risco_overflow = (
        carga > 145
        or (
            len(headline) > 46
            and len(apoio) > 78
            and bool(cta)
        )
    )

    if not risco_overflow:
        return {
            "headline": headline,
            "support": apoio,
            "cta": cta,
            "changed": False,
            "reason": None,
        }

    headline_curta = (
        tema.get(
            "headline"
        )
        or headline
    )

    apoio_curto = (
        tema.get(
            "support"
        )
        or apoio
    )

    cta_curto = (
        tema.get(
            "cta"
        )
        or cta
    )

    return {
        "headline": headline_curta,
        "support": apoio_curto,
        "cta": cta_curto,
        "changed": True,
        "reason": "TEXT_BUDGET",
    }


# =========================================================
# EXTRAÇÃO COPY
# =========================================================

def extrair_copy(
    briefing,
    family,
    pedido,
):
    headline = extrair_secao(
        briefing,
        "📝 HEADLINE",
        [
            "💬 TEXTO DE APOIO",
            "👉 CTA",
            "📷 FOTO IDEAL",
            "🎨 DIREÇÃO VISUAL",
        ],
    )

    apoio = extrair_secao(
        briefing,
        "💬 TEXTO DE APOIO",
        [
            "👉 CTA",
            "📷 FOTO IDEAL",
            "🎨 DIREÇÃO VISUAL",
        ],
    )

    cta = extrair_secao(
        briefing,
        "👉 CTA",
        [
            "📷 FOTO IDEAL",
            "🎨 DIREÇÃO VISUAL",
        ],
    )

    if family == FAMILY_EVENT:
        return adaptar_copy_evento(
            pedido,
            headline,
            apoio,
            cta,
        )

    if family == FAMILY_SEASONAL:
        return adaptar_copy_sazonal(
            pedido,
            headline,
            apoio,
            cta,
        )

    if not headline:
        headline = (
            "Sua transformação pode começar hoje."
        )

    if not apoio:
        apoio = (
            "Conheça uma experiência de treino "
            "pensada para mulheres reais."
        )

    fidelidade = adaptar_copy_dynamic(
        pedido,
        headline,
        apoio,
        cta,
    )

    if fidelidade.get(
        "changed"
    ):
        print(
            "Copy Dynamic corrigida por fidelidade ao pedido:",
            fidelidade.get(
                "theme"
            ),
            flush=True,
        )

    headline = (
        fidelidade.get(
            "headline"
        )
        or headline
    )

    apoio = (
        fidelidade.get(
            "support"
        )
        or apoio
    )

    cta = (
        fidelidade.get(
            "cta"
        )
        or cta
        or ""
    )

    compactada = (
        compactar_copy_dynamic_para_layout(
            pedido,
            headline,
            apoio,
            cta,
        )
    )

    if compactada.get(
        "changed"
    ):
        print(
            "Copy Dynamic compactada para caber no layout:",
            compactada.get(
                "reason"
            ),
            flush=True,
        )

        headline = (
            compactada.get(
                "headline"
            )
            or headline
        )

        apoio = (
            compactada.get(
                "support"
            )
            or apoio
        )

        cta = (
            compactada.get(
                "cta"
            )
            or ""
        )

    return {
        "headline": limitar(
            headline,
            50,
        ),

        "support": limitar(
            apoio,
            88,
        ),

        "cta": (
            limitar(
                cta,
                28,
            )
            if cta
            else ""
        ),
    }


# =========================================================
# GERAÇÃO
# =========================================================

def gerar_criativo(
    pedido,
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
    temporarios = []

    output_format = (
        output_format
        or "FEED"
    ).strip().upper()

    if (
        layout_fixo
        and str(layout_fixo).startswith(
            "STORY_"
        )
    ):
        output_format = "STORY"

        layout_fixo = str(
            layout_fixo
        )[
            len("STORY_"):
        ]

    if output_format not in {
        "FEED",
        "STORY",
    }:
        output_format = "FEED"

    try:
        # =================================================
        # PEDIDO EFETIVO DE RENDER
        # =================================================
        #
        # Em edição cirúrgica ("faça apenas isso"), o layout
        # deve receber exatamente o pedido da versão anterior.
        # A nova instrução serve apenas para a substituição.
        #
        pedido_render = (
            render_request_fixo
            or pedido
        )

        pedido_foto = (
            photo_selection_request
            or pedido_render
        )

        # =================================================
        # FAMÍLIA
        # =================================================

        family = escolher_familia(
            pedido_render,
            family_override=(
                family_fixa
            ),
        )

        print(
            "Família escolhida:",
            family,
            flush=True,
        )

        # =================================================
        # DIREÇÃO SEASONAL
        # =================================================

        seasonal_direction = None
        photo_requirements = None

        if family == FAMILY_SEASONAL:
            seasonal_direction = (
                interpretar_referencias(
                    pedido_render
                )
            )

            photo_requirements = (
                seasonal_direction.get(
                    "photo_requirements",
                    {}
                )
            )

            print(
                "Campanha Seasonal:",
                seasonal_direction.get(
                    "campaign_type"
                ),
                flush=True,
            )

            print(
                "Arquétipo Seasonal:",
                seasonal_direction.get(
                    "archetype"
                ),
                flush=True,
            )

            print(
                "Requisitos de foto:",
                photo_requirements,
                flush=True,
            )

        # =================================================
        # BRIEFING
        # =================================================

        if briefing_fixo:
            briefing = (
                briefing_fixo
            )

            print(
                "Briefing congelado da versão anterior.",
                flush=True,
            )

        else:
            pedido_briefing = (
                preparar_pedido_para_briefing(
                    pedido
                )
            )

            briefing = criar_briefing(
                pedido_briefing
            )

        # =================================================
        # FOTO
        # =================================================

        if foto_fixa_id:
            # /refazer mantém exatamente a fotografia
            # anterior, preservando a semântica existente.
            foto = buscar_foto_por_id(
                foto_fixa_id
            )

            selecao = {
                "selected": foto,

                "decision": {
                    "reason": (
                        "Foto mantida da versão anterior."
                    )
                },

                "photo_requirements": (
                    photo_requirements
                    or {}
                ),
            }

        elif foto_fixa_nome:
            foto = buscar_foto_especifica(
                foto_fixa_nome
            )

            print(
                "Foto específica selecionada:",
                foto.get(
                    "filename"
                ),
                "| drive_file_id:",
                foto.get(
                    "drive_file_id"
                ),
                flush=True,
            )

            selecao = {
                "selected": foto,

                "decision": {
                    "reason": (
                        "Fotografia específica solicitada "
                        "pelo usuário."
                    )
                },

                "photo_requirements": (
                    photo_requirements
                    or {}
                ),
            }

        else:
            selecao = (
                selecionar_melhor_foto(
                    pedido_foto,
                    quantidade=5,

                    excluir_drive_file_id=(
                        excluir_foto_id
                    ),

                    photo_requirements=(
                        photo_requirements
                    ),
                )
            )

            foto = selecao[
                "selected"
            ]

        # Segurança final específica para novas
        # seleções de Circuito Slim.
        if (
            family == FAMILY_SEASONAL
            and seasonal_direction
            and seasonal_direction.get(
                "campaign_type"
            )
            == "CIRCUITO_SLIM"
            and not foto_fixa_id
            and not foto_fixa_nome
        ):
            pessoas = int(
                foto.get(
                    "people_count"
                )
                or 0
            )

            if pessoas < 11:
                raise RuntimeError(
                    "Circuito Slim exige uma fotografia "
                    "com pelo menos 11 pessoas visíveis."
                )

        extensao = (
            os.path.splitext(
                foto[
                    "filename"
                ]
            )[1]
            or ".jpg"
        )

        temp = (
            tempfile.NamedTemporaryFile(
                suffix=extensao,
                delete=False,
            )
        )

        caminho_foto = (
            temp.name
        )

        temp.close()

        temporarios.append(
            caminho_foto
        )

        baixar_arquivo(
            foto[
                "drive_file_id"
            ],
            caminho_foto,
        )

        # =================================================
        # COPY
        # =================================================

        # =================================================
        # COPY ESTRUTURADA
        # =================================================
        #
        # Se o histórico já possui a copy realmente renderizada,
        # ela é a fonte da verdade. Não reconstruímos a partir
        # do briefing.
        #
        if copy_fixa:
            copy = {
                "headline": (
                    copy_fixa.get(
                        "headline"
                    )
                    or ""
                ),
                "support": (
                    copy_fixa.get(
                        "support"
                    )
                    or ""
                ),
                "cta": (
                    copy_fixa.get(
                        "cta"
                    )
                    or ""
                ),
            }

            print(
                "Copy estruturada congelada da versão anterior.",
                flush=True,
            )

        else:
            copy = extrair_copy(
                briefing,
                family,
                pedido,
            )

            # Compatibilidade com criativos antigos que ainda
            # não possuem copy estruturada no banco.
            if (
                family == FAMILY_SEASONAL
                and not copy_override
                and not literal_replace
            ):
                copy = aplicar_instrucao_revisao_sazonal(
                    copy,
                    pedido,
                )

        if literal_replace:
            copy = aplicar_substituicao_literal(
                copy,
                literal_replace,
            )

        if copy_override:
            print(
                "Copy override explícita aplicada:",
                copy_override,
                flush=True,
            )

            for campo in (
                "headline",
                "support",
                "cta",
            ):
                if campo in copy_override:
                    copy[
                        campo
                    ] = (
                        copy_override[
                            campo
                        ]
                        or ""
                    )

        # O histórico reflete a copy realmente renderizada.
        briefing = sincronizar_briefing_com_copy(
            briefing,
            copy,
        )

        print(
            "Headline final:",
            copy.get(
                "headline"
            ),
            flush=True,
        )

        # =================================================
        # RENDER
        # =================================================

        if output_format == "STORY":
            print(
                "Render Story:",
                "1080x1920",
                "| family:",
                family,
                "| layout base:",
                layout_fixo,
                flush=True,
            )

            base_layout_story = (
                layout_fixo
                or (
                    seasonal_direction.get(
                        "archetype"
                    )
                    if (
                        family == FAMILY_SEASONAL
                        and seasonal_direction
                    )
                    else None
                )
                or (
                    "EVENT"
                    if family == FAMILY_EVENT
                    else "DYNAMIC"
                )
            )

            visual = render_story(
                caminho_foto,
                copy,
                pedido_render,
                foto,
                family,
                base_layout_story,
                seasonal_direction=(
                    seasonal_direction
                ),
                render_overrides=(
                    render_overrides
                    or {}
                ),
            )

        elif family == FAMILY_EVENT:
            visual = render_event(
                caminho_foto,
                copy,
                pedido_render,
                foto,

                layout_override=(
                    layout_fixo
                ),

                background_override=(
                    background_style_fixo
                ),
            )

        elif family == FAMILY_SEASONAL:
            # /trocarfoto mantém o arquétipo anterior.
            archetype_override = (
                layout_fixo
                if layout_fixo
                in {
                    "SEASONAL_CLEAN",
                    "SEASONAL_PHOTO",
                    "SEASONAL_PROMO",
                }
                else None
            )

            visual = render_seasonal(
                caminho_foto,
                copy,
                pedido_render,
                foto,
                seasonal_direction,
                archetype_override=(
                    archetype_override
                ),
                render_overrides=(
                    render_overrides
                    or {}
                ),
            )

        else:
            visual = render_dynamic(
                caminho_foto,
                copy,
                pedido_render,
                foto,

                composition_override=(
                    layout_fixo
                ),

                background_override=(
                    background_style_fixo
                ),

                render_overrides=(
                    render_overrides
                    or {}
                ),
            )

        # =================================================
        # RESULTADO
        # =================================================

        return {
            "image_path": (
                visual[
                    "image_path"
                ]
            ),

            "briefing": briefing,

            "photo": foto,

            "selection": selecao,

            "family": (
                visual[
                    "family"
                ]
            ),

            "layout": (
                visual[
                    "composition"
                ]
            ),

            "background_style": (
                visual[
                    "background_style"
                ]
            ),

            "copy": copy,

            "event_meta": (
                visual.get(
                    "event_meta"
                )
            ),

            "campaign_type": (
                visual.get(
                    "campaign_type"
                )
            ),

            "seasonal_direction": (
                seasonal_direction
            ),

            "photo_requirements": (
                photo_requirements
            ),

            "render_overrides": {
                **(
                    render_overrides
                    or {}
                ),
                "output_format": (
                    output_format
                ),
            },

            "output_format": (
                output_format
            ),

            "width": (
                visual.get(
                    "width",
                    1080,
                )
            ),

            "height": (
                visual.get(
                    "height",
                    1920
                    if output_format == "STORY"
                    else 1350,
                )
            ),

            "publisher_layout": (
                visual.get(
                    "publisher_layout"
                )
            ),

            "generation_mode": (
                "DETERMINISTIC_COMPOSITE"
            ),

            "design_locked": bool(
                briefing_fixo
                or family_fixa
                or layout_fixo
                or background_style_fixo
            ),
        }

    finally:
        for caminho in temporarios:
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
