"""
Sapmalı dünya: uçağın POH tablosundan farklı davrandığı bir test dünyası.

    yakıt_sapmalı = yakıt × (1 + e × (devir − 1750) / 150)

e > 0 iken yüksek devir tablodakinden daha pahalı (optimum aşağı kayar), e < 0 iken daha ucuz
(optimum yukarı kayar). 1750 RPM'de yakıt değişmez; 1600 ve 1900 RPM'de yakıt ±e oranında değişir.
Tork değişmez.

UYARI: Bu fiziksel bir model DEĞİLDİR. Motor yaşlanması, pervane aşınması ya da kurulum farkı gibi
nedenlerle gerçek uçağın tablodan saptığı durumu temsil eden bir duyarlılık analizidir. Amaç,
tablodan çıkarılmış sabit bir çizelgenin model hatasına karşı ne kadar dayanıklı olduğunu ölçmek.
"""
from sanal_ucak import sanal_ucak

MERKEZ_DEVIR = 1750   # yakıtın değişmediği devir
YARIM_ARALIK = 150    # 1600 ve 1900 RPM'de sapma tam e oranında


def sapmali_dunya(e, taban=sanal_ucak):
    """sanal_ucak ile aynı imzaya sahip sapmalı bir dünya fonksiyonu döndürür.

    e: sapma oranı (ör. 0,01 = %1). taban: sapmanın uygulandığı dünya (varsayılan sanal_ucak;
    hız için önbellekli bir sürümü de verilebilir, sonuç aynıdır)."""
    def dunya(irtifa_ft, sicaklik_C, hiz_kt, devir_rpm):
        sonuc = taban(irtifa_ft, sicaklik_C, hiz_kt, devir_rpm)
        if sonuc is None:
            return None  # taban dünyada geçersizse sapmalı dünyada da geçersiz
        yakit, tork = sonuc
        return yakit * (1 + e * (devir_rpm - MERKEZ_DEVIR) / YARIM_ARALIK), tork
    return dunya
