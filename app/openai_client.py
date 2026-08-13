import os
import re
import json
from openai import OpenAI


API_KEY = os.getenv("OPENAI_API_KEY")

if not API_KEY:
    raise RuntimeError("OPENAI_API_KEY não configurada")

# Timeout evita que uma chamada travada segure o bot indefinidamente;
# max_retries usa o backoff exponencial nativo do SDK para erros
# transitórios (rate limit, conexão, 5xx). Configurável por ambiente.
OPENAI_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT", "60"))
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "4"))

client = OpenAI(
    api_key=API_KEY,
    timeout=OPENAI_TIMEOUT,
    max_retries=OPENAI_MAX_RETRIES,
)

BRAND_RULES_FILE = "/app/data/brand_rules.json"


def extrair_json(texto, default=None):
    """
    Faz o parse de JSON vindo de um modelo de forma tolerante.

    Modelos frequentemente embrulham o JSON em cercas markdown
    (```json ... ```) ou adicionam texto ao redor. Esta função remove a
    cerca, isola o primeiro bloco {...} ou [...] e só então faz o parse.

    Em caso de falha total: se ``default`` foi informado, retorna-o;
    caso contrário levanta ValueError com um trecho do conteúdo, para o
    erro ser diagnosticável em vez de um JSONDecodeError cru.
    """

    if texto is None:
        if default is not None:
            return default
        raise ValueError("Resposta vazia ao tentar extrair JSON.")

    bruto = str(texto).strip()

    # Remove cercas de código ```json ... ``` ou ``` ... ```.
    cerca = re.match(
        r"^```(?:json)?\s*(.*?)\s*```$",
        bruto,
        re.DOTALL | re.IGNORECASE,
    )
    if cerca:
        bruto = cerca.group(1).strip()

    try:
        return json.loads(bruto)
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: isola o primeiro objeto/array balanceado do texto.
    inicio = None
    for i, ch in enumerate(bruto):
        if ch in "{[":
            inicio = i
            break

    if inicio is not None:
        fim_char = "}" if bruto[inicio] == "{" else "]"
        fim = bruto.rfind(fim_char)
        if fim > inicio:
            try:
                return json.loads(bruto[inicio : fim + 1])
            except (json.JSONDecodeError, ValueError):
                pass

    if default is not None:
        return default

    raise ValueError(
        "Não foi possível extrair JSON da resposta do modelo: "
        f"{bruto[:200]!r}"
    )


def carregar_regras_marca():
    if not os.path.exists(BRAND_RULES_FILE):
        return None

    with open(
        BRAND_RULES_FILE,
        "r",
        encoding="utf-8",
    ) as arquivo:
        return json.load(arquivo)


def criar_briefing(pedido):
    regras = carregar_regras_marca()

    if not regras:
        raise RuntimeError(
            "brand_rules.json não encontrado. "
            "Execute a consolidação do manual da marca primeiro."
        )

    regras_json = json.dumps(
        regras,
        ensure_ascii=False,
        indent=2,
    )

    system_prompt = f"""
Você é o Diretor Criativo oficial da marca descrita abaixo.

Sua função é transformar o pedido do usuário em um briefing
para criação de peças publicitárias para Instagram.

==========================
REGRAS OFICIAIS DA MARCA
==========================

{regras_json}

==========================
REGRAS OBRIGATÓRIAS
==========================

1. As regras oficiais da marca têm prioridade sobre qualquer
preferência genérica de design.

2. Nunca invente:
- cores
- fontes
- versões de logo
- preços
- promoções
- condições comerciais
- características da empresa
- serviços
- dados institucionais

3. Quando alguma informação não existir na base oficial
ou no pedido do usuário, não invente.

4. Use apenas cores presentes nas regras da marca.

5. Use apenas tipografias presentes nas regras da marca.

6. Respeite integralmente as regras de uso do logo.

7. Para fotografia:
- siga as preferências definidas no manual;
- respeite as restrições;
- dê preferência futura a fotos reais disponíveis no acervo.

8. Não crie uma identidade visual nova.
Você está trabalhando dentro da identidade SlimFit Studio.

9. Quando o manual determinar o uso de modelos oficiais,
leve isso em consideração na direção visual.

10. Responda sempre em português do Brasil.

==========================
FORMATO DA RESPOSTA
==========================

🎯 OBJETIVO
Explique em uma frase o objetivo da peça.

📐 FORMATO
Sugira Feed 4:5 ou Story 9:16 conforme o pedido.
Se não houver indicação, use Feed 4:5.

💡 CONCEITO CRIATIVO
Explique brevemente a ideia central.

📝 HEADLINE
Crie uma headline curta e coerente com o tom da marca.

💬 TEXTO DE APOIO
Crie um texto secundário curto.

👉 CTA
Crie uma chamada para ação.

📷 FOTO IDEAL
Descreva a fotografia que deve ser buscada no acervo,
seguindo obrigatoriamente as regras fotográficas da marca.

🎨 DIREÇÃO VISUAL
Defina a direção visual usando exclusivamente:
- identidade da marca;
- cores autorizadas;
- tipografia oficial;
- regras de logo;
- regras de layout.

Não invente elementos fora do manual.
"""

    response = client.responses.create(
        model="gpt-5.6-terra",
        reasoning={"effort": "low"},
        instructions=system_prompt,
        input=pedido,
    )

    return response.output_text
