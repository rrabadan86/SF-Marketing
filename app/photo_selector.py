import os
import json
import base64
import sqlite3
import tempfile

from PIL import Image
from pillow_heif import register_heif_opener

from drive_client import baixar_arquivo
from photo_search import buscar_fotos
from openai_client import client

from photo_intelligence import (
    buscar_candidatos_inteligentes,
    photo_intelligence_status,
)


register_heif_opener()


DB_FILE = "/app/data/creative_agent.db"

APPROVED_PHOTO_COOLDOWN = 40


# =========================================================
# COOLDOWN
# =========================================================

def fotos_em_cooldown(
    limite=APPROVED_PHOTO_COOLDOWN,
):
    if not os.path.exists(
        DB_FILE
    ):
        return set()

    conn = sqlite3.connect(
        DB_FILE
    )

    try:
        tabela = conn.execute("""
            SELECT name
            FROM sqlite_master
            WHERE
                type = 'table'
                AND name = 'creatives'
        """).fetchone()

        if not tabela:
            return set()

        rows = conn.execute("""
            SELECT
                source_photo_id,
                status
            FROM creatives
            ORDER BY id DESC
            LIMIT ?
        """, (
            limite,
        )).fetchall()

        return {
            row[0]
            for row in rows
            if (
                row[0]
                and str(
                    row[1]
                    or ""
                ).upper()
                == "APPROVED"
            )
        }

    finally:
        conn.close()


def diagnostico_cooldown():
    bloqueadas = (
        fotos_em_cooldown()
    )

    return {
        "cooldown_size": (
            APPROVED_PHOTO_COOLDOWN
        ),

        "blocked_count": len(
            bloqueadas
        ),

        "blocked_ids": sorted(
            bloqueadas
        ),
    }


# =========================================================
# BUSCA ESTRUTURADA
# =========================================================

def buscar_fotos_por_minimo_pessoas(
    minimo,
    limite=80,
):
    """
    Busca diretamente no catálogo indexado.

    Esta função existe para requisitos que precisam
    ser BLOQUEANTES, como Circuito Slim.

    A busca semântica não é usada como primeiro filtro
    porque uma ótima fotografia de grupo poderia estar
    fora dos primeiros resultados semânticos.
    """

    conn = sqlite3.connect(
        DB_FILE
    )

    conn.row_factory = (
        sqlite3.Row
    )

    try:
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
            WHERE
                indexed = 1
                AND COALESCE(
                    people_count,
                    0
                ) >= ?
            ORDER BY
                COALESCE(
                    brand_fit_score,
                    0
                ) DESC,
                COALESCE(
                    quality_score,
                    0
                ) DESC,
                people_count DESC
            LIMIT ?
        """, (
            int(
                minimo
            ),
            int(
                limite
            ),
        )).fetchall()

        return [
            dict(
                row
            )
            for row in rows
        ]

    finally:
        conn.close()


# =========================================================
# PREVIEW
# =========================================================

def criar_preview(
    caminho_original,
):
    imagem = Image.open(
        caminho_original
    ).convert("RGB")

    largura, altura = (
        imagem.size
    )

    max_dim = 1000

    if max(
        largura,
        altura,
    ) > max_dim:
        proporcao = (
            max_dim
            / max(
                largura,
                altura,
            )
        )

        imagem = imagem.resize(
            (
                int(
                    largura
                    * proporcao
                ),
                int(
                    altura
                    * proporcao
                ),
            ),
            Image.Resampling.LANCZOS,
        )

    temp = (
        tempfile.NamedTemporaryFile(
            suffix=".jpg",
            delete=False,
        )
    )

    caminho_preview = (
        temp.name
    )

    temp.close()

    imagem.save(
        caminho_preview,
        "JPEG",
        quality=80,
        optimize=True,
    )

    return caminho_preview


def imagem_para_base64(
    caminho,
):
    with open(
        caminho,
        "rb",
    ) as arquivo:
        return (
            base64.b64encode(
                arquivo.read()
            ).decode(
                "utf-8"
            )
        )


# =========================================================
# REQUISITOS
# =========================================================

def normalizar_requisitos(
    photo_requirements=None,
):
    requisitos = {
        "required": False,
        "min_people_count": None,
        "prefer_group": False,
        "prefer_action": False,
        "prefer_collective_class": False,
        "selection_mode": "normal",
    }

    if photo_requirements:
        requisitos.update(
            photo_requirements
        )

    minimo = requisitos.get(
        "min_people_count"
    )

    if minimo is not None:
        try:
            requisitos[
                "min_people_count"
            ] = int(
                minimo
            )
        except Exception:
            requisitos[
                "min_people_count"
            ] = None

    return requisitos


def atende_requisitos(
    foto,
    requisitos,
):
    minimo = requisitos.get(
        "min_people_count"
    )

    if minimo is not None:
        try:
            pessoas = int(
                foto.get(
                    "people_count"
                )
                or 0
            )
        except Exception:
            pessoas = 0

        if pessoas < minimo:
            return False

    return True


# =========================================================
# CRITÉRIO VISUAL EXPLÍCITO DO /TROCARFOTO
# =========================================================

def extrair_criterio_foto_estrito(
    pedido,
):
    texto = (
        pedido
        or ""
    )

    marcador = (
        "INSTRUÇÃO EXCLUSIVA PARA A NOVA FOTO:"
    )

    if marcador not in texto:
        return ""

    criterio = texto.split(
        marcador,
        1,
    )[1]

    cortes = [
        "Use esta instrução somente",
        "Não altere copy",
        "Nao altere copy",
    ]

    for corte in cortes:
        if corte in criterio:
            criterio = criterio.split(
                corte,
                1,
            )[0]

    return criterio.strip()


def buscar_catalogo_visual(
    limite=None,
):
    """
    Retorna o catálogo visual completo indexado.

    Importante:
    não ordenamos só por qualidade/marca antes da triagem,
    porque isso escondia fotos visualmente muito relevantes
    que estavam fora do top 72/90.
    """

    conn = sqlite3.connect(
        DB_FILE
    )

    conn.row_factory = (
        sqlite3.Row
    )

    try:
        sql = """
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
            WHERE indexed = 1
        """

        params = ()

        if limite is not None:
            sql += " LIMIT ?"
            params = (
                int(
                    limite
                ),
            )

        rows = conn.execute(
            sql,
            params,
        ).fetchall()

        return [
            dict(
                row
            )
            for row in rows
        ]

    finally:
        conn.close()


def combinar_candidatos_sem_duplicar(
    *listas,
):
    resultado = []
    vistos = set()

    for lista in listas:
        for foto in (
            lista
            or []
        ):
            drive_id = foto.get(
                "drive_file_id"
            )

            if not drive_id:
                continue

            if drive_id in vistos:
                continue

            vistos.add(
                drive_id
            )

            resultado.append(
                foto
            )

    return resultado


def criar_preview_criterio(
    caminho_original,
):
    imagem = Image.open(
        caminho_original
    ).convert(
        "RGB"
    )

    largura, altura = (
        imagem.size
    )

    max_dim = 640

    if max(
        largura,
        altura,
    ) > max_dim:
        proporcao = (
            max_dim
            / max(
                largura,
                altura,
            )
        )

        imagem = imagem.resize(
            (
                int(
                    largura
                    * proporcao
                ),
                int(
                    altura
                    * proporcao
                ),
            ),
            Image.Resampling.LANCZOS,
        )

    temp = (
        tempfile.NamedTemporaryFile(
            suffix=".jpg",
            delete=False,
        )
    )

    caminho_preview = (
        temp.name
    )

    temp.close()

    imagem.save(
        caminho_preview,
        "JPEG",
        quality=72,
        optimize=True,
    )

    return caminho_preview


def avaliar_lote_criterio_visual(
    lote,
    criterio,
):
    """
    Avalia aderência visual em 3 níveis:

    exact_match:
        atende literalmente ao pedido.

    strong_match:
        pode não ser literal, mas comunica fortemente a mesma
        intenção visual.

    weak_match:
        aproximação insuficiente para uso automático.

    Isso resolve pedidos humanos como "camisa do Brasil",
    quando o usuário pode estar procurando, na prática,
    uma estética de seleção/Brasil: predominância de amarelo,
    verde, uniforme esportivo e clima de Copa.
    """

    temporarios = []
    conteudo = []

    instrucoes = f"""
Você está fazendo uma TRIAGEM VISUAL inteligente de
fotografias reais do acervo da SlimFit Studio.

CRITÉRIO DO USUÁRIO:

{criterio}

Analise cada fotografia VISUALMENTE e considere tanto:

A) correspondência LITERAL;
B) intenção visual provável do pedido.

Exemplo importante:
se o usuário pedir "mulheres com camisa/camiseta do Brasil",
considere:
- EXACT_MATCH quando várias pessoas usam claramente camisa,
  jersey ou uniforme do Brasil;
- STRONG_MATCH quando a cena comunica inequivocamente estética
  de seleção/Brasil/Copa, por exemplo várias pessoas com
  camisetas esportivas amarelas/verde-amarelas, uniformes de
  "seleção", ou mistura forte de amarelo + camisa do Brasil;
- não trate uma única roupa amarela isolada como suficiente.

Se o usuário disser "quase a totalidade", interprete isso como
uma preferência MUITO FORTE de ranking, não como uma condição
binária impossível. Uma foto com a grande maioria em amarelo
ou uniforme de seleção pode ser strong_match mesmo que nem
todas usem camisa oficial do Brasil.

Também valorize:
- quantidade de pessoas que cumprem o critério;
- proporção do grupo que cumpre o critério;
- clareza visual do elemento pedido;
- semelhança com uma foto de campanha temática.

Não identifique pessoas.

Retorne SOMENTE JSON válido:

{{
  "evaluations": [
    {{
      "index": 1,
      "exact_match": false,
      "strong_match": true,
      "score": 92,
      "matching_people_estimate": 6,
      "group_people_estimate": 7,
      "reason": "maioria do grupo em amarelo e estética clara de seleção/Brasil"
    }}
  ]
}}

score:
- 95-100 = correspondência visual excepcional
- 85-94 = correspondência forte
- 70-84 = aproximação útil
- abaixo de 70 = fraca
"""

    conteudo.append({
        "type": "input_text",
        "text": instrucoes,
    })

    try:
        for indice, foto in enumerate(
            lote,
            start=1,
        ):
            sufixo = (
                os.path.splitext(
                    foto[
                        "filename"
                    ]
                )[1]
                or ".jpg"
            )

            temp_original = (
                tempfile.NamedTemporaryFile(
                    suffix=sufixo,
                    delete=False,
                )
            )

            caminho_original = (
                temp_original.name
            )

            temp_original.close()

            baixar_arquivo(
                foto[
                    "drive_file_id"
                ],
                caminho_original,
            )

            preview = criar_preview_criterio(
                caminho_original
            )

            temporarios.extend([
                caminho_original,
                preview,
            ])

            imagem_b64 = imagem_para_base64(
                preview
            )

            conteudo.append({
                "type": "input_text",
                "text": (
                    f"FOTO {indice}\n"
                    f"Arquivo: "
                    f"{foto.get('filename', '')}\n"
                    f"Descrição indexada: "
                    f"{foto.get('description', '')}\n"
                    f"Tags indexadas: "
                    f"{foto.get('tags', '')}\n"
                    f"Pessoas indexadas: "
                    f"{foto.get('people_count', '')}"
                ),
            })

            conteudo.append({
                "type": "input_image",
                "image_url": (
                    "data:image/jpeg;base64,"
                    + imagem_b64
                ),
            })

        response = client.responses.create(
            model="gpt-5.6-terra",
            reasoning={
                "effort": "low"
            },
            input=[
                {
                    "role": "user",
                    "content": conteudo,
                }
            ],
        )

        resposta = (
            response.output_text
            .strip()
        )

        if resposta.startswith(
            "```json"
        ):
            resposta = resposta[7:]

        if resposta.startswith(
            "```"
        ):
            resposta = resposta[3:]

        if resposta.endswith(
            "```"
        ):
            resposta = resposta[:-3]

        dados = json.loads(
            resposta.strip()
        )

        avaliacoes = dados.get(
            "evaluations",
            []
        )

        resultado = []

        for avaliacao in avaliacoes:
            try:
                indice = (
                    int(
                        avaliacao.get(
                            "index"
                        )
                    )
                    - 1
                )
            except Exception:
                continue

            if (
                indice < 0
                or indice >= len(
                    lote
                )
            ):
                continue

            foto = dict(
                lote[
                    indice
                ]
            )

            foto[
                "_visual_exact_match"
            ] = bool(
                avaliacao.get(
                    "exact_match",
                    False,
                )
            )

            foto[
                "_visual_strong_match"
            ] = bool(
                avaliacao.get(
                    "strong_match",
                    False,
                )
            )

            try:
                foto[
                    "_visual_match_score"
                ] = float(
                    avaliacao.get(
                        "score",
                        0,
                    )
                    or 0
                )
            except Exception:
                foto[
                    "_visual_match_score"
                ] = 0.0

            try:
                foto[
                    "_matching_people_estimate"
                ] = int(
                    avaliacao.get(
                        "matching_people_estimate",
                        0,
                    )
                    or 0
                )
            except Exception:
                foto[
                    "_matching_people_estimate"
                ] = 0

            try:
                foto[
                    "_group_people_estimate"
                ] = int(
                    avaliacao.get(
                        "group_people_estimate",
                        0,
                    )
                    or 0
                )
            except Exception:
                foto[
                    "_group_people_estimate"
                ] = int(
                    foto.get(
                        "people_count",
                        0,
                    )
                    or 0
                )

            grupo = max(
                1,
                foto[
                    "_group_people_estimate"
                ],
            )

            foto[
                "_matching_ratio"
            ] = min(
                1.0,
                max(
                    0.0,
                    foto[
                        "_matching_people_estimate"
                    ]
                    / grupo,
                ),
            )

            foto[
                "_visual_match_reason"
            ] = str(
                avaliacao.get(
                    "reason",
                    "",
                )
                or ""
            )

            resultado.append(
                foto
            )

        return resultado

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


def filtrar_por_criterio_visual(
    candidatos,
    criterio,
    tamanho_lote=8,
):
    """
    Avalia TODO o universo recebido.

    Não existe mais corte fixo em 72/90 antes da visão.
    """

    universo = list(
        candidatos
    )

    avaliadas = []

    print(
        "Modo de critério visual inteligente ativado.",
        flush=True,
    )

    print(
        "Critério visual:",
        criterio,
        flush=True,
    )

    print(
        "Fotos no universo visual:",
        len(
            universo
        ),
        flush=True,
    )

    for inicio in range(
        0,
        len(
            universo
        ),
        tamanho_lote,
    ):
        lote = universo[
            inicio:
            inicio + tamanho_lote
        ]

        resultado_lote = (
            avaliar_lote_criterio_visual(
                lote,
                criterio,
            )
        )

        avaliadas.extend(
            resultado_lote
        )

    # Primeiro aceitamos correspondência exata ou forte.
    compativeis = [
        foto
        for foto in avaliadas
        if (
            foto.get(
                "_visual_exact_match"
            )
            or foto.get(
                "_visual_strong_match"
            )
            or float(
                foto.get(
                    "_visual_match_score",
                    0,
                )
                or 0
            ) >= 85
        )
    ]

    # Ranking inteligente:
    # 1) exact match
    # 2) score visual
    # 3) proporção de pessoas aderentes
    # 4) número absoluto de pessoas aderentes
    # 5) brand fit / qualidade
    compativeis.sort(
        key=lambda foto: (
            1
            if foto.get(
                "_visual_exact_match"
            )
            else 0,

            float(
                foto.get(
                    "_visual_match_score",
                    0,
                )
                or 0
            ),

            float(
                foto.get(
                    "_matching_ratio",
                    0,
                )
                or 0
            ),

            int(
                foto.get(
                    "_matching_people_estimate",
                    0,
                )
                or 0
            ),

            float(
                foto.get(
                    "brand_fit_score",
                    0,
                )
                or 0
            ),

            float(
                foto.get(
                    "quality_score",
                    0,
                )
                or 0
            ),
        ),
        reverse=True,
    )

    print(
        "Melhores aderências visuais:",
        ", ".join(
            (
                f"{foto.get('filename', '?')}"
                f" [score={foto.get('_visual_match_score', 0):.0f}"
                f", ratio={foto.get('_matching_ratio', 0):.2f}"
                f", match={foto.get('_matching_people_estimate', 0)}"
                f"/{foto.get('_group_people_estimate', 0)}]"
            )
            for foto in compativeis[
                :15
            ]
        )
        or "nenhuma",
        flush=True,
    )

    return compativeis



# =========================================================
# PREVIEW INTELIGENTE
# =========================================================

def obter_preview_candidato(
    foto,
    temporarios,
):
    """
    Usa primeiro o preview persistente criado pelo Photo
    Intelligence. Só baixa o original do Drive se o preview
    não existir no cache local.
    """

    preview_indexado = (
        foto.get(
            "preview_path"
        )
        or ""
    )

    if (
        preview_indexado
        and os.path.exists(
            preview_indexado
        )
    ):
        return preview_indexado

    sufixo = (
        os.path.splitext(
            foto.get(
                "filename",
                "",
            )
        )[1]
        or ".jpg"
    )

    temp_original = (
        tempfile.NamedTemporaryFile(
            suffix=sufixo,
            delete=False,
        )
    )

    caminho_original = (
        temp_original.name
    )

    temp_original.close()

    baixar_arquivo(
        foto[
            "drive_file_id"
        ],
        caminho_original,
    )

    preview = criar_preview(
        caminho_original
    )

    temporarios.extend([
        caminho_original,
        preview,
    ])

    return preview


def normalizar_resultado_visual_final(
    resultado,
):
    try:
        index = int(
            resultado.get(
                "index"
            )
        )
    except Exception:
        index = None

    try:
        score = float(
            resultado.get(
                "criterion_score",
                0,
            )
            or 0
        )
    except Exception:
        score = 0.0

    try:
        matching = int(
            resultado.get(
                "matching_people_estimate",
                0,
            )
            or 0
        )
    except Exception:
        matching = 0

    try:
        group = int(
            resultado.get(
                "group_people_estimate",
                0,
            )
            or 0
        )
    except Exception:
        group = 0

    hard_match = bool(
        resultado.get(
            "hard_match",
            False,
        )
    )

    ratio = (
        matching / group
        if group > 0
        else 0.0
    )

    return {
        "index": index,
        "hard_match": hard_match,
        "criterion_score": score,
        "matching_people_estimate": matching,
        "group_people_estimate": group,
        "matching_ratio": ratio,
        "reason": str(
            resultado.get(
                "reason",
                "",
            )
            or ""
        ),
    }

# =========================================================
# SELEÇÃO
# =========================================================

def selecionar_melhor_foto(
    pedido,
    quantidade=5,
    excluir_drive_file_id=None,
    photo_requirements=None,
):
    requisitos = normalizar_requisitos(
        photo_requirements
    )

    criterio_estrito = (
        extrair_criterio_foto_estrito(
            pedido
        )
    )

    bloqueadas_cooldown = (
        fotos_em_cooldown()
    )

    # Em /trocarfoto manual, a instrução explícita tem
    # prioridade sobre cooldown, mas a foto atual continua
    # obrigatoriamente excluída.
    if criterio_estrito:
        bloqueadas = set()

        print(
            "Cooldown ignorado nesta troca manual "
            "com critério explícito.",
            flush=True,
        )

    else:
        bloqueadas = set(
            bloqueadas_cooldown
        )

    if excluir_drive_file_id:
        bloqueadas.add(
            excluir_drive_file_id
        )

    print(
        f"Fotos em cooldown: "
        f"{len(bloqueadas_cooldown)}",
        flush=True,
    )

    print(
        "Requisitos da foto:",
        json.dumps(
            requisitos,
            ensure_ascii=False,
        ),
        flush=True,
    )

    minimo_pessoas = (
        requisitos.get(
            "min_people_count"
        )
    )

    # =====================================================
    # 1. UNIVERSO DE CANDIDATOS
    # =====================================================

    if criterio_estrito:
        status_inteligencia = (
            photo_intelligence_status()
        )

        if status_inteligencia[
            "ready"
        ] > 0:
            excluir_inteligencia = set(
                bloqueadas
            )

            shortlist = (
                buscar_candidatos_inteligentes(
                    criterio_estrito,
                    limite=max(
                        12,
                        quantidade * 2,
                    ),
                    excluir_ids=(
                        excluir_inteligencia
                    ),
                )
            )

            candidatos_originais = (
                shortlist[
                    "results"
                ]
            )

            busca_criteria = {
                "mode": (
                    "photo_intelligence_v2"
                ),
                "visual_criterion": (
                    criterio_estrito
                ),
                "filters": (
                    shortlist.get(
                        "filters",
                        {}
                    )
                ),
                "indexed_count": (
                    shortlist.get(
                        "indexed_count",
                        0,
                    )
                ),
            }

            print(
                "Photo Intelligence:",
                status_inteligencia[
                    "ready"
                ],
                "/",
                status_inteligencia[
                    "total"
                ],
                "| shortlist:",
                len(
                    candidatos_originais
                ),
                "| filtros:",
                json.dumps(
                    shortlist.get(
                        "filters",
                        {}
                    ),
                    ensure_ascii=False,
                ),
                flush=True,
            )

        else:
            # Fallback temporário enquanto o novo índice ainda
            # não foi construído.
            busca_semantica = buscar_fotos(
                criterio_estrito,
                limite=40,
            )

            candidatos_originais = (
                busca_semantica.get(
                    "results",
                    []
                )
            )

            busca_criteria = {
                "mode": (
                    "semantic_fallback_no_visual_index"
                ),
                "visual_criterion": (
                    criterio_estrito
                ),
            }

            print(
                "⚠️ Photo Intelligence ainda vazio. "
                "Usando fallback semântico.",
                flush=True,
            )

    elif minimo_pessoas is not None:
        candidatos_originais = (
            buscar_fotos_por_minimo_pessoas(
                minimo_pessoas,
                limite=max(
                    quantidade * 12,
                    80,
                ),
            )
        )

        busca_criteria = {
            "mode": "structured_people_filter",
            "min_people_count": (
                minimo_pessoas
            ),
        }

        print(
            f"Fotos com pelo menos "
            f"{minimo_pessoas} pessoas: "
            f"{len(candidatos_originais)}",
            flush=True,
        )

        if not candidatos_originais:
            raise RuntimeError(
                "Não encontrei nenhuma fotografia "
                f"indexada com pelo menos "
                f"{minimo_pessoas} pessoas."
            )

    else:
        limite_busca = max(
            quantidade * 5,
            25,
        )

        busca = buscar_fotos(
            pedido,
            limite=limite_busca,
        )

        candidatos_originais = (
            busca[
                "results"
            ]
        )

        busca_criteria = (
            busca.get(
                "criteria",
                {}
            )
        )

    candidatos_originais = [
        foto
        for foto in candidatos_originais
        if atende_requisitos(
            foto,
            requisitos,
        )
    ]

    candidatos_elegiveis = [
        foto
        for foto in candidatos_originais
        if foto.get(
            "drive_file_id"
        ) not in bloqueadas
    ]

    # =====================================================
    # 2. TRIAGEM VISUAL INTELIGENTE
    # =====================================================

    if criterio_estrito:
        # A busca semântica/estruturada já reduziu centenas de
        # fotos para uma shortlist pequena. A visão agora serve
        # apenas como juiz final, nunca como mecanismo de busca
        # sobre o acervo inteiro.
        candidatos = candidatos_elegiveis[
            :max(
                quantidade,
                8,
            )
        ]

        if not candidatos:
            raise RuntimeError(
                "Não encontrei no índice visual uma fotografia "
                "com aderência suficiente ao critério: "
                f"{criterio_estrito}."
            )

    else:
        candidatos = candidatos_elegiveis[
            :quantidade
        ]

        if not candidatos:
            print(
                "⚠️ Cooldown eliminou todos os candidatos. "
                "Liberando somente o cooldown.",
                flush=True,
            )

            candidatos = [
                foto
                for foto in candidatos_originais
                if (
                    not excluir_drive_file_id
                    or foto.get(
                        "drive_file_id"
                    )
                    != excluir_drive_file_id
                )
            ][
                :quantidade
            ]

    if not candidatos:
        raise RuntimeError(
            "Nenhuma foto candidata encontrada."
        )

    print(
        "Candidatos após filtros:",
        ", ".join(
            (
                f"{foto.get('filename', '?')}"
                f" ({foto.get('people_count', '?')} pessoas)"
            )
            for foto in candidatos
        ),
        flush=True,
    )

    # =====================================================
    # 3. CURADORIA VISUAL FINAL
    # =====================================================

    temporarios = []
    conteudo = []

    instrucao_grupo = ""

    if minimo_pessoas is not None:
        instrucao_grupo = f"""
REQUISITO JÁ VALIDADO:
todas as imagens têm pelo menos {minimo_pessoas} pessoas.
"""

    elif requisitos.get(
        "prefer_group"
    ):
        instrucao_grupo = """
Quando houver qualidade semelhante, prefira sensação de grupo.
"""

    instrucao_criterio = ""

    if criterio_estrito:
        instrucao_criterio = f"""
CRITÉRIO VISUAL PRINCIPAL:

{criterio_estrito}

Você deve verificar VISUALMENTE cada candidata e decidir se
ela realmente atende ao pedido.

REGRAS:
- hard_match=true somente quando a imagem atende de forma
  clara ao núcleo do critério.
- Não transforme um tema específico em algo genérico.
  Ex.: "festa junina" exige sinais visuais compatíveis como
  roupa típica/xadrez/caipira, chapéu de palha, bandeirinhas
  ou decoração temática. "grupo em festa" sozinho NÃO basta.
- Para pedidos quantitativos ("maioria", "quase todas",
  "todas"), estime quantas pessoas realmente atendem.
- EXPRESSÕES COMO "de preto", "de branco", "de amarelo",
  "vestidas de preto" ou equivalentes significam que a COR
  DEVE SER PREDOMINANTE NO LOOK/ROUPA DA PESSOA.
  Não conte como aderente alguém que esteja, por exemplo,
  com camiseta rosa e apenas legging preta, tênis preto ou
  pequenos detalhes pretos. A aparência geral da roupa deve
  ser predominantemente da cor pedida.
- Quando o pedido falar em "maioria das mulheres de preto",
  conte somente mulheres cujo look seja visualmente
  predominantemente preto.
- Se o pedido disser "maioria", mais da metade do grupo deve
  atender visualmente.
- Se disser "quase todas", a proporção deve ser claramente
  alta.
- Se disser "todas", aceite pequena incerteza de oclusão,
  mas não aceite várias pessoas fora do critério.
- Uma foto com 7 de 8 aderentes deve superar uma com 5 de 8,
  quando ambas forem hard_match.
- Os metadados indexados e color_ratio servem apenas como
  sinais de pré-seleção. Na validação final, CONFIE NA IMAGEM.
  Se o índice disser black_ratio alto, mas visualmente as
  pessoas estiverem principalmente de rosa, vermelho, azul
  ou outra cor, marque hard_match=false.
- Qualidade/composição só desempata entre fotos que atendem
  ao pedido.

Se NENHUMA candidata atender, não escolha uma aproximação.
"""

    instrucoes = f"""
Você é o Diretor de Fotografia da SlimFit Studio.

PEDIDO:

{pedido}

Compare visualmente as candidatas e escolha APENAS UMA.

{instrucao_grupo}

{instrucao_criterio}

Prioridades:

1. Aderência visual ao critério do usuário.
2. Proporção de pessoas que atendem ao critério.
3. Quantidade absoluta de pessoas aderentes.
4. Qualidade fotográfica.
5. Boa iluminação.
6. Composição.
7. Aparência natural.
8. Aderência à SlimFit Studio.
9. Compatibilidade com Feed 4:5.

Retorne SOMENTE JSON válido.

Quando houver CRITÉRIO VISUAL PRINCIPAL, use exatamente:

{{
  "results": [
    {{
      "index": 1,
      "hard_match": true,
      "criterion_score": 95,
      "matching_people_estimate": 7,
      "group_people_estimate": 8,
      "reason": "motivo visual objetivo"
    }}
  ],
  "selected_index": 1,
  "reason": "por que esta é a melhor entre as que atendem"
}}

criterion_score vai de 0 a 100.
selected_index começa em 1.
Se nenhuma foto tiver hard_match=true, use selected_index=0.

Quando NÃO houver critério visual explícito, use:

{{
  "selected_index": 1,
  "reason": "motivo objetivo",
  "strengths": [],
  "warnings": []
}}
"""

    conteudo.append({
        "type": "input_text",
        "text": instrucoes,
    })

    try:
        for indice, foto in enumerate(
            candidatos,
            start=1,
        ):
            preview = obter_preview_candidato(
                foto,
                temporarios,
            )

            imagem_b64 = (
                imagem_para_base64(
                    preview
                )
            )

            conteudo.append({
                "type": "input_text",
                "text": (
                    f"FOTO {indice}\n"
                    f"Arquivo: {foto.get('filename', '')}\n"
                    f"Pessoas indexadas: "
                    f"{foto.get('people_count', '')}\n"
                    f"Score de busca inteligente: "
                    f"{foto.get('_smart_score', '')}\n"
                    f"Similaridade semântica: "
                    f"{foto.get('_semantic_similarity', '')}\n"
                    f"Cor objetiva preferida: "
                    f"{foto.get('_preferred_color', '')}\n"
                    f"Proporção estruturada da cor: "
                    f"{foto.get('_structured_color_ratio', '')}\n"
                    f"Proporção mínima estruturada: "
                    f"{foto.get('_required_color_ratio', '')}\n"
                    f"Descrição visual indexada: "
                    f"{foto.get('visual_description', '')}\n"
                    f"Dados visuais indexados: "
                    f"{foto.get('visual_data_json', '')}"
                ),
            })

            conteudo.append({
                "type": "input_image",
                "image_url": (
                    "data:image/jpeg;base64,"
                    + imagem_b64
                ),
            })

        response = (
            client.responses.create(
                model="gpt-5.6-terra",
                reasoning={
                    "effort": "low"
                },
                input=[
                    {
                        "role": "user",
                        "content": conteudo,
                    }
                ],
            )
        )

        resposta = (
            response.output_text
            .strip()
        )

        if resposta.startswith(
            "```json"
        ):
            resposta = resposta[7:]

        if resposta.startswith(
            "```"
        ):
            resposta = resposta[3:]

        if resposta.endswith(
            "```"
        ):
            resposta = resposta[:-3]

        decisao = json.loads(
            resposta.strip()
        )

        avaliacao_escolhida = None

        if criterio_estrito:
            resultados_visuais = []

            for item in decisao.get(
                "results",
                []
            ):
                normalizado = (
                    normalizar_resultado_visual_final(
                        item
                    )
                )

                if (
                    normalizado[
                        "index"
                    ] is not None
                ):
                    resultados_visuais.append(
                        normalizado
                    )

            hard_matches = [
                item
                for item in resultados_visuais
                if item[
                    "hard_match"
                ]
            ]

            print(
                "Validação visual final:",
                ", ".join(
                    (
                        f"#{item['index']} "
                        f"hard={item['hard_match']} "
                        f"score={item['criterion_score']:.0f} "
                        f"ratio={item['matching_ratio']:.2f}"
                    )
                    for item in resultados_visuais
                ),
                flush=True,
            )

            if not hard_matches:
                raise RuntimeError(
                    "Nenhuma das fotos finalistas atende "
                    "visualmente ao critério solicitado: "
                    f"{criterio_estrito}."
                )

            # Não dependemos cegamente de selected_index.
            # Entre hard matches, priorizamos aderência visual,
            # proporção e quantidade de pessoas aderentes.
            hard_matches.sort(
                key=lambda item: (
                    item[
                        "criterion_score"
                    ],
                    item[
                        "matching_ratio"
                    ],
                    item[
                        "matching_people_estimate"
                    ],
                ),
                reverse=True,
            )

            avaliacao_escolhida = (
                hard_matches[
                    0
                ]
            )

            indice = (
                int(
                    avaliacao_escolhida[
                        "index"
                    ]
                )
                - 1
            )

        else:
            indice = (
                int(
                    decisao[
                        "selected_index"
                    ]
                )
                - 1
            )

        if (
            indice < 0
            or indice >= len(
                candidatos
            )
        ):
            raise RuntimeError(
                "Índice selecionado inválido."
            )

        escolhida = candidatos[
            indice
        ]

        if not atende_requisitos(
            escolhida,
            requisitos,
        ):
            raise RuntimeError(
                "A fotografia selecionada não atende "
                "aos requisitos obrigatórios."
            )

        if avaliacao_escolhida:
            escolhida[
                "_visual_match_score"
            ] = avaliacao_escolhida[
                "criterion_score"
            ]

            escolhida[
                "_matching_people_estimate"
            ] = avaliacao_escolhida[
                "matching_people_estimate"
            ]

            escolhida[
                "_group_people_estimate"
            ] = avaliacao_escolhida[
                "group_people_estimate"
            ]

            escolhida[
                "_matching_ratio"
            ] = avaliacao_escolhida[
                "matching_ratio"
            ]

            escolhida[
                "_visual_match_reason"
            ] = avaliacao_escolhida[
                "reason"
            ]

        print(
            "Foto escolhida:",
            escolhida[
                "filename"
            ],
            "| pessoas:",
            escolhida.get(
                "people_count"
            ),
            "| semantic:",
            (
                f"{float(escolhida.get('_semantic_similarity', 0) or 0):.3f}"
            ),
            "| color_ratio:",
            (
                f"{float(escolhida.get('_structured_color_ratio', 0) or 0):.2f}"
            ),
            "| hard_match:",
            bool(
                avaliacao_escolhida
            ),
            "| score visual:",
            escolhida.get(
                "_visual_match_score",
                "",
            ),
            "| aderentes:",
            escolhida.get(
                "_matching_people_estimate",
                "",
            ),
            "/",
            escolhida.get(
                "_group_people_estimate",
                "",
            ),
            flush=True,
        )

        return {
            "selected": escolhida,
            "decision": decisao,
            "candidates": candidatos,
            "criteria": busca_criteria,
            "photo_requirements": requisitos,
            "cooldown": {
                "size": (
                    APPROVED_PHOTO_COOLDOWN
                ),
                "blocked_count": len(
                    bloqueadas_cooldown
                ),
            },
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
