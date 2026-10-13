"""
Adım 8 demosu: gerçekçi ölçümle P&O çalışır, her yeni devirde pala açısı PalaKomutu'na gönderilir.

Örnekler:
    python analiz/demo_pala.py --profil clarky                      # kuru mod, donanım yok
    python analiz/demo_pala.py --profil arad10 --port COM5          # Arduino'ya gönderir
    python analiz/demo_pala.py --profil naca4412 --hiz-carpani 0    # beklemeden, anında

Simülasyon zamanı GercekciOlcum'un içinde ilerler. --hiz-carpani, bu zamanın gerçek zamana göre
kaç kat hızlı oynatılacağını belirler (10: 20 s'lik ölçüm 2 s sürer). 0 verilirse hiç beklenmez.
"""
import argparse
import sys
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from olcum import GercekciOlcum
from pala_acisi import PROFIL_ADLARI, PROFILLER
from pala_algoritma import pala_perturb_observe
from sanal_ucak import sanal_ucak
from seri_port import PalaKomutu

GURULTU_YUZDE = 1.0
ORTALAMA_S = 20.0
SABIT_DEVIR = 1900


def calistir(profil, irtifa, sicaklik, hiz, port=None, hiz_carpani=10.0, seed=0, sessiz=False):
    """Demoyu bir profil için çalıştırır: (PalaSonuc, GercekciOlcum, PalaKomutu)."""
    olc = GercekciOlcum(irtifa, sicaklik, hiz, gurultu_yuzde=GURULTU_YUZDE, ortalama_s=ORTALAMA_S, seed=seed)
    baslangic = time.monotonic()

    def zamana_kadar_bekle(t_sim):
        """Gerçek zaman, simülasyon zamanının hiz_carpani'na bölünmüşüne yetişene kadar bekler."""
        if hiz_carpani and hiz_carpani > 0:
            kalan = baslangic + t_sim / hiz_carpani - time.monotonic()
            if kalan > 0:
                time.sleep(kalan)

    def yaz(metin):
        if not sessiz:
            print(metin)

    def adim_bildir(s):
        zamana_kadar_bekle(s["t_olcum_s"])
        yakit = "geçersiz" if s["yakit"] is None else f"{s['yakit']:8.2f}"
        karar = "kabul" if s["kabul"] else "ret"
        yaz(f"{s['t_olcum_s']:7.1f} s  {s['devir']:7.1f} RPM  {yakit} PPH  {karar:<5}  "
            f"β75 {s['beta75']:6.2f}°  (30 inç: {s['beta_30inc']:5.2f}°)  [{s['neden']}]")

    komut = PalaKomutu(port=port, sessiz=sessiz)

    def gonder(beta75):
        zamana_kadar_bekle(olc.t)
        komut.gonder(beta75)

    yaz(f"\n=== {PROFIL_ADLARI[profil]} | {irtifa} ft, {sicaklik} °C, {hiz} kt | "
        f"{'kuru mod' if port is None else port} | hız çarpanı {hiz_carpani:g} ===")
    yaz(f"{'Zaman':>9}  {'Devir':>11}  {'Ölçülen yakıt':>12}  Karar  Pala açısı")
    try:
        sonuc = pala_perturb_observe(olc, profil, irtifa, sicaklik, hiz, komut=gonder, adim_bildir=adim_bildir)
        # Arama bitti: bulunan devre dön ve açısını gönder (son ölçülen devir bulunan devir olmayabilir)
        if olc.komut != sonuc.devir:
            gonder(sonuc.beta75)
            olc.devam_et(sonuc.devir, olc.t)
    finally:
        komut.kapat()
    return sonuc, olc, komut


def ozet(profil, irtifa, sicaklik, hiz, sonuc, olc, komut):
    y_bulunan = sanal_ucak(irtifa, sicaklik, hiz, sonuc.devir)[0]
    y_1900 = sanal_ucak(irtifa, sicaklik, hiz, SABIT_DEVIR)[0]
    p1900 = sonuc.gecmis.loc[sonuc.gecmis.devir == SABIT_DEVIR].iloc[0]
    print(f"--- Özet ({PROFIL_ADLARI[profil]}) ---")
    print(f"Bulunan devir     : {sonuc.devir:g} RPM ({sonuc.sonuc.olcum_sayisi} ölçüm, {olc.t:.0f} s arama)")
    print(f"Pala açısı        : β75 = {sonuc.beta75:.2f}°, 30 inç = {sonuc.beta_30inc:.2f}°  "
          f"(1900 RPM'de β75 = {p1900.beta75:.2f}°)")
    print(f"Gerçek yakıt      : {y_bulunan:.2f} PPH (1900 RPM: {y_1900:.2f} PPH)")
    print(f"Tasarruf (kararlı): {y_1900 - y_bulunan:.2f} PPH (%{100 * (y_1900 - y_bulunan) / y_1900:.2f})")
    print(f"Pervane           : itki {sonuc.pala.itki_N:.0f} N, verim {sonuc.pala.verim:.3f}, J {sonuc.pala.J:.3f}")
    print(f"Gönderilen komut  : {len(komut.gonderilenler)}, Arduino cevabı: {len(komut.yanitlar)}, "
          f"uyarı: {len(komut.uyarilar)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profil", choices=PROFILLER, default="clarky")
    ap.add_argument("--irtifa", type=int, default=2000, help="ft (tablodaki değerlerden biri)")
    ap.add_argument("--sicaklik", type=int, default=10, help="°C (tablodaki değerlerden biri)")
    ap.add_argument("--hiz", type=float, default=161, help="kt")
    ap.add_argument("--port", default=None, help="seri port (ör. COM5, /dev/ttyACM0); verilmezse kuru mod")
    ap.add_argument("--hiz-carpani", type=float, default=10, help="simülasyon gerçek zamandan kaç kat hızlı")
    ap.add_argument("--seed", type=int, default=0, help="gürültü tohumu")
    a = ap.parse_args()

    sonuc, olc, komut = calistir(a.profil, a.irtifa, a.sicaklik, a.hiz, a.port, a.hiz_carpani, a.seed)
    print(sonuc.gecmis.to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    ozet(a.profil, a.irtifa, a.sicaklik, a.hiz, sonuc, olc, komut)


if __name__ == "__main__":
    main()
