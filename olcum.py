"""
Test dünyası ile algoritma arasındaki köprü.

Algoritma yalnızca olc(devir) -> yakıt (PPH) ya da None bekler. Buradaki
fonksiyonlar sanal_ucak()'ı bu biçime çevirir. Gürültülü ölçüm ya da başka bir
test dünyası eklenecekse buraya yeni bir olc üretici yazılır; algoritma aynı kalır.
"""
import numpy as np

from sanal_ucak import DEVIRLER, sanal_ucak


def olcum_fonksiyonu(irtifa, sicaklik, hiz):
    """Sabit koşul (irtifa ft, sıcaklık °C, hız kt) için olc(devir) fonksiyonu döndürür."""
    def olc(devir):
        sonuc = sanal_ucak(irtifa, sicaklik, hiz, devir)
        # sanal_ucak (yakıt, tork) döndürür; algoritmaya yalnızca yakıt verilir
        return None if sonuc is None else sonuc[0]
    return olc


def referans_tarama(irtifa, sicaklik, hiz, adim=1):
    """Devri 1600-1900 arasında `adim` RPM aralıkla tarar: (devirler, yakıtlar) dizileri.

    Algoritmanın bulduğu sonucu karşılaştırmak için "gerçek" eğri ve optimum buradan alınır.
    Geçersiz devirlerde yakıt NaN olur.
    """
    olc = olcum_fonksiyonu(irtifa, sicaklik, hiz)
    devirler = np.arange(DEVIRLER[0], DEVIRLER[-1] + 1, adim)
    yakitlar = [olc(d) for d in devirler]
    yakitlar = np.array([np.nan if y is None else y for y in yakitlar])
    return devirler, yakitlar
