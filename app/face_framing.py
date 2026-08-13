"""
Enquadramento com detecção de rosto.

Descobre onde estão os rostos na fotografia e devolve um ponto de foco
(focus_x, focus_y) normalizado (0..1) para usar no ``ImageOps.fit`` dos
renderizadores. Objetivo: centralizar horizontalmente no(s) rosto(s) e
proteger a cabeça (foco um pouco acima), corrigindo os dois problemas
relatados — foto mal centralizada e cabeça cortada.

TOTALMENTE tolerante a falha: se o OpenCV não estiver instalado, o
cascade não carregar, ou nenhum rosto for encontrado, retorna ``None`` e o
chamador mantém o enquadramento padrão. Nunca levanta exceção.
"""

import os


_CASCADE_PATH = os.path.join(
    os.path.dirname(__file__),
    "assets",
    "haarcascade_frontalface_default.xml",
)

_cascade = None
_DISPONIVEL = False

try:
    import cv2
    import numpy as np

    if os.path.exists(_CASCADE_PATH):
        _cascade = cv2.CascadeClassifier(_CASCADE_PATH)
        _DISPONIVEL = not _cascade.empty()
except Exception as erro:  # pragma: no cover
    print(
        "face_framing indisponível "
        f"({type(erro).__name__}: {erro}); usando enquadramento padrão.",
        flush=True,
    )
    _DISPONIVEL = False


def detectar_foco_rosto(
    pil_img,
    default=None,
    fy_padrao=0.32,
):
    """
    Retorna (focus_x, focus_y) centrado nos rostos, com a cabeça
    protegida (foco acima do centro dos rostos). Retorna ``default`` se a
    detecção não estiver disponível ou não houver rosto.

    focus_y é puxado para o topo do rosto mais alto, para o crop preservar
    a cabeça em vez de cortá-la.
    """

    if not _DISPONIVEL:
        return default

    try:
        img = pil_img.convert("RGB")
        largura, altura = img.size

        if largura <= 0 or altura <= 0:
            return default

        # Reduz para detecção mais rápida sem perder precisão relevante.
        escala = (
            720.0 / max(largura, altura)
            if max(largura, altura) > 720
            else 1.0
        )
        peq = img.resize(
            (
                max(1, int(largura * escala)),
                max(1, int(altura * escala)),
            )
        )

        arr = np.array(peq)[:, :, ::-1].copy()  # RGB -> BGR
        cinza = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)

        rostos = _cascade.detectMultiScale(
            cinza,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(24, 24),
        )

        if len(rostos) == 0:
            return default

        pw, ph = peq.size

        xs = [x for (x, y, w, h) in rostos]
        xe = [x + w for (x, y, w, h) in rostos]
        ys = [y for (x, y, w, h) in rostos]
        alturas = [h for (x, y, w, h) in rostos]

        centro_x = (min(xs) + max(xe)) / 2.0
        topo_rostos = min(ys)
        altura_rosto = max(alturas)

        focus_x = centro_x / pw

        # Empurra o foco para um pouco ACIMA do topo do rosto mais alto,
        # dando folga para a cabeça inteira (incl. testa/cabelo).
        alvo_y = topo_rostos - altura_rosto * 0.35
        focus_y = alvo_y / ph

        focus_x = float(min(1.0, max(0.0, focus_x)))
        focus_y = float(min(1.0, max(0.0, focus_y)))

        return (focus_x, focus_y)

    except Exception as erro:  # pragma: no cover
        print(
            "face_framing: falha na detecção "
            f"({type(erro).__name__}: {erro}); usando padrão.",
            flush=True,
        )
        return default
