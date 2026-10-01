"""
sanal_ucak() fonksiyonunu elle denemek için.
Aşağıdaki dört değeri değiştir, dosyayı çalıştır (VS Code'da sağ üstteki ▶ düğmesi).
"""
import numpy as np

from sanal_ucak import DEVIRLER, _tablo, sanal_ucak

IRTIFA = 2000   # ft  (tabloda olan bir değer: 2000, 4000, ... 24000)
SICAKLIK = 10   # °C  (o irtifada tabloda olan bir değer)
HIZ = 161       # knot
DEVIR = 1820    # RPM (1600-1900 arası)

# 1) Tablodan seçilen satırlar: sonucu bunlarla elle karşılaştırabilirsin
kosul = _tablo[(_tablo.irtifa_ft == IRTIFA) & (_tablo.sicaklik_C == SICAKLIK)]
print(f"--- Tablo: {IRTIFA} ft, {SICAKLIK} °C ---")
print(kosul[["devir_rpm", "hiz_ktas", "yakit_pph", "tork_ftlb"]].to_string(index=False))

# 2) Her devirde, istenen hızdaki yakıt (tablodaki 3 devir için ara sonuç)
print(f"\n--- {HIZ} kt hızda, tablodaki devirlerde ---")
for d in DEVIRLER:
    sonuc = sanal_ucak(IRTIFA, SICAKLIK, HIZ, d)
    print(f"{d} RPM: " + ("GEÇERSİZ" if sonuc is None else f"{sonuc[0]:.1f} PPH, {sonuc[1]:.0f} ft-lb"))

# 3) İstediğin devirde sonuç
sonuc = sanal_ucak(IRTIFA, SICAKLIK, HIZ, DEVIR)
print(f"\n--- SONUÇ: {DEVIR} RPM ---")
print("GEÇERSİZ" if sonuc is None else f"{sonuc[0]:.1f} PPH, {sonuc[1]:.0f} ft-lb")

# 4) Devri 1600'den 1900'e tara (en az yakıtın nerede olduğunu görmek için)
if sonuc is not None:
    print("\n--- Devir taraması ---")
    for d in np.arange(1600, 1901, 25):
        y, t = sanal_ucak(IRTIFA, SICAKLIK, HIZ, d)
        print(f"{d} RPM: {y:.1f} PPH")
