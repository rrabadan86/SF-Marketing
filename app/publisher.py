import os
import tempfile

from datetime import datetime

from PIL import Image

from finalizer import (
    ajustar_para_instagram_4x5,
    aplicar_nitidez,
)

from logo_manager import (
    escolher_posicao_logo,
    baixar_logo_por_tipo,
    aplicar_logo,
)

from drive_client import (
    localizar_pasta_gerados,
    upload_arquivo,
)


# =========================================================
# FORMATOS DE SAÍDA
# =========================================================

FEED_SIZE = (
    1080,
    1350,
)

STORY_SIZE = (
    1080,
    1920,
)


# =========================================================
# REGRA DE MARCA POR COMPOSIÇÃO
# =========================================================

def decidir_logo(
    caminho_base,
    family=None,
    layout=None,
):
    """
    Algumas composições possuem área de marca
    planejada estruturalmente.

    Nesses casos a regra explícita tem prioridade
    sobre a análise automática de luminância.

    Nos demais criativos, preservamos integralmente
    o comportamento automático anterior.
    """

    # -----------------------------------------------------
    # SLIMFIT SEASONAL / PHOTO
    # -----------------------------------------------------
    #
    # O layout possui cartão claro inferior destinado
    # exclusivamente à copy.
    #
    # Portanto a marca não deve disputar espaço com
    # headline, apoio ou CTA.
    #
    # A fotografia ocupa o topo e oferece a zona
    # planejada para a assinatura SlimFit.
    # -----------------------------------------------------

    if (
        family
        == "SLIMFIT_SEASONAL"
        and layout
        == "SEASONAL_PHOTO"
    ):
        return {
            "posicao": (
                "superior_direito"
            ),

            "tipo_logo": (
                "branca"
            ),

            "diagnostico": [
                {
                    "posicao": (
                        "superior_direito"
                    ),

                    "tipo_logo": (
                        "branca"
                    ),

                    "score": 999,

                    "motivo": (
                        "Regra estrutural "
                        "SEASONAL_PHOTO"
                    ),
                }
            ],

            "mode": (
                "LAYOUT_OVERRIDE"
            ),
        }

    # -----------------------------------------------------
    # DEMAIS LAYOUTS
    # -----------------------------------------------------

    decisao = (
        escolher_posicao_logo(
            caminho_base
        )
    )

    decisao[
        "mode"
    ] = "AUTO"

    return decisao


# =========================================================
# DETECÇÃO DE FORMATO
# =========================================================

def detectar_formato(
    caminho_imagem,
):
    """
    Identifica se a imagem recebida pelo publisher já é
    um Story 9:16 ou se deve seguir pelo fluxo Feed 4:5.

    O Story gerado pelo renderer é 1080x1920.
    Também aceitamos uma pequena tolerância de proporção
    para não destruir um Story válido por arredondamento.
    """

    with Image.open(
        caminho_imagem
    ) as imagem:
        largura, altura = (
            imagem.size
        )

    if (
        largura <= 0
        or altura <= 0
    ):
        raise RuntimeError(
            "Dimensões inválidas na imagem "
            "recebida pelo publisher."
        )

    proporcao = (
        largura
        / altura
    )

    proporcao_story = (
        9
        / 16
    )

    tolerancia_story = 0.015

    eh_story = (
        (
            largura,
            altura,
        )
        == STORY_SIZE
        or abs(
            proporcao
            - proporcao_story
        )
        <= tolerancia_story
    )

    if eh_story:
        return {
            "format": "STORY",
            "width": largura,
            "height": altura,
        }

    return {
        "format": "FEED",
        "width": largura,
        "height": altura,
    }


# =========================================================
# PREPARAÇÃO DO CANVAS
# =========================================================

def preparar_canvas_publicacao(
    caminho_bruto,
):
    """
    FEED:
        mantém o comportamento histórico:
        normaliza para 1080x1350 usando finalizer.

    STORY:
        NÃO passa pelo ajustar_para_instagram_4x5.
        Apenas converte para JPEG preservando integralmente
        o canvas 1080x1920.
    """

    formato = detectar_formato(
        caminho_bruto
    )

    temp_base = (
        tempfile.NamedTemporaryFile(
            suffix=".jpg",
            delete=False,
        )
    )

    caminho_base = (
        temp_base.name
    )

    temp_base.close()

    if (
        formato[
            "format"
        ]
        == "STORY"
    ):
        print(
            "Publisher:",
            "Story detectado",
            f"{formato['width']}x"
            f"{formato['height']}",
            "- preservando formato 9:16",
            flush=True,
        )

        with Image.open(
            caminho_bruto
        ) as imagem:
            imagem = (
                imagem
                .convert(
                    "RGB"
                )
            )

            # O renderer oficial já entrega 1080x1920.
            # Caso chegue outro Story 9:16, normalizamos
            # somente para o tamanho oficial, sem virar 4:5.
            if (
                imagem.size
                != STORY_SIZE
            ):
                imagem = imagem.resize(
                    STORY_SIZE,
                    Image.Resampling.LANCZOS,
                )

            imagem = aplicar_nitidez(
                imagem
            )

            imagem.save(
                caminho_base,
                "JPEG",
                quality=95,
                subsampling=0,
            )

        return {
            "image_path": (
                caminho_base
            ),
            "format": (
                "STORY"
            ),
            "width": (
                STORY_SIZE[0]
            ),
            "height": (
                STORY_SIZE[1]
            ),
        }

    print(
        "Publisher:",
        "Feed detectado",
        f"{formato['width']}x"
        f"{formato['height']}",
        "- ajustando para 1080x1350",
        flush=True,
    )

    ajustar_para_instagram_4x5(
        caminho_bruto,
        caminho_base,
    )

    return {
        "image_path": (
            caminho_base
        ),
        "format": (
            "FEED"
        ),
        "width": (
            FEED_SIZE[0]
        ),
        "height": (
            FEED_SIZE[1]
        ),
    }


# =========================================================
# FINALIZAÇÃO E PUBLICAÇÃO
# =========================================================

def finalizar_e_publicar(
    caminho_bruto,
    family=None,
    layout=None,
):
    temporarios = []

    try:
        # ==========================================
        # 1. PREPARAÇÃO DO FORMATO
        # ==========================================

        base = (
            preparar_canvas_publicacao(
                caminho_bruto
            )
        )

        caminho_base = (
            base[
                "image_path"
            ]
        )

        temporarios.append(
            caminho_base
        )

        # ==========================================
        # 2. DECISÃO DA LOGO
        # ==========================================

        decisao_logo = decidir_logo(
            caminho_base,
            family=family,
            layout=layout,
        )

        posicao = (
            decisao_logo[
                "posicao"
            ]
        )

        tipo_logo = (
            decisao_logo[
                "tipo_logo"
            ]
        )

        print(
            "Decisão de logo:",
            f"family={family}",
            f"layout={layout}",
            f"tipo={tipo_logo}",
            f"posição={posicao}",
            f"modo={decisao_logo.get('mode')}",
            f"formato={base['format']}",
            flush=True,
        )

        # ==========================================
        # 3. DOWNLOAD DA LOGO
        # ==========================================

        (
            caminho_logo,
            logo,
            tipo_real,
            cor_logo,
        ) = baixar_logo_por_tipo(
            tipo_logo
        )

        temporarios.append(
            caminho_logo
        )

        # ==========================================
        # 4. APLICAÇÃO DA LOGO
        # ==========================================

        temp_final = (
            tempfile.NamedTemporaryFile(
                suffix=".jpg",
                delete=False,
            )
        )

        caminho_final = (
            temp_final.name
        )

        temp_final.close()

        aplicar_logo(
            caminho_base,
            caminho_logo,
            caminho_final,
            posicao,
        )

        # ==========================================
        # 5. VALIDAÇÃO FINAL DE DIMENSÃO
        # ==========================================

        with Image.open(
            caminho_final
        ) as imagem_final:
            largura_final, altura_final = (
                imagem_final.size
            )

        esperado = (
            STORY_SIZE
            if base[
                "format"
            ]
            == "STORY"
            else FEED_SIZE
        )

        if (
            largura_final,
            altura_final,
        ) != esperado:
            raise RuntimeError(
                "Publisher alterou indevidamente "
                "as dimensões finais. "
                f"Esperado: {esperado[0]}x"
                f"{esperado[1]} | "
                f"Obtido: {largura_final}x"
                f"{altura_final}"
            )

        print(
            "Publisher final:",
            base[
                "format"
            ],
            f"{largura_final}x"
            f"{altura_final}",
            flush=True,
        )

        # ==========================================
        # 6. NOME FINAL
        # ==========================================

        agora = (
            datetime.now()
            .strftime(
                "%Y%m%d_%H%M%S"
            )
        )

        sufixo_formato = (
            "story"
            if base[
                "format"
            ]
            == "STORY"
            else "feed"
        )

        nome_final = (
            f"criativo_{sufixo_formato}_"
            f"{agora}.jpg"
        )

        # ==========================================
        # 7. UPLOAD DRIVE
        # ==========================================

        pasta = (
            localizar_pasta_gerados()
        )

        arquivo_drive = (
            upload_arquivo(
                caminho_final,
                nome_final,
                pasta[
                    "id"
                ],
                mime_type="image/jpeg",
            )
        )

        return {
            "image_path": (
                caminho_final
            ),

            "drive_file": (
                arquivo_drive
            ),

            "logo_name": (
                logo[
                    "name"
                ]
            ),

            "logo_type": (
                tipo_real
            ),

            "logo_position": (
                posicao
            ),

            "logo_color": (
                cor_logo
            ),

            "logo_diagnostic": (
                decisao_logo[
                    "diagnostico"
                ]
            ),

            "logo_decision_mode": (
                decisao_logo.get(
                    "mode",
                    "AUTO",
                )
            ),

            "filename": (
                nome_final
            ),

            "format": (
                base[
                    "format"
                ]
            ),

            "width": (
                largura_final
            ),

            "height": (
                altura_final
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
