"""
Algoritmanın seçtiği devirden pala açısını hesaplar.

Gerçek uçaktaki sabit hızlı pervane regülatörünün mantığı: motor belli bir güç veriyor, pala da
bu gücü seçilen devirde emecek açıya gelir. Burada:
1. Gücü test dünyasının torkundan bulur: P = devir × tork / 5252 (hp).
2. Bunu boyutsuz güç katsayısına çevirir: C_P = P / (ρ n³ D⁵).
3. BEMT ile üretilmiş pervane haritasında, o J'de bu C_P'yi veren β₀.₇₅'i arar.

Haritalar (veri/haritalar/<profil>_harita.csv) ayrı bir çalışmada üretildi; bu modül onları yalnızca okur.
"""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from sanal_ucak import sanal_ucak

HARITA_KLASORU = Path(__file__).with_name("veri") / "haritalar"
PROFILLER = ("clarky", "naca4412", "arad10")
PROFIL_ADLARI = {"clarky": "Clark Y", "naca4412": "NACA 4412", "arad10": "ARA-D %10"}

CAP_M = 2.69                  # pervane çapı
YARICAP_M = CAP_M / 2         # 1,345 m
R_30INC_M = 30 * 0.0254       # POH'un pala açısını verdiği istasyon: 30 inç = 0,762 m
R_075_M = 0.75 * YARICAP_M    # haritanın referans istasyonu: 0,75R = 1,00875 m

FT_M = 0.3048
KT_MS = 0.5144
HP_W = 745.7
R_HAVA = 287.05               # J/(kg·K)

TARAMA_ADIMI = 0.01           # derece, ilk kesişimi bulmak için kaba tarama
IKIYE_BOLME_TOL = 1e-6        # derece


class Harita:
    """Bir pala profilinin C_T(J, β) ve C_P(J, β) haritası; düzenli ızgarada çift doğrusal interpolasyon."""

    def __init__(self, profil):
        if profil not in PROFILLER:
            raise ValueError(f"Bilinmeyen profil {profil!r}; seçenekler: {', '.join(PROFILLER)}")
        self.profil = profil
        tablo = pd.read_csv(HARITA_KLASORU / f"{profil}_harita.csv")
        self.J = np.sort(tablo.J.unique())
        self.beta = np.sort(tablo.beta75.unique())
        # Izgara düzenli ve eksiksiz olmalı; değilse çift doğrusal interpolasyon yanlış hücreye bakar
        if len(tablo) != len(self.J) * len(self.beta):
            raise ValueError(f"{profil} haritası düzenli bir ızgara değil")
        tablo = tablo.sort_values(["beta75", "J"])
        sekil = (len(self.beta), len(self.J))
        self._CT = tablo.CT.to_numpy().reshape(sekil)   # [β indeksi, J indeksi]
        self._CP = tablo.CP.to_numpy().reshape(sekil)

        geometri = pd.read_csv(HARITA_KLASORU / f"{profil}_geometri.csv")
        self._r = geometri.r_m.to_numpy()
        self._teta = geometri.pala_acisi_deg.to_numpy()

    def _ara(self, dizi, J, beta):
        """Çift doğrusal interpolasyon. Izgara dışında NaN döner (ekstrapolasyon yapılmaz)."""
        if not (self.J[0] <= J <= self.J[-1] and self.beta[0] <= beta <= self.beta[-1]):
            return np.nan
        # Hücre indeksleri: son düğümde son hücrenin üst kenarı kullanılır
        i = min(np.searchsorted(self.beta, beta, side="right") - 1, len(self.beta) - 2)
        j = min(np.searchsorted(self.J, J, side="right") - 1, len(self.J) - 2)
        tb = (beta - self.beta[i]) / (self.beta[i + 1] - self.beta[i])
        tj = (J - self.J[j]) / (self.J[j + 1] - self.J[j])
        return float((1 - tb) * ((1 - tj) * dizi[i, j] + tj * dizi[i, j + 1])
                     + tb * ((1 - tj) * dizi[i + 1, j] + tj * dizi[i + 1, j + 1]))

    def CT(self, J, beta):
        return self._ara(self._CT, J, beta)

    def CP(self, J, beta):
        return self._ara(self._CP, J, beta)

    def teta(self, r_m):
        """Tasarım noktasındaki pala açısı dağılımı θ(r), derece."""
        return float(np.interp(r_m, self._r, self._teta))

    def beta_bul(self, J, CP_gerekli):
        """C_P(J, β) = CP_gerekli denkleminin 15°'den yukarı doğru İLK kökü; kesişim yoksa NaN.

        Düşük J / yüksek β bölgesinde stall yüzünden C_P, β ile tekdüze artmayabilir; birden çok kök
        olabilir. Fiziksel olan, regülatörün düşük açıdan gelerek ulaştığı ilk köktür.
        """
        if not self.J[0] <= J <= self.J[-1]:
            return np.nan  # J harita aralığı dışında
        betalar = np.arange(self.beta[0], self.beta[-1] + TARAMA_ADIMI / 2, TARAMA_ADIMI)
        betalar[-1] = min(betalar[-1], self.beta[-1])
        # Tarama vektörel: önce her β düğümünde J yönünde, sonra β yönünde doğrusal ara değer.
        # Bu, CP() ile aynı çift doğrusal interpolasyondur, yalnızca 3500 noktayı tek seferde hesaplar.
        j = min(np.searchsorted(self.J, J, side="right") - 1, len(self.J) - 2)
        tj = (J - self.J[j]) / (self.J[j + 1] - self.J[j])
        CP_dugum = (1 - tj) * self._CP[:, j] + tj * self._CP[:, j + 1]
        fark = np.interp(betalar, self.beta, CP_dugum) - CP_gerekli
        if fark[0] == 0:
            return float(betalar[0])
        isaret_degisimi = np.flatnonzero(np.sign(fark[:-1]) != np.sign(fark[1:]))
        if isaret_degisimi.size == 0:
            return np.nan
        k = isaret_degisimi[0]
        a, b, fa = betalar[k], betalar[k + 1], fark[k]
        while b - a > IKIYE_BOLME_TOL:
            orta = (a + b) / 2
            fo = self.CP(J, orta) - CP_gerekli
            if fo == 0:
                return float(orta)
            if np.sign(fo) == np.sign(fa):
                a, fa = orta, fo
            else:
                b = orta
        return float((a + b) / 2)


@lru_cache(maxsize=None)
def harita(profil):
    """Profil haritası; her profil bir kez okunur ve önbellekte tutulur."""
    return Harita(profil)


def yogunluk(irtifa_ft, sicaklik_C):
    """Hava yoğunluğu (kg/m³): basınç ISA'dan (basınç irtifası), sıcaklık gerçek değerden."""
    h = irtifa_ft * FT_M
    T_isa = 288.15 - 0.0065 * h
    p = 101325 * (T_isa / 288.15) ** 5.25588
    return p / (R_HAVA * (sicaklik_C + 273.15))


@dataclass
class PalaAcisi:
    beta75: float        # 0,75R'de pala açısı (derece); kesişim yoksa NaN
    beta_30inc: float    # 30 inç istasyonunda pala açısı (POH'un kullandığı), derece
    itki_N: float        # itki (N)
    verim: float         # pervane verimi J·C_T/C_P
    J: float             # ilerleme oranı
    C_P: float           # gerekli güç katsayısı
    guc_W: float         # motorun pervaneye verdiği güç (W)
    rho: float           # hava yoğunluğu (kg/m³)


def pala_acisi(profil, irtifa_ft, sicaklik_C, hiz_kt, devir_rpm, dunya=sanal_ucak):
    """Verilen koşul ve devirde, motorun gücünü emen pala açısı. Test dünyası koşulu geçersiz sayarsa None."""
    sonuc = dunya(irtifa_ft, sicaklik_C, hiz_kt, devir_rpm)
    if sonuc is None:
        return None
    _, tork_ftlb = sonuc
    h = harita(profil)

    guc_W = devir_rpm * tork_ftlb / 5252 * HP_W
    rho = yogunluk(irtifa_ft, sicaklik_C)
    V = hiz_kt * KT_MS
    n = devir_rpm / 60
    J = V / (n * CAP_M)
    CP_gerekli = guc_W / (rho * n**3 * CAP_M**5)

    beta75 = h.beta_bul(J, CP_gerekli)
    if np.isnan(beta75):
        return PalaAcisi(np.nan, np.nan, np.nan, np.nan, J, CP_gerekli, guc_W, rho)
    beta_30inc = beta75 + h.teta(R_30INC_M) - h.teta(R_075_M)
    CT = h.CT(J, beta75)
    itki_N = CT * rho * n**2 * CAP_M**4
    verim = J * CT / CP_gerekli
    return PalaAcisi(beta75, beta_30inc, itki_N, verim, J, CP_gerekli, guc_W, rho)


if __name__ == "__main__":
    print(f"{'Profil':<11}{'Devir':>7}{'J':>7}{'C_P':>8}{'β75':>8}{'β30inç':>8}{'İtki N':>9}{'Verim':>7}")
    for profil in PROFILLER:
        for devir in (1900, 1750, 1600):
            s = pala_acisi(profil, 2000, 10, 161, devir)
            print(f"{PROFIL_ADLARI[profil]:<11}{devir:>7}{s.J:>7.3f}{s.C_P:>8.4f}{s.beta75:>8.2f}"
                  f"{s.beta_30inc:>8.2f}{s.itki_N:>9.0f}{s.verim:>7.3f}")
