"""
Adım 6: Gerçekçi ölçüm altında net kazanç.

Ölçüm artık anında ve kusursuz değil (olcum.GercekciOlcum): devir değişince motor gecikmeyle
oturur, ölçmeden önce beklenir, gürültülü örneklerin ortalaması alınır. Soru: devri arama
sırasında oynatmanın maliyeti dahil, algoritma sabit 1900 RPM'e göre net kazanç sağlıyor mu?

VARSAYIMLAR (gerçek motor/sensör verisine dayanmıyor):
- Motor gecikmesi birinci derece, zaman sabiti tau = 2 s; her yeni devirde 3·tau = 6 s beklenir
- Sensör gürültüsü beyaz Gauss, standart sapma gerçek yakıtın %0,5'i ya da %1'i
- Örnekleme 10 Hz
- Her koşu 10 dakikalık seyir: 1900 RPM'den arama, bulunan devre dönüş, süre bitene kadar orada kalma

Deney A: 4 koşul × 12 parametre kombinasyonu × 30 tohum
Deney B: Deney A'nın en iyi kombinasyonuyla Adım 5'teki bütün koşullar × 5 tohum
Çıktılar sonuclar/ klasörüne yazılır, özet konsola basılır.
"""
import itertools
import sys
from multiprocessing import Pool
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))  # kök dizindeki modüller (algoritma, olcum, sanal_ucak, adim3_grafik) bulunsun

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, Normalize, TwoSlopeNorm, to_rgb
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

from adim3_grafik import IKINCIL, IZGARA, EKSEN, KOSULLAR, MUREKKEP, RENKLER, SOLUK, ZEMIN, kosul_etiketi, sade_eksen
from algoritma import perturb_observe
from analiz.adim5 import MAVI, TURUNCU
from olcum import GercekciOlcum, olcum_fonksiyonu, referans_tarama

SONUC_KLASORU = KOK / "sonuclar"
SEYIR_S = 600          # 10 dakikalık seyir
TAU_S = 2.0            # VARSAYIM: motor zaman sabiti
TOLERANS_PPH = 0.5     # başarı: bulunan devirdeki gerçek yakıt referanstan en fazla bu kadar fazla
SABIT_DEVIR = 1900

# Deney A parametre ızgarası
GURULTULER = [0.5, 1.0]   # VARSAYIM: sensör gürültüsü, gerçek değerin yüzdesi (standart sapma)
ORTALAMALAR = [2, 5, 10]  # ölçüm ortalaması süresi (s)
ESIKLER = [0, 0.5]        # algoritmanın "daha iyi" eşiği (PPH)
TOHUM_A, TOHUM_B = 30, 5

# Net tasarruf ısı haritası: iki uçlu (kayıp kırmızı, kazanç mavi, sıfır nötr gri)
IKI_UCLU = LinearSegmentedColormap.from_list(
    "kayip_kazanc", ["#a32d2b", "#e34948", "#f4b8b7", "#f0efec", "#9ec5f4", "#2a78d6", "#184f95"])


# ---------------------------------------------------------------- tek koşu

def simule_et(irtifa, sicaklik, hiz, gurultu_yuzde, ortalama_s, esik_pph, seed, tau_s=TAU_S):
    """Bir koşu: 1900 RPM'den arama, bulunan devre dönüş, seyir süresi bitene kadar orada kalma.
    Döndürür: (ölçüm sistemi, algoritma sonucu, arama bitiş zamanı s)."""
    olc = GercekciOlcum(irtifa, sicaklik, hiz, tau_s=tau_s, ortalama_s=ortalama_s,
                        gurultu_yuzde=gurultu_yuzde, seed=seed)
    sonuc = perturb_observe(olc, baslangic_devir=1900, baslangic_adim=50, en_kucuk_adim=10, esik_pph=esik_pph)
    arama_bitis = olc.t
    # Son ölçülen devir reddedilmiş olabilir: bulunan devre geri dön ve süre bitene kadar orada kal
    olc.devam_et(sonuc.devir, SEYIR_S)
    return olc, sonuc, arama_bitis


def kosu_yap(is_):
    """Tek koşunun bütün ölçütleri. Paralel çalışabilsin diye üst düzey fonksiyon.
    is_: koşul, parametreler, seed ve ref_yakit_pph (gürültüsüz en düşük yakıt)."""
    olc, sonuc, arama_bitis = simule_et(is_["irtifa_ft"], is_["sicaklik_C"], is_["hiz_kt"], is_["gurultu_yuzde"],
                                        is_["ortalama_s"], is_["esik_pph"], is_["seed"])
    kayit = olc.kayit()
    t, gercek = kayit.t_s.to_numpy(), kayit.gercek_yakit.to_numpy()
    # Gürültüsüz test dünyası: 1900 RPM yakıtı ve bulunan devirdeki gerçek yakıt buradan (yuvarlanmamış)
    ideal = olcum_fonksiyonu(is_["irtifa_ft"], is_["sicaklik_C"], is_["hiz_kt"])
    y1900 = ideal(SABIT_DEVIR)

    # Yakılan yakıt: her kayıt satırı dt saniyelik bir aralık; PPH × s / 3600 = lb
    seyirde = t <= SEYIR_S + 1e-9
    yakilan_lb = gercek[seyirde].sum() * olc.dt / 3600
    sabit_lb = y1900 * SEYIR_S / 3600
    net_lb = sabit_lb - yakilan_lb

    # Arama maliyeti: arama süresince sabit 1900'e göre fazladan yakılan (negatifse kazanç)
    aramada = t <= arama_bitis + 1e-9
    arama_maliyeti_lb = (gercek[aramada] - y1900).sum() * olc.dt / 3600

    # Bulunan devirdeki gerçek (gürültüsüz) yakıt ve oradaki kararlı kazanç hızı
    bulunan_gercek = ideal(sonuc.devir)
    kararli_kazanc_pph = y1900 - bulunan_gercek
    # Başabaş: arama bittikten sonra, kararlı kazancın arama maliyetini karşılama süresi
    if arama_maliyeti_lb <= 0:
        basabas_s = 0.0           # arama zaten kârda bitti
    elif kararli_kazanc_pph > 0:
        basabas_s = arama_maliyeti_lb / kararli_kazanc_pph * 3600
    else:
        basabas_s = np.inf        # bulunan devir 1900'den iyi değil: maliyet hiç karşılanmaz

    fark = bulunan_gercek - is_["ref_yakit_pph"]
    return dict(
        {k: v for k, v in is_.items() if k != "seed"},
        bulunan_devir_rpm=sonuc.devir,
        bulunan_gercek_yakit_pph=bulunan_gercek,
        yakit_farki_pph=fark,
        basari=bool(fark <= TOLERANS_PPH),
        yakit_1900_pph=y1900,
        yakinsama_s=arama_bitis,
        olcum_sayisi=sonuc.olcum_sayisi,
        olcum_limiti_doldu=sonuc.durma_nedeni == "ölçüm limiti doldu",
        arama_maliyeti_lb=arama_maliyeti_lb,
        kararli_kazanc_pph=kararli_kazanc_pph,
        net_tasarruf_lb=net_lb,
        net_tasarruf_pph=net_lb / (SEYIR_S / 3600),  # 10 dakikadaki tasarrufun saatlik karşılığı
        net_tasarruf_yuzde=100 * net_lb / sabit_lb,
        basabas_s=basabas_s,
    )


def paralel(isler):
    with Pool() as havuz:
        return pd.DataFrame(havuz.map(kosu_yap, isler, chunksize=8))


# ---------------------------------------------------------------- deneyler

def deney_a():
    """4 koşul × 12 kombinasyon × 30 tohum. Aynı koşul ve tohum bütün kombinasyonlarda aynı seed'i kullanır."""
    isler = []
    for kosul_no, (irtifa, sicaklik, hiz) in enumerate(KOSULLAR):
        devirler, yakitlar = referans_tarama(irtifa, sicaklik, hiz)  # gürültüsüz 1 RPM referans
        ref = float(np.nanmin(yakitlar))
        for gurultu, ortalama, esik in itertools.product(GURULTULER, ORTALAMALAR, ESIKLER):
            for tohum in range(TOHUM_A):
                isler.append(dict(irtifa_ft=irtifa, sicaklik_C=sicaklik, hiz_kt=hiz, gurultu_yuzde=gurultu,
                                  ortalama_s=ortalama, esik_pph=esik, tohum=tohum, seed=[1, kosul_no, tohum],
                                  ref_yakit_pph=ref))
    return paralel(isler)


def kombinasyon_ozeti(df):
    """Her parametre kombinasyonu için başarı oranı ve ortalama ölçütler."""
    return df.groupby(["gurultu_yuzde", "ortalama_s", "esik_pph"]).agg(
        basari_orani=("basari", "mean"),
        net_tasarruf_pph=("net_tasarruf_pph", "mean"),
        net_tasarruf_yuzde=("net_tasarruf_yuzde", "mean"),
        yakinsama_s=("yakinsama_s", "mean"),
        olcum_sayisi=("olcum_sayisi", "mean"),
        arama_maliyeti_lb=("arama_maliyeti_lb", "mean"),
        net_kayip_orani=("net_tasarruf_lb", lambda s: (s < 0).mean()),
    ).reset_index()


def en_iyi_kombinasyon(ozet, gurultu):
    """Seçim ölçütü: verilen gürültü düzeyinde, başarı oranı en yükseğe en fazla 5 puan yakın
    olan kombinasyonlar arasından ortalama net tasarrufu en büyük olan."""
    aday = ozet[ozet.gurultu_yuzde == gurultu]
    aday = aday[aday.basari_orani >= aday.basari_orani.max() - 0.05]
    return aday.loc[aday.net_tasarruf_pph.idxmax()]


def deney_b(ortalama_s, esik_pph, gurultu_yuzde):
    """Adım 5'teki bütün koşullar × 5 tohum, seçilen kombinasyonla."""
    zarf = pd.read_csv(SONUC_KLASORU / "zarf_sonuclari.csv")
    isler = []
    for kosul_no, s in zarf.iterrows():
        for tohum in range(TOHUM_B):
            isler.append(dict(irtifa_ft=int(s.irtifa_ft), agirlik_lb=int(s.agirlik_lb), sicaklik_C=int(s.sicaklik_C),
                              hiz_kt=int(s.hiz_kt), hiz_konumu=s.hiz_konumu, optimum_limitte=s.optimum_limitte,
                              ideal_tasarruf_pph=s.tasarruf_pph, gurultu_yuzde=gurultu_yuzde, ortalama_s=ortalama_s,
                              esik_pph=esik_pph, tohum=tohum, seed=[2, kosul_no, tohum],
                              ref_yakit_pph=s.ref_yakit_pph))
    return paralel(isler)


# ---------------------------------------------------------------- grafikler

def kaydet(fig, dosya):
    try:
        fig.savefig(dosya, dpi=150, facecolor=ZEMIN)
        print(f"Grafik kaydedildi: sonuclar/{dosya.name}")
    except OSError:
        # Windows, dosya başka bir programda (ör. Fotoğraflar) açıkken üzerine yazdırmıyor
        print(f"{dosya.name} kaydedilemedi: dosya başka bir programda açık olabilir. Kapatıp tekrar çalıştır.")


def basliklar(fig, baslik, alt_baslik, y=0.965):
    fig.text(0.05, y, baslik, fontsize=15, color=MUREKKEP, weight="bold")
    fig.text(0.05, y - 0.04, alt_baslik, fontsize=10, color=IKINCIL)


def zaman_serisi_grafigi(gurultu, ortalama, esik, dosya):
    """Grafik 1: 2000 ft, 10 °C, 161 kt'ta tek bir koşu (Deney A'daki tohum 0)."""
    kosul_no = 1
    irtifa, sicaklik, hiz = KOSULLAR[kosul_no]
    renk = RENKLER[kosul_no]
    olc, sonuc, arama_bitis = simule_et(irtifa, sicaklik, hiz, gurultu, ortalama, esik, seed=[1, kosul_no, 0])
    k = olc.kayit()
    devirler, yakitlar = referans_tarama(irtifa, sicaklik, hiz)
    i = np.nanargmin(yakitlar)
    ref_devir, ref_yakit, y1900 = devirler[i], yakitlar[i], yakitlar[devirler == SABIT_DEVIR][0]

    # t = 0'da 1900 RPM'de kararlı seyir
    t = np.r_[0.0, k.t_s]
    komut = np.r_[SABIT_DEVIR, k.komut_devir]
    gercek = np.r_[y1900, k.gercek_yakit]
    son = min(SEYIR_S, arama_bitis + 60)
    gorunen = k.t_s <= son

    fig, (ust, alt) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, facecolor=ZEMIN,
                                   gridspec_kw=dict(height_ratios=[1, 1.7]))
    for ax in (ust, alt):
        sade_eksen(ax, "")
        ax.set_xticks(np.arange(0, son + 1, 10))
        ax.set_xlim(0, son)
        ax.set_xlabel("")
    alt.set_xlabel("Zaman (s)", color=IKINCIL, fontsize=9)

    # Üst: komut edilen devir
    ust.plot(t, komut, drawstyle="steps-pre", color=MUREKKEP, linewidth=2)
    ust.axhline(ref_devir, color=IKINCIL, linewidth=1, linestyle=":")
    ust.text(son, ref_devir, f"Referans optimum {ref_devir} RPM ", ha="right", va="bottom", fontsize=8.5, color=IKINCIL)
    ust.set_ylabel("Komut edilen devir (RPM)", color=IKINCIL, fontsize=9)
    ust.set_yticks(np.arange(1700, 1951, 50))
    ust.set_ylim(min(komut[t <= son].min(), ref_devir) - 25, 1925)

    # Alt: sensör okumaları, gerçek yakıt, ölçüm ortalamaları
    alt.plot(k.t_s[gorunen], k.olculen_yakit[gorunen], "o", ms=1.6, color=SOLUK, alpha=0.5, zorder=1)
    alt.plot(t[t <= son], gercek[t <= son], color=renk, linewidth=2, zorder=3)
    olculenler = [g for g in sonuc.gecmis if g["neden"] != "limit"]
    o = k.ornek.to_numpy()
    baslar = np.flatnonzero(o & ~np.r_[False, o[:-1]])
    bitisler = np.flatnonzero(o & ~np.r_[o[1:], False])
    assert len(baslar) == len(olculenler)  # her ölçüm bir örnekleme penceresi
    for b, e, g in zip(baslar, bitisler, olculenler):
        t0, t1 = k.t_s[b] - olc.dt, k.t_s[e]
        alt.plot([t0, t1], [g["yakit"]] * 2, color=MUREKKEP, linewidth=2.5, zorder=4)
        alt.plot(t1, g["yakit"], "o", ms=7, mfc=MUREKKEP if g["kabul"] else ZEMIN, mec=MUREKKEP, mew=1.8, zorder=5)
    alt.axhline(y1900, color=IKINCIL, linewidth=1, linestyle="--", zorder=2)
    alt.axhline(ref_yakit, color=IKINCIL, linewidth=1, linestyle=":", zorder=2)
    etiket_kutusu = dict(boxstyle="round,pad=0.2", fc=ZEMIN, ec="none")
    alt.text(son, y1900, f"Sabit 1900 RPM: {y1900:.1f} PPH ", ha="right", va="bottom", fontsize=8.5, color=IKINCIL,
             bbox=etiket_kutusu, zorder=7)
    alt.text(son, ref_yakit, f"Referans en düşük: {ref_yakit:.1f} PPH ", ha="right", va="top", fontsize=8.5,
             color=IKINCIL, bbox=etiket_kutusu, zorder=7)
    alt.set_ylabel("Yakıt debisi (PPH)", color=IKINCIL, fontsize=9)
    alt.set_ylim(np.percentile(k.olculen_yakit[gorunen], [0.5, 99.5]) + np.array([-1, 1]))

    # Arama bitişi
    for ax in (ust, alt):
        ax.axvline(arama_bitis, color=MUREKKEP, linewidth=1.2, linestyle=(0, (4, 3)), zorder=6)
    ust.text(arama_bitis + 1, 1915, f"Arama bitti: {arama_bitis:.0f} s, {sonuc.olcum_sayisi} ölçüm → "
             f"{sonuc.devir:g} RPM", ha="left", va="top", fontsize=9, color=MUREKKEP)

    isaretler = [
        Line2D([], [], color=renk, linewidth=2, label="Gerçek yakıt (gürültüsüz)"),
        Line2D([], [], ls="", marker="o", ms=4, color=SOLUK, label="Sensör okuması (10 Hz)"),
        Line2D([], [], color=MUREKKEP, linewidth=2.5, marker="o", ms=7, mfc=MUREKKEP, label="Ölçüm ortalaması, kabul"),
        Line2D([], [], color=MUREKKEP, linewidth=2.5, marker="o", ms=7, mfc=ZEMIN, label="Ölçüm ortalaması, ret"),
    ]
    fig.legend(handles=isaretler, loc="upper left", bbox_to_anchor=(0.045, 0.9), ncol=4, frameon=False,
               fontsize=9, labelcolor=IKINCIL, handlelength=2)
    basliklar(fig, f"Gürültülü ölçümle tek bir arama: {kosul_etiketi(irtifa, sicaklik, hiz)}",
              f"Gürültü %{gurultu:g}, ortalama {ortalama:g} s, eşik {esik:g} PPH. VARSAYIM: tau = {TAU_S:g} s, "
              f"yeni devirde {3 * TAU_S:g} s bekleme, 10 Hz. Aramadan sonra devir {SEYIR_S // 60} dk dolana kadar sabit.")
    fig.tight_layout(rect=(0.03, 0, 1, 0.86), h_pad=1.5)
    kaydet(fig, dosya)


def parametre_grafigi(ozet, secilen, dosya):
    """Grafik 2: kombinasyonlara göre başarı oranı, ortalama net tasarruf ve arama süresi (ısı haritası)."""
    satirlar = [(g, e) for g in GURULTULER for e in ESIKLER]
    etiketler = [f"Gürültü %{g:g} · eşik {e:g} PPH" for g, e in satirlar]
    m = ozet.net_tasarruf_pph.abs().max()
    paneller = [
        ("basari_orani", "Başarı oranı (%)", MAVI, Normalize(50, 100), 100, "{:.0f}"),
        ("net_tasarruf_pph", "Ortalama net tasarruf (PPH)", IKI_UCLU, TwoSlopeNorm(0, -m, m), 1, "{:.2f}"),
        ("yakinsama_s", "Ortalama arama süresi (s)", TURUNCU, Normalize(0, ozet.yakinsama_s.max()), 1, "{:.0f}"),
    ]
    fig, eksenler = plt.subplots(1, 3, figsize=(16, 5.6), facecolor=ZEMIN, sharey=True)
    for ax, (sutun, baslik, cmap, norm, carpan, bicim) in zip(eksenler, paneller):
        izgara = np.array([[ozet[(ozet.gurultu_yuzde == g) & (ozet.esik_pph == e) & (ozet.ortalama_s == o)]
                            [sutun].iloc[0] * carpan for o in ORTALAMALAR] for g, e in satirlar])
        harita = ax.pcolormesh(np.arange(len(ORTALAMALAR) + 1) - 0.5, np.arange(len(satirlar) + 1) - 0.5, izgara,
                               cmap=cmap, norm=norm, edgecolors=ZEMIN, linewidth=2)
        for i in range(len(satirlar)):
            for j in range(len(ORTALAMALAR)):
                r, g_, b = to_rgb(cmap(norm(izgara[i, j])))
                yazi = "white" if 0.2126 * r + 0.7152 * g_ + 0.0722 * b < 0.5 else MUREKKEP
                ax.text(j, i, bicim.format(izgara[i, j]), ha="center", va="center", fontsize=10, color=yazi)
                # Seçilen ayar (ortalama süresi, eşik) her iki gürültü düzeyinde çerçeveli
                if ORTALAMALAR[j] == secilen["ortalama_s"] and satirlar[i][1] == secilen["esik_pph"]:
                    ax.add_patch(Rectangle((j - 0.47, i - 0.47), 0.94, 0.94, fill=False, ec=MUREKKEP, lw=2.2))
        ax.set_facecolor(ZEMIN)
        ax.set_title(baslik, loc="left", color=MUREKKEP, fontsize=11, pad=10)
        ax.set_xticks(range(len(ORTALAMALAR)), [f"{o} s" for o in ORTALAMALAR])
        ax.set_yticks(range(len(satirlar)), etiketler)
        ax.invert_yaxis()
        ax.set_xlabel("Ölçüm ortalaması süresi", color=IKINCIL, fontsize=9)
        ax.tick_params(colors=SOLUK, length=0, labelsize=9)
        for kenar in ax.spines.values():
            kenar.set_visible(False)
        cb = fig.colorbar(harita, ax=ax, fraction=0.05, pad=0.03)
        cb.outline.set_visible(False)
        cb.ax.tick_params(colors=SOLUK, length=0, labelsize=8)
    basliklar(fig, "Ölçüm ortalaması uzadıkça başarı artıyor, eşik ise kazandırmıyor",
              f"Deney A: 4 koşul × {TOHUM_A} tohum (kombinasyon başına {4 * TOHUM_A} koşu), {SEYIR_S // 60} dakikalık "
              f"seyir. Çerçeve: seçilen ayar (ortalama {secilen['ortalama_s']:g} s, eşik {secilen['esik_pph']:g} PPH).",
              y=0.95)
    fig.tight_layout(rect=(0.03, 0, 1, 0.84), w_pad=2)
    kaydet(fig, dosya)


def histogram_grafigi(kosul, gurultu, ortalama, esik, dosya):
    """Grafik 3: tüm zarfta koşul başına ortalama net tasarrufun dağılımı."""
    fig, ax = plt.subplots(figsize=(12, 5.8), facecolor=ZEMIN)
    sade_eksen(ax, "Koşul sayısı")
    ax.set_xticks(np.arange(-1, 7))
    alt_sinir = np.floor(min(kosul.net_tasarruf_pph.min(), 0) * 4) / 4
    ust_sinir = np.ceil(max(kosul.net_tasarruf_pph.max(), kosul.ideal_tasarruf_pph.max()) * 4) / 4
    kutular = np.arange(alt_sinir, ust_sinir + 0.25, 0.25)  # 0 bir kutu sınırı: kayıp ve kazanç ayrı kutularda
    _, _, cubuklar = ax.hist(kosul.net_tasarruf_pph, kutular, color="#2a78d6", ec=ZEMIN, lw=1.5, zorder=2)
    for c in cubuklar:
        if c.get_x() < 0:
            c.set_facecolor("#e34948")
    ax.hist(kosul.ideal_tasarruf_pph, kutular, histtype="step", color=MUREKKEP, lw=1.5, zorder=3)
    ax.axvline(0, color=MUREKKEP, linewidth=1.2, linestyle=(0, (4, 3)), zorder=4)
    ax.set_xlim(kutular[0] - 0.1, kutular[-1] + 0.1)
    ax.set_xlabel(f"{SEYIR_S // 60} dakikalık seyirde net tasarruf (PPH karşılığı)", color=IKINCIL, fontsize=9)

    kayip = kosul.net_tasarruf_pph < 0
    ax.annotate(f"Net kayıp: {kayip.sum()} koşul (%{100 * kayip.mean():.0f})\n"
                f"en kötü {kosul.net_tasarruf_pph.min():.2f} PPH", (0, ax.get_ylim()[1] * 0.92), xytext=(-8, 0),
                textcoords="offset points", ha="right", va="top", fontsize=9, color=MUREKKEP)
    isaretler = [
        Rectangle((0, 0), 1, 1, fc="#2a78d6", label="Net kazanç (koşul başına 5 tohum ortalaması)"),
        Rectangle((0, 0), 1, 1, fc="#e34948", label="Net kayıp"),
        Line2D([], [], color=MUREKKEP, lw=1.5, label="Gürültüsüz, aramasız potansiyel (Adım 5)"),
    ]
    fig.legend(handles=isaretler, loc="upper left", bbox_to_anchor=(0.045, 0.875), ncol=3, frameon=False,
               fontsize=9, labelcolor=IKINCIL, handlelength=1.6)
    basliklar(fig, "Tüm uçuş zarfında net tasarrufun dağılımı",
              f"{len(kosul)} koşul. Gürültü %{gurultu:g}, ortalama {ortalama:g} s, eşik {esik:g} PPH. "
              f"VARSAYIM: tau = {TAU_S:g} s, 10 Hz örnekleme. Arama maliyeti dahil, sabit 1900 RPM'e göre.")
    fig.tight_layout(rect=(0.03, 0, 1, 0.82))
    kaydet(fig, dosya)


# ---------------------------------------------------------------- özet

def ozet_yazdir(ozet_a, secilen, gurultu_b, b, kosul):
    print("=" * 78)
    print("ADIM 6: GERÇEKÇİ ÖLÇÜMLE NET KAZANÇ")
    print("=" * 78)
    print(f"VARSAYIMLAR: motor zaman sabiti tau = {TAU_S:g} s (her yeni devirde {3 * TAU_S:g} s bekleme), "
          f"sensör gürültüsü\n  beyaz Gauss (std = gerçek yakıtın yüzdesi, örnekler bağımsız), örnekleme 10 Hz, "
          f"seyir {SEYIR_S // 60} dk, başlangıç 1900 RPM.")

    print(f"\nDENEY A: 4 koşul × {TOHUM_A} tohum (kombinasyon başına {4 * TOHUM_A} koşu)")
    print(f"  {'Gürültü':>8}{'Ort. (s)':>9}{'Eşik':>6}{'Başarı':>8}{'Net (PPH)':>11}{'Net (%)':>9}"
          f"{'Arama (s)':>11}{'Ölçüm':>7}{'Arama mal. (lb)':>17}{'Net kayıp':>11}")
    for _, s in ozet_a.iterrows():
        isaret = "  ←" if (s.ortalama_s == secilen["ortalama_s"] and s.esik_pph == secilen["esik_pph"]) else ""
        print(f"  {'%' + format(s.gurultu_yuzde, 'g'):>8}{s.ortalama_s:>9g}{s.esik_pph:>6g}{100 * s.basari_orani:>7.0f}%"
              f"{s.net_tasarruf_pph:>11.2f}{s.net_tasarruf_yuzde:>9.2f}{s.yakinsama_s:>11.0f}{s.olcum_sayisi:>7.1f}"
              f"{s.arama_maliyeti_lb:>17.3f}{100 * s.net_kayip_orani:>10.0f}%{isaret}")

    print(f"\nSEÇİLEN AYAR: ölçüm ortalaması {secilen['ortalama_s']:g} s, eşik {secilen['esik_pph']:g} PPH")
    print("  Ölçüt: her gürültü düzeyinde, başarı oranı en yükseğe en fazla 5 puan yakın olanlar arasından\n"
          "  ortalama net tasarrufu en büyük olan. İki gürültü düzeyinde de aynı ayar seçildi.")
    print(f"  Gürültü bizim seçebileceğimiz bir ayar değil, bir varsayım. Deney B kötümser düzeyle (%{gurultu_b:g}) "
          f"çalıştırıldı.")

    basari = b.basari.mean()
    kayip = kosul.net_tasarruf_pph < 0
    print(f"\nDENEY B: {len(kosul)} koşul × {TOHUM_B} tohum = {len(b)} koşu (gürültü %{gurultu_b:g})")
    print(f"  Başarı oranı (koşu)            : %{100 * basari:.1f} (fark ≤ {TOLERANS_PPH} PPH), "
          f"en büyük fark {b.yakit_farki_pph.max():.2f} PPH")
    print(f"  Net tasarruf (koşul ortalaması)  {'PPH':>8}{'%':>8}")
    for ad, islem in [("Ortalama", "mean"), ("Medyan", "median"), ("En düşük", "min"), ("En yüksek", "max")]:
        print(f"    {ad:<30}{getattr(kosul.net_tasarruf_pph, islem)():>8.2f}"
              f"{getattr(kosul.net_tasarruf_yuzde, islem)():>8.2f}")
    print(f"    {'İdeal (Adım 5) ortalama':<30}{kosul.ideal_tasarruf_pph.mean():>8.2f}"
          f"{kosul.ideal_tasarruf_yuzde.mean():>8.2f}  (gürültüsüz, aramasız)")
    print(f"  Arama süresi                   : ortalama {b.yakinsama_s.mean():.0f} s, en fazla "
          f"{b.yakinsama_s.max():.0f} s; ölçüm sayısı ortalama {b.olcum_sayisi.mean():.1f}, "
          f"limit dolan {b.olcum_limiti_doldu.sum()} koşu")
    print(f"  Arama maliyeti                 : ortalama {b.arama_maliyeti_lb.mean():+.3f} lb "
          f"(koşuların %{100 * (b.arama_maliyeti_lb > 0).mean():.0f}'inde pozitif)")
    sonlu = b.basabas_s[np.isfinite(b.basabas_s) & (b.basabas_s > 0)]
    print(f"  Başabaş süresi                 : maliyetli koşularda medyan {sonlu.median():.0f} s; "
          f"{np.isinf(b.basabas_s).sum()} koşuda hiç karşılanmıyor")
    print(f"  NET KAYIP                      : koşulların %{100 * kayip.mean():.1f}'inde ({kayip.sum()} koşul), "
          f"koşuların %{100 * (b.net_tasarruf_pph < 0).mean():.1f}'inde")
    if kayip.any():
        print(f"    Kayıp koşullarda ortalama {kosul.net_tasarruf_pph[kayip].mean():.3f} PPH "
              f"(%{kosul.net_tasarruf_yuzde[kayip].mean():.3f}), en kötü {kosul.net_tasarruf_pph.min():.3f} PPH")

    print("\n  Net kaybın yoğunlaştığı yer")
    potansiyel = pd.cut(kosul.ideal_tasarruf_pph, [-np.inf, 0.005, 0.5, 2, np.inf],
                        labels=["0 (optimum ≈ 1900)", "0-0,5 PPH", "0,5-2 PPH", "> 2 PPH"])
    gruplar = [("İdeal tasarruf potansiyeline göre", potansiyel),
               ("Referans optimumun yerine göre", kosul.optimum_limitte.map(
                   {"1900": "1900 RPM (limit)", "1600": "1600 RPM (limit)", "arada": "arada"})),
               ("İrtifaya göre", pd.cut(kosul.irtifa_ft, [0, 6000, 12000, 18000, 24000],
                                        labels=["2.000-6.000 ft", "8.000-12.000 ft", "14.000-18.000 ft",
                                                "20.000-24.000 ft"]))]
    for baslik, anahtar in gruplar:
        print(f"    {baslik}:")
        tablo = kosul.groupby(anahtar, observed=True).agg(koşul=("net_tasarruf_pph", "size"),
                                                           kayip=("net_tasarruf_pph", lambda s: (s < 0).sum()),
                                                           net=("net_tasarruf_pph", "mean"))
        for ad, s in tablo.iterrows():
            print(f"      {ad:<22} {s.kayip:>4.0f}/{s['koşul']:<4.0f} kayıp (%{100 * s.kayip / s['koşul']:4.0f}),"
                  f" ortalama net {s.net:+.2f} PPH")


# ---------------------------------------------------------------- ana akış

if __name__ == "__main__":
    SONUC_KLASORU.mkdir(exist_ok=True)

    # Deney A
    print(f"Deney A: {4 * 12 * TOHUM_A} koşu (paralel)...")
    a = deney_a()
    a.round(4).to_csv(SONUC_KLASORU / "adim6_parametre_taramasi.csv", index=False)
    ozet_a = kombinasyon_ozeti(a)
    secimler = [en_iyi_kombinasyon(ozet_a, g) for g in GURULTULER]
    secilen = secimler[-1]  # kötümser gürültü düzeyindeki seçim
    if any((s.ortalama_s, s.esik_pph) != (secilen.ortalama_s, secilen.esik_pph) for s in secimler):
        print("UYARI: gürültü düzeylerinde farklı ayarlar seçildi; Deney B kötümser düzeyin seçimini kullanıyor.")
    gurultu_b = max(GURULTULER)

    # Deney B
    print(f"Deney B: {392 * TOHUM_B} koşu (paralel)...")
    b = deney_b(secilen.ortalama_s, secilen.esik_pph, gurultu_b)
    b.round(4).to_csv(SONUC_KLASORU / "adim6_zarf_kosular.csv", index=False)
    kosul = b.groupby(["irtifa_ft", "agirlik_lb", "sicaklik_C", "hiz_kt"], sort=False).agg(
        hiz_konumu=("hiz_konumu", "first"), optimum_limitte=("optimum_limitte", "first"),
        ideal_tasarruf_pph=("ideal_tasarruf_pph", "first"), yakit_1900_pph=("yakit_1900_pph", "first"),
        net_tasarruf_pph=("net_tasarruf_pph", "mean"), net_tasarruf_yuzde=("net_tasarruf_yuzde", "mean"),
        net_en_dusuk_pph=("net_tasarruf_pph", "min"), net_en_yuksek_pph=("net_tasarruf_pph", "max"),
        basari_orani=("basari", "mean"), yakinsama_s=("yakinsama_s", "mean"), olcum_sayisi=("olcum_sayisi", "mean"),
        arama_maliyeti_lb=("arama_maliyeti_lb", "mean"),
    ).reset_index()
    kosul["ideal_tasarruf_yuzde"] = 100 * kosul.ideal_tasarruf_pph / kosul.yakit_1900_pph
    kosul["net_kayip"] = kosul.net_tasarruf_pph < 0
    kosul.round(4).to_csv(SONUC_KLASORU / "adim6_zarf.csv", index=False)

    ozet_yazdir(ozet_a, secilen, gurultu_b, b, kosul)
    print("\nTablolar kaydedildi: sonuclar/adim6_parametre_taramasi.csv, sonuclar/adim6_zarf.csv "
          "(koşul başına), sonuclar/adim6_zarf_kosular.csv (koşu başına)")

    zaman_serisi_grafigi(gurultu_b, secilen.ortalama_s, secilen.esik_pph,
                         SONUC_KLASORU / "adim6_zaman_serisi.png")
    parametre_grafigi(ozet_a, secilen, SONUC_KLASORU / "adim6_parametre_karsilastirma.png")
    histogram_grafigi(kosul, gurultu_b, secilen.ortalama_s, secilen.esik_pph,
                      SONUC_KLASORU / "adim6_net_tasarruf_dagilimi.png")
    plt.show()
