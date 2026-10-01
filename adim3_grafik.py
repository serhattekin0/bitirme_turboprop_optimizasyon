"""
Adım 3: Birkaç koşulda devri 1600'den 1900'e tarayıp yakıt–devir eğrisini çizer.
Koşulları aşağıdaki KOSULLAR listesinden değiştirebilirsin, sonra dosyayı çalıştır.
Grafik ekranda açılır ve adim3_yakit_devir.png olarak kaydedilir.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

from sanal_ucak import DEVIRLER, sanal_ucak

# (irtifa ft, sıcaklık °C, hız kt) - irtifa ve sıcaklık tabloda olan değerler olmalı (en fazla 8 koşul)
KOSULLAR = [
    (2000, -54, 142),
    (2000, 10, 161),
    (6000, 0, 160),
    (14000, -20, 160),
]

DEVIR_TARAMA = np.arange(DEVIRLER[0], DEVIRLER[-1] + 1, 5)  # 5 RPM adımla tarama

# Her koşul bu sırayla bir renk alır
RENKLER = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
ZEMIN, MUREKKEP, IKINCIL, SOLUK = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
IZGARA, EKSEN = "#e1e0d9", "#c3c2b7"

plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]


def tara(irtifa, sicaklik, hiz):
    """Devri 1600-1900 arasında tarar ve yakıt dizisini döndürür; koşul geçersizse None."""
    sonuclar = [sanal_ucak(irtifa, sicaklik, hiz, d) for d in DEVIR_TARAMA]
    if sonuclar[0] is None:
        return None
    return np.array([yakit for yakit, _ in sonuclar])


def kosul_etiketi(irtifa, sicaklik, hiz):
    return f"{irtifa} ft, {sicaklik} °C, {hiz} kt"


def sade_eksen(ax, baslik):
    ax.set_facecolor(ZEMIN)
    ax.set_title(baslik, loc="left", color=MUREKKEP, fontsize=11, pad=10)
    ax.grid(axis="y", color=IZGARA, linewidth=1)
    ax.set_axisbelow(True)
    for kenar in ("top", "right", "left"):
        ax.spines[kenar].set_visible(False)
    ax.spines["bottom"].set_color(EKSEN)
    ax.tick_params(colors=SOLUK, length=0, labelsize=9)
    ax.set_xticks(np.arange(1600, 1901, 50))
    ax.set_xlim(1590, 1910)
    ax.set_xlabel("Pervane devri (RPM)", color=IKINCIL, fontsize=9)


# Doğrudan çalıştırıldığında grafiği çizer; adim4 gibi başka dosyalar yukarıdaki
# renkleri, koşulları ve fonksiyonları import edebilsin diye __main__ altında.
if __name__ == "__main__":
    fig, (sol, sag) = plt.subplots(1, 2, figsize=(12, 5.8), facecolor=ZEMIN)
    sade_eksen(sol, "Yakıt debisi (PPH)")
    sade_eksen(sag, "En düşük yakıttan fark (PPH)")

    print(f"{'Koşul':<24}{'Optimum':>10}{'Yakıt':>10}{'1900 RPM':>10}{'Kazanç':>9}")
    for renk, (irtifa, sicaklik, hiz) in zip(RENKLER, KOSULLAR):
        etiket = kosul_etiketi(irtifa, sicaklik, hiz)
        yakit = tara(irtifa, sicaklik, hiz)
        if yakit is None:
            print(f"{etiket:<24}  GEÇERSİZ: bu hızı üç devir birden tutamıyor, atlandı")
            continue

        k = yakit.argmin()
        opt_devir, opt_yakit = DEVIR_TARAMA[k], yakit[k]
        print(f"{etiket:<24}{opt_devir:>6} RPM{opt_yakit:>10.1f}{yakit[-1]:>10.1f}{yakit[-1] - opt_yakit:>9.1f}")

        # Sol: gerçek yakıt değerleri
        sol.plot(DEVIR_TARAMA, yakit, color=renk, linewidth=2, solid_capstyle="round", label=etiket)
        tablo_yakit = [sanal_ucak(irtifa, sicaklik, hiz, d)[0] for d in DEVIRLER]
        sol.plot(DEVIRLER, tablo_yakit, "o", ms=7, mfc=ZEMIN, mec=renk, mew=2, zorder=4)
        sol.plot(opt_devir, opt_yakit, "o", ms=10, mfc=renk, mec=ZEMIN, mew=2, zorder=5)
        hiza = "right" if opt_devir > 1870 else "left" if opt_devir < 1630 else "center"
        sol.annotate(f"{opt_devir} RPM · {opt_yakit:.1f} PPH", (opt_devir, opt_yakit), xytext=(0, -12),
                     textcoords="offset points", ha=hiza, va="top", color=MUREKKEP, fontsize=9,
                     bbox=dict(boxstyle="round,pad=0.2", fc=ZEMIN, ec="none"), zorder=6)

        # Sağ: her eğri kendi minimumuna göre; optimumun yatayda kayması burada görünür
        sag.plot(DEVIR_TARAMA, yakit - opt_yakit, color=renk, linewidth=2, solid_capstyle="round")
        sag.plot(opt_devir, 0, "o", ms=10, mfc=renk, mec=ZEMIN, mew=2, zorder=5)

    sol.margins(y=0.12)
    sag.set_ylim(bottom=-1)

    isaretler = [
        Line2D([], [], ls="", marker="o", ms=7, mfc=ZEMIN, mec=IKINCIL, mew=2, label="Tablodan (1600/1750/1900)"),
        Line2D([], [], ls="", marker="o", ms=10, mfc=IKINCIL, mec=ZEMIN, mew=2, label="En az yakıt"),
    ]
    fig.legend(handles=sol.get_lines()[0::3] + isaretler, loc="upper left", bbox_to_anchor=(0.045, 0.905),
               ncol=6, frameon=False, fontsize=9, labelcolor=IKINCIL, handlelength=1.6, columnspacing=1.4)
    fig.text(0.05, 0.965, "Optimum devir koşula göre kayıyor", fontsize=15, color=MUREKKEP, weight="bold")
    fig.text(0.05, 0.925, "Cessna 208B seyir tablosu: her devirde hıza göre ara değer, devirler arasında 2. derece eğri",
             fontsize=10, color=IKINCIL)
    fig.tight_layout(rect=(0.03, 0, 1, 0.85))

    cikti = Path(__file__).with_name("adim3_yakit_devir.png")
    try:
        fig.savefig(cikti, dpi=150, facecolor=ZEMIN)
        print(f"\nGrafik kaydedildi: {cikti.name}")
    except OSError:
        # Windows, dosya başka bir programda (ör. Fotoğraflar) açıkken üzerine yazdırmıyor
        print(f"\n{cikti.name} kaydedilemedi: dosya başka bir programda açık olabilir. Kapatıp tekrar çalıştır.")
    plt.show()
