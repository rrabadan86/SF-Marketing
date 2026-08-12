import re
import unicodedata


FAMILY_DYNAMIC = "SLIMFIT_DYNAMIC"
FAMILY_EVENT = "SLIMFIT_EVENT"
FAMILY_SEASONAL = "SLIMFIT_SEASONAL"


VALID_FAMILIES = {
    FAMILY_DYNAMIC,
    FAMILY_EVENT,
    FAMILY_SEASONAL,
}


def normalizar(texto):
    texto = str(
        texto or ""
    ).strip()

    texto = unicodedata.normalize(
        "NFKD",
        texto,
    )

    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(
            caractere
        )
    )

    return texto.lower()


def parece_data_ou_horario(texto):
    padroes = [
        r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b",
        r"\b\d{1,2}:\d{2}\b",
        r"\b\d{1,2}h\d{0,2}\b",
    ]

    return any(
        re.search(
            padrao,
            texto,
            flags=re.IGNORECASE,
        )
        for padrao in padroes
    )


def eh_sazonal(texto):
    termos = [
        "circuito slim",

        "dia das maes",
        "dia da mae",

        "dia das mulheres",
        "dia da mulher",

        "dia mundial da saude",
        "campanha de saude",

        "dia mundial da atividade fisica",
        "atividade fisica",

        "outubro rosa",

        "copa slim",

        "desafio de pascoa",
        "pascoa",
    ]

    return any(
        termo in texto
        for termo in termos
    )


def eh_evento(texto):
    termos = [
        "aulao",
        "evento",
        "encontro",
        "workshop",
        "confraternizacao",
        "comemoracao",
        "celebracao",
        "aniversario",
        "edicao especial",
        "feriado",
    ]

    if any(
        termo in texto
        for termo in termos
    ):
        return True

    # Menções a sábado/domingo só caracterizam EVENT
    # quando também há sinais claros de atividade marcada.
    dias = [
        "sabado",
        "domingo",
    ]

    if (
        any(
            dia in texto
            for dia in dias
        )
        and parece_data_ou_horario(
            texto
        )
    ):
        return True

    return False


def escolher_familia(
    pedido,
    family_override=None,
):
    if (
        family_override
        in VALID_FAMILIES
    ):
        return family_override

    texto = normalizar(
        pedido
    )

    # Campanhas com identidade própria têm prioridade
    # sobre o roteamento genérico de evento.
    if eh_sazonal(
        texto
    ):
        return FAMILY_SEASONAL

    if eh_evento(
        texto
    ):
        return FAMILY_EVENT

    return FAMILY_DYNAMIC
