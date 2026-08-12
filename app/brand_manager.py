import os
import json
import tempfile

from pypdf import PdfReader

from drive_client import (
    ROOT_FOLDER_ID,
    listar_pasta,
    localizar_subpasta,
    baixar_arquivo,
)

from openai_client import client


DATA_DIR = "/app/data"

BRAND_RULES_FILE = os.path.join(
    DATA_DIR,
    "brand_rules.json",
)


def extrair_texto_pdf(caminho):
    reader = PdfReader(caminho)

    textos = []

    for pagina in reader.pages:
        texto = pagina.extract_text()

        if texto:
            textos.append(texto)

    return "\n\n".join(textos)


def carregar_documentos_marca():
    pasta = localizar_subpasta(
        ROOT_FOLDER_ID,
        "00_MANUAL_MARCA",
    )

    if not pasta:
        raise RuntimeError(
            "Pasta 00_MANUAL_MARCA não encontrada."
        )

    arquivos = listar_pasta(pasta["id"])

    documentos = []

    for arquivo in arquivos:

        mime_type = arquivo["mimeType"]

        if mime_type != "application/pdf":
            print(
                f"Ignorando temporariamente: {arquivo['name']} "
                f"({mime_type})",
                flush=True,
            )
            continue

        with tempfile.NamedTemporaryFile(
            suffix=".pdf",
            delete=False,
        ) as temp:
            caminho = temp.name

        try:
            baixar_arquivo(
                arquivo["id"],
                caminho,
            )

            texto = extrair_texto_pdf(caminho)

            documentos.append({
                "nome": arquivo["name"],
                "texto": texto,
            })

        finally:
            if os.path.exists(caminho):
                os.remove(caminho)

    return documentos


def gerar_brand_rules():
    documentos = carregar_documentos_marca()

    if not documentos:
        raise RuntimeError(
            "Nenhum PDF encontrado em 00_MANUAL_MARCA."
        )

    conteudo = ""

    for documento in documentos:
        conteudo += (
            "\n\n==============================\n"
            f"ARQUIVO: {documento['nome']}\n"
            "==============================\n\n"
            f"{documento['texto']}"
        )

    prompt = """
Você é responsável por consolidar os manuais oficiais
de identidade de uma marca.

Leia TODO o conteúdo fornecido e gere um único conjunto
de regras estruturadas para um agente de criação de
peças publicitárias.

NÃO invente informações.

Se determinada informação não existir nos documentos,
use null ou uma lista vazia.

Se houver regras explícitas sobre:

- identidade da marca
- propósito
- posicionamento
- público
- personalidade
- tom de voz
- cores
- tipografias
- uso de logo
- área de proteção
- fotografia
- composição
- elementos gráficos
- aplicações permitidas
- aplicações proibidas
- exemplos
- restrições

registre essas informações.

Retorne SOMENTE JSON válido.

Use esta estrutura:

{
  "brand_name": null,

  "identity": {
    "purpose": null,
    "positioning": null,
    "personality": [],
    "tone_of_voice": []
  },

  "audience": [],

  "colors": {
    "primary": [],
    "secondary": [],
    "support": []
  },

  "typography": {
    "primary": null,
    "secondary": null,
    "rules": []
  },

  "logo": {
    "rules": [],
    "clear_space": null,
    "minimum_size": null,
    "allowed_versions": [],
    "prohibited_uses": []
  },

  "photography": {
    "preferred": [],
    "avoid": []
  },

  "layout": {
    "rules": [],
    "preferred": [],
    "avoid": []
  },

  "graphic_elements": {
    "allowed": [],
    "rules": []
  },

  "copywriting": {
    "rules": [],
    "preferred_words": [],
    "avoid_words": []
  },

  "mandatory_rules": [],

  "prohibited_rules": [],

  "source_files": []
}
"""

    response = client.responses.create(
        model="gpt-5.6-terra",
        reasoning={"effort": "medium"},
        instructions=prompt,
        input=conteudo,
    )

    resposta = response.output_text.strip()

    if resposta.startswith("```json"):
        resposta = resposta[7:]

    if resposta.startswith("```"):
        resposta = resposta[3:]

    if resposta.endswith("```"):
        resposta = resposta[:-3]

    resposta = resposta.strip()

    regras = json.loads(resposta)

    regras["source_files"] = [
        documento["nome"]
        for documento in documentos
    ]

    os.makedirs(
        DATA_DIR,
        exist_ok=True,
    )

    with open(
        BRAND_RULES_FILE,
        "w",
        encoding="utf-8",
    ) as arquivo:
        json.dump(
            regras,
            arquivo,
            ensure_ascii=False,
            indent=2,
        )

    return regras
