import unicodedata


def normalizar(texto):
    if not texto:
        return ""

    texto = unicodedata.normalize(
        "NFKD",
        texto,
    )

    texto = "".join(
        c
        for c in texto
        if not unicodedata.combining(c)
    )

    return texto.lower()


def contem_algum(
    texto,
    termos,
):
    return any(
        termo in texto
        for termo in termos
    )


def escolher_template(
    foto,
    pedido,
):
    pedido_normalizado = normalizar(
        pedido
    )

    orientation = normalizar(
        foto.get(
            "orientation"
        )
    )

    text_space = normalizar(
        foto.get(
            "text_space"
        )
    )

    people_count = (
        foto.get(
            "people_count"
        )
        or 0
    )

    # =====================================================
    # 1. INTENÇÃO EXPLÍCITA DO USUÁRIO
    # =====================================================
    # Se o usuário pedir um estilo claramente,
    # o pedido tem prioridade sobre os metadados da foto.

    # TEMPLATE B
    # Foto cheia + painel lateral.
    if contem_algum(
        pedido_normalizado,
        [
            "espaco lateral",
            "texto lateral",
            "headline lateral",
            "painel lateral",
            "faixa lateral",
            "composicao lateral",
            "layout lateral",
            "texto na esquerda",
            "texto a esquerda",
            "texto na direita",
            "texto a direita",
            "editorial",
        ],
    ):
        return {
            "template": "B",
            "reason": (
                "Template B forçado pelo pedido: "
                "composição com painel lateral."
            ),
            "mode": "USER_INTENT",
        }

    # TEMPLATE C
    # Foto ocupando quase tudo + conteúdo na base.
    if contem_algum(
        pedido_normalizado,
        [
            "foto ocupando quase toda",
            "foto ocupando toda",
            "foto em tela cheia",
            "foto cheia",
            "imagem cheia",
            "texto concentrado na parte inferior",
            "texto na parte inferior",
            "texto embaixo",
            "texto na base",
            "faixa inferior",
            "rodape",
            "visual",
            "fotografica",
            "fotografico",
        ],
    ):
        return {
            "template": "C",
            "reason": (
                "Template C forçado pelo pedido: "
                "fotografia dominante com conteúdo inferior."
            ),
            "mode": "USER_INTENT",
        }

    # TEMPLATE A
    # Institucional / grupo / composição segura.
    if contem_algum(
        pedido_normalizado,
        [
            "institucional",
            "composicao segura",
            "layout seguro",
            "grupo de alunas",
            "foto de grupo",
            "grupo",
            "classico",
            "tradicional",
        ],
    ):
        return {
            "template": "A",
            "reason": (
                "Template A forçado pelo pedido: "
                "composição institucional e segura."
            ),
            "mode": "USER_INTENT",
        }

    # =====================================================
    # 2. ESCOLHA AUTOMÁTICA
    # =====================================================
    # Só chegamos aqui quando o usuário não determinou
    # claramente o tipo de composição.

    # Espaço lateral detectado na indexação:
    # excelente candidato a Template B.
    if text_space in [
        "esquerda",
        "direita",
    ]:
        return {
            "template": "B",
            "reason": (
                "Template B escolhido automaticamente "
                "porque a foto possui espaço lateral."
            ),
            "mode": "AUTO",
        }

    # Fotos verticais com poucos sujeitos permitem
    # fotografia dominante.
    if (
        orientation == "vertical"
        and people_count <= 4
    ):
        return {
            "template": "C",
            "reason": (
                "Template C escolhido automaticamente "
                "para valorizar uma fotografia vertical."
            ),
            "mode": "AUTO",
        }

    # Espaço inferior ou ausência clara de espaço
    # também favorece faixa inferior.
    if text_space in [
        "inferior",
        "nenhum",
    ]:
        return {
            "template": "C",
            "reason": (
                "Template C escolhido automaticamente "
                "para concentrar a informação na base."
            ),
            "mode": "AUTO",
        }

    # Grupo grande:
    # melhor separar foto e texto.
    if people_count >= 5:
        return {
            "template": "A",
            "reason": (
                "Template A escolhido automaticamente "
                "por se tratar de uma foto com várias pessoas."
            ),
            "mode": "AUTO",
        }

    # =====================================================
    # 3. FALLBACK
    # =====================================================

    return {
        "template": "A",
        "reason": (
            "Template A usado como composição padrão."
        ),
        "mode": "DEFAULT",
    }
