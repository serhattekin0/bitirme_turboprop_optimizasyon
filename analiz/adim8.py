"""
Adım 8: Algoritmanın bulduğu devirden pala açısı.

Çıktılar (sonuclar/):
- adim8_pala_acisi.csv: Adım 5'in bütün koşulları × üç profil; referans optimum devirde ve 1900 RPM'de β75
- adim8_aci_devir.png: 2000 ft, 10 °C, 161 kt'ta pala açısı–devir eğrisi, üç profil
- adim8_demo_zaman_serisi.png: demo koşusunun zaman serisi (üstte devir, altta pala açısı), üç profil
Konsola özet yazar.
"""
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from adim3_grafik import IKINCIL, MUREKKEP, RENKLER, SOLUK, ZEMIN, kosul_etiketi, sade_eksen
from analiz.demo_pala import GURULTU_YUZDE, ORTALAMA_S, calistir
from olcum import referans_tarama
from pala_acisi import PROFIL_ADLARI, PROFILLER, R_30INC_M, R_075_M, harita, pala_acisi

SONUC_KLASORU = KOK / "sonuclar"
KOSUL = (2000, 10, 161)
SABIT_DEVIR = 1900
CIZGI = {"clarky": "-", "naca4412": (0, (6, 3)), "arad10": (0, (1.5, 2))}  # renge ek ikincil kodlama
PROFIL_RENK = dict(zip(PROFILLER, RENKLER))


def kaydet(fig, dosya):
    yol = SONUC_KLASORU / dosya
    try:
        fig.savefig(yol, dpi=150, facecolor=ZEMIN)
        print(f"Grafik kaydedildi: sonuclar/{dosya}")
    except OSError:
        print(f"{dosya} kaydedilemedi: dosya başka bir programda açık olabilir.")


def basliklar(fig, baslik, alt_baslik, y=0.965):
    fig.text(0.05, y, baslik, fontsize=15, color=MUREKKEP, weight="bold")
    fig.text(0.05, y - 0.022, alt_baslik, fontsize=10, color=IKINCIL, va="top", linespacing=1.5)


# ---------------------------------------------------------------- tablo

def zarf_tablosu():
    zarf = pd.read_csv(SONUC_KLASORU / "zarf_sonuclari.csv")
    satirlar = []
    for profil in PROFILLER:
        for s in zarf.itertuples():
            ref = pala_acisi(profil, s.irtifa_ft, s.sicaklik_C, s.hiz_kt, s.ref_devir_rpm)
            sabit = pala_acisi(profil, s.irtifa_ft, s.sicaklik_C, s.hiz_kt, SABIT_DEVIR)
            satirlar.append(dict(
                profil=profil, irtifa_ft=s.irtifa_ft, sicaklik_C=s.sicaklik_C, hiz_kt=s.hiz_kt,
                ref_devir_rpm=s.ref_devir_rpm,
                beta75_ref_deg=ref.beta75, beta75_1900_deg=sabit.beta75,
                beta75_fark_deg=ref.beta75 - sabit.beta75,
                beta30inc_ref_deg=ref.beta_30inc, beta30inc_1900_deg=sabit.beta_30inc,
                J_ref=ref.J, CP_ref=ref.C_P, verim_ref=ref.verim, verim_1900=sabit.verim,
            ))
    return pd.DataFrame(satirlar)


# ---------------------------------------------------------------- grafik 1

def aci_devir_grafigi(dosya):
    devirler = np.arange(1600, 1901, 5)
    fig, ax = plt.subplots(figsize=(12, 6), facecolor=ZEMIN)
    sade_eksen(ax, "0,75R'de pala açısı β₀.₇₅ (°)")
    ax.set_xlim(1590, 1960)
    ax.set_xticks(np.arange(1600, 1901, 50))
    for profil in PROFILLER:
        beta = np.array([pala_acisi(profil, *KOSUL, d).beta75 for d in devirler])
        renk = PROFIL_RENK[profil]
        ax.plot(devirler, beta, color=renk, linewidth=2, linestyle=CIZGI[profil], solid_capstyle="round")
        nokta = [1600, 1750, 1900]
        ax.plot(nokta, [beta[devirler == d][0] for d in nokta], "o", ms=8, mfc=ZEMIN, mec=renk, mew=2, zorder=4)
        # Doğrudan etiket (sağ uç)
        ax.text(1906, beta[-1], f"{PROFIL_ADLARI[profil]}  {beta[-1]:.1f}°", va="center", ha="left",
                fontsize=9, color=MUREKKEP)
    # Referans optimum devri: test dünyasında 1 RPM tarama (161 kt zarf ızgarasında yok)
    tarama_devir, tarama_yakit = referans_tarama(*KOSUL)
    ref_devir = int(tarama_devir[np.nanargmin(tarama_yakit)])
    ax.axvline(ref_devir, color=IKINCIL, linewidth=1, linestyle=":")
    ax.text(ref_devir + 3, ax.get_ylim()[1], f"Referans optimum {ref_devir} RPM", va="top", ha="left",
            fontsize=8.5, color=IKINCIL)
    isaretler = [Line2D([], [], color=PROFIL_RENK[p], linewidth=2, linestyle=CIZGI[p], label=PROFIL_ADLARI[p])
                 for p in PROFILLER]
    isaretler.append(Line2D([], [], ls="", marker="o", ms=8, mfc=ZEMIN, mec=IKINCIL, mew=2,
                            label="Test değerleri (1600/1750/1900)"))
    fig.legend(handles=isaretler, loc="upper left", bbox_to_anchor=(0.045, 0.87), ncol=4, frameon=False,
               fontsize=9, labelcolor=IKINCIL, handlelength=2.4)
    farklar = ", ".join(f"{PROFIL_ADLARI[p]} +{harita(p).teta(R_30INC_M) - harita(p).teta(R_075_M):.2f}°"
                        for p in PROFILLER)
    basliklar(fig, f"Devir düştükçe pala açısı artıyor: {kosul_etiketi(*KOSUL)}",
              f"Aynı motor gücünü daha düşük devirde emmek için pala daha büyük açıya gelir.\n"
              f"30 inç istasyonundaki açı = β₀.₇₅ + sabit ({farklar}).")
    fig.tight_layout(rect=(0.03, 0, 1, 0.82))
    kaydet(fig, dosya)


# ---------------------------------------------------------------- grafik 2

def demo_grafigi(dosya, seed=0, sonra_s=30):
    fig, (ust, alt) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, facecolor=ZEMIN,
                                   gridspec_kw=dict(height_ratios=[1, 1.4]))
    kosular = {}
    for profil in PROFILLER:
        sonuc, olc, _ = calistir(profil, *KOSUL, port=None, hiz_carpani=0, seed=seed, sessiz=True)
        arama_bitis = olc.t
        olc.devam_et(sonuc.devir, arama_bitis + sonra_s)
        k = olc.kayit()
        aci = dict(zip(sonuc.gecmis.devir, sonuc.gecmis.beta75))
        t = np.r_[0.0, k.t_s]
        komut = np.r_[SABIT_DEVIR, k.komut_devir]
        beta = np.array([aci[d] for d in komut])
        kosular[profil] = (sonuc, arama_bitis)
        renk = PROFIL_RENK[profil]
        ust.plot(t, komut, drawstyle="steps-pre", color=renk, linewidth=2, linestyle=CIZGI[profil])
        alt.plot(t, beta, drawstyle="steps-pre", color=renk, linewidth=2, linestyle=CIZGI[profil])
        alt.text(t[-1] + 1, beta[-1], f"{PROFIL_ADLARI[profil]}  {beta[-1]:.2f}°", va="center", ha="left",
                 fontsize=9, color=MUREKKEP)
    son = t[-1]
    for ax in (ust, alt):
        sade_eksen(ax, "")
        ax.set_xticks(np.arange(0, son + 1, 20))
        ax.set_xlim(0, son + 45)
        ax.set_xlabel("")
    alt.set_xlabel("Simülasyon zamanı (s)", color=IKINCIL, fontsize=9)
    ust.set_ylabel("Komut edilen devir (RPM)", color=IKINCIL, fontsize=9)
    alt.set_ylabel("Komut edilen β₀.₇₅ (°)", color=IKINCIL, fontsize=9)
    ust.set_yticks(np.arange(1700, 1951, 50))
    ust.set_ylim(1690, 1925)

    sonuc, arama_bitis = kosular[PROFILLER[0]]
    for ax in (ust, alt):
        ax.axvline(arama_bitis, color=MUREKKEP, linewidth=1.2, linestyle=(0, (4, 3)), zorder=6)
    ust.text(arama_bitis + 1, 1915, f"Arama bitti: {arama_bitis:.0f} s, {sonuc.sonuc.olcum_sayisi} ölçüm → "
             f"{sonuc.devir:g} RPM", ha="left", va="top", fontsize=9, color=MUREKKEP)
    isaretler = [Line2D([], [], color=PROFIL_RENK[p], linewidth=2, linestyle=CIZGI[p], label=PROFIL_ADLARI[p])
                 for p in PROFILLER]
    fig.legend(handles=isaretler, loc="upper left", bbox_to_anchor=(0.045, 0.9), ncol=3, frameon=False,
               fontsize=9, labelcolor=IKINCIL, handlelength=2.4)
    basliklar(fig, f"Demo koşusu: devir ve pala açısı komutları, {kosul_etiketi(*KOSUL)}",
              f"Gürültü %{GURULTU_YUZDE:g}, ortalama {ORTALAMA_S:g} s, tohum {seed}. Yakıt pala profiline bağlı "
              f"olmadığı için devir izi üç profilde aynı (çizgiler üst üste); farklı olan pala açısı.")
    fig.tight_layout(rect=(0.03, 0, 1, 0.86), h_pad=1.5)
    kaydet(fig, dosya)
    return kosular


def main():
    SONUC_KLASORU.mkdir(exist_ok=True)
    tablo = zarf_tablosu()
    tablo.to_csv(SONUC_KLASORU / "adim8_pala_acisi.csv", index=False, float_format="%.4f")
    print(f"Tablo kaydedildi: sonuclar/adim8_pala_acisi.csv ({len(tablo)} satır)")
    print(f"Kesişim bulunamayan (NaN): ref {tablo.beta75_ref_deg.isna().sum()}, "
          f"1900 {tablo.beta75_1900_deg.isna().sum()}")

    ozet = tablo.groupby("profil", sort=False).agg(
        beta75_ref_min=("beta75_ref_deg", "min"), beta75_ref_max=("beta75_ref_deg", "max"),
        beta75_1900_min=("beta75_1900_deg", "min"), beta75_1900_max=("beta75_1900_deg", "max"),
        fark_ort=("beta75_fark_deg", "mean"), fark_max=("beta75_fark_deg", "max"),
        verim_ref_ort=("verim_ref", "mean"), verim_1900_ort=("verim_1900", "mean"),
    )
    print(ozet.round(3).to_string())
    arada = tablo[tablo.ref_devir_rpm < SABIT_DEVIR]
    print(f"Optimumu 1900'ün altında olan koşullarda ortalama Δβ75: "
          f"{arada.groupby('profil', sort=False).beta75_fark_deg.mean().round(2).to_dict()}")

    aci_devir_grafigi("adim8_aci_devir.png")
    kosular = demo_grafigi("adim8_demo_zaman_serisi.png")
    for profil, (sonuc, arama_bitis) in kosular.items():
        print(f"Demo {PROFIL_ADLARI[profil]}: {sonuc.devir:g} RPM, β75 {sonuc.beta75:.2f}°, "
              f"30 inç {sonuc.beta_30inc:.2f}°, arama {arama_bitis:.0f} s")


if __name__ == "__main__":
    main()
