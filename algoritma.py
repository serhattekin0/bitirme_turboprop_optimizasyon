"""
Perturb & observe (P&O) ile optimum pervane devri arama.

Algoritma uçağı, tabloyu ya da CSV'yi bilmez. Dışarıdan verilen tek bir ölçüm
fonksiyonuyla konuşur:

    olc(devir_rpm) -> yakıt debisi (PPH) ya da geçersizse None

Böylece ölçüm fonksiyonu (gürültülü sürüm, başka test dünyası, gerçek motor)
değiştiğinde bu dosyaya dokunmak gerekmez.
"""
from dataclasses import dataclass, field


@dataclass
class Sonuc:
    devir: float          # bulunan devir (RPM)
    yakit: float          # bulunan devirde ölçülen yakıt (PPH)
    olcum_sayisi: int     # olc() kaç kez çağrıldı
    durma_nedeni: str     # "adım en küçük adımın altına düştü" ya da "ölçüm limiti doldu"
    # Her deneme bir sözlük: devir, yakit (ölçülmediyse/geçersizse None), kabul (True/False),
    # neden ("başlangıç", "daha iyi", "daha kötü", "geçersiz", "limit")
    gecmis: list = field(default_factory=list)


def perturb_observe(
    olc,
    baslangic_devir=1900,
    baslangic_adim=50,
    en_kucuk_adim=10,
    alt_limit=1600,
    ust_limit=1900,
    baslangic_yon=-1,
    en_fazla_olcum=50,
    esik_pph=0,
):
    """Sabit uçuş koşulunda yakıtı en aza indiren devri P&O ile arar.

    Her adımda devir yon*adim kadar oynatılır (perturb), yakıt ölçülür (observe):
    - yakıt düştüyse yeni devre geçilir, aynı yönde aynı adımla devam edilir;
    - düşmediyse (eşit, daha yüksek, geçersiz ya da limit) yerinde kalınır,
      yön çevrilir ve adım yarıya indirilir.
    Adım en_kucuk_adim'ın altına düşünce ya da ölçüm sayısı en_fazla_olcum'a
    ulaşınca durur.

    esik_pph: yeni ölçüm eskisinden esik_pph'den daha fazla düşükse "daha iyi" sayılır.
    Gürültülü ölçümde boşuna yön değiştirmeyi azaltır. Varsayılan 0 = eski davranış
    (her düşüş, ne kadar küçük olursa olsun, kabul edilir; eşitlik "daha kötü").
    """
    if not alt_limit < ust_limit:
        raise ValueError("alt_limit, ust_limit'ten küçük olmalı")
    if not alt_limit <= baslangic_devir <= ust_limit:
        raise ValueError(f"Başlangıç devri {baslangic_devir}, {alt_limit}-{ust_limit} aralığında olmalı")
    if baslangic_yon not in (-1, 1):
        raise ValueError("baslangic_yon -1 (aşağı) ya da +1 (yukarı) olmalı")
    if not 0 < en_kucuk_adim <= baslangic_adim:
        raise ValueError("0 < en_kucuk_adim <= baslangic_adim olmalı")
    if en_fazla_olcum < 1:
        raise ValueError("en_fazla_olcum en az 1 olmalı")
    if esik_pph < 0:
        raise ValueError("esik_pph negatif olamaz")

    # 1) Başlangıç noktasını ölç; karşılaştırma için bir referans gerekiyor
    devir = baslangic_devir
    yakit = olc(devir)
    olcum_sayisi = 1
    if yakit is None:
        raise ValueError(f"Başlangıç devrinde ({devir} RPM) ölçüm geçersiz; karşılaştırma yapılamaz")
    gecmis = [dict(devir=devir, yakit=yakit, kabul=True, neden="başlangıç")]

    adim, yon = baslangic_adim, baslangic_yon
    durma_nedeni = "adım en küçük adımın altına düştü"

    while adim >= en_kucuk_adim:
        # 2) Perturb: devri bir adım oynat, limitlere kırp
        yeni_devir = min(max(devir + yon * adim, alt_limit), ust_limit)

        if yeni_devir == devir:
            # Limitteyiz, gidecek yer yok: ölçmeden "daha kötü" say
            yeni_yakit, neden = None, "limit"
        else:
            if olcum_sayisi >= en_fazla_olcum:
                durma_nedeni = "ölçüm limiti doldu"
                break
            # 3) Observe: yeni devirde yakıtı ölç
            yeni_yakit = olc(yeni_devir)
            olcum_sayisi += 1
            if yeni_yakit is None:
                neden = "geçersiz"
            elif yeni_yakit < yakit - esik_pph:
                neden = "daha iyi"
            else:
                neden = "daha kötü"

        kabul = neden == "daha iyi"
        gecmis.append(dict(devir=yeni_devir, yakit=yeni_yakit, kabul=kabul, neden=neden))

        if kabul:
            # Yakıt düştü: yeni devre geç, aynı yönde devam et
            devir, yakit = yeni_devir, yeni_yakit
        else:
            # Yakıt düşmedi: yerinde kal, geri dön ve daha ince adımla dene
            yon = -yon
            adim /= 2

    return Sonuc(devir=devir, yakit=yakit, olcum_sayisi=olcum_sayisi,
                 durma_nedeni=durma_nedeni, gecmis=gecmis)
