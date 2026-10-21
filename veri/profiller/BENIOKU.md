# NeuralFoil profil polarları

Üç profil, iki Reynolds sayısı. Her klasörde `clarky.csv`, `naca4412.csv`, `arad10.csv`.
Bu dosyalar `UmutBosver/Bitirme-Projesi` deposundaki `veri/profiller/` klasörüne olduğu gibi konabilir;
oradaki okuyucu `#` satırlarını ve fazladan sütunları (`cm`, `guven`) atlar.

| Klasör | Re | Ne zaman |
|---|---|---|
| `re1p2M/` | 1,2 milyon | **Önerilen.** Depo README'si 0,75R'de Re ≈ 1,2 milyon diyor. Adım 8'de kullanılan haritalar bu polarlarla birebir yeniden üretiliyor. |
| `re2p5M/` | 2,5 milyon | `pervane/ayarlar.py`'deki tasarım açıları (5,1° / 4,6° / 8,2°) bu Re'de bulunmuş; karşılaştırma için. |

## Ayarlar

- NeuralFoil 0,3,3, model `xlarge` (paketin varsayılanı), n_crit = 9 (serbest geçiş, pürüzsüz yüzey).
- NeuralFoil sıkıştırılamaz akış çözer: Mach = 0. Sıkıştırılabilirlik pervane kodunda ayrıca ekleniyor.
- Hücum açısı −10° … +20°, 0,25° adım (121 satır).
- Koordinatlar: UIUC veritabanı (`clarky`, `naca4412`, `arad10`), aerosandbox içindeki kopyası.
  t/c: Clark Y 0,117, NACA 4412 0,120, ARA-D %10 0,100.
- Sütunlar: `alpha` (°), `cl`, `cd`, `cm`, `guven` (NeuralFoil analysis_confidence, 0–1).

## Kontroller

Depodaki kontrol değerleri (Re = 2,5 milyon, en iyi L/D açısı ve C_L), `re2p5M/` ile:

| Profil | Depodaki | Bu polarlar |
|---|---|---|
| Clark Y | α = 5,1°, C_L = 0,96 | C_L(5,1°) = 0,963 |
| NACA 4412 | α = 4,6°, C_L = 0,99 | C_L(4,6°) = 0,995 |
| ARA-D %10 | α = 8,2°, C_L = 1,37 | C_L(8,2°) = 1,377 |

(0,1° adımla en iyi L/D açısı üçünde de birebir aynı çıkıyor. Daha büyük `xxxlarge` modeli bu değerleri
tutturmuyor; demek ki kontrol değerleri varsayılan modelle üretilmiş.)

`scripts/pervane_haritalari.py` bu polarlarla çalıştırıldığında:

- Tasarım gücü POH'a %0,15 içinde, üç profilde de.
- Maksimum verim: Clark Y 0,893, NACA 4412 0,886–0,890 → TAMAM; ARA-D %10 0,904–0,905 → betiğin
  0,80–0,90 aralığının biraz üstünde ("ARALIK DIŞI"). Bu, betiğin kendi kontrol aralığı; hata değil,
  raporda yorumlanmalı.
- `re1p2M/` ile üretilen haritalar, Adım 8'de kullanılan haritalarla 2000 ft / 10 °C / 161 kt'ta aynı
  β₀.₇₅'i veriyor (fark ≤ 0,04°).

## Sınırlamalar

- Pürüzsüz yüzey, n_crit = 9: sürükleme iyimser.
- Tek Re: kesitten kesite Re değişimi yok.
- NeuralFoil bir sinir ağı yaklaşımı (XFOIL'e eğitilmiş). `guven` hiçbir açıda 0,92'nin altına inmiyor, yani bu
  aralıkta model kendi eğitim verisinin içinde; ama stall sonrası değerler XFOIL'de de belirsizdir.
