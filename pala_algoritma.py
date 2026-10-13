"""
Perturb & observe'u pala açısıyla birlikte çalıştıran sarmalayıcı.

algoritma.py değişmedi. Sarmalayıcı, algoritmaya verilen olc(devir) fonksiyonunu sarar:
her ölçümden önce denenen devrin pala açısını hesaplar ve (verildiyse) komut fonksiyonuna gönderir,
sonra asıl ölçümü yapar. Prototipte sıra da böyle: önce pala döner, devir oturur, sonra yakıt ölçülür.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from algoritma import Sonuc, perturb_observe
from pala_acisi import PalaAcisi, pala_acisi
from sanal_ucak import sanal_ucak


@dataclass
class PalaSonuc:
    sonuc: Sonuc              # perturb_observe'un kendi sonucu (değişmeden)
    gecmis: pd.DataFrame      # adım başına: devir, yakit, kabul, neden, beta75, beta_30inc (+ zaman, varsa)
    devir: float              # bulunan devir
    pala: PalaAcisi           # bulunan devirdeki pala açısı ve diğer büyüklükler

    @property
    def beta75(self):
        return self.pala.beta75

    @property
    def beta_30inc(self):
        return self.pala.beta_30inc


def pala_perturb_observe(olc, profil, irtifa, sicaklik, hiz, dunya=sanal_ucak, komut=None, adim_bildir=None,
                         **po_ayarlari):
    """Perturb & observe'u çalıştırır; her ölçülen devir için pala açısını hesaplar ve kaydeder.

    olc:         algoritmaya verilecek ölçüm fonksiyonu (olcum_fonksiyonu, GercekciOlcum, ...)
    komut:       komut(beta75) - her yeni devirde ölçümden ÖNCE çağrılır (ör. PalaKomutu.gonder)
    adim_bildir: adim_bildir(satir) - her ölçümden SONRA çağrılır; satır, geçmiş tablosunun satırıyla
                 aynı alanlara sahip bir sözlük (canlı konsol çıktısı için)
    po_ayarlari: perturb_observe'a aynen geçirilir (baslangic_devir, esik_pph, ...)

    Kabul/ret kararı algoritmanın içinde verilir ve olc()'dan görünmez. Canlı bildirim için karar,
    algoritmanın kuralı (yeni yakıt < kabul edilen yakıt − esik_pph) burada tekrarlanarak bulunur;
    koşu bitince algoritmanın kendi geçmişiyle karşılaştırılır, uyuşmazsa hata verilir.
    """
    esik = po_ayarlari.get("esik_pph", 0)
    acilar = {}            # devir -> PalaAcisi (aynı devir tekrar denenirse yeniden hesaplanmaz)
    olcumler = []          # olc() çağrıları sırasıyla: devir, yakıt, zaman, tahmini kabul
    durum = {"yakit": None}

    def aci(devir):
        if devir not in acilar:
            acilar[devir] = pala_acisi(profil, irtifa, sicaklik, hiz, devir, dunya)
        return acilar[devir]

    def sarili_olc(devir):
        p = aci(devir)
        t_komut = getattr(olc, "t", None)
        if komut is not None and p is not None and not np.isnan(p.beta75):
            komut(p.beta75)
        yakit = olc(devir)
        # Algoritmanın kabul kuralı; ilk ölçüm başlangıç noktası, her zaman "kabul"
        if durum["yakit"] is None:
            kabul, neden = yakit is not None, "başlangıç"
        elif yakit is None:
            kabul, neden = False, "geçersiz"
        else:
            kabul = yakit < durum["yakit"] - esik
            neden = "daha iyi" if kabul else "daha kötü"
        if kabul:
            durum["yakit"] = yakit
        satir = _satir(devir, yakit, kabul, neden, p, t_komut, getattr(olc, "t", None))
        olcumler.append(satir)
        if adim_bildir is not None:
            adim_bildir(satir)
        return yakit

    sonuc = perturb_observe(sarili_olc, **po_ayarlari)

    # Geçmiş tablosu algoritmanın kendi geçmişinden kurulur; "limit" adımlarında olc() çağrılmaz
    satirlar, o = [], iter(olcumler)
    for g in sonuc.gecmis:
        if g["neden"] == "limit":
            satirlar.append(_satir(g["devir"], None, False, "limit", aci(g["devir"]), None, None))
            continue
        s = next(o)
        if (s["devir"], s["kabul"], s["neden"]) != (g["devir"], g["kabul"], g["neden"]):
            raise RuntimeError(f"Canlı kabul kararı algoritmayla uyuşmuyor: {s} / {g}")
        satirlar.append(s)

    return PalaSonuc(sonuc=sonuc, gecmis=pd.DataFrame(satirlar), devir=sonuc.devir, pala=aci(sonuc.devir))


def _satir(devir, yakit, kabul, neden, p, t_komut, t_olcum):
    satir = dict(devir=devir, yakit=yakit, kabul=kabul, neden=neden,
                 beta75=np.nan if p is None else p.beta75,
                 beta_30inc=np.nan if p is None else p.beta_30inc)
    if t_komut is not None or t_olcum is not None:
        satir.update(t_komut_s=t_komut, t_olcum_s=t_olcum)
    return satir
