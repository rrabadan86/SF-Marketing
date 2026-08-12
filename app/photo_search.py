import json
import sqlite3
import unicodedata

from openai_client import client


DB_FILE = "/app/data/creative_agent.db"


def normalizar(texto):
    if not texto:
        return ""

    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )

    return texto.lower()


def gerar_criterios_busca(pedido):
    prompt = """
Você é um curador de fotografias para criativos
da marca SlimFit Studio.

Transforme o pedido do usuário em critérios objetivos
para busca dentro de um banco de fotografias já catalogadas.

Retorne SOMENTE JSON válido:

{
  "search_terms": [],
  "preferred_orientation": null,
  "preferred_text_space": [],
  "minimum_people": null,
  "maximum_people": null
}

Regras:

- search_terms deve conter de 4 a 10 termos curtos em português.
- Use termos visualmente pesquisáveis.
- Não inclua conceitos abstratos que não possam ser vistos.
- Exemplos bons:
  "mulheres", "treino", "halteres", "grupo",
  "professora", "sorrindo", "equipamentos".
- preferred_orientation:
  "vertical", "horizontal", "quadrada" ou null.
- preferred_text_space pode conter:
  "superior", "inferior", "esquerda",
  "direita", "centro", "nenhum".
- Não invente informações comerciais.
"""

    response = client.responses.create(
        model="gpt-5.6-terra",
        reasoning={"effort": "low"},
        instructions=prompt,
        input=pedido,
    )

    resposta = response.output_text.strip()

    if resposta.startswith("```json"):
        resposta = resposta[7:]

    if resposta.startswith("```"):
        resposta = resposta[3:]

    if resposta.endswith("```"):
        resposta = resposta[:-3]

    return json.loads(resposta.strip())


def buscar_fotos(pedido, limite=8):
    criterios = gerar_criterios_busca(pedido)

    termos = [
        normalizar(t)
        for t in criterios.get("search_terms", [])
        if t
    ]

    orientacao = criterios.get("preferred_orientation")
    espacos = criterios.get("preferred_text_space", [])
    minimo_pessoas = criterios.get("minimum_people")
    maximo_pessoas = criterios.get("maximum_people")

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row

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
        WHERE indexed = 1
    """).fetchall()

    conn.close()

    resultados = []

    for row in rows:
        descricao = normalizar(row["description"])
        tags = normalizar(row["tags"])

        texto_pesquisa = f"{descricao} {tags}"

        score = 0.0
        matches = []

        score += float(row["brand_fit_score"] or 0) * 2.0
        score += float(row["quality_score"] or 0) * 1.5

        for termo in termos:
            if termo in texto_pesquisa:
                score += 5.0
                matches.append(termo)

        if orientacao and row["orientation"] == orientacao:
            score += 3.0

        if espacos and row["text_space"] in espacos:
            score += 2.0

        pessoas = row["people_count"]

        if pessoas is not None:
            if minimo_pessoas is not None and pessoas < minimo_pessoas:
                score -= 5.0

            if maximo_pessoas is not None and pessoas > maximo_pessoas:
                score -= 5.0

        if termos and not matches:
            score -= 8.0

        resultados.append({
            "drive_file_id": row["drive_file_id"],
            "filename": row["filename"],
            "folder": row["folder"],
            "description": row["description"],
            "orientation": row["orientation"],
            "people_count": row["people_count"],
            "text_space": row["text_space"],
            "quality_score": row["quality_score"],
            "brand_fit_score": row["brand_fit_score"],
            "matches": matches,
            "score": round(score, 2),
        })

    resultados.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    return {
        "criteria": criterios,
        "results": resultados[:limite],
    }
