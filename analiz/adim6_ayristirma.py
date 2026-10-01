"""
Adım 6 raporunun (rapor_2348_11026.md) 5. bölümündeki "kaybın kaynağı" hesabı.

Girdi: analiz/adim6.py'nin yazdığı sonuclar/adim6_zarf_kosular.csv (koşu başına) ve
sonuclar/adim6_zarf.csv (koşul başına). Simülasyon yapmaz, yalnızca bu tabloları ayrıştırır.

1. Optimumu zaten 1900'de olan (ideal potansiyeli sıfır) koşularda net kaybın ne kadarı aramanın
   kendisinden, ne kadarı yanlış devirde kalmaktan geliyor
2. Başarısız koşular: gerçek kazanç varken nerede takılıyor
3. Seyir süresine duyarlılık (simülasyon değil, kaba ekstrapolasyon)
4. Optimumu "arada" olup net kayıp veren koşulların ideal potansiyeli
"""
from pathlib import Path

import pandas as pd

SONUC = Path(__file__).resolve().parent.parent / "sonuclar"
SEYIR_S = 600
SIFIR_POTANSIYEL = 0.005  # PPH; bunun altındaki ideal tasarruf "sıfır" sayılır

kosular = pd.read_csv(SONUC / "adim6_zarf_kosular.csv")
kosullar = pd.read_csv(SONUC / "adim6_zarf.csv")

# 1) Sıfır potansiyelli koşularda kaybın ayrıştırılması
sifir = kosular[kosular.ideal_tasarruf_pph < SIFIR_POTANSIYEL]
bitmeyen = sifir[sifir.bulunan_devir_rpm != 1900]
# Arama maliyetinin 10 dakikaya yayılmış PPH karşılığı (lb / (10/60 h))
arama_pph = sifir.arama_maliyeti_lb.mean() / (SEYIR_S / 3600)
net_kayip_pph = -sifir.net_tasarruf_pph.mean()
print("1) İdeal potansiyeli sıfır olan koşular (optimum ≈ 1900)")
print(f"   Koşu sayısı                      : {len(sifir)}")
print(f"   1900'de biten                    : %{100 * (sifir.bulunan_devir_rpm == 1900).mean():.0f}")
print(f"   Bulunan devir dağılımı           : {sifir.bulunan_devir_rpm.value_counts().to_dict()}")
print(f"   Ortalama net kayıp               : {net_kayip_pph:.3f} PPH")
print(f"   Arama maliyeti                   : {sifir.arama_maliyeti_lb.mean():.4f} lb = {arama_pph:.3f} PPH "
      f"(kaybın %{100 * arama_pph / net_kayip_pph:.0f}'i)")
print(f"   Kalan (yanlış devirde kalmak)    : {net_kayip_pph - arama_pph:.3f} PPH "
      f"(kaybın %{100 * (1 - arama_pph / net_kayip_pph):.0f}'i)")
print(f"   1900'de bitmeyenlerde kararlı kayıp: {-bitmeyen.kararli_kazanc_pph.mean():.3f} PPH")

# 2) Başarısız koşular
basarisiz = kosular[~kosular.basari]
en_kotu = basarisiz.loc[basarisiz.yakit_farki_pph.idxmax()]
print("\n2) Başarısız koşular (fark > 0,5 PPH)")
print(f"   Sayı                             : {len(basarisiz)}/{len(kosular)} (%{100 * len(basarisiz) / len(kosular):.1f})")
print(f"   Ortalama ideal potansiyel        : {basarisiz.ideal_tasarruf_pph.mean():.2f} PPH")
print(f"   Tam 1900'de kalan                : {(basarisiz.bulunan_devir_rpm == 1900).sum()}")
print(f"   En kötü                          : {en_kotu.irtifa_ft} ft, {en_kotu.sicaklik_C} °C, {en_kotu.hiz_kt} kt, "
      f"tohum {en_kotu.tohum}: {en_kotu.bulunan_devir_rpm:g} RPM, fark {en_kotu.yakit_farki_pph:.2f} PPH")

# 3) Seyir süresine duyarlılık: arama sonrası kararlı kazancın seyir boyunca sürdüğü varsayılır
#    net = (−arama maliyeti + kararlı kazanç × (T − arama süresi)) / T
print("\n3) Seyir süresine duyarlılık (kaba ekstrapolasyon, simülasyon değil)")
for dakika in (10, 30, 60):
    T = dakika * 60
    net = (-kosular.arama_maliyeti_lb + kosular.kararli_kazanc_pph * (T - kosular.yakinsama_s) / 3600) / (T / 3600)
    kosul_net = net.groupby([kosular.irtifa_ft, kosular.sicaklik_C, kosular.hiz_kt]).mean()
    print(f"   {dakika:>2} dk: ortalama net {kosul_net.mean():.3f} PPH, net kayıplı koşul %{100 * (kosul_net < 0).mean():.1f}")

# 4) Optimumu arada olup net kayıp veren koşullar
arada = kosullar[(kosullar.optimum_limitte == "arada") & kosullar.net_kayip]
print("\n4) Optimumu arada olup net kayıp veren koşullar")
print(f"   Sayı                             : {len(arada)}")
print(f"   İdeal potansiyel                 : ortalama {arada.ideal_tasarruf_pph.mean():.3f}, "
      f"en fazla {arada.ideal_tasarruf_pph.max():.3f} PPH")
