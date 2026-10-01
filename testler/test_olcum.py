"""
olcum.GercekciOlcum testleri: motor gecikmesi, gürültü, tekrarlanabilirlik ve
gürültüsüz/gecikmesiz durumda Adım 5 sonuçlarına dönüş.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from algoritma import perturb_observe
from olcum import GercekciOlcum
from sanal_ucak import sanal_ucak

ZARF_CSV = Path(__file__).resolve().parent.parent / "sonuclar" / "zarf_sonuclari.csv"


@pytest.mark.slow  # bütün zarfı tarar
def test_gurultusuz_ve_gecikmesiz_adim5_ile_ayni():
    """Gürültü 0 ve tau çok küçükken her ölçüm anında ve kusursuz: bütün zarfta Adım 5 sonuçları çıkmalı."""
    zarf = pd.read_csv(ZARF_CSV)
    farklar = []
    for s in zarf.itertuples():
        olc = GercekciOlcum(s.irtifa_ft, s.sicaklik_C, s.hiz_kt, tau_s=1e-6, gurultu_yuzde=0, ortalama_s=0.1)
        sonuc = perturb_observe(olc)
        if (sonuc.devir != s.bulunan_devir_rpm or sonuc.olcum_sayisi != s.olcum_sayisi
                or abs(sonuc.yakit - s.bulunan_yakit_pph) > 1e-3):
            farklar.append((s.irtifa_ft, s.sicaklik_C, s.hiz_kt, sonuc.devir, s.bulunan_devir_rpm))
    assert not farklar, f"{len(farklar)} koşulda Adım 5'ten farklı: {farklar[:5]}"


def kosu(seed):
    olc = GercekciOlcum(2000, 10, 161, gurultu_yuzde=1, ortalama_s=2, seed=seed)
    sonuc = perturb_observe(olc)
    olc.devam_et(sonuc.devir, 300)
    return sonuc, olc.kayit()


def test_ayni_tohum_ayni_sonuc():
    sonuc1, kayit1 = kosu(seed=42)
    sonuc2, kayit2 = kosu(seed=42)
    assert sonuc1 == sonuc2  # bulunan devir, yakıt, ölçüm sayısı ve bütün geçmiş
    pd.testing.assert_frame_equal(kayit1, kayit2)


def test_farkli_tohum_farkli_olcum():
    _, kayit1 = kosu(seed=1)
    _, kayit2 = kosu(seed=2)
    assert not np.allclose(kayit1.olculen_yakit[:50], kayit2.olculen_yakit[:50])


def test_birinci_derece_gecikme():
    """Devir değişince gerçek yakıt, farkın e^(-t/tau) kadarı kalacak şekilde yeni değere yaklaşmalı."""
    olc = GercekciOlcum(2000, 10, 161, tau_s=2.0, bekleme_s=2.0, ortalama_s=0.1, gurultu_yuzde=0)
    y0 = olc(1900)  # başlangıçta 1900'de kararlı: ölçüm anında ve kusursuz
    assert y0 == pytest.approx(sanal_ucak(2000, 10, 161, 1900)[0])
    hedef = sanal_ucak(2000, 10, 161, 1600)[0]
    y1 = olc(1600)  # 2 s bekleme + 1 örnek (0,1 s) sonra
    assert y1 == pytest.approx(hedef + (y0 - hedef) * np.exp(-2.1 / 2.0))
    assert olc.t == pytest.approx(0.1 + 2.1)


def test_gurultu_duzeyi():
    """Sensör okumalarının bağıl standart sapması gurultu_yuzde'ye yakın olmalı."""
    olc = GercekciOlcum(2000, 10, 161, gurultu_yuzde=1.0, seed=0)
    olc.devam_et(1900, 600)  # 6000 okuma, 1900'de kararlı
    k = olc.kayit()
    bagil = k.olculen_yakit / k.gercek_yakit - 1
    assert bagil.std() == pytest.approx(0.01, rel=0.05)
    assert abs(bagil.mean()) < 0.001
