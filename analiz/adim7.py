"""
Adım 7: Model hatasına dayanıklılık.

Parça A: Mevcut dünyada iyileştirme. Ölçüm ortalaması (10/20/30 s) ve geri dönüş kontrolü
(kapalı/açık) Adım 5'teki 392 koşulda, 5 tohumla karşılaştırılır.

Parça B: Sapmalı dünya. Uçak tablodan farklı davrandığında dört yöntem karşılaştırılır:
  Y1 sabit 1900, Y2 sabit çizelge (sapmasız tablodan), Y3 P&O (1900'den), Y4 hibrit (çizelgeden).
Ana ölçüt pişmanlık: 10 dakikada yakılan yakıt eksi aynı süreyi gerçek optimumda geçirmenin yakıtı.

VARSAYIMLAR (Adım 6 ile aynı, gerçek veriye dayanmıyor): motor zaman sabiti tau = 2 s, her yeni devirde
3·tau = 6 s bekleme, sensör gürültüsü %1 beyaz Gauss (örnekler bağımsız), örnekleme 10 Hz, 10 dk seyir.
Sapmalı dünya fiziksel bir model değildir; model hatası için bir duyarlılık analizidir (sapmali_ucak.py).
"""
import functools
import sys
from multiprocessing import Pool
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))  # kök dizindeki modüller bulunsun

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import transforms
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from adim3_grafik import IKINCIL, MUREKKEP, RENKLER, SOLUK, ZEMIN, sade_eksen
from algoritma import perturb_observe
from analiz.adim6 import SABIT_DEVIR, SEYIR_S, TAU_S, TOLERANS_PPH, basliklar, kaydet, net_olcutleri
from olcum import GercekciOlcum, olcum_fonksiyonu, referans_tarama
from sanal_ucak import sanal_ucak
from sapmali_ucak import sapmali_dunya
from stratejiler import geri_donus_kontrolu

SONUC_KLASORU = KOK / "sonuclar"
GURULTU_YUZDE = 1.0          # VARSAYIM: sensör gürültüsü (Adım 6'nın kötümser düzeyi)
DT_S = 0.1                   # VARSAYIM: 10 Hz örnekleme
K_GERI_DONUS = 2.0           # geri dönüş kontrolü eşiği: k × iki ortalamanın farkının std'si
TOHUM = 5
ORTALAMALAR_A = [10, 20, 30]
SAPMALAR = [-0.01, -0.005, 0.0, 0.005, 0.01]
# Y3 ve Y4 tanım gereği geri dönüş kontrolüyle çalışır. Parça A'da kontrol ortalama net tasarrufu düşürdüğü
# için kontrolsüz sürümleri (Y3k, Y4k; aynı tohumlar) ek olarak raporlanır.
YONTEMLER = {"Y1": "Sabit 1900", "Y2": "Sabit çizelge", "Y3": "P&O", "Y4": "Hibrit",
             "Y3k": "P&O (kontrolsüz)", "Y4k": "Hibrit (kontrolsüz)"}
YONTEM_RENGI = {"Y1": IKINCIL, "Y2": RENKLER[0], "Y3": RENKLER[1], "Y4": RENKLER[2],
                "Y3k": RENKLER[1], "Y4k": RENKLER[2]}
ANA_YONTEMLER = ["Y1", "Y2", "Y3", "Y4"]

# Aynı (irtifa, sıcaklık, hız, devir) için sanal_ucak bir kez hesaplanır. Sonuç birebir aynıdır,
# yalnızca hız içindir (her işlemcinin kendi önbelleği olur).
tablo_dunyasi = functools.lru_cache(maxsize=None)(sanal_ucak)


# ---------------------------------------------------------------- tek koşu

def kosu(dunya, irtifa, sicaklik, hiz, ortalama_s, seed, baslangic_devir=SABIT_DEVIR, baslangic_adim=50,
         geri_donus=False, referans_devir=None):
    """Bir koşu: başlangıç devrinde kararlı seyirden P&O araması, istenirse geri dönüş kontrolü,
    karar verilen devirde seyir süresi bitene kadar kalma.
    Döndürür: (ölçüm sistemi, karar devri, arama bitiş zamanı s, P&O sonucu, geri dönüş sonucu ya da None)."""
    olc = GercekciOlcum(irtifa, sicaklik, hiz, tau_s=TAU_S, ortalama_s=ortalama_s, gurultu_yuzde=GURULTU_YUZDE,
                        dt_s=DT_S, baslangic_devir=baslangic_devir, seed=seed, dunya=dunya)
    sonuc = perturb_observe(olc, baslangic_devir=baslangic_devir, baslangic_adim=baslangic_adim, en_kucuk_adim=10)
    devir, kontrol = sonuc.devir, None
    if geri_donus:
        # Yeniden ölçümler olc üzerinden yapılır: süreleri ve yakıtları arama maliyetine girer
        referans = baslangic_devir if referans_devir is None else referans_devir
        kontrol = geri_donus_kontrolu(olc, sonuc.devir, referans, GURULTU_YUZDE / 100, round(ortalama_s / DT_S),
                                      k=K_GERI_DONUS)
        devir = kontrol.devir
    arama_bitis = olc.t
    olc.devam_et(devir, SEYIR_S)
    return olc, devir, arama_bitis, sonuc, kontrol


def kosu_olcutleri(dunya, kosul, olc, devir, arama_bitis, sonuc, kontrol, opt_yakit):
    """Bir koşunun ölçütleri. opt_yakit: o dünyadaki gerçek en düşük yakıt (PPH)."""
    ideal = olcum_fonksiyonu(kosul["irtifa_ft"], kosul["sicaklik_C"], kosul["hiz_kt"], dunya)
    y1900, y_devir = ideal(SABIT_DEVIR), ideal(devir)
    n = net_olcutleri(olc, arama_bitis, y1900, y_devir)
    # Pişmanlık: yakılan yakıt eksi aynı süreyi gerçek optimumda geçirmenin yakıtı, PPH karşılığı
    pismanlik = (n["yakilan_lb"] - opt_yakit * SEYIR_S / 3600) / (SEYIR_S / 3600)
    return dict(
        bulunan_devir_rpm=devir,
        bulunan_gercek_yakit_pph=y_devir,
        yakit_farki_pph=y_devir - opt_yakit,
        basari=bool(y_devir - opt_yakit <= TOLERANS_PPH),
        arama_suresi_s=arama_bitis,
        olcum_sayisi=sonuc.olcum_sayisi + (kontrol.olcum_sayisi if kontrol else 0),
        geri_donuldu=bool(kontrol and kontrol.geri_donuldu),
        pismanlik_pph=pismanlik,
        net_tasarruf_pph=n["net_tasarruf_pph"],
        net_tasarruf_yuzde=n["net_tasarruf_yuzde"],
        arama_maliyeti_lb=n["arama_maliyeti_lb"],
    )


def zarf_kosullari():
    """Adım 5'teki 392 koşul ve sabit çizelgedeki devirleri."""
    zarf = pd.read_csv(SONUC_KLASORU / "zarf_sonuclari.csv")
    cizelge = pd.read_csv(SONUC_KLASORU / "sabit_cizelge.csv")
    zarf = zarf.merge(cizelge, on=["irtifa_ft", "agirlik_lb", "sicaklik_C", "hiz_kt"], validate="one_to_one")
    return [dict(kosul_no=i, irtifa_ft=int(s.irtifa_ft), agirlik_lb=int(s.agirlik_lb), sicaklik_C=int(s.sicaklik_C),
                 hiz_kt=int(s.hiz_kt), optimum_limitte=s.optimum_limitte, ideal_tasarruf_pph=s.tasarruf_pph,
                 cizelge_devir_rpm=int(s.optimum_devir_rpm))
            for i, s in zarf.iterrows()]


def paralel(fonksiyon, isler):
    with Pool() as havuz:
        return pd.DataFrame([satir for satirlar in havuz.map(fonksiyon, isler) for satir in satirlar])


# ---------------------------------------------------------------- Parça A

def parca_a_kosulu(kosul):
    """Bir koşulda bütün Parça A ayarları × 5 tohum. Tohumlar Adım 6 Deney B ile aynı:
    'ortalama 10 s, geri dönüş kapalı' ayarı Adım 6 sonuçlarını birebir verir."""
    dunya = tablo_dunyasi
    devirler, yakitlar = referans_tarama(kosul["irtifa_ft"], kosul["sicaklik_C"], kosul["hiz_kt"], dunya=dunya)
    opt_yakit = float(np.nanmin(yakitlar))
    satirlar = []
    for ortalama in ORTALAMALAR_A:
        for geri_donus in (False, True):
            for tohum in range(TOHUM):
                sonuc = kosu(dunya, kosul["irtifa_ft"], kosul["sicaklik_C"], kosul["hiz_kt"], ortalama,
                             seed=[2, kosul["kosul_no"], tohum], geri_donus=geri_donus)
                satirlar.append(dict(kosul, ortalama_s=ortalama, geri_donus=geri_donus, tohum=tohum,
                                     **kosu_olcutleri(dunya, kosul, *sonuc, opt_yakit)))
    return satirlar


def ayar_ozeti(kosular):
    """Her ayar için başarı, net tasarruf (koşul ortalamaları üzerinden), net kayıp ve arama süresi."""
    satirlar = []
    for (ortalama, geri_donus), grup in kosular.groupby(["ortalama_s", "geri_donus"]):
        kosul_net = grup.groupby("kosul_no").net_tasarruf_pph.mean()
        satirlar.append(dict(
            ortalama_s=ortalama, geri_donus=geri_donus,
            basari_orani=grup.basari.mean(),
            net_ortalama_pph=kosul_net.mean(),
            net_ortalama_yuzde=grup.groupby("kosul_no").net_tasarruf_yuzde.mean().mean(),
            net_medyan_pph=kosul_net.median(),
            net_kayipli_kosul_orani=(kosul_net < 0).mean(),
            en_kotu_kosul_pph=kosul_net.min(),
            en_kotu_kosu_pph=grup.net_tasarruf_pph.min(),
            arama_suresi_s=grup.arama_suresi_s.mean(),
            olcum_sayisi=grup.olcum_sayisi.mean(),
            geri_donus_orani=grup.geri_donuldu.mean(),
        ))
    return pd.DataFrame(satirlar)


def en_iyi_ayar(ozet):
    """Adım 6'daki ölçüt: başarı oranı en yükseğe en fazla 5 puan yakın olan ayarlar arasından
    ortalama net tasarrufu en büyük olan."""
    aday = ozet[ozet.basari_orani >= ozet.basari_orani.max() - 0.05]
    return aday.loc[aday.net_ortalama_pph.idxmax()]


# ---------------------------------------------------------------- Parça B

def parca_b_kosulu(is_):
    """Bir koşulda bütün sapmalar: 1 RPM referans tarama, Y1/Y2 doğrudan, Y3/Y4 5 tohumla."""
    kosul, ortalama = is_["kosul"], is_["ortalama_s"]
    irtifa, sicaklik, hiz, cizelge = kosul["irtifa_ft"], kosul["sicaklik_C"], kosul["hiz_kt"], kosul["cizelge_devir_rpm"]
    satirlar = []
    opt_sapmasiz = None
    for e in sorted(SAPMALAR, key=abs):  # önce e = 0: optimumun kaymasını ölçmek için
        dunya = sapmali_dunya(e, taban=tablo_dunyasi)
        devirler, yakitlar = referans_tarama(irtifa, sicaklik, hiz, dunya=dunya)
        k = np.nanargmin(yakitlar)
        opt_devir, opt_yakit = int(devirler[k]), float(yakitlar[k])
        if e == 0:
            opt_sapmasiz = opt_devir
        y1900 = float(yakitlar[devirler == SABIT_DEVIR][0])
        ortak = dict(kosul, e=e, opt_devir_rpm=opt_devir, opt_kayma_rpm=opt_devir - opt_sapmasiz,
                     opt_yakit_pph=opt_yakit, yakit_1900_pph=y1900)

        # Y1 ve Y2: arama yok, 10 dakika aynı devirde (1900'den geçiş ihmal edildi); gerçek yakıttan doğrudan
        for yontem, devir in (("Y1", SABIT_DEVIR), ("Y2", cizelge)):
            y = float(yakitlar[devirler == devir][0])
            satirlar.append(dict(ortak, yontem=yontem, tohum=-1, bulunan_devir_rpm=devir, bulunan_gercek_yakit_pph=y,
                                 yakit_farki_pph=y - opt_yakit, basari=bool(y - opt_yakit <= TOLERANS_PPH),
                                 arama_suresi_s=0.0, olcum_sayisi=0, geri_donuldu=False, pismanlik_pph=y - opt_yakit,
                                 net_tasarruf_pph=y1900 - y, net_tasarruf_yuzde=100 * (y1900 - y) / y1900,
                                 arama_maliyeti_lb=0.0))

        # Y3: 1900'den P&O + geri dönüş (referans 1900). Y4: çizelge devrinden 25 RPM adımla P&O + geri dönüş
        # (referans çizelge devri). Y3k/Y4k: aynı, geri dönüş kontrolü olmadan.
        # Aynı koşul ve tohum, bütün sapmalarda ve bütün yöntemlerde aynı seed'i kullanır.
        for tohum in range(TOHUM):
            seed = [4, kosul["kosul_no"], tohum]
            for yontem, ayar in (("Y3", dict(baslangic_devir=SABIT_DEVIR, baslangic_adim=50, geri_donus=True)),
                                 ("Y4", dict(baslangic_devir=cizelge, baslangic_adim=25, geri_donus=True)),
                                 ("Y3k", dict(baslangic_devir=SABIT_DEVIR, baslangic_adim=50)),
                                 ("Y4k", dict(baslangic_devir=cizelge, baslangic_adim=25))):
                sonuc = kosu(dunya, irtifa, sicaklik, hiz, ortalama, seed, **ayar)
                satirlar.append(dict(ortak, yontem=yontem, tohum=tohum,
                                     **kosu_olcutleri(dunya, kosul, *sonuc, opt_yakit)))
    return satirlar


def yontem_ozeti(kosular):
    """Yöntem × sapma özeti. Koşul başına önce tohumların ortalaması alınır."""
    satirlar = []
    for (yontem, e), grup in kosular.groupby(["yontem", "e"]):
        kosul_ort = grup.groupby("kosul_no")[["pismanlik_pph", "net_tasarruf_pph", "net_tasarruf_yuzde"]].mean()
        ilk = grup.groupby("kosul_no").first()
        satirlar.append(dict(
            yontem=yontem, yontem_adi=YONTEMLER[yontem], e=e,
            pismanlik_ortalama_pph=kosul_ort.pismanlik_pph.mean(),
            pismanlik_medyan_pph=kosul_ort.pismanlik_pph.median(),
            pismanlik_en_kotu_kosul_pph=kosul_ort.pismanlik_pph.max(),
            net_ortalama_pph=kosul_ort.net_tasarruf_pph.mean(),
            net_ortalama_yuzde=kosul_ort.net_tasarruf_yuzde.mean(),
            net_kayipli_kosul_orani=(kosul_ort.net_tasarruf_pph < -1e-9).mean(),
            basari_orani=grup.basari.mean(),
            arama_suresi_s=grup.arama_suresi_s.mean(),
            geri_donus_orani=grup.geri_donuldu.mean(),
            opt_kayma_ortalama_rpm=ilk.opt_kayma_rpm.mean(),
            opt_kayma_mutlak_rpm=ilk.opt_kayma_rpm.abs().mean(),
            opt_limitte_orani=ilk.opt_devir_rpm.isin([1600, 1900]).mean(),
        ))
    return pd.DataFrame(satirlar)


def tek_kosul(ortalama):
    """2000 ft, 10 °C, 161 kt: her sapmada eğri, gerçek optimum, çizelge devri ve Y3/Y4'ün bulduğu devirler.
    161 kt çizelgede yok; çizelge devri olarak sapmasız tablonun bu hızdaki optimumu alınır."""
    irtifa, sicaklik, hiz = 2000, 10, 161
    devirler0, yakitlar0 = referans_tarama(irtifa, sicaklik, hiz, dunya=sapmali_dunya(0, taban=tablo_dunyasi))
    cizelge = int(devirler0[np.nanargmin(yakitlar0)])
    sonuclar = []
    for e in SAPMALAR:
        dunya = sapmali_dunya(e, taban=tablo_dunyasi)
        devirler, yakitlar = referans_tarama(irtifa, sicaklik, hiz, dunya=dunya)
        bulunanlar = {}
        for yontem, ayar in (("Y3", dict(baslangic_devir=SABIT_DEVIR, baslangic_adim=50)),
                             ("Y4", dict(baslangic_devir=cizelge, baslangic_adim=25))):
            bulunanlar[yontem] = [kosu(dunya, irtifa, sicaklik, hiz, ortalama, [5, tohum], geri_donus=True, **ayar)[1]
                                  for tohum in range(TOHUM)]
        sonuclar.append(dict(e=e, devirler=devirler, yakitlar=yakitlar, cizelge=cizelge,
                             opt_devir=int(devirler[np.nanargmin(yakitlar)]), **bulunanlar))
    return sonuclar


# ---------------------------------------------------------------- grafikler

def parca_a_grafigi(ozet, secilen, dosya):
    """Ayarlara göre başarı, ortalama net tasarruf ve net kayıplı koşul oranı (gruplu sütunlar)."""
    paneller = [("basari_orani", "Başarı oranı (%)", 100, "{:.1f}"),
                ("net_ortalama_pph", "Ortalama net tasarruf (PPH)", 1, "{:.2f}"),
                ("net_kayipli_kosul_orani", "Net kayıplı koşul oranı (%)", 100, "{:.0f}")]
    renkler = {False: SOLUK, True: RENKLER[0]}
    fig, eksenler = plt.subplots(1, 3, figsize=(15, 5.2), facecolor=ZEMIN)
    x = np.arange(len(ORTALAMALAR_A))
    for ax, (sutun, baslik, carpan, bicim) in zip(eksenler, paneller):
        sade_eksen(ax, baslik)
        for i, geri_donus in enumerate((False, True)):
            alt = ozet[ozet.geri_donus == geri_donus].sort_values("ortalama_s")
            degerler = alt[sutun].to_numpy() * carpan
            cubuklar = ax.bar(x + (i - 0.5) * 0.38, degerler, 0.36, color=renkler[geri_donus], zorder=2)
            for c, v in zip(cubuklar, degerler):
                ax.text(c.get_x() + c.get_width() / 2, v, bicim.format(v), ha="center", va="bottom", fontsize=8.5,
                        color=MUREKKEP)
            # Seçilen ayar: çerçeveli
            for c, o in zip(cubuklar, alt.ortalama_s):
                if o == secilen["ortalama_s"] and geri_donus == secilen["geri_donus"]:
                    c.set_edgecolor(MUREKKEP)
                    c.set_linewidth(2)
        ax.set_xticks(x, [f"{o} s" for o in ORTALAMALAR_A])
        ax.set_xlim(-0.6, len(x) - 0.4)
        ax.set_xlabel("Ölçüm ortalaması süresi", color=IKINCIL, fontsize=9)
        ax.margins(y=0.12)
    fig.legend(handles=[Patch(fc=SOLUK, label="Geri dönüş kontrolü kapalı"),
                        Patch(fc=RENKLER[0], label=f"Geri dönüş kontrolü açık (k = {K_GERI_DONUS:g})")],
               loc="upper left", bbox_to_anchor=(0.045, 0.86), ncol=2, frameon=False, fontsize=9, labelcolor=IKINCIL)
    basliklar(fig, "Parça A: ölçüm ortalaması ve geri dönüş kontrolü",
              f"392 koşul × {TOHUM} tohum, gürültü %{GURULTU_YUZDE:g}, eşik 0, 10 dakikalık seyir. Çerçeve: seçilen ayar "
              f"({secilen['ortalama_s']:g} s, geri dönüş {'açık' if secilen['geri_donus'] else 'kapalı'}).", y=0.96)
    fig.tight_layout(rect=(0.03, 0, 1, 0.8), w_pad=3)
    kaydet(fig, dosya)


def cizgi_stili(yontem):
    """Ana yöntemler düz çizgi ve dolu işaret; kontrolsüz sürümler ince kesikli çizgi ve içi boş işaret."""
    kontrolsuz = yontem.endswith("k")
    return dict(color=YONTEM_RENGI[yontem], linewidth=1.3 if kontrolsuz else 2.2, marker="o", ms=7 if kontrolsuz else 8,
                mfc=ZEMIN if kontrolsuz else YONTEM_RENGI[yontem], mec=YONTEM_RENGI[yontem] if kontrolsuz else ZEMIN,
                mew=1.6 if kontrolsuz else 2, linestyle=(0, (4, 2.5)) if kontrolsuz else "-")


def sapma_grafigi(ozet, sutun, baslik, alt_baslik, eksen_etiketi, dosya):
    """X: sapma e (%), Y: yöntemlerin ortalama değeri. Her yöntem bir çizgi. Altı çizgi sağ uçta birbirine çok
    yaklaştığı için doğrudan etiket yerine yalnızca açıklama kutusu kullanılır."""
    fig, ax = plt.subplots(figsize=(11, 6.2), facecolor=ZEMIN)
    sade_eksen(ax, eksen_etiketi)
    x = np.array(SAPMALAR) * 100
    for yontem in YONTEMLER:
        alt = ozet[ozet.yontem == yontem].sort_values("e")
        ax.plot(x, alt[sutun], **cizgi_stili(yontem), zorder=3)
    ax.set_xticks(x, [f"{v:+g}".replace(".", ",") if v else "0" for v in x])
    ax.set_xlim(x[0] - 0.1, x[-1] + 0.1)
    ax.set_xlabel("Model sapması e (%)   ←  yüksek devir tablodan ucuz   ·   yüksek devir tablodan pahalı  →",
                  color=IKINCIL, fontsize=9)
    ax.axhline(0, color=SOLUK, linewidth=1, zorder=1)
    fig.legend(handles=[Line2D([], [], **cizgi_stili(y), label=f"{y}: {a}") for y, a in YONTEMLER.items()],
               loc="upper left", bbox_to_anchor=(0.045, 0.87), ncol=3, frameon=False, fontsize=9, labelcolor=IKINCIL)
    basliklar(fig, baslik, alt_baslik)
    fig.tight_layout(rect=(0.03, 0, 1, 0.8))
    kaydet(fig, dosya)


def e_etiketi(e):
    """Türkçe yüzde yazımı: e = −%1, e = +%0,5, e = 0 (sapmasız)."""
    if e == 0:
        return "e = 0 (sapmasız)"
    return f"e = {'+' if e > 0 else '−'}%{abs(100 * e):g}".replace(".", ",")


def tek_kosul_grafigi(sonuclar, dosya):
    fig, eksenler = plt.subplots(1, len(sonuclar), figsize=(18, 5.6), facecolor=ZEMIN, sharey=True)
    for ax, s in zip(eksenler, sonuclar):
        sade_eksen(ax, e_etiketi(s["e"]))
        ax.set_xticks(np.arange(1600, 1901, 100))
        ax.set_xlabel("Pervane devri (RPM)", color=IKINCIL, fontsize=9)
        ax.plot(s["devirler"], s["yakitlar"], color=IKINCIL, linewidth=2, zorder=2)
        ax.axvline(s["cizelge"], color=YONTEM_RENGI["Y2"], linewidth=1.5, linestyle=(0, (4, 3)), zorder=1)
        yakit = dict(zip(s["devirler"], s["yakitlar"]))
        opt = s["opt_devir"]
        ax.plot(opt, yakit[opt], "*", ms=15, color=MUREKKEP, mec=ZEMIN, mew=1, zorder=5)
        # Tohumların bulduğu devirler: Y3 eğrinin üstünde, Y4 altında; aynı devirdekiler üst üste dizilir
        for yontem, yon, isaret in (("Y3", 1, "o"), ("Y4", -1, "D")):
            sayac = {}
            for devir in s[yontem]:
                sira = sayac.get(devir, 0)
                sayac[devir] = sira + 1
                y = np.interp(devir, s["devirler"], s["yakitlar"])
                kaydir = transforms.offset_copy(ax.transData, fig=fig, x=0, y=yon * (9 + 8 * sira), units="points")
                ax.plot(devir, y, isaret, ms=6.5, color=YONTEM_RENGI[yontem], mec=ZEMIN, mew=1, transform=kaydir,
                        zorder=4)
    eksenler[0].set_ylabel("Yakıt debisi (PPH)", color=IKINCIL, fontsize=9)
    eksenler[0].margins(y=0.15)
    isaretler = [
        Line2D([], [], color=IKINCIL, lw=2, label="Sapmalı yakıt–devir eğrisi"),
        Line2D([], [], ls="", marker="*", ms=13, color=MUREKKEP, label="Gerçek optimum"),
        Line2D([], [], color=YONTEM_RENGI["Y2"], lw=1.5, linestyle=(0, (4, 3)), label="Çizelge devri (sapmasız)"),
        Line2D([], [], ls="", marker="o", ms=7, color=YONTEM_RENGI["Y3"], label="Y3 P&O'nun bulduğu (5 tohum, üstte)"),
        Line2D([], [], ls="", marker="D", ms=6.5, color=YONTEM_RENGI["Y4"], label="Y4 hibritin bulduğu (5 tohum, altta)"),
    ]
    fig.legend(handles=isaretler, loc="upper left", bbox_to_anchor=(0.045, 0.86), ncol=5, frameon=False, fontsize=9,
               labelcolor=IKINCIL)
    basliklar(fig, "Tek koşul: 2000 ft, 10 °C, 161 kt",
              "Sapma büyüdükçe gerçek optimum çizelge devrinden uzaklaşıyor. 161 kt çizelgede olmadığından çizelge "
              "devri olarak sapmasız optimum alındı.")
    fig.tight_layout(rect=(0.03, 0, 1, 0.8), w_pad=1.5)
    kaydet(fig, dosya)


# ---------------------------------------------------------------- ana akış

def ozet_yazdir(ozet_a, secilen, ozet_b, tek):
    print("=" * 84)
    print("ADIM 7: MODEL HATASINA DAYANIKLILIK")
    print("=" * 84)
    print(f"VARSAYIMLAR: tau = {TAU_S:g} s (yeni devirde {3 * TAU_S:g} s bekleme), gürültü %{GURULTU_YUZDE:g} beyaz Gauss, "
          f"10 Hz, seyir {SEYIR_S // 60} dk, eşik 0.\n  Sapmalı dünya fiziksel bir model değil, model hatası için "
          "duyarlılık analizi.")

    print(f"\nPARÇA A: 392 koşul × {TOHUM} tohum (net değerler koşul ortalamaları üzerinden)")
    print(f"  {'Ort. (s)':>8}{'Geri dönüş':>12}{'Başarı':>8}{'Net ort.':>10}{'Net medyan':>12}{'Kayıplı koşul':>15}"
          f"{'En kötü koşul':>15}{'En kötü koşu':>14}{'Arama (s)':>11}{'Geri dönülen':>14}")
    for _, r in ozet_a.iterrows():
        isaret = "  ←" if (r.ortalama_s == secilen.ortalama_s and r.geri_donus == secilen.geri_donus) else ""
        print(f"  {r.ortalama_s:>8g}{'açık' if r.geri_donus else 'kapalı':>12}{100 * r.basari_orani:>7.1f}%"
              f"{r.net_ortalama_pph:>10.3f}{r.net_medyan_pph:>12.3f}{100 * r.net_kayipli_kosul_orani:>14.1f}%"
              f"{r.en_kotu_kosul_pph:>15.3f}{r.en_kotu_kosu_pph:>14.3f}{r.arama_suresi_s:>11.0f}"
              f"{100 * r.geri_donus_orani:>13.0f}%{isaret}")
    print(f"  Seçilen: ortalama {secilen.ortalama_s:g} s, geri dönüş {'açık' if secilen.geri_donus else 'kapalı'} "
          "(Adım 6 ölçütü: başarıda en iyiye 5 puan yakın olanlar arasında en büyük ortalama net tasarruf)")

    print(f"\nPARÇA B: sapmalı dünya, 392 koşul, Y3/Y4 {TOHUM} tohum, ortalama {secilen.ortalama_s:g} s")
    kayma = ozet_b[ozet_b.yontem == "Y1"].set_index("e")
    print("  Optimum devrin kayması (sapmasız optimuma göre)")
    print(f"  {'e':>8}{'Ortalama (RPM)':>16}{'|Ortalama| (RPM)':>18}{'Limitte':>10}")
    for e, r in kayma.iterrows():
        print(f"  {100 * e:>+7.1f}%{r.opt_kayma_ortalama_rpm:>16.1f}{r.opt_kayma_mutlak_rpm:>18.1f}"
              f"{100 * r.opt_limitte_orani:>9.0f}%")
    for sutun, baslik, bicim in [("pismanlik_ortalama_pph", "Ortalama pişmanlık (PPH)", "{:>9.3f}"),
                                 ("net_ortalama_pph", "1900'e göre ortalama net tasarruf (PPH)", "{:>9.3f}"),
                                 ("net_ortalama_yuzde", "1900'e göre ortalama net tasarruf (%)", "{:>9.3f}"),
                                 ("net_kayipli_kosul_orani", "1900'e göre net kayıplı koşul oranı (%)", "{:>9.1%}"),
                                 ("basari_orani", "Başarı oranı (gerçek optimumdan ≤ 0,5 PPH, %)", "{:>9.1%}")]:
        print(f"\n  {baslik}")
        print(f"  {'Yöntem':<24}" + "".join(f"{100 * e:>+8.1f}%" for e in SAPMALAR))
        tablo = ozet_b.pivot(index="yontem", columns="e", values=sutun)
        for yontem, ad in YONTEMLER.items():
            print(f"  {yontem + ' ' + ad:<24}" + "".join(bicim.format(tablo.loc[yontem, e]) for e in SAPMALAR))

    print("\n  Tek koşul: 2000 ft, 10 °C, 161 kt (çizelge devri = sapmasız optimum)")
    for s in tek:
        print(f"  e {100 * s['e']:>+5.1f}%: optimum {s['opt_devir']} RPM, çizelge {s['cizelge']} RPM, "
              f"Y3 {[f'{d:g}' for d in s['Y3']]}, Y4 {[f'{d:g}' for d in s['Y4']]}")


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    SONUC_KLASORU.mkdir(exist_ok=True)
    kosullar = zarf_kosullari()

    # Parça A
    print(f"Parça A: {len(kosullar)} koşul × {len(ORTALAMALAR_A) * 2} ayar × {TOHUM} tohum (paralel)...")
    a = paralel(parca_a_kosulu, kosullar)
    ozet_a = ayar_ozeti(a)
    ozet_a.round(4).to_csv(SONUC_KLASORU / "adim7a_ayarlar.csv", index=False)
    secilen = en_iyi_ayar(ozet_a)

    # Parça B
    print(f"Parça B: {len(kosullar)} koşul × {len(SAPMALAR)} sapma, Y3/Y4 (+ kontrolsüz) × {TOHUM} tohum (paralel)...")
    b = paralel(parca_b_kosulu, [dict(kosul=k, ortalama_s=secilen.ortalama_s) for k in kosullar])
    b = b.sort_values(["kosul_no", "e", "yontem", "tohum"]).reset_index(drop=True)
    sutunlar = ["irtifa_ft", "agirlik_lb", "sicaklik_C", "hiz_kt", "e", "yontem", "tohum", "opt_devir_rpm",
                "opt_kayma_rpm", "opt_yakit_pph", "yakit_1900_pph", "cizelge_devir_rpm", "bulunan_devir_rpm",
                "bulunan_gercek_yakit_pph", "pismanlik_pph", "net_tasarruf_pph", "net_tasarruf_yuzde", "basari",
                "arama_suresi_s", "olcum_sayisi", "geri_donuldu"]
    b[sutunlar].round(4).to_csv(SONUC_KLASORU / "adim7b_sonuclar.csv", index=False)
    ozet_b = yontem_ozeti(b)
    ozet_b.round(4).to_csv(SONUC_KLASORU / "adim7b_ozet.csv", index=False)
    tek = tek_kosul(secilen.ortalama_s)

    ozet_yazdir(ozet_a, secilen, ozet_b, tek)
    print("\nTablolar kaydedildi: sonuclar/adim7a_ayarlar.csv, sonuclar/adim7b_sonuclar.csv, sonuclar/adim7b_ozet.csv")

    parca_a_grafigi(ozet_a, secilen, SONUC_KLASORU / "adim7a_ayarlar.png")
    alt_baslik = (f"392 koşul ortalaması. Gürültü %{GURULTU_YUZDE:g}, ortalama {secilen.ortalama_s:g} s, 10 dk seyir. "
                  "Kesikli: geri dönüş kontrolü olmadan (aynı tohumlar).")
    sapma_grafigi(ozet_b, "pismanlik_ortalama_pph", "Model sapması büyüdükçe hangi yöntem ne kadar kaybediyor",
                  alt_baslik, "Ortalama pişmanlık (PPH): gerçek optimuma göre fazladan yakılan",
                  SONUC_KLASORU / "adim7b_pismanlik.png")
    sapma_grafigi(ozet_b, "net_ortalama_pph", "Sabit 1900 RPM'e göre ortalama net tasarruf", alt_baslik,
                  "1900'e göre ortalama net tasarruf (PPH)", SONUC_KLASORU / "adim7b_net_tasarruf.png")
    tek_kosul_grafigi(tek, SONUC_KLASORU / "adim7b_tek_kosul.png")
    plt.show()
