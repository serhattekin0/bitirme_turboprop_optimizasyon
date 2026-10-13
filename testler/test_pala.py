"""
Adım 8 testleri: pala açısı hesabı, P&O sarmalayıcısı ve kuru moddaki PalaKomutu.
"""
import math
import time

import numpy as np
import pandas as pd
import pytest

from algoritma import perturb_observe
from olcum import GercekciOlcum, olcum_fonksiyonu
from pala_acisi import PROFILLER, harita, pala_acisi, yogunluk
from pala_algoritma import pala_perturb_observe
from seri_port import PalaKomutu

KOSUL = (2000, 10, 161)

# 2000 ft, 10 °C, 161 kt'ta beklenen β75 (derece), ±0,3°
BEKLENEN = {
    "clarky":   {1900: 27.5, 1750: 30.5, 1600: 34.4},
    "naca4412": {1900: 27.0, 1750: 30.0, 1600: 33.8},
    "arad10":   {1900: 30.0, 1750: 33.4, 1600: 37.9},
}


# ---------------------------------------------------------------- pala açısı

@pytest.mark.parametrize("profil", PROFILLER)
@pytest.mark.parametrize("devir", [1900, 1750, 1600])
def test_beklenen_beta75(profil, devir):
    assert pala_acisi(profil, *KOSUL, devir).beta75 == pytest.approx(BEKLENEN[profil][devir], abs=0.3)


@pytest.mark.parametrize("profil", PROFILLER)
def test_devir_dustukce_beta_artar(profil):
    betalar = [pala_acisi(profil, *KOSUL, d).beta75 for d in range(1900, 1599, -10)]
    assert np.all(np.diff(betalar) > 0), betalar


@pytest.mark.parametrize("profil", PROFILLER)
@pytest.mark.parametrize("kosul", [KOSUL, (2000, -54, 142), (6000, 0, 160), (14000, -20, 160)])
@pytest.mark.parametrize("devir", [1600, 1700, 1800, 1900])
def test_geri_hesaplanan_cp_gerekliye_esit(profil, kosul, devir):
    p = pala_acisi(profil, *kosul, devir)
    if p is None:
        pytest.skip("koşul bu devirde geçersiz")
    cp = harita(profil).CP(p.J, p.beta75)
    assert cp == pytest.approx(p.C_P, rel=0.005)


def test_yogunluk_isa_deniz_seviyesi():
    assert yogunluk(0, 15) == pytest.approx(1.225, abs=1e-3)


def test_harita_onbellekte():
    assert harita("clarky") is harita("clarky")


def test_cift_dogrusal_interpolasyon_dugumlerde_tablo_degeri():
    h = harita("naca4412")
    tablo = pd.read_csv("veri/haritalar/naca4412_harita.csv")
    for s in tablo.sample(50, random_state=0).itertuples():
        assert h.CP(s.J, s.beta75) == pytest.approx(s.CP, abs=1e-12)
        assert h.CT(s.J, s.beta75) == pytest.approx(s.CT, abs=1e-12)
    # İki düğüm ortası iki değerin ortalaması
    assert h.CP(0.525, 20) == pytest.approx((h.CP(0.5, 20) + h.CP(0.55, 20)) / 2)


def test_ilk_kesisim_alinir():
    """ARA-D, J = 0,5'te C_P β ile tekdüze değil (stall): 0,0708 için birden çok kök var, ilki 28–29° arası."""
    h = harita("arad10")
    beta = h.beta_bul(0.5, 0.0708)
    assert 28 < beta < 29
    assert h.CP(0.5, beta) == pytest.approx(0.0708, rel=1e-4)
    # Sonraki köklerin de var olduğunu doğrula (test gerçekten tekdüze olmayan bölgeyi sınıyor)
    cp = [h.CP(0.5, b) for b in np.arange(29, 38, 0.1)]
    assert np.sum(np.diff(np.sign(np.array(cp) - 0.0708)) != 0) >= 2


def test_kesisim_yoksa_nan():
    h = harita("clarky")
    assert math.isnan(h.beta_bul(0.5, 0.5))      # haritadaki en büyük C_P'den büyük
    assert math.isnan(h.beta_bul(0.3, 0.05))     # J harita dışında


def test_gecersiz_kosul_none():
    assert pala_acisi("clarky", 2000, 10, 175, 1600) is None


def test_bilinmeyen_profil():
    with pytest.raises(ValueError):
        pala_acisi("naca0012", *KOSUL, 1900)


# ---------------------------------------------------------------- sarmalayıcı

def test_sarmalayici_algoritmayi_degistirmez():
    olc = olcum_fonksiyonu(*KOSUL)
    sade = perturb_observe(olc)
    gonderilen = []
    s = pala_perturb_observe(olc, "clarky", *KOSUL, komut=gonderilen.append)
    assert s.sonuc == sade
    assert s.devir == sade.devir
    assert list(s.gecmis.columns[:6]) == ["devir", "yakit", "kabul", "neden", "beta75", "beta_30inc"]
    assert len(s.gecmis) == len(sade.gecmis)
    assert len(gonderilen) == sade.olcum_sayisi  # her ölçümden önce bir komut
    beklenen = pala_acisi("clarky", *KOSUL, sade.devir)
    assert s.beta75 == pytest.approx(beklenen.beta75)
    assert s.beta_30inc == pytest.approx(beklenen.beta_30inc)
    for satir in s.gecmis.itertuples():
        assert satir.beta75 == pytest.approx(pala_acisi("clarky", *KOSUL, satir.devir).beta75)


def test_sarmalayici_limit_adimlari():
    """Optimumu 1600'de olan koşulda algoritma alt limite dayanır; "limit" satırı da tabloda olmalı."""
    s = pala_perturb_observe(olcum_fonksiyonu(2000, -54, 147), "naca4412", 2000, -54, 147)
    assert s.devir == 1600
    limit = s.gecmis[s.gecmis.neden == "limit"]
    assert len(limit) > 0 and limit.yakit.isna().all() and limit.beta75.notna().all()


@pytest.mark.parametrize("seed", range(5))
def test_sarmalayici_gurultulu_olcumde_kabul_karari_tutarli(seed):
    """Canlı kabul kararı, gürültülü ölçümde de algoritmanın kararıyla aynı olmalı (uyuşmazsa hata verir)."""
    olc = GercekciOlcum(*KOSUL, gurultu_yuzde=1, ortalama_s=2, seed=seed)
    satirlar = []
    s = pala_perturb_observe(olc, "arad10", *KOSUL, adim_bildir=satirlar.append)
    assert len(satirlar) == s.sonuc.olcum_sayisi
    assert s.gecmis.t_olcum_s.dropna().is_monotonic_increasing


# ---------------------------------------------------------------- PalaKomutu (kuru mod)

def test_mesaj_bicimi():
    k = PalaKomutu(sessiz=True)
    assert k.kuru
    assert k.gonder(30.5) == "B 30.50\n"
    assert k.gonder(27.456) == "B 27.46\n"
    assert [m for _, m in k.gonderilenler] == ["B 30.50\n", "B 27.46\n"]


def test_sinir_disi_aci_kirpilir_ve_uyarilir(capsys):
    k = PalaKomutu(aci_min=15, aci_max=50)
    assert k.gonder(55) == "B 50.00\n"
    assert k.gonder(10.2) == "B 15.00\n"
    assert k.gonder(30) == "B 30.00\n"
    assert len(k.uyarilar) == 2
    assert "UYARI" in capsys.readouterr().out


def test_nan_aci_gonderilmez():
    k = PalaKomutu(sessiz=True)
    assert k.gonder(float("nan")) is None
    assert not k.gonderilenler and k.uyarilar


def test_hiz_siniri():
    k = PalaKomutu(max_hz=10, sessiz=True)
    t0 = time.monotonic()
    for aci in range(20, 26):
        k.gonder(aci)
    zamanlar = np.array([t for t, _ in k.gonderilenler])
    assert np.all(np.diff(zamanlar) >= 0.1 - 1e-3)
    assert time.monotonic() - t0 >= 0.5 - 1e-3   # 6 mesaj, 5 aralık
    assert len(k.gonderilenler) == 6              # hiçbir komut düşürülmedi
