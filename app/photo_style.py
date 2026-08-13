"""
Tratamento de foto padronizado — coesão visual de marca.

As fotos do acervo vêm de fontes e câmeras diferentes (temperaturas de cor
e contrastes variados). Um realce leve e uniforme faz todas "pertencerem à
mesma marca", sem filtro pesado. Aplicado no ponto de carregamento de cada
renderizador.

Totalmente tolerante a falha: qualquer erro devolve a imagem original.
"""

from PIL import Image, ImageEnhance


def tratar_foto(img):
    try:
        img = img.convert("RGB")

        # Realce sutil e consistente.
        img = ImageEnhance.Contrast(img).enhance(1.06)
        img = ImageEnhance.Color(img).enhance(1.05)
        img = ImageEnhance.Brightness(img).enhance(1.01)

        # Toque de calor (acolhimento): R levemente acima, B levemente
        # abaixo. Mantém a pele natural e alinha com o tom da marca.
        r, g, b = img.split()
        r = r.point(lambda v: min(255, int(v * 1.03)))
        b = b.point(lambda v: int(v * 0.985))
        return Image.merge("RGB", (r, g, b))

    except Exception:
        return img
