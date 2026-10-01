"""
stratejiler.geri_donus_kontrolu testleri.
"""
from math import sqrt

import pandas as pd
import pytest

from algoritma import perturb_observe
from olcum import GercekciOlcum
from sapmali_ucak import sapmali_dunya
from stratejiler import geri_donus_kontrolu


def test_gurultusuz_optimum_1900_ise_1900de_biter():
    """14000 ft, -20 °C, 160 kt'ta optimum 1900. Gürültü sıfırken P&O + kontrol 1900'de bitmeli."""
    olc = GercekciOlcum(14000, -20, 160, gurultu_yuzde=0, ortalama_s=1)
    sonuc = perturb_observe(olc)
    kontrol = geri_donus_kontrolu(olc, sonuc.devir, 1900, gurultu_orani=0, ornek_sayisi=10)
    assert kontrol.devir == 1900


def test_gurultusuz_kotu_devirden_geri_doner():
    """Bulunan devir (1850) referanstan (1900) kötüyse referansa dönülmeli."""
    olc = GercekciOlcum(14000, -20, 160, gurultu_yuzde=0, ortalama_s=1)
    kontrol = geri_donus_kontrolu(olc, 1850, 1900, gurultu_orani=0, ornek_sayisi=10)
    assert kontrol.devir == 1900 and kontrol.geri_donuldu and kontrol.olcum_sayisi == 2


def test_gercekten_iyi_devir_tutulur():
    """2000 ft, 10 °C, 161 kt'ta 1800 RPM 1900'den ~2,6 PPH iyi: tutulmalı."""
    olc = GercekciOlcum(2000, 10, 161, gurultu_yuzde=0, ortalama_s=1)
    kontrol = geri_donus_kontrolu(olc, 1800, 1900, gurultu_orani=0, ornek_sayisi=10)
    assert kontrol.devir == 1800 and not kontrol.geri_donuldu


def test_esik_formulu_ve_sure_maliyete_girer():
    olc = GercekciOlcum(2000, 10, 161, gurultu_yuzde=1, ortalama_s=2, seed=0)
    olc(1850)  # P&O'nun son denediği devir gibi: motor 1850'de
    t0 = olc.t
    kontrol = geri_donus_kontrolu(olc, 1800, 1900, gurultu_orani=0.01, ornek_sayisi=20, k=2)
    yakit = (kontrol.yakit_referans + kontrol.yakit_bulunan) / 2
    assert kontrol.esik_pph == pytest.approx(2 * sqrt(2) * 0.01 * yakit / sqrt(20))
    # İki yeniden ölçüm ölçüm sisteminin zamanını ilerletir: her biri 6 s bekleme + 2 s ortalama
    assert olc.t - t0 == pytest.approx(2 * (6 + 2))
    assert olc.komut == 1800  # önce referans, sonra bulunan ölçülür: tutulursa motor zaten orada


def test_ayni_devirse_olcum_yapilmaz():
    olc = GercekciOlcum(2000, 10, 161, gurultu_yuzde=1, seed=0)
    kontrol = geri_donus_kontrolu(olc, 1900, 1900, gurultu_orani=0.01, ornek_sayisi=50)
    assert kontrol.devir == 1900 and kontrol.olcum_sayisi == 0 and olc.t == 0


def kosu(seed):
    """Sapmalı dünyada P&O + geri dönüş kontrolü + seyir."""
    olc = GercekciOlcum(2000, 10, 161, gurultu_yuzde=1, ortalama_s=5, seed=seed, dunya=sapmali_dunya(0.005))
    sonuc = perturb_observe(olc)
    kontrol = geri_donus_kontrolu(olc, sonuc.devir, 1900, gurultu_orani=0.01, ornek_sayisi=50)
    olc.devam_et(kontrol.devir, 300)
    return sonuc, kontrol, olc.kayit()


def test_ayni_tohum_ayni_sonuc():
    sonuc1, kontrol1, kayit1 = kosu(seed=7)
    sonuc2, kontrol2, kayit2 = kosu(seed=7)
    assert sonuc1 == sonuc2 and kontrol1 == kontrol2
    pd.testing.assert_frame_equal(kayit1, kayit2)
