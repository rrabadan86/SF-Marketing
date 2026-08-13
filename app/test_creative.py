"""
Testes de regressão do Creative Agent — protegem enquadramento, zoom,
detecção de rosto, tratamento de foto, temas e composições do Dynamic.

Rode com:
    cd app && python -m pytest test_creative.py -q
    # ou, sem pytest:
    cd app && python test_creative.py

Não faz rede nem usa o Drive/IA — só a renderização local.
"""

import os
import tempfile

from PIL import Image

import face_framing
import photo_style
import dynamic_layout as dl
import date_utils
from seasonal_layout import ajustar_foto_na_moldura


# ---------------------------------------------------------------
# Fotos sintéticas
# ---------------------------------------------------------------

def _foto(w, h, cor=(150, 140, 130)):
    img = Image.new("RGB", (w, h), cor)
    # um gradiente simples para o zoom mudar o conteúdo de forma detectável
    for y in range(0, h, 4):
        for x in range(0, w, 4):
            img.putpixel((x, y), ((x + y) % 256, y % 256, x % 256))
    return img


def _foto_arquivo(w=1200, h=1600):
    img = _foto(w, h)
    caminho = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False).name
    img.save(caminho, "JPEG", quality=90)
    return caminho


COPY = {
    "headline": "Sua evolução começa aqui.",
    "support": "No SlimFit, cada treino conta para a sua melhor versão.",
    "cta": "Agende sua aula.",
}


# ---------------------------------------------------------------
# face_framing
# ---------------------------------------------------------------

def test_face_cascade_disponivel():
    # O cascade embutido deve carregar (senão a detecção nunca funciona).
    assert face_framing._DISPONIVEL is True


def test_face_sem_rosto_retorna_default():
    liso = Image.new("RGB", (1000, 1000), (180, 180, 180))
    assert face_framing.detectar_foco_rosto(liso, default=(0.5, 0.4)) == (0.5, 0.4)


def test_face_nunca_levanta():
    # Entrada inválida não pode quebrar a renderização.
    assert face_framing.detectar_foco_rosto(None, default=(0.5, 0.4)) == (0.5, 0.4)


# ---------------------------------------------------------------
# photo_style
# ---------------------------------------------------------------

def test_tratar_foto_preserva_dimensoes_e_modo():
    img = _foto(400, 500)
    out = photo_style.tratar_foto(img)
    assert out.size == (400, 500)
    assert out.mode == "RGB"


# ---------------------------------------------------------------
# ajustar_foto_na_moldura (motor de zoom)
# ---------------------------------------------------------------

def test_zoom_in_reduz_janela():
    _, base = ajustar_foto_na_moldura(_foto(2000, 2000), 1080, 1350, scale=1.0)
    _, zin = ajustar_foto_na_moldura(_foto(2000, 2000), 1080, 1350, scale=1.2)
    assert zin["janela"][0] < base["janela"][0]


def test_saida_sempre_no_tamanho_da_moldura():
    for s in (0.85, 1.0, 1.2):
        foto, _ = ajustar_foto_na_moldura(_foto(1200, 1600), 1080, 1350, scale=s)
        assert foto.size == (1080, 1350)


# ---------------------------------------------------------------
# Dynamic — detecção de tema e composição
# ---------------------------------------------------------------

def test_detectar_tema_wave():
    assert dl.detectar_tema_wave("post normal") == "coral"
    assert dl.detectar_tema_wave("post com fundo escuro") == "escuro"
    assert dl.detectar_tema_wave("versão tiffany") == "tiffany"


def test_detectar_composicao():
    assert dl.detectar_composicao("post normal") == "DYNAMIC_WAVE"
    assert dl.detectar_composicao("estilo foto em destaque") == "DYNAMIC_BOLD"
    assert dl.detectar_composicao("post dividido, bloco de cor") == "DYNAMIC_SPLIT"


# ---------------------------------------------------------------
# Dynamic — crop_foto honra zoom
# ---------------------------------------------------------------

def test_crop_foto_honra_zoom():
    caminho = _foto_arquivo()
    neutro = dl.crop_foto(caminho, {"photo_zoom": 1.0})
    zin = dl.crop_foto(caminho, {"photo_zoom": 1.3})
    assert neutro.size == (dl.WIDTH, dl.HEIGHT)
    assert zin.size == (dl.WIDTH, dl.HEIGHT)
    # zoom-in deve mudar os pixels (aproximou)
    assert list(neutro.getdata()) != list(zin.getdata())


# ---------------------------------------------------------------
# Dynamic — renderiza cada composição sem erro, no tamanho certo
# ---------------------------------------------------------------

def test_render_composicoes():
    caminho = _foto_arquivo()
    for pedido, esperado in [
        ("post normal", "DYNAMIC_WAVE"),
        ("estilo foto em destaque", "DYNAMIC_BOLD"),
        ("post dividido bloco de cor", "DYNAMIC_SPLIT"),
    ]:
        r = dl.render_dynamic(caminho, COPY, pedido, foto={})
        assert r["composition"] == esperado
        img = Image.open(r["image_path"])
        assert img.size == (dl.WIDTH, dl.HEIGHT)


def test_render_wave_temas():
    caminho = _foto_arquivo()
    for tema in ("coral", "tiffany", "escuro"):
        canvas = dl.render_wave(
            caminho, COPY, f"post fundo {tema}",
            render_overrides={"wave_theme": tema},
        )
        assert canvas.size == (dl.WIDTH, dl.HEIGHT)


# ---------------------------------------------------------------
# Dynamic — aviso de zoom-out no limite geométrico
# ---------------------------------------------------------------

def test_zoom_out_limitado_avisa_em_foto_horizontal():
    # Foto horizontal numa moldura vertical: "menos zoom" bate no limite.
    caminho = _foto_arquivo(3024, 2016)
    neutro = dl.render_dynamic(caminho, COPY, "post normal", foto={},
                               render_overrides={"photo_zoom": 1.0})
    afasta = dl.render_dynamic(caminho, COPY, "post normal", foto={},
                               render_overrides={"photo_zoom": 0.92})
    aproxima = dl.render_dynamic(caminho, COPY, "post normal", foto={},
                                 render_overrides={"photo_zoom": 1.22})
    assert not neutro.get("photo_note")
    assert afasta.get("photo_note")  # avisou que não dá para afastar mais
    assert not aproxima.get("photo_note")


# ---------------------------------------------------------------
# Destaque de trecho (negrito + sublinhado inline)
# ---------------------------------------------------------------

def test_marcadores_nunca_vazam_no_texto():
    import adaptive_layout as al
    assert al.limpar_marcadores("a **b c** d") == "a b c d"
    # segmentar preserva ordem e marca a ênfase
    segs = al.segmentar_enfase("a **b** c")
    assert segs == [("a ", False), ("b", True), (" c", False)]


def test_render_com_destaque_nao_quebra_e_sem_asteriscos():
    caminho = _foto_arquivo()
    copy = {
        "headline": "Circuito Slim",
        "support": "Venha no **sábado às 9h45**. Vagas abertas!",
        "cta": "Check-in aberto!",
    }
    r = dl.render_dynamic(caminho, copy, "post normal", foto={})
    img = Image.open(r["image_path"])
    assert img.size == (dl.WIDTH, dl.HEIGHT)


# ---------------------------------------------------------------
# date_utils
# ---------------------------------------------------------------

def test_extrair_data():
    assert date_utils.extrair_data("evento 16/08 legal") == "16/08"
    assert not date_utils.extrair_data("sem data aqui")


def test_extrair_horario():
    assert date_utils.extrair_horario("comeca as 9h") == "9h"
    assert not date_utils.extrair_horario("sem hora")


def test_extrair_dia_semana():
    assert date_utils.extrair_dia_semana("no sabado") == "SÁBADO"
    assert not date_utils.extrair_dia_semana("qualquer dia")


if __name__ == "__main__":
    import sys

    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    falhas = 0
    for t in testes:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            falhas += 1
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:
            falhas += 1
            print(f"ERRO {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(testes) - falhas}/{len(testes)} passaram")
    sys.exit(1 if falhas else 0)
