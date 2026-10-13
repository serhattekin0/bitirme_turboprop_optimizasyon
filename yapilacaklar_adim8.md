# Adım 8: Bekleyen düzeltmeler

Adım 8'in kodu ve raporu bağımsız olarak denetlendi (10 ajan; her bulgu ayrı bir ajanla çürütülmeye
çalışıldı). Hesaplamalarda hata çıkmadı. Aşağıdaki 6 küçük sorun doğrulandı ve henüz düzeltilmedi.
Hiçbiri sonuçları ya da `ilerleme_raporu.md`'yi değiştirmiyor.

## Kod

1. **(orta) Demo gerçek portla çalışınca zamanlama 2 s kayıyor.** `analiz/demo_pala.py`
   - Sorun: `baslangic = time.monotonic()` satırı, port açılmadan önce alınıyor. `PalaKomutu`
     port açılırken 2 s bekliyor (`acilis_bekleme_s`). Bu yüzden 1900 RPM'deki açı servoda yalnızca
     0,1 s kalıyor, ardından ikinci açı geliyor. Kuru modda sorun yok.
   - Düzeltme: `baslangic = time.monotonic()` satırını `komut = PalaKomutu(...)` satırının hemen
     altına taşımak.

2. **(düşük) Arduino cevabı yarım gelirse yanlış okunabiliyor.** `seri_port.py`, `yanitlari_oku()`
   - Sorun: Port `timeout=0` ile açılı. Bu ayarda `readline()` yarım satırı da döndürüyor. Program
     kapanırken (`kapat()`) son `"OK 29.64"` cevabı ikiye bölünürse `29.0` diye kaydediliyor ya da
     kayboluyor.
   - Düzeltme: Gelen baytları bir tamponda biriktirmek (`self._rx += self._seri.read(in_waiting)`)
     ve yalnızca `\n` ile biten satırları ayrıştırmak. `OK` satırını
     `re.fullmatch(r"OK (-?\d+\.\d+)", satir)` ile okumak, eşleşmezse uyarı yazmak.
     İsteğe bağlı: `kapat()`'ta okumadan önce en fazla 0,1 s cevap beklemek.

## Testler (`testler/test_pala.py`)

3. **(düşük) Komut–ölçüm sırası ve eşik/eşitlik durumları test edilmiyor.**
   - Sorun: `test_sarmalayici_algoritmayi_degistirmez` yalnızca komut sayısına bakıyor, sırasına
     bakmıyor. Oysa rapor "her ölçümden önce bir komut" sınandı diyor. Eşik (`esik_pph > 0`) ve
     eşit yakıt durumları da hiç sınanmıyor. Denetimde kod kasıtlı bozuldu (eşik yok sayıldı, `<`
     yerine `<=` yazıldı, komut ölçümden sonraya alındı); bütün testler yine geçti.
   - Düzeltme: Üç test eklemek.
     - Olayları sırayla kaydedip `olaylar == ["komut", "olc"] * olcum_sayisi` olduğunu sınamak.
     - Aynı tohumla `esik_pph=1.0` verildiğinde sarmalayıcının sonucunun `perturb_observe` ile
       aynı olduğunu sınamak.
     - Eşit değer döndüren sentetik bir `olc` ile eşitlik durumunu sınamak, ör.
       `{1900: 10, 1850: 10, 1875: 11, 1862.5: 11}.get(d, 12)`.

4. **(düşük) Bir test göreli dosya yoluna bağlı.**
   - Sorun: `test_cift_dogrusal_interpolasyon_dugumlerde_tablo_degeri`,
     `"veri/haritalar/naca4412_harita.csv"` yolunu kullanıyor. `testler/` klasöründen
     çalıştırılınca kırılıyor.
   - Düzeltme: `HARITA_KLASORU`'nu import edip
     `pd.read_csv(HARITA_KLASORU / "naca4412_harita.csv")` kullanmak.

## Rapor (`rapor_adim8.md`)

5. **(düşük) J ve C_P aralığı yalnızca referans devri kapsıyor.** (Bölüm 1.2)
   - Sorun: Raporda "J 0,89–1,10, C_P 0,068–0,114" yazıyor. 1900 RPM noktaları da sayılınca aralık
     daha geniş.
   - Düzeltme: "Bu zarfta J 0,86–1,10, C_P 0,055–0,114 aralığında kaldı (en düşük değerler 1900
     RPM'de). Stall bölgesine hiç girilmedi; stall başlangıcına en az 6,4° pay var (ARA-D)."
   - İsteğe bağlı: `analiz/adim8.py` CSV'ye `J_1900` ve `CP_1900` sütunlarını da yazsın.

6. **(düşük) Sınırlamalar 1. maddedeki bir açıklama yanlış.**
   - Sorun: "POH'taki yakıt farklarının bir kısmının motor tarafından gelmesinden" ifadesi itki
     tutarsızlığını açıklamıyor. Tutarsızlık güç ile itki arasında; yakıt bu hesaba girmiyor.
   - Düzeltme: Bu ifadeyi silmek. İstenirse yerine çekinceli bir aday yazmak: "ya da haritalarda
     Mach etkisinin 1900 RPM referansıyla alınmasından (madde 2)".

## Diğer açık konular

- Eski test `test_olcum.py::test_gurultusuz_ve_gecikmesiz_adim5_ile_ayni` bu ortamda kayan nokta
  eşitliği yüzünden kalıyor: 2000 ft / −30 °C / 152 kt'ta 1700 ve 1725 RPM'deki yakıt eşit.
  Test ve dosyalar değiştirilmedi.
- NeuralFoil polarları (Re 1,2 ve 2,5 milyon) üretildi, kullanıcıya zip olarak verildi.
  Pervane deposuna (`UmutBosver/Bitirme-Projesi`, `veri/profiller/`) henüz eklenmedi.
