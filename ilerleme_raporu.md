# Bitirme Projesi İlerleme Raporu

**Konu:** Cessna 208B Grand Caravan'da pervane devrinin, seyir sırasında yakıtı en aza indirecek
şekilde otomatik olarak ayarlanması.

**Fikir:** Pilot seyirde genellikle devri sabit bir değerde (ör. 1900 RPM) tutar. Oysa her uçuş
koşulunda (irtifa, sıcaklık, hız) yakıtı en az yakan devir farklıdır. Bir algoritma devri küçük
adımlarla değiştirip yakıt debisini ölçerek bu en iyi devri kendisi bulabilir. Prototipte bu devir,
pala açısını bir servo ile değiştirerek uygulanacak.

---

## Şu ana kadar yapılanlar

### 1. Uçak verisinin sayısallaştırılması
Uçağın el kitabındaki (POH) seyir performans tabloları sayısal bir tabloya aktarıldı:
farklı irtifa, sıcaklık ve devirlerde (1600, 1750, 1900 RPM) hız, tork ve yakıt debisi
(yaklaşık 1080 satır).

### 2. Sanal uçak (test ortamı)
Bu tablodan beslenen bir "sanal uçak" yazıldı. Verilen irtifa, sıcaklık, hız ve devirde yakıt
debisini ve torku veriyor. Algoritma, gerçek uçak yerine bu sanal uçak üzerinde denendi.

### 3. Yakıt–devir eğrileri
Birkaç uçuş koşulunda devir 1600'den 1900'e taranarak yakıt–devir eğrileri çizildi. En az yakıtın
her koşulda farklı bir devirde olduğu görüldü.

### 4. Arama algoritması
"Perturb & observe" (dene ve gözle) algoritması yazıldı: Devri bir adım değiştirir, yakıt
azaldıysa aynı yönde devam eder, artarsa geri döner ve adımı küçültür. Dört örnek koşulda en iyi
devri buldu.

### 5. Bütün uçuş zarfında deneme
Algoritma el kitabındaki bütün uçuş koşullarında (392 koşul) çalıştırıldı.
- Her koşulda en iyi devri buldu.
- Sabit 1900 RPM'e göre yakıt tasarrufu ortalama **%0,2**, en fazla **%2**.
- Kazanç alçak irtifa ve soğuk havada büyük, yüksek irtifada neredeyse yok.

### 6. Gerçekçi ölçüm
Gerçekte yakıt ölçümü gürültülüdür ve motor yeni devre hemen oturmaz. Bu etkiler simülasyona
eklendi (%1 ölçüm gürültüsü, motor gecikmesi, ölçümlerin ortalaması).
- Algoritma koşuların yaklaşık **%96**'sında yine doğru devre ulaştı.
- Arama sırasında harcanan yakıt dahil, ideal kazancın yaklaşık **%80**'i elde edildi.

### 7. Model hatasına dayanıklılık
Gerçek uçak el kitabından biraz farklı davranabilir (motor yaşı, pervane durumu vb.). Bu yüzden
el kitabından bilerek saptırılmış bir sanal uçakta üç yöntem karşılaştırıldı: sabit 1900 RPM,
el kitabından hazırlanmış sabit bir devir çizelgesi ve arama algoritması.
- Uçak el kitabına tam uyuyorsa en iyisi çizelge.
- Uçak el kitabından saptıkça çizelgenin hatası hızla büyüyor; arama algoritmasının hatası ise
  küçük kalıyor.
- **Bu, projenin ana sonucu:** Arama algoritması, gerçek uçağın el kitabından farklı olduğu
  durumlara karşı daha dayanıklı.

### 8. Pervane modeli (paralel çalışma)
Gerçek pervanenin verisi olmadığı için aynı çap (2,69 m) ve pala sayısında (3) temsili pervaneler
tasarlandı:
- Üç pala profili: Clark Y, NACA 4412, ARA-D %10.
- Profil verileri NeuralFoil programıyla üretildi.
- Pala tasarımı Adkins–Liebeck yöntemiyle, performans hesabı pala elemanı–momentum teorisiyle
  (BEMT) yapıldı.
- Her profil için pervane haritaları çıkarıldı: hangi pala açısında ne kadar itki ve güç.
- Model, JavaProp programıyla karşılaştırılarak doğrulandı.

### 9. Pala açısı ve prototip bağlantısı
Algoritmanın bulduğu devir, pervane haritası kullanılarak bir **pala açısına** çevrildi. Mantık,
gerçek uçaktaki devir regülatörüyle aynı: Pala, motorun gücünü seçilen devirde emecek açıya gelir.
- Devir düştükçe pala açısı büyüyor. Örneğin 2000 ft, 10 °C, 161 kt'ta 1900 RPM'den 1600 RPM'e
  inerken açı yaklaşık 27,5°'den 34,4°'e çıkıyor (Clark Y).
- Algoritma artık her adımda denediği devirle birlikte pala açısını da veriyor.
- Açı, bilgisayardan seri port üzerinden Arduino'ya gönderiliyor. Arduino açıyı servoya
  uyguluyor. Donanım olmadan da denenebilen bir deneme modu var.
- Örnek bir koşuda algoritma yaklaşık 2,5 dakikada en iyi devri buldu ve palayı yaklaşık 2°
  çevirdi; sabit 1900 RPM'e göre tasarruf %0,7.

---

## Her adımda yapılan kontroller

- Her adım için otomatik testler yazıldı ve çalıştırıldı.
- Her adımın sonuçları ayrı bir raporda toplandı.

---

## Bilinen sınırlamalar

- Test ortamı uçağın el kitabından türetildi; gerçek uçuş verisi kullanılmadı.
- Pervane haritaları Caravan'ın gerçek pervanesine değil, temsili pervanelere ait.
- El kitabındaki güç değerleri ile pervane haritaları birbirini tam doğrulamıyor. Devir düştükçe
  hesaplanan itki %2–3 azalıyor; oysa aynı hızda sabit kalmalıydı.
- Profil verileri pürüzsüz yüzey varsayımıyla üretildi; sürükleme biraz iyimser.

---

## Sıradaki adımlar

1. Pervane haritalarını son profil verileriyle yeniden üretmek ve pala geometrisini CAD'e
   aktarmak.
2. Prototipte servo–pala açısı kalibrasyonunu ölçmek.
3. Algoritmayı Arduino ve servo ile prototip üzerinde denemek.
4. Sonuçları tez metnine aktarmak.
