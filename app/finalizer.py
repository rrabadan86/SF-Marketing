from PIL import Image, ImageFilter


def aplicar_nitidez(imagem):
    """
    Realce sutil de nitidez (unsharp mask) para compensar o amaciamento
    natural do redimensionamento LANCZOS. O threshold evita realçar ruído
    em áreas lisas (fundos chapados da identidade), agindo principalmente
    nas bordas da fotografia e do texto.
    """
    return imagem.filter(
        ImageFilter.UnsharpMask(
            radius=1.5,
            percent=65,
            threshold=3,
        )
    )


def ajustar_para_instagram_4x5(
    caminho_entrada,
    caminho_saida,
    largura_final=1080,
    altura_final=1350,
):
    imagem = Image.open(caminho_entrada).convert("RGB")

    largura, altura = imagem.size

    proporcao_origem = largura / altura
    proporcao_destino = largura_final / altura_final

    if proporcao_origem > proporcao_destino:
        nova_altura = altura_final
        nova_largura = int(nova_altura * proporcao_origem)
    else:
        nova_largura = largura_final
        nova_altura = int(nova_largura / proporcao_origem)

    imagem = imagem.resize(
        (nova_largura, nova_altura),
        Image.LANCZOS,
    )

    esquerda = max(0, (nova_largura - largura_final) // 2)
    topo = max(0, (nova_altura - altura_final) // 2)

    imagem = imagem.crop(
        (
            esquerda,
            topo,
            esquerda + largura_final,
            topo + altura_final,
        )
    )

    imagem = aplicar_nitidez(imagem)

    imagem.save(
        caminho_saida,
        "JPEG",
        quality=95,
        subsampling=0,
        optimize=True,
    )

    return caminho_saida
