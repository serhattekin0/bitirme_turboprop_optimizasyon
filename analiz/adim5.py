"""
Adım 5: Perturb & observe algoritmasını POH tablosundaki bütün uçuş zarfında çalıştırır.

Koşullar:
- CSV'deki her irtifa–sıcaklık (ara değer yok, yalnızca tablodaki değerler)
- Her biri için üç devrin de (1600/1750/1900) ulaşabildiği ortak hız aralığı;
  bu aralıkta 5 kt arayla hızlar, iki uç dahil. Ortak aralık boşsa koşul atlanır.

Her koşulda 1 RPM taramayla referans optimum bulunur, algoritma 1900 RPM'den başlatılır.
Çıktılar sonuclar/ klasörüne yazılır:
- zarf_sonuclari.csv, sabit_cizelge.csv
- optimum_devir_isi_haritasi.png, tasarruf_isi_haritasi.png
Konsola özet yazdırılır. Referans tarama yavaş olduğu için koşullar paralel çözülür.
"""
import sys
from multiprocessing import Pool
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))  # kök dizindeki modüller (algoritma, olcum, sanal_ucak, adim3_grafik) bulunsun

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, Normalize, to_rgb

from adim3_grafik import EKSEN, IKINCIL, MUREKKEP, SOLUK, ZEMIN
from algoritma import perturb_observe
from olcum import olcum_fonksiyonu, referans_tarama
from sanal_ucak import CSV_YOLU, DEVIRLER

SONUC_KLASORU = KOK / "sonuclar"
HIZ_ARALIGI = 5        # kt, ortak hız aralığında seçilen hızlar arası
TOLERANS_PPH = 0.5     # başarı ölçütü: referans en düşük yakıttan en fazla bu kadar fazla
ALT_LIMIT, UST_LIMIT = DEVIRLER[0], DEVIRLER[-1]
SABIT_DEVIR = 1900     # tasarrufun referansı: devir hiç değiştirilmeseydi

# Isı haritası renkleri: tek renk tonunda açıktan koyuya (adım 3'ün mavisi ve turuncusu)
MAVI = LinearSegmentedColormap.from_list("mavi", ["#cde2fb", "#86b6ef", "#2a78d6", "#1c5cab", "#0d366b"])
TURUNCU = LinearSegmentedColormap.from_list("turuncu", ["#fbe3d8", "#f5b294", "#eb6834", "#b8461b", "#7a2c0e"])


# ---------------------------------------------------------------- koşullar

def ortak_hiz_araligi(kosul_tablosu):
    """Üç devrin de ulaşabildiği hız aralığı (alt, üst).
    Alt sınır: devirlerin en düşük hızlarının en büyüğü; üst sınır: en yüksek hızlarının en küçüğü.
    Aralık boşsa alt > üst olur; bir devir tabloda hiç yoksa None döner."""
    altlar, ustler = [], []
    for devir in DEVIRLER:
        hizlar = kosul_tablosu.loc[kosul_tablosu.devir_rpm == devir, "hiz_ktas"]
        if hizlar.empty:
            return None
        altlar.append(int(hizlar.min()))
        ustler.append(int(hizlar.max()))
    return max(altlar), min(ustler)


def zarf_kosullari():
    """Tablodaki her irtifa–sıcaklık için 5 kt arayla hızlar: (koşullar, atlananlar) listeleri."""
    tablo = pd.read_csv(CSV_YOLU)
    kosullar, atlananlar = [], []
    for (irtifa, sicaklik), grup in tablo.groupby(["irtifa_ft", "sicaklik_C"]):
        temel = dict(irtifa_ft=int(irtifa), agirlik_lb=int(grup.agirlik_lb.iloc[0]), sicaklik_C=int(sicaklik))
        aralik = ortak_hiz_araligi(grup)
        if aralik is None or aralik[0] > aralik[1]:
            atlananlar.append(dict(temel, hiz_alt_kt=aralik and aralik[0], hiz_ust_kt=aralik and aralik[1]))
            continue

        alt, ust = aralik
        hizlar = list(range(alt, ust + 1, HIZ_ARALIGI))
        if hizlar[-1] != ust:
            hizlar.append(ust)  # üst uç her zaman dahil
        for hiz in hizlar:
            # Aralığın neresinde: 0 = alt sınır, 1 = üst sınır (tek noktalı aralıkta 0)
            konum = (hiz - alt) / (ust - alt) if ust > alt else 0.0
            kosullar.append(dict(temel, hiz_kt=hiz, hiz_alt_kt=alt, hiz_ust_kt=ust, hiz_konumu=round(konum, 3)))
    return kosullar, atlananlar


# ---------------------------------------------------------------- çözüm

def kosulu_coz(kosul):
    """Tek koşul: 1 RPM referans tarama + algoritma. Paralel çalışabilsin diye üst düzey fonksiyon."""
    irtifa, sicaklik, hiz = kosul["irtifa_ft"], kosul["sicaklik_C"], kosul["hiz_kt"]

    # Referans optimum: devri 1600'den 1900'e 1'er RPM tara
    devirler, yakitlar = referans_tarama(irtifa, sicaklik, hiz)
    k = np.nanargmin(yakitlar)
    ref_devir, ref_yakit = int(devirler[k]), float(yakitlar[k])
    yakit_1900 = float(yakitlar[devirler == SABIT_DEVIR][0])

    # Algoritma: yalnızca olc(devir) fonksiyonunu görür
    sonuc = perturb_observe(olcum_fonksiyonu(irtifa, sicaklik, hiz),
                            baslangic_devir=1900, baslangic_adim=50, en_kucuk_adim=10)

    tasarruf = yakit_1900 - sonuc.yakit
    return dict(
        kosul,
        ref_devir_rpm=ref_devir,
        ref_yakit_pph=ref_yakit,
        bulunan_devir_rpm=sonuc.devir,
        bulunan_yakit_pph=sonuc.yakit,
        yakit_farki_pph=sonuc.yakit - ref_yakit,
        yakit_1900_pph=yakit_1900,
        tasarruf_pph=tasarruf,
        tasarruf_yuzde=100 * tasarruf / yakit_1900,
        olcum_sayisi=sonuc.olcum_sayisi,
        optimum_limitte=str(ref_devir) if ref_devir in (ALT_LIMIT, UST_LIMIT) else "arada",
        gecmis=sonuc.gecmis,  # yalnızca bellekte; başarısız koşulları açıklamak için
    )


def zarfi_coz(kosullar, paralel=True):
    """Bütün koşulları çözer. Referans tarama yavaş olduğu için varsayılan olarak tüm çekirdekleri kullanır."""
    if not paralel:
        return [kosulu_coz(k) for k in kosullar]
    with Pool() as havuz:
        return havuz.map(kosulu_coz, kosullar)


def basarisiz_detayi(s):
    """Başarısız bir koşulun açıklaması: koşul, referans, bulunan ve denenen devirler."""
    denenen = ", ".join(
        f"{g['devir']:g}" + ("" if g["yakit"] is None else f" ({g['yakit']:.2f}, {'kabul' if g['kabul'] else 'ret'})")
        + (" [limit]" if g["neden"] == "limit" else "")
        for g in s["gecmis"])
    return (f"{s['irtifa_ft']} ft, {s['sicaklik_C']} °C, {s['hiz_kt']} kt ({s['agirlik_lb']} lb): "
            f"referans {s['ref_devir_rpm']} RPM / {s['ref_yakit_pph']:.2f} PPH, "
            f"bulunan {s['bulunan_devir_rpm']:g} RPM / {s['bulunan_yakit_pph']:.2f} PPH, "
            f"fark {s['yakit_farki_pph']:+.3f} PPH\n    denenen: {denenen}")


# ---------------------------------------------------------------- grafik

def hiz_seviyesi_sec(df, seviye):
    """Her irtifa–sıcaklık için tek satır seçer: ortak hız aralığının 'alt' ucu, 'orta'sı ya da 'ust' ucu.
    Orta: aralığın tam ortasına en yakın 5 kt'lık hız (eşitlikte yavaş olan)."""
    hedef = {"alt": df.hiz_alt_kt, "ust": df.hiz_ust_kt, "orta": (df.hiz_alt_kt + df.hiz_ust_kt) / 2}[seviye]
    return (df.assign(_uzaklik=(df.hiz_kt - hedef).abs())
              .sort_values(["_uzaklik", "hiz_kt"])
              .groupby(["irtifa_ft", "sicaklik_C"]).head(1))


def isi_haritasi(df, sutun, cmap, norm, bicim, baslik, alt_baslik, renk_etiketi, dosya):
    """3 panel yan yana (alt uç, orta, üst uç): X sıcaklık, Y irtifa, renk `sutun`. Boş hücreler boş kalır."""
    irtifalar = sorted(df.irtifa_ft.unique())
    sicakliklar = sorted(df.sicaklik_C.unique())
    paneller = [("alt", "Ortak hız aralığının alt ucu"), ("orta", "Ortak hız aralığının ortası"),
                ("ust", "Ortak hız aralığının üst ucu")]

    fig, eksenler = plt.subplots(1, 3, figsize=(18, 7.6), facecolor=ZEMIN, sharey=True)
    for ax, (seviye, panel_basligi) in zip(eksenler, paneller):
        izgara = (hiz_seviyesi_sec(df, seviye)
                  .pivot(index="irtifa_ft", columns="sicaklik_C", values=sutun)
                  .reindex(index=irtifalar, columns=sicakliklar))
        degerler = np.ma.masked_invalid(izgara.to_numpy(dtype=float))

        # Hücreler arasında zemin renginde ince boşluk
        x_kenar = np.arange(len(sicakliklar) + 1) - 0.5
        y_kenar = np.arange(len(irtifalar) + 1) - 0.5
        harita = ax.pcolormesh(x_kenar, y_kenar, degerler, cmap=cmap, norm=norm,
                               edgecolors=ZEMIN, linewidth=1.5)

        # Her dolu hücreye değeri yaz; koyu hücrede açık, açık hücrede koyu yazı
        for i in range(len(irtifalar)):
            for j in range(len(sicakliklar)):
                if degerler.mask[i, j]:
                    continue
                v = degerler[i, j]
                r, g, b = to_rgb(cmap(norm(v)))
                yazi_rengi = "white" if 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.5 else MUREKKEP
                ax.text(j, i, bicim(v), ha="center", va="center", fontsize=7.5, color=yazi_rengi)

        ax.set_facecolor(ZEMIN)
        ax.set_title(panel_basligi, loc="left", color=MUREKKEP, fontsize=11, pad=10)
        ax.set_xticks(range(len(sicakliklar)), [f"{t:g}" for t in sicakliklar])
        ax.set_yticks(range(len(irtifalar)), [f"{h:,}".replace(",", ".") for h in irtifalar])
        ax.set_xlabel("Sıcaklık (°C)", color=IKINCIL, fontsize=9)
        ax.tick_params(colors=SOLUK, length=0, labelsize=9)
        for kenar in ax.spines.values():
            kenar.set_visible(False)
    eksenler[0].set_ylabel("İrtifa (ft)", color=IKINCIL, fontsize=9)

    fig.text(0.05, 0.965, baslik, fontsize=15, color=MUREKKEP, weight="bold")
    fig.text(0.05, 0.925, alt_baslik, fontsize=10, color=IKINCIL)
    fig.tight_layout(rect=(0.03, 0, 0.93, 0.9), w_pad=2)

    renk_cubugu = fig.colorbar(harita, ax=eksenler, fraction=0.015, pad=0.015)
    renk_cubugu.outline.set_visible(False)
    renk_cubugu.ax.tick_params(colors=SOLUK, length=0, labelsize=9)
    renk_cubugu.set_label(renk_etiketi, color=IKINCIL, fontsize=9)

    try:
        fig.savefig(dosya, dpi=150, facecolor=ZEMIN)
        print(f"Grafik kaydedildi: sonuclar/{dosya.name}")
    except OSError:
        # Windows, dosya başka bir programda (ör. Fotoğraflar) açıkken üzerine yazdırmıyor
        print(f"{dosya.name} kaydedilemedi: dosya başka bir programda açık olabilir. Kapatıp tekrar çalıştır.")
    return fig


# ---------------------------------------------------------------- özet

def ozet_yazdir(df, atlananlar, kombinasyon_sayisi):
    basarili = df.yakit_farki_pph <= TOLERANS_PPH
    print("=" * 72)
    print("TÜM UÇUŞ ZARFI ÖZETİ (başlangıç 1900 RPM, adım 50 RPM, en küçük adım 10 RPM)")
    print("=" * 72)
    print(f"İrtifa–sıcaklık kombinasyonu : {kombinasyon_sayisi} (kullanılan {kombinasyon_sayisi - len(atlananlar)}, "
          f"atlanan {len(atlananlar)})")
    print(f"Toplam koşul (hızlarla)      : {len(df)}")
    print(f"Başarı (fark ≤ {TOLERANS_PPH} PPH)      : {basarili.sum()}/{len(df)} (%{100 * basarili.mean():.1f}), "
          f"en büyük fark {df.yakit_farki_pph.max():.3f} PPH")

    print(f"\n1900 RPM'e göre tasarruf      {'PPH':>8}{'%':>8}")
    for ad, islem in [("Ortalama", "mean"), ("Medyan", "median"), ("En düşük", "min"), ("En yüksek", "max")]:
        print(f"  {ad:<27}{getattr(df.tasarruf_pph, islem)():>8.2f}{getattr(df.tasarruf_yuzde, islem)():>8.2f}")
    en_iyi = df.loc[df.tasarruf_pph.idxmax()]
    print(f"  En yüksek tasarruf: {en_iyi.irtifa_ft} ft, {en_iyi.sicaklik_C} °C, {en_iyi.hiz_kt} kt "
          f"(1900 → {en_iyi.bulunan_devir_rpm:g} RPM)")

    print("\nOptimum devrin yeri (referans)")
    for ad, deger in [("1900 RPM (üst limit)", "1900"), ("1600 RPM (alt limit)", "1600"), ("Arada", "arada")]:
        oran = (df.optimum_limitte == deger).mean()
        print(f"  {ad:<27}%{100 * oran:5.1f}  ({(df.optimum_limitte == deger).sum()} koşul)")

    print(f"\nÖlçüm sayısı: ortalama {df.olcum_sayisi.mean():.1f}, en az {df.olcum_sayisi.min()}, "
          f"en fazla {df.olcum_sayisi.max()}")

    print("\nİrtifaya göre")
    irtifa_tablosu = df.groupby("irtifa_ft").agg(
        agirlik=("agirlik_lb", "first"), kosul=("hiz_kt", "size"),
        tasarruf_pph=("tasarruf_pph", "mean"), tasarruf_yuzde=("tasarruf_yuzde", "mean"),
        optimum_devir=("ref_devir_rpm", "mean"))
    print(f"  {'İrtifa (ft)':>11}{'Ağırlık (lb)':>14}{'Koşul':>7}{'Tasarruf (PPH)':>16}{'Tasarruf (%)':>14}"
          f"{'Ort. optimum (RPM)':>20}")
    for irtifa, s in irtifa_tablosu.iterrows():
        print(f"  {irtifa:>11}{s.agirlik:>14.0f}{s.kosul:>7.0f}{s.tasarruf_pph:>16.2f}{s.tasarruf_yuzde:>14.2f}"
              f"{s.optimum_devir:>20.0f}")

    print(f"\nAtlanan kombinasyonlar ({len(atlananlar)}): üç devrin ortak hız aralığı yok")
    for a in atlananlar:
        aralik = "devir eksik" if a["hiz_alt_kt"] is None else f"alt {a['hiz_alt_kt']} kt > üst {a['hiz_ust_kt']} kt"
        print(f"  {a['irtifa_ft']:>6} ft, {a['sicaklik_C']:>4} °C  ({aralik})")


# ---------------------------------------------------------------- ana akış

if __name__ == "__main__":
    kosullar, atlananlar = zarf_kosullari()
    kombinasyon_sayisi = len({(k["irtifa_ft"], k["sicaklik_C"]) for k in kosullar}) + len(atlananlar)
    print(f"{len(kosullar)} koşul çözülüyor (paralel)...")
    sonuclar = zarfi_coz(kosullar)

    # 1) Tüm sonuçlar
    SONUC_KLASORU.mkdir(exist_ok=True)
    df = pd.DataFrame(sonuclar).drop(columns="gecmis")
    sutunlar = ["irtifa_ft", "agirlik_lb", "sicaklik_C", "hiz_kt", "hiz_alt_kt", "hiz_ust_kt", "hiz_konumu",
                "ref_devir_rpm", "ref_yakit_pph", "bulunan_devir_rpm", "bulunan_yakit_pph", "yakit_farki_pph",
                "yakit_1900_pph", "tasarruf_pph", "tasarruf_yuzde", "olcum_sayisi", "optimum_limitte"]
    df = df[sutunlar]
    df.round(4).to_csv(SONUC_KLASORU / "zarf_sonuclari.csv", index=False)

    # 2) Sabit çizelge: her irtifa, sıcaklık ve hız için referans optimum devir
    (df[["irtifa_ft", "agirlik_lb", "sicaklik_C", "hiz_kt", "ref_devir_rpm"]]
     .rename(columns={"ref_devir_rpm": "optimum_devir_rpm"})
     .to_csv(SONUC_KLASORU / "sabit_cizelge.csv", index=False))

    # 3) Konsol özeti
    ozet_yazdir(df, atlananlar, kombinasyon_sayisi)
    basarisizlar = [s for s in sonuclar if s["yakit_farki_pph"] > TOLERANS_PPH]
    if basarisizlar:
        print(f"\nBAŞARISIZ KOŞULLAR ({len(basarisizlar)}):")
        for s in basarisizlar:
            print("  " + basarisiz_detayi(s))
    print(f"\nTablolar kaydedildi: sonuclar/zarf_sonuclari.csv, sonuclar/sabit_cizelge.csv")

    # 4) Optimum devir ısı haritası
    bos_hucre = "Boş hücre: tabloda yok ya da üç devrin ortak hız aralığı yok."
    isi_haritasi(
        df, "ref_devir_rpm", MAVI, Normalize(ALT_LIMIT, UST_LIMIT), lambda v: f"{v:.0f}",
        "Optimum pervane devri uçuş zarfında nasıl kayıyor",
        "Referans optimum (1 RPM tarama). Alçak irtifa ve soğuk havada optimum 1900 RPM'in altına iniyor, "
        "16.000 ft ve üstünde neredeyse hep 1900 RPM. " + bos_hucre,
        "Optimum devir (RPM)", SONUC_KLASORU / "optimum_devir_isi_haritasi.png")

    # 5) Tasarruf ısı haritası
    isi_haritasi(
        df, "tasarruf_yuzde", TURUNCU, Normalize(0, df.tasarruf_yuzde.max()), lambda v: f"{v:.2f}",
        "Algoritmanın 1900 RPM'e göre yakıt tasarrufu",
        "Algoritmanın bulduğu devirdeki yakıtın sabit 1900 RPM'e göre azalması (%). " + bos_hucre,
        "1900 RPM'e göre tasarruf (%)", SONUC_KLASORU / "tasarruf_isi_haritasi.png")
    plt.show()
