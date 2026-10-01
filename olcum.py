"""
Test dünyası ile algoritma arasındaki köprü.

Algoritma yalnızca olc(devir) -> yakıt (PPH) ya da None bekler. Buradaki
fonksiyonlar sanal_ucak()'ı bu biçime çevirir; algoritma hangisinin verildiğini bilmez.
- olcum_fonksiyonu: ideal ölçüm (anında, kusursuz)
- GercekciOlcum: motor gecikmesi, bekleme, gürültülü örneklerin ortalaması, zaman serisi kaydı
"""
import numpy as np
import pandas as pd

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


class GercekciOlcum:
    """Gerçekçi ölçüm sistemi. Nesnenin kendisi olc(devir) -> yakıt (PPH) olarak algoritmaya verilir.

    İçeride dt adımlı bir zaman simülasyonu çalışır. Her olc(devir) çağrısında:
    1. Devir değiştiyse yeni devir komut edilir ve bekleme_s kadar beklenir (motor oturur).
    2. Sonra ortalama_s boyunca her adımda bir gürültülü örnek alınır; örneklerin ortalaması döner.
    Gerçek yakıt debisi, sanal_ucak'ın yeni devirdeki değerine birinci derece gecikmeyle yaklaşır.

    VARSAYIMLAR (gerçek motor/sensör verisine dayanmıyor, parametre olarak değiştirilebilir):
    - Motor gecikmesi birinci derece, zaman sabiti tau_s = 2 s.
    - Sensör gürültüsü beyaz Gauss: standart sapma = gerçek yakıt × gurultu_yuzde / 100,
      örnekler birbirinden bağımsız (gerçek sensörlerde gürültü ilişkili olabilir; bu iyimser bir varsayım).
    - Örnekleme 10 Hz: her dt = 0,1 s adımında bir örnek.
    - Uçak başlangıçta baslangic_devir'de kararlı seyirde.
    """

    def __init__(self, irtifa, sicaklik, hiz, tau_s=2.0, bekleme_s=None, ortalama_s=5.0,
                 gurultu_yuzde=1.0, dt_s=0.1, baslangic_devir=1900, seed=None):
        self.irtifa, self.sicaklik, self.hiz = irtifa, sicaklik, hiz
        self.tau_s = tau_s
        self.bekleme_s = 3 * tau_s if bekleme_s is None else bekleme_s  # varsayılan: 3 zaman sabiti (~%95 oturma)
        self.ortalama_s = ortalama_s
        self.gurultu = gurultu_yuzde / 100
        self.dt = dt_s
        # Birinci derece gecikmenin tam ayrıklaştırılması: her adımda farkın (1 - e^(-dt/tau)) kadarı kapanır
        self._alfa = 1 - np.exp(-dt_s / tau_s)
        self._rng = np.random.default_rng(seed)

        self.komut = baslangic_devir
        self.gercek = self._kararli_yakit(baslangic_devir)
        if self.gercek is None:
            raise ValueError(f"Başlangıç devrinde ({baslangic_devir} RPM) bu koşul geçersiz")
        self._adim_sayisi = 0
        # Zaman serisi: her dt adımı bir satır (t sonundaki değerler)
        self._kayit = {"t_s": [], "komut_devir": [], "gercek_yakit": [], "olculen_yakit": [], "ornek": []}

    @property
    def t(self):
        """Şu anki zaman (s). Adım sayısından hesaplanır; toplama hatası birikmesin."""
        return self._adim_sayisi * self.dt

    def _kararli_yakit(self, devir):
        sonuc = sanal_ucak(self.irtifa, self.sicaklik, self.hiz, devir)
        return None if sonuc is None else sonuc[0]

    def _adim(self, hedef, ornek):
        """Zamanı bir dt ilerletir: gerçek yakıt hedefe yaklaşır, sensör bir okuma üretir."""
        self._adim_sayisi += 1
        self.gercek += self._alfa * (hedef - self.gercek)
        # Sensör her adımda okur; ortalamaya yalnızca ölçüm penceresindeki okumalar (ornek=True) girer
        olculen = self.gercek * (1 + self.gurultu * self._rng.standard_normal())
        for anahtar, deger in zip(self._kayit, (self.t, self.komut, self.gercek, olculen, ornek)):
            self._kayit[anahtar].append(deger)
        return olculen

    def __call__(self, devir):
        """olc(devir): devri ayarla, bekle, ortalama_s boyunca örnekle, ortalamayı döndür."""
        hedef = self._kararli_yakit(devir)
        if hedef is None:
            return None  # uçak bu devirde bu hızı tutamıyor: devir komut edilmez, zaman ilerlemez
        if devir != self.komut:
            self.komut = devir
            for _ in range(round(self.bekleme_s / self.dt)):
                self._adim(hedef, ornek=False)
        ornekler = [self._adim(hedef, ornek=True) for _ in range(max(1, round(self.ortalama_s / self.dt)))]
        return float(np.mean(ornekler))

    def devam_et(self, devir, bitis_s):
        """Ölçüm yapmadan devri komut eder ve zamanı bitis_s'ye kadar ilerletir (aramadan sonraki seyir)."""
        hedef = self._kararli_yakit(devir)
        self.komut = devir
        while self.t < bitis_s - 1e-9:
            self._adim(hedef, ornek=False)

    def kayit(self):
        """Zaman serisi tablosu: t_s, komut_devir, gercek_yakit (gürültüsüz), olculen_yakit, ornek."""
        return pd.DataFrame(self._kayit)
