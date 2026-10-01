"""
sapmali_ucak.sapmali_dunya testleri: e = 0'da tabloyla birebir aynı olmalı, sapma optimumu
beklenen yönde kaydırmalı.
"""
import functools

import numpy as np
import pytest

from olcum import referans_tarama
from sanal_ucak import sanal_ucak
from sapmali_ucak import sapmali_dunya

KOSULLAR = [(2000, -54, 142), (2000, 10, 161), (6000, 0, 160), (14000, -20, 160)]


def test_sapmasiz_dunya_tablo_ile_ayni():
    dunya = sapmali_dunya(0)
    for kosul in KOSULLAR:
        for devir in (1550, 1600, 1637.5, 1750, 1823, 1900, 1950):  # limit dışı (None) dahil
            assert dunya(*kosul, devir) == sanal_ucak(*kosul, devir)
    assert dunya(2000, 10, 175, 1750) is None  # bu hızı tutamayan koşul tabloda da None
    with pytest.raises(ValueError):
        dunya(3000, 10, 161, 1750)  # tabloda olmayan irtifa: sanal_ucak gibi hata


def test_yakit_carpani_ve_tork():
    y0, t0 = sanal_ucak(2000, 10, 161, 1900)
    for e in (-0.01, 0.005, 0.01):
        dunya = sapmali_dunya(e)
        y, t = dunya(2000, 10, 161, 1900)
        assert t == t0                                            # tork değişmez
        assert y == pytest.approx(y0 * (1 + e))                   # 1900'de tam e oranında
        assert dunya(2000, 10, 161, 1750) == sanal_ucak(2000, 10, 161, 1750)  # 1750'de değişmez
        assert dunya(2000, 10, 161, 1600)[0] == pytest.approx(sanal_ucak(2000, 10, 161, 1600)[0] * (1 - e))


@pytest.mark.parametrize("kosul", KOSULLAR, ids=[f"{i}ft_{s}C_{h}kt" for i, s, h in KOSULLAR])
def test_optimum_kayma_yonu(kosul):
    """e > 0 yüksek devri pahalılaştırır: optimum sapmasızdan büyük olmamalı. e < 0 için tersi."""
    taban = functools.lru_cache(maxsize=None)(sanal_ucak)  # aynı devirler 5 kez taranıyor, hız için
    optimum = {}
    for e in (-0.01, -0.005, 0.0, 0.005, 0.01):
        devirler, yakitlar = referans_tarama(*kosul, dunya=sapmali_dunya(e, taban=taban))
        optimum[e] = devirler[np.nanargmin(yakitlar)]
    assert optimum[0.005] <= optimum[0.0] and optimum[0.01] <= optimum[0.005]
    assert optimum[-0.005] >= optimum[0.0] and optimum[-0.01] >= optimum[-0.005]
