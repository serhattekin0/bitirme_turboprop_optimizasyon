"""
Sanal uçak: Cessna 208B Grand Caravan seyir performans tablosundan (POH)
beslenen tek fonksiyon. Optimizasyon algoritması uçakla yalnızca
sanal_ucak() üzerinden konuşur.
"""
from pathlib import Path

import numpy as np
import pandas as pd

CSV_YOLU = Path(__file__).with_name("caravan_seyir_performansi.csv")
DEVIRLER = (1600, 1750, 1900)

_tablo = pd.read_csv(CSV_YOLU)


def sanal_ucak(irtifa_ft, sicaklik_C, hiz_kt, devir_rpm):
    """Verilen koşuldaki yakıt debisini (PPH) ve torku (ft-lb) döndürür: (yakit, tork).

    Uçak bu koşulda bu hızı bu devirde tutamıyorsa None ("geçersiz") döner.
    Şimdilik irtifa ve sıcaklık, tabloda birebir bulunan değerlerden biri olmalı.
    """
    kosul = _tablo[(_tablo.irtifa_ft == irtifa_ft) & (_tablo.sicaklik_C == sicaklik_C)]
    if kosul.empty:
        raise ValueError(
            f"{irtifa_ft} ft / {sicaklik_C} °C tabloda yok "
            "(irtifa-sıcaklık interpolasyonu henüz eklenmedi)"
        )
    # Üç noktadan geçen parabol, 1600-1900 dışında ekstrapolasyon yapar; güvenilmez.
    if not DEVIRLER[0] <= devir_rpm <= DEVIRLER[-1]:
        return None

    yakitlar, torklar = [], []
    for devir in DEVIRLER:
        # Aynı hız bazen iki satırda geçiyor (ör. maks_seyir ve en_iyi_menzil); ortalaması alınır.
        # groupby hızları artan sıraya da dizer; np.interp bunu ister (tabloda azalan sırada).
        satirlar = (
            kosul[kosul.devir_rpm == devir]
            .groupby("hiz_ktas")[["yakit_pph", "tork_ftlb"]]
            .mean()
        )
        hizlar = satirlar.index.to_numpy()
        # Tablo aralığı dışında: bu devir o hıza çıkamıyor ya da o hız tabloda yok.
        if satirlar.empty or not hizlar[0] <= hiz_kt <= hizlar[-1]:
            return None
        yakitlar.append(np.interp(hiz_kt, hizlar, satirlar.yakit_pph))
        torklar.append(np.interp(hiz_kt, hizlar, satirlar.tork_ftlb))

    yakit = np.polyval(np.polyfit(DEVIRLER, yakitlar, 2), devir_rpm)
    tork = np.polyval(np.polyfit(DEVIRLER, torklar, 2), devir_rpm)
    return float(yakit), float(tork)


if __name__ == "__main__":
    # KONTROL: 2000 ft, 10 °C, 161 kt
    beklenen = {1900: 374, 1750: 372, 1600: 381}
    for devir, pph in beklenen.items():
        yakit, tork = sanal_ucak(2000, 10, 161, devir)
        print(f"{devir} RPM -> {yakit:6.1f} PPH, {tork:6.0f} ft-lb  (beklenen ~{pph})")
        assert abs(yakit - pph) < 1, (devir, yakit)

    yakit, tork = sanal_ucak(2000, 10, 161, 1820)
    print(f"1820 RPM -> {yakit:6.1f} PPH, {tork:6.0f} ft-lb  (ara devir)")

    # Geçersiz durumlar
    assert sanal_ucak(2000, 10, 175, 1750) is None  # 1600 RPM en fazla 168 kt
    assert sanal_ucak(2000, 10, 150, 1750) is None  # 1900 RPM tablosu 155 kt'dan başlıyor
    assert sanal_ucak(2000, 10, 161, 2000) is None  # devir 1600-1900 dışında
    print("Geçersiz durumlar None döndü.")
