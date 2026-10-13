# Bitirme Projesi İlerleme Raporu

**Konu:** Cessna 208B Grand Caravan'da pervane devrinin, seyir sırasında yakıtı en aza indirecek
şekilde otomatik olarak ayarlanması.

**Fikir:** Her uçuş koşulunda (irtifa, sıcaklık, hız) yakıtı en az yakan pervane devri farklıdır.
Bir algoritma devri küçük adımlarla değiştirip yakıt debisini ölçerek bu en iyi devri kendisi
bulabilir. Prototipte bu devre, pala açısı bir servo ile değiştirilerek ulaşılacak.

**Karşılaştırma ölçütü:** Uçağın el kitabı (POH) seyir tablolarını üç devirde veriyor: 1600, 1750
ve 1900 RPM. Bütün tasarruf rakamları, aynı uçuş hızında **sabit 1900 RPM** ile uçmaya göre
verildi. Algoritma da aramaya 1900 RPM'den başlıyor. Pilot başka bir devirde uçuyorsa
(ör. 1750 RPM) rakamlar değişir.

---

## Şu ana kadar yapılanlar

### 1. Uçak verisinin sayısallaştırılması
El kitabındaki seyir performans tabloları sayısal bir tabloya aktarıldı: farklı irtifa, sıcaklık
ve devirlerde hız, tork ve yakıt debisi (yaklaşık 1080 satır).

### 2. Sanal uçak (test ortamı)
Bu tablodan beslenen bir "sanal uçak" yazıldı. Sanal uçak, girilen irtifa, sıcaklık, hız ve
devirde yakıt debisini ve torku hesaplıyor. El kitabında yalnızca üç devir olduğu için aradaki
devirlerdeki değerler bu üç noktadan geçen bir eğriyle hesaplanıyor. Algoritma, gerçek uçak yerine
bu sanal uçak üzerinde denendi.

### 3. Yakıt–devir eğrileri
Birkaç uçuş koşulunda devir 1600'den 1900'e taranarak yakıt–devir eğrileri çizildi. En az yakıtın
her koşulda farklı bir devirde olduğu görüldü.

### 4. Arama algoritması
"Perturb & observe" (dene ve gözle) algoritması yazıldı. Algoritma devri bir adım değiştiriyor.
Yakıt azaldıysa aynı yönde devam ediyor; azalmadıysa geri dönüp adımı küçültüyor. Dört örnek
koşulda en iyi devri buldu.

### 5. Uçuş zarfı genelinde deneme
Algoritma, el kitabı tablolarından seçilen 392 uçuş koşulunda çalıştırıldı: 2.000–24.000 ft,
−54 ile +30 °C arası, 142–182 kt. Bunlar, üç devrin de aynı hızı verebildiği koşullar.
- Her koşulda en iyi devri buldu.
- Sabit 1900 RPM'e göre yakıt tasarrufu ortalama **%0,2**, en fazla **%2**.
- Koşulların yaklaşık yarısında en iyi devir zaten 1900 RPM; ortalamanın küçük olmasının nedeni bu.
- Kazanç alçak irtifa ve soğuk havada daha belirgin, yüksek irtifada ise neredeyse yok.

### 6. Gerçekçi ölçüm
Gerçekte yakıt ölçümü gürültülüdür ve motor yeni devre hemen oturmaz. Bu etkiler simülasyona
eklendi: %1 ölçüm gürültüsü, motor gecikmesi ve ölçümlerin ortalamasının alınması.
- Algoritma koşuların yaklaşık **%96**'sında en iyi devre yeterince yakın bir devirde durdu
  (yakıt farkı saatte 0,5 lb'den az).
- Arama sırasında harcanan yakıt dahil, gürültüsüz durumdaki kazancın yaklaşık **%80**'i elde
  edildi.
- Kazanılacak bir şey olmayan koşullarda, yani en iyi devrin zaten 1900 RPM olduğu (çoğu yüksek
  irtifadaki) koşullarda, arama çok küçük bir kayba yol açıyor. Kazancın belirgin olduğu
  koşullarda hiç kayıp yok.

### 7. Model hatasına dayanıklılık
Önce 6. adımdaki küçük kayıpları azaltmak için iki ayar denendi:
- Ölçüm süresini 10 saniyeden 20 saniyeye çıkarmak başarıyı yaklaşık %99'a yükseltti. Bu ayar
  kullanıldı.
- Aramanın sonunda emin olunamazsa 1900 RPM'e geri dönen bir kontrol, tasarrufu azalttığı için
  kullanılmadı.

Gerçek uçak el kitabından biraz farklı davranabilir (motor yaşı, pervane durumu vb.). Bu yüzden yakıt
değerleri el kitabından bilerek saptırılmış bir sanal uçakta (1600 ve 1900 RPM'de %1'e kadar)
dört yöntem karşılaştırıldı:
- sabit 1900 RPM,
- devir çizelgesi: her uçuş koşulu için el kitabından önceden hesaplanmış en iyi devri veren tablo,
- arama algoritması,
- çizelge devrinden başlayıp arama yapan karma bir yöntem.

Ölçüt, o uçağın gerçek en iyi devrinde uçmaya göre fazladan yakılan yakıt.
- Uçak el kitabına tam uyuyorsa en iyisi çizelge. Küçük sapmalarda (%0,5) çizelge ile arama
  algoritması hâlâ başa baş.
- Sapma büyüdükçe (%1) çizelgenin fazladan yakıtı hızla artıyor. Arama algoritmasınınki sınırlı
  kalıyor; algoritma çizelgeden açıkça daha iyi oluyor.
- Karma yöntem beklenenden zayıf çıktı: Çoğunlukla çizelge devrinde kaldığı için sapmanın bir
  yönünde iyi, öbür yönünde neredeyse çizelge kadar kötü sonuç verdi.
- Farklar mutlak olarak küçük (yakıtın %1'inden az). Önemli olan eğilim.

**Projenin ana sonucu:** Arama algoritması, gerçek uçağın el kitabından farklı olduğu durumlara
karşı daha dayanıklı. Sapma burada yapay ve basit bir modelle, %1'e kadar denendi.

### 8. Pervane modeli (paralel çalışma)
Gerçek pervanenin verisi olmadığı için aynı çap (2,69 m) ve pala sayısında (3) temsili pervaneler
tasarlandı:
- Üç pala profili: Clark Y, NACA 4412, ARA-D %10.
- Profil verileri NeuralFoil programıyla üretildi.
- Pervaneler 10.000 ft, 0 °C, 179 kt ve 1900 RPM'deki seyir koşuluna göre Adkins–Liebeck
  yöntemiyle tasarlandı. Performans, pala elemanı–momentum teorisiyle (BEMT) hesaplandı.
- Her profil için pervane haritaları çıkarıldı: hangi pala açısında ne kadar itki ve güç.
- Hesap yöntemi, Clark Y profilli pervane için JavaProp programıyla karşılaştırıldı. Aynı profil
  verisi kullanıldığında itki ve güç katsayıları %1'den az farkla tuttu. Diğer iki profil için bu
  karşılaştırma henüz yapılmadı.
- Pala üzerindeki akışa uygun Reynolds sayısında (yaklaşık 1,2 milyon) profil verileri NeuralFoil
  ile yeniden üretildi. Bu verilerle haritalar pratikte aynı çıkıyor. Veriler henüz pervane
  modelinin deposuna eklenmedi.

### 9. Pala açısı ve prototip bağlantısı
Algoritmanın bulduğu devir, pervane haritası kullanılarak bir **pala açısına** çevrildi. Mantık,
gerçek uçaktaki devir regülatörüyle aynı: Pala, motorun gücünü seçilen devirde emecek açıya gelir.
- Devir düştükçe pala açısı büyüyor. Örneğin 2000 ft, 10 °C, 161 kt'ta 1900 RPM'den 1600 RPM'e
  inerken açı yaklaşık 27,5°'den 34,4°'ye çıkıyor (Clark Y).
- Algoritma artık her adımda, denediği devirle birlikte pala açısını da veriyor.
- Bilgisayar tarafında, açıyı seri port üzerinden Arduino'ya gönderen program yazıldı. Arduino için
  de açıyı servoya uygulayacak taslak bir program hazırlandı. Bu taslak henüz derlenmedi ve
  donanımda denenmedi.
- Şimdiye kadarki denemeler, komutları yalnızca ekrana yazan donanımsız modda yapıldı. Örnek bir
  koşuda algoritma yaklaşık 2,5 dakikada en iyi devri buldu ve palayı yaklaşık 2° çevirdi. Sabit
  1900 RPM'e göre tasarruf %0,7.

---

## Kontroller

- Algoritma ve sonraki adımlar için otomatik testler yazıldı. Son çalıştırmada 111 testin 110'u
  geçti. Kalan bir eski test, sayısal bir yuvarlama farkından kalıyor.
- İlk adımlarda (tablo ve sanal uçak) sonuçlar el kitabı tablosuyla karşılaştırılarak elle kontrol
  edildi.
- 5, 6, 7 ve 9. adımların sonuçları ayrıntılı olarak ayrı raporlarda var. Pervane modeli kendi
  deposunda anlatılıyor.

---

## Bilinen sınırlamalar

- Test ortamı uçağın el kitabından türetildi; gerçek uçuş verisi kullanılmadı.
- El kitabındaki yakıt değerleri tam sayıya yuvarlanmış. Bu yüzden bulunan en iyi devir yaklaşık
  ±30 RPM belirsiz, ama bunun yakıta etkisi çok küçük.
- Pervane haritaları Caravan'ın gerçek pervanesine değil, temsili pervanelere ait.
- El kitabındaki güç değerleri ile pervane haritaları birbirini tam doğrulamıyor. Devir düştükçe
  hesaplanan itki %2–4 azalıyor; oysa aynı hızda sabit kalmalıydı.
- Profil verileri pürüzsüz yüzey varsayımıyla üretildi. Bu yüzden sürükleme gerçekte olduğundan
  düşük (iyimser) çıkıyor.
- Arduino programı ve servo–pala açısı eşleştirmesi henüz donanımda denenmedi; eşleştirme şimdilik
  varsayılan değerlerle.

---

## Sıradaki adımlar

1. Yeni profil verilerini pervane modeline ekleyip haritaları yeniden üretmek, ardından pala
   geometrisini CAD'e aktarmak.
2. Arduino programını derleyip prototipte servo–pala açısı eşleştirmesini ölçmek.
3. Algoritmayı Arduino ve servo ile prototip üzerinde denemek.
4. Sonuçları tez metnine aktarmak.
