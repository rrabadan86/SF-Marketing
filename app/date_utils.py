"""Utilidades de data/horário — extraídas dos renderizadores (eram
idênticas em seasonal_layout e event_layout)."""

import re


MESES = 'janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro'

def extrair_data(pedido):
    texto = pedido or ''
    padroes = ['\\b\\d{1,2}/\\d{1,2}(?:/\\d{2,4})?\\b', f'\\b\\d{{1,2}}\\s+de\\s+(?:{MESES})\\b']
    for padrao in padroes:
        match = re.search(padrao, texto, flags=re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return ''

def extrair_horario(pedido):
    texto = pedido or ''
    padroes = ['\\b\\d{1,2}:\\d{2}\\b', '\\b\\d{1,2}h\\d{0,2}\\b', '\\b(?:às|as)\\s+\\d{1,2}(?::\\d{2})?\\b']
    for padrao in padroes:
        match = re.search(padrao, texto, flags=re.IGNORECASE)
        if match:
            valor = match.group(0).strip()
            return re.sub('^(às|as)\\s+', '', valor, flags=re.IGNORECASE)
    return ''

def extrair_dia_semana(pedido):
    texto = (pedido or '').lower()
    mapa = [('segunda', 'SEGUNDA'), ('terça', 'TERÇA'), ('terca', 'TERÇA'), ('quarta', 'QUARTA'), ('quinta', 'QUINTA'), ('sexta', 'SEXTA'), ('sábado', 'SÁBADO'), ('sabado', 'SÁBADO'), ('domingo', 'DOMINGO')]
    for termo, saida in mapa:
        if termo in texto:
            return saida
    return ''
