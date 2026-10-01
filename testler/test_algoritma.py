"""
algoritma.perturb_observe testleri.

Referans: test dünyasında devir 1600-1900 arasında 1'er RPM taranır, en düşük yakıt alınır.
Başarı: algoritmanın bulduğu devirdeki yakıt, referans en düşük yakıttan en fazla 0,5 PPH fazla.
Eğrilerin dibi çok düz olduğu için devir farkına değil yakıt farkına bakılır.
"""
import ast
from pathlib import Path

import numpy as np
import pytest

from algoritma import perturb_observe
from olcum import olcum_fonksiyonu, referans_tarama

ALT, UST = 1600, 1900
TOLERANS_PPH = 0.5

# (irtifa ft, sıcaklık °C, hız kt)
KOSULLAR = [
    (2000, -54, 142),
    (2000, 10, 161),
    (6000, 0, 160),
    (14000, -20, 160),
]
# (başlangıç devri, başlangıç yönü): 1900'den aşağı ve 1600'den yukarı
BASLANGICLAR = [(1900, -1), (1600, +1)]

kosul_parametresi = pytest.mark.parametrize(
    "kosul", KOSULLAR, ids=[f"{i}ft_{s}C_{h}kt" for i, s, h in KOSULLAR])
baslangic_parametresi = pytest.mark.parametrize(
    "baslangic_devir, yon", BASLANGICLAR, ids=["1900_asagi", "1600_yukari"])


def sayan(olc):
    """olc'yi sarar ve kaç kez çağrıldığını sayar (algoritmanın sayacını doğrulamak için)."""
    def sarili(devir):
        sarili.cagri += 1
        return olc(devir)
    sarili.cagri = 0
    return sarili


@kosul_parametresi
@baslangic_parametresi
def test_optimum_yakit(kosul, baslangic_devir, yon):
    _, yakitlar = referans_tarama(*kosul)
    ref_yakit = np.nanmin(yakitlar)

    olc = sayan(olcum_fonksiyonu(*kosul))
    sonuc = perturb_observe(olc, baslangic_devir=baslangic_devir, baslangic_yon=yon)

    # Asıl ölçüt: yakıt farkı en fazla 0,5 PPH
    assert sonuc.yakit - ref_yakit <= TOLERANS_PPH
    # Bulunan devir ve denenen her devir limitler içinde
    assert ALT <= sonuc.devir <= UST
    assert all(ALT <= g["devir"] <= UST for g in sonuc.gecmis)
    # Raporlanan yakıt gerçekten o devirdeki test dünyası değeri
    assert sonuc.yakit == pytest.approx(olcum_fonksiyonu(*kosul)(sonuc.devir))
    # Ölçüm sayacı doğru ve güvenlik sınırının altında
    assert sonuc.olcum_sayisi == olc.cagri <= 50
    assert sonuc.olcum_sayisi == sum(g["neden"] != "limit" for g in sonuc.gecmis)


@baslangic_parametresi
def test_optimum_limitte(baslangic_devir, yon):
    """14000 ft'ta optimum 1900 RPM'de (üst limit): algoritma limitte kalmalı, dışarı taşmamalı."""
    kosul = (14000, -20, 160)
    devirler, yakitlar = referans_tarama(*kosul)
    assert devirler[np.nanargmin(yakitlar)] == UST  # önkoşul: optimum gerçekten limitte

    sonuc = perturb_observe(olcum_fonksiyonu(*kosul), baslangic_devir=baslangic_devir, baslangic_yon=yon)

    assert sonuc.devir == UST
    # Limitin ötesine gitme isteği ölçülmeden "daha kötü" sayılmalı
    limit_denemeleri = [g for g in sonuc.gecmis if g["neden"] == "limit"]
    assert limit_denemeleri
    assert all(g["devir"] == UST and g["yakit"] is None and not g["kabul"] for g in limit_denemeleri)


def test_gecersiz_olcum_daha_kotu_sayilir():
    """Yapay dünya: 1800 RPM altı geçersiz (None), gerçek dip 1700'de.
    Algoritma geçersiz bölgeye hiç geçmemeli, geçerli bölgenin en iyisinde (1800) kalmalı."""
    def olc(devir):
        return None if devir < 1800 else 300 + 1e-3 * (devir - 1700) ** 2

    sonuc = perturb_observe(olc)

    assert sonuc.devir == 1800
    gecersizler = [g for g in sonuc.gecmis if g["neden"] == "geçersiz"]
    assert gecersizler and not any(g["kabul"] for g in gecersizler)


def test_olcum_limiti():
    """Güvenlik sınırı: en_fazla_olcum dolunca algoritma durmalı."""
    olc = sayan(lambda devir: 300 + 1e-3 * (devir - 1700) ** 2)

    sonuc = perturb_observe(olc, en_fazla_olcum=3)

    assert sonuc.olcum_sayisi == olc.cagri == 3
    assert sonuc.durma_nedeni == "ölçüm limiti doldu"


def test_algoritma_tabloyu_gormez():
    """algoritma.py test dünyasını, tabloyu ya da pandas'ı içe aktarmamalı; yalnızca olc() ile konuşur."""
    kaynak = Path(__file__).resolve().parent.parent / "algoritma.py"
    agac = ast.parse(kaynak.read_text(encoding="utf-8"))
    moduller = set()
    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.Import):
            moduller |= {a.name.split(".")[0] for a in dugum.names}
        elif isinstance(dugum, ast.ImportFrom):
            moduller.add(dugum.module.split(".")[0])
    assert not moduller & {"sanal_ucak", "olcum", "pandas"}
