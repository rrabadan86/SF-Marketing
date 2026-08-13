"""
Testes de enquadramento de foto (ajustar_foto_na_moldura).

Cobrem o comportamento de zoom in / zoom out que antes só era
verificável rodando o bot no Telegram. Rode com:

    cd app && python -m pytest test_photo_framing.py -q
    # ou, sem pytest:
    cd app && python test_photo_framing.py
"""

from PIL import Image

from seasonal_layout import ajustar_foto_na_moldura


ALVO_W = 916
ALVO_H = 545  # moldura horizontal do SEASONAL_PROMO


def _foto(w, h):
    """Foto sintética com um marcador escuro no topo (a 'cabeça')."""
    img = Image.new("RGB", (w, h), (200, 200, 200))
    for y in range(int(h * 0.12)):
        for x in range(w):
            img.putpixel((x, y), (10, 10, 10))
    return img


def test_saida_sempre_no_tamanho_da_moldura():
    for scale in (0.82, 0.9, 1.0, 1.1, 1.2):
        foto, _ = ajustar_foto_na_moldura(
            _foto(1200, 1600), ALVO_W, ALVO_H, scale=scale
        )
        assert foto.size == (ALVO_W, ALVO_H)


def test_cover_padrao_preenche_moldura():
    _, info = ajustar_foto_na_moldura(_foto(1200, 1600), ALVO_W, ALVO_H, scale=1.0)
    assert info["modo"] == "COVER"
    assert info["zoom_out_limitado"] is False


def test_zoom_in_amostra_janela_menor():
    """scale > 1 deve amostrar uma janela MENOR da origem (pessoa maior)."""
    _, base = ajustar_foto_na_moldura(_foto(1600, 1600), ALVO_W, ALVO_H, scale=1.0)
    _, zoom = ajustar_foto_na_moldura(_foto(1600, 1600), ALVO_W, ALVO_H, scale=1.2)
    assert zoom["janela"][0] < base["janela"][0]
    assert zoom["janela"][1] < base["janela"][1]


def test_zoom_monotonico():
    """Mais zoom => janela estritamente menor em cada passo."""
    larguras = []
    for scale in (0.9, 1.0, 1.1, 1.2):
        _, info = ajustar_foto_na_moldura(_foto(2000, 2000), ALVO_W, ALVO_H, scale=scale)
        larguras.append(info["janela"][0])
    assert larguras == sorted(larguras, reverse=True)


def test_zoom_out_a_partir_de_um_crop_ja_aproximado():
    """
    Verdade geométrica: o 'cover' já usa a extensão total da origem na
    dimensão de aperto, então NÃO existe afastamento abaixo do cover
    preenchendo a moldura. O afastamento real só faz sentido quando o
    ponto de partida está aproximado (scale > 1): reduzir a escala então
    devolve a janela ao tamanho do cover. Este teste garante que ir de
    1.15 -> 1.0 amplia a janela amostrada (afasta de verdade).
    """
    _, aproximado = ajustar_foto_na_moldura(_foto(2000, 2000), ALVO_W, ALVO_H, scale=1.15)
    _, afastado = ajustar_foto_na_moldura(_foto(2000, 2000), ALVO_W, ALVO_H, scale=1.0)
    assert afastado["janela"][0] > aproximado["janela"][0]
    assert afastado["janela"][1] > aproximado["janela"][1]


def test_retrato_em_moldura_horizontal_limita_zoom_out_sem_montagem():
    """
    O caso do bug: retrato 1200x1600 já é mostrado em largura cheia numa
    moldura horizontal. Afastar mais é geometricamente impossível sem
    letterbox, então o resultado é limitado ao cover (preenche a moldura
    inteira) em vez de virar uma tira flutuante sobre blur.
    """
    foto, info = ajustar_foto_na_moldura(_foto(1200, 1600), ALVO_W, ALVO_H, scale=0.82)
    assert foto.size == (ALVO_W, ALVO_H)
    assert info["zoom_out_limitado"] is True


def test_focus_y_topo_preserva_cabeca():
    """focus_y=0.0 deve ancorar no topo (a 'cabeça' escura fica visível)."""
    foto, _ = ajustar_foto_na_moldura(
        _foto(1200, 1600), ALVO_W, ALVO_H, scale=1.0, focus_y=0.0
    )
    # Amostra a faixa superior central: deve conter pixels escuros (cabeça).
    escuros = sum(
        1
        for x in range(0, ALVO_W, 20)
        if foto.getpixel((x, 5))[0] < 60
    )
    assert escuros > 0


def test_contain_usa_fundo_solido_nao_blur():
    foto, info = ajustar_foto_na_moldura(
        _foto(1200, 1600), ALVO_W, ALVO_H, scale=1.0, modo="contain",
        cor_fundo=(0, 128, 128),
    )
    assert foto.size == (ALVO_W, ALVO_H)
    assert info["modo"] == "CONTAIN"
    # As laterais devem ser exatamente a cor de fundo (sólida, sem blur).
    assert foto.getpixel((2, ALVO_H // 2)) == (0, 128, 128)


if __name__ == "__main__":
    import sys

    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in testes:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            falhas += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(testes) - falhas}/{len(testes)} passaram")
    sys.exit(1 if falhas else 0)
