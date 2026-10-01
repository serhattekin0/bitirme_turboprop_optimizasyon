"""
Adım 4: Perturb & observe algoritmasını adım 3'teki dört koşulda çalıştırır.
- Her koşul için yakıt–devir eğrisi ve algoritmanın denediği devirler (2x2 grafik,
  analiz/adim4_algoritma.png olarak kaydedilir)
- Konsola özet tablo: bulunan devir, gerçek optimum, yakıt farkı, sabit 1900 RPM'e göre tasarruf
Renkler, koşullar ve eksen stili adim3_grafik.py'den alınır.
"""
import sys
from pathlib import Path

# Kök dizindeki modüller (algoritma, olcum, adim3_grafik) bulunsun diye
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

from adim3_grafik import IKINCIL, KOSULLAR, MUREKKEP, RENKLER, ZEMIN, kosul_etiketi, sade_eksen
from algoritma import perturb_observe
from olcum import olcum_fonksiyonu, referans_tarama

SABIT_DEVIR = 1900  # karşılaştırma: devir hiç değiştirilmeseydi


def kosulu_coz(irtifa, sicaklik, hiz):
    """Bir koşulda referans taramayı ve algoritmayı (varsayılan ayarlarla) çalıştırır."""
    devirler, yakitlar = referans_tarama(irtifa, sicaklik, hiz)  # 1 RPM aralıkla "gerçek" eğri
    sonuc = perturb_observe(olcum_fonksiyonu(irtifa, sicaklik, hiz))
    return devirler, yakitlar, sonuc


def ciz(ax, renk, etiket, devirler, yakitlar, sonuc):
    sade_eksen(ax, etiket)
    ax.set_ylabel("Yakıt debisi (PPH)", color=IKINCIL, fontsize=9)

    # Tarama sonucu: yakıt–devir eğrisi
    ax.plot(devirler, yakitlar, color=renk, linewidth=2, solid_capstyle="round", zorder=2)

    # Eksen aralığı: üstte bilgi kutusuna, altta optimum etiketine yer bırak
    alt, ust = np.nanmin(yakitlar), np.nanmax(yakitlar)
    taban = alt - 0.22 * (ust - alt)
    ax.set_ylim(taban, ust + 0.45 * (ust - alt))

    # Gerçek optimum: 1 RPM taramadaki en düşük yakıt. Eğriden eksene kesikli çizgi ile gösterilir.
    k = np.nanargmin(yakitlar)
    opt_devir, opt_yakit = devirler[k], yakitlar[k]
    ax.vlines(opt_devir, taban, opt_yakit, color=MUREKKEP, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
    kenarda = opt_devir > 1750  # sağ yarıdaysa etiket çizginin soluna
    ax.annotate(f"Gerçek optimum {opt_devir:g} RPM", (opt_devir, taban), xytext=(-5 if kenarda else 5, 4),
                textcoords="offset points", ha="right" if kenarda else "left", va="bottom",
                color=IKINCIL, fontsize=8)

    # Algoritmanın ölçümleri sırasıyla numaralı: kabul dolu, ret içi boş.
    # "limit" denemeleri ölçüm değildir, geçersiz ölçümlerin yakıtı yoktur; ikisi de çizilmez.
    olcumler = [g for g in sonuc.gecmis if g["neden"] != "limit"]
    numaralar = {}  # aynı devir birden çok kez ölçüldüyse numaralar tek etikette birleşir
    for sira, g in enumerate(olcumler, start=1):
        if g["yakit"] is None:
            continue
        ax.plot(g["devir"], g["yakit"], "o", ms=9, mfc=renk if g["kabul"] else ZEMIN,
                mec=renk, mew=2, zorder=4)
        numaralar.setdefault(g["devir"], (g["yakit"], []))[1].append(str(sira))
    for devir, (yakit, siralar) in numaralar.items():
        # Bulunan noktanın etiketi halkanın üstüne çıksın
        aralik = 12 if devir == sonuc.devir else 7
        ax.annotate(",".join(siralar), (devir, yakit), xytext=(0, aralik), textcoords="offset points",
                    ha="center", va="bottom", color=MUREKKEP, fontsize=8, zorder=6)

    # Bulunan nokta: koyu halka
    ax.plot(sonuc.devir, sonuc.yakit, "o", ms=17, mfc="none", mec=MUREKKEP, mew=1.5, zorder=5)

    # Bilgi kutusu, eğrinin alçak ucunun üstüne (boş köşe)
    sagda = yakitlar[-1] <= yakitlar[0]
    metin = (f"Gerçek optimum: {opt_devir:g} RPM · {opt_yakit:.2f} PPH\n"
             f"Bulunan: {sonuc.devir:g} RPM · {sonuc.yakit:.2f} PPH\n"
             f"Yakıt farkı: {sonuc.yakit - opt_yakit:+.3f} PPH · {sonuc.olcum_sayisi} ölçüm")
    ax.text(0.98 if sagda else 0.02, 0.96, metin, transform=ax.transAxes, ha="right" if sagda else "left",
            va="top", multialignment="left", fontsize=8.5, color=IKINCIL, linespacing=1.5,
            bbox=dict(boxstyle="round,pad=0.4", fc=ZEMIN, ec="none"), zorder=7)
    return opt_devir, opt_yakit


fig, eksenler = plt.subplots(2, 2, figsize=(12, 9), facecolor=ZEMIN)

satirlar = []
for ax, renk, kosul in zip(eksenler.flat, RENKLER, KOSULLAR):
    etiket = kosul_etiketi(*kosul)
    devirler, yakitlar, sonuc = kosulu_coz(*kosul)
    opt_devir, opt_yakit = ciz(ax, renk, etiket, devirler, yakitlar, sonuc)
    # Sabit 1900 RPM'deki yakıt: tasarrufun referansı
    sabit_yakit = yakitlar[devirler == SABIT_DEVIR][0]
    satirlar.append((etiket, sonuc, opt_devir, opt_yakit, sabit_yakit))

isaretler = [
    Line2D([], [], ls="", marker="o", ms=9, mfc=IKINCIL, mec=IKINCIL, mew=2, label="Kabul edilen ölçüm"),
    Line2D([], [], ls="", marker="o", ms=9, mfc=ZEMIN, mec=IKINCIL, mew=2, label="Reddedilen ölçüm"),
    Line2D([], [], ls="", marker="o", ms=15, mfc="none", mec=MUREKKEP, mew=1.5, label="Algoritmanın bulduğu devir"),
    Line2D([], [], color=MUREKKEP, linewidth=1, linestyle=(0, (4, 3)), label="Gerçek optimum (1 RPM tarama)"),
]
fig.legend(handles=isaretler, loc="upper left", bbox_to_anchor=(0.045, 0.925), ncol=4, frameon=False,
           fontsize=9, labelcolor=IKINCIL, handlelength=1.8, columnspacing=1.6)
fig.text(0.05, 0.975, "Perturb & observe en az yakıtlı devri buluyor", fontsize=15, color=MUREKKEP,
         weight="bold")
fig.text(0.05, 0.945, "1900 RPM'den 50 RPM adımla aşağı başlar; yakıt artınca geri döner ve adımı yarıya "
         "indirir, adım 10 RPM'in altına düşünce durur. Numaralar ölçüm sırası.", fontsize=10, color=IKINCIL)
fig.tight_layout(rect=(0.03, 0, 1, 0.9), h_pad=2.5, w_pad=3)

# Özet tablo
print(f"{'Koşul':<26}{'Bulunan':>9}{'Optimum':>9}{'Yakıt farkı':>13}"
      f"{'1900 RPM’e göre tasarruf':>27}{'Ölçüm':>7}")
print(f"{'':<26}{'(RPM)':>9}{'(RPM)':>9}{'(PPH)':>13}{'(PPH)':>15}{'(%)':>12}{'':>7}")
for etiket, sonuc, opt_devir, opt_yakit, sabit_yakit in satirlar:
    tasarruf = sabit_yakit - sonuc.yakit
    print(f"{etiket:<26}{sonuc.devir:>9g}{opt_devir:>9g}{sonuc.yakit - opt_yakit:>13.3f}"
          f"{tasarruf:>15.2f}{100 * tasarruf / sabit_yakit:>12.2f}{sonuc.olcum_sayisi:>7}")

cikti = Path(__file__).with_name("adim4_algoritma.png")
try:
    fig.savefig(cikti, dpi=150, facecolor=ZEMIN)
    print(f"\nGrafik kaydedildi: analiz/{cikti.name}")
except OSError:
    # Windows, dosya başka bir programda (ör. Fotoğraflar) açıkken üzerine yazdırmıyor
    print(f"\n{cikti.name} kaydedilemedi: dosya başka bir programda açık olabilir. Kapatıp tekrar çalıştır.")
plt.show()
