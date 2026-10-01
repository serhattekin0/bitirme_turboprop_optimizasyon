"""
P&O aramasının etrafına eklenen stratejiler.

Stratejiler de algoritma gibi yalnızca olc(devir) -> yakıt (PPH) ya da None fonksiyonunu görür;
test dünyasını ya da tabloyu bilmez.
"""
from dataclasses import dataclass
from math import sqrt


@dataclass
class GeriDonusSonucu:
    devir: float               # karar: bulunan devir ya da referans devir
    geri_donuldu: bool         # referans devre geri dönüldü mü
    yakit_bulunan: float       # bulunan devirde yeniden ölçülen yakıt (kontrol yapılmadıysa None)
    yakit_referans: float      # referans devirde yeniden ölçülen yakıt (kontrol yapılmadıysa None)
    esik_pph: float            # kullanılan karar eşiği (kontrol yapılmadıysa None)
    olcum_sayisi: int          # kontrolün yaptığı ölçüm sayısı (0 ya da 2)


def geri_donus_kontrolu(olc, bulunan_devir, referans_devir, gurultu_orani, ornek_sayisi, k=2.0):
    """P&O bittikten sonra bulunan devri bir referans devirle (normalde başlangıç devri) karşılaştırır.

    Her iki devirde yakıt, aramadakiyle aynı ölçüm sistemiyle yeniden ölçülür. Bulunan devir,
    referanstan en az `esik` kadar düşük ölçülmezse referans devre geri dönülür. Amaç, gürültü
    yüzünden referanstan aslında iyi olmayan bir devirde kalmayı önlemek.

    Eşik, iki ölçüm ortalamasının farkındaki gürültüden hesaplanır:
        esik = k × sqrt(2) × (gurultu_orani × yakıt) / sqrt(ornek_sayisi)
    gurultu_orani: tek örneğin bağıl standart sapması (ör. 0,01); ornek_sayisi: bir ölçümdeki örnek
    sayısı; yakıt: iki ölçümün ortalaması. k = 2 yaklaşık %98 tek yönlü güven demektir
    (gürültüsüz durumda eşik 0 olur ve en küçük düşüş bile yeterlidir).

    Yeniden ölçümler olc() üzerinden yapıldığı için süreleri ve yakıtları ölçüm sisteminin kaydına,
    yani arama maliyetine girer. Önce referans, sonra bulunan devir ölçülür: bulunan devir
    tutulursa motor zaten oradadır, ek bir geçiş gerekmez.
    """
    if bulunan_devir == referans_devir:
        # Karşılaştırılacak bir şey yok: ölçüm yapmadan referansta kal
        return GeriDonusSonucu(referans_devir, False, None, None, None, 0)

    yakit_referans = olc(referans_devir)
    yakit_bulunan = olc(bulunan_devir)
    if yakit_bulunan is None:
        return GeriDonusSonucu(referans_devir, True, None, yakit_referans, None, 2)
    if yakit_referans is None:
        return GeriDonusSonucu(bulunan_devir, False, yakit_bulunan, None, None, 2)

    yakit = (yakit_referans + yakit_bulunan) / 2
    esik = k * sqrt(2) * gurultu_orani * yakit / sqrt(ornek_sayisi)
    tut = yakit_referans - yakit_bulunan >= esik
    return GeriDonusSonucu(bulunan_devir if tut else referans_devir, not tut,
                           yakit_bulunan, yakit_referans, esik, 2)
