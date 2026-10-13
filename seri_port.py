"""
Pala açısını seri port üzerinden Arduino'ya gönderir (arduino/pala_servo/pala_servo.ino).

Mesaj: "B 30.50\\n" (0,75R'de pala açısı, derece, 2 ondalık, nokta ile).
Arduino açıyı uyguladıktan sonra "OK 30.50" döner. Cevap okunursa kaydedilir; gelmezse beklenmez.

port=None ise kuru çalışma modu: hiçbir donanım açılmaz, mesajlar yalnızca listeye ve konsola yazılır.
"""
import math
import time


class PalaKomutu:
    def __init__(self, port=None, baud=115200, aci_min=15, aci_max=50, max_hz=10, acilis_bekleme_s=2.0,
                 sessiz=False):
        if not aci_min < aci_max:
            raise ValueError("aci_min, aci_max'tan küçük olmalı")
        if max_hz <= 0:
            raise ValueError("max_hz pozitif olmalı")
        self.port = port
        self.aci_min, self.aci_max = aci_min, aci_max
        self.min_aralik_s = 1 / max_hz
        self.sessiz = sessiz
        self.gonderilenler = []   # (zaman_s, mesaj) - zaman: time.monotonic()
        self.yanitlar = []        # (zaman_s, açı) - Arduino'nun "OK <açı>" cevapları
        self.uyarilar = []
        self._son_gonderim = -math.inf
        self._seri = None
        if port is not None:
            import serial  # pyserial yalnızca gerçek port kullanılırken gerekir

            # timeout=0: okumalar engellemez, cevap yoksa beklenmez
            self._seri = serial.Serial(port, baud, timeout=0, write_timeout=1)
            # Çoğu Arduino port açılınca yeniden başlar; açılış mesajı gelmeden komut gönderilmesin
            time.sleep(acilis_bekleme_s)
            self._seri.reset_input_buffer()

    @property
    def kuru(self):
        return self._seri is None

    def _yaz(self, metin):
        if not self.sessiz:
            print(metin)

    def _uyar(self, metin):
        self.uyarilar.append(metin)
        self._yaz(f"UYARI: {metin}")

    def gonder(self, aci):
        """Açıyı sınırlara kırpar, hız sınırına uyarak gönderir; gönderilen mesajı döndürür (gönderilmezse None)."""
        if aci is None or math.isnan(aci):
            self._uyar("geçersiz açı (NaN), komut gönderilmedi")
            return None
        kirpilmis = min(max(aci, self.aci_min), self.aci_max)
        if kirpilmis != aci:
            self._uyar(f"açı {aci:.2f}°, {self.aci_min}–{self.aci_max}° aralığı dışında; {kirpilmis:.2f}°'ye kırpıldı")

        # Hız sınırı: iki mesaj arası en az 1/max_hz saniye. Komut düşürülmez, sıra gelene kadar beklenir;
        # servo için son komut önemli olduğu için atlamak yerine geciktirmek tercih edildi.
        bekle = self._son_gonderim + self.min_aralik_s - time.monotonic()
        if bekle > 0:
            time.sleep(bekle)

        mesaj = f"B {kirpilmis:.2f}\n"
        self._son_gonderim = time.monotonic()
        self.gonderilenler.append((self._son_gonderim, mesaj))
        if self.kuru:
            self._yaz(f"  [kuru] -> {mesaj.strip()}")
        else:
            self._seri.write(mesaj.encode("ascii"))
            self.yanitlari_oku()
        return mesaj

    def yanitlari_oku(self):
        """Tamponda bekleyen "OK <açı>" satırlarını okur ve kaydeder; beklemez."""
        if self.kuru:
            return
        while self._seri.in_waiting:
            satir = self._seri.readline().decode("ascii", errors="replace").strip()
            if not satir:
                break
            if satir.startswith("OK "):
                try:
                    self.yanitlar.append((time.monotonic(), float(satir[3:])))
                except ValueError:
                    self._uyar(f"anlaşılamayan cevap: {satir!r}")
            else:
                self._yaz(f"  [arduino] {satir}")

    def kapat(self):
        if self._seri is not None:
            self.yanitlari_oku()
            self._seri.close()
            self._seri = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.kapat()
