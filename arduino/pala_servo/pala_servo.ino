/*
 * Pala açısı servo sürücüsü (taslak)
 *
 * ÖNEMLİ: Pala açısı, palanın 0,75R kesitinde ölçülmeli.
 *         (2,69 m çaplı pervane için r = 0,75 x 1,345 m = 1,009 m.)
 *         Python tarafı (pala_acisi.py) bu istasyondaki açıyı (beta75) gönderir.
 *
 * Protokol (115200 baud, satır sonu '\n'):
 *   Gelen : "B <açı>"   ör. "B 30.50"  -> 0,75R'de istenen pala açısı, derece
 *   Giden : "OK <açı>"  ör. "OK 30.50" -> sınırlara kırpılıp uygulanan pala açısı
 *   Anlaşılmayan satırlara "ERR <satır>" döner.
 */
#include <Servo.h>

// ---------------------------------------------------------------- sabitler
const int   SERVO_PINI     = 9;
const long  BAUD           = 115200;
const float PALA_ACI_MIN   = 15.0;   // derece (0,75R), Python tarafındaki aci_min ile aynı
const float PALA_ACI_MAX   = 50.0;   // derece (0,75R), Python tarafındaki aci_max ile aynı
const int   SERVO_US_MIN   = 544;    // servo.write(0) karşılığı darbe genişliği (Servo kütüphanesi varsayılanı)
const int   SERVO_US_MAX   = 2400;   // servo.write(180) karşılığı

// ---------------------------------------------------------------- kalibrasyon tablosu
// YER TUTUCU: Aşağıdaki değerler doğrusal bir varsayımdır, ölçülmüş DEĞİLDİR.
// Prototipte servo açısı adım adım değiştirilip palanın 0,75R kesitindeki açısı
// açıölçerle ölçülerek doldurulacak. pala_acisi[] artan sırada olmalı.
// Nokta sayısı değişebilir; KALIBRASYON_N kendiliğinden güncellenir.
const float pala_acisi[]  = {15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0};    // derece, 0,75R
const float servo_acisi[] = {20.0, 40.0, 60.0, 80.0, 100.0, 120.0, 140.0, 160.0}; // derece, servo mili
const int KALIBRASYON_N = sizeof(pala_acisi) / sizeof(pala_acisi[0]);

Servo servo;
char tampon[32];
int tampon_uzunluk = 0;

// Pala açısını kalibrasyon tablosundan parça parça doğrusal ara değerle servo açısına çevirir.
float servo_acisina_cevir(float pala) {
  if (pala <= pala_acisi[0]) return servo_acisi[0];
  if (pala >= pala_acisi[KALIBRASYON_N - 1]) return servo_acisi[KALIBRASYON_N - 1];
  for (int i = 0; i < KALIBRASYON_N - 1; i++) {
    if (pala <= pala_acisi[i + 1]) {
      float t = (pala - pala_acisi[i]) / (pala_acisi[i + 1] - pala_acisi[i]);
      return servo_acisi[i] + t * (servo_acisi[i + 1] - servo_acisi[i]);
    }
  }
  return servo_acisi[KALIBRASYON_N - 1];
}

// Servo açısını mikrosaniyeye çevirip yazar; servo.write(int) yerine kesirli derece çözünürlüğü verir.
void servoyu_sur(float servo_derece) {
  int us = SERVO_US_MIN + (int)(servo_derece / 180.0 * (SERVO_US_MAX - SERVO_US_MIN) + 0.5);
  servo.writeMicroseconds(us);
}

void satiri_isle(const char *satir) {
  if (satir[0] == 'B' && satir[1] == ' ') {
    char *son;
    float aci = strtod(satir + 2, &son);
    if (son != satir + 2) {
      aci = constrain(aci, PALA_ACI_MIN, PALA_ACI_MAX);
      servoyu_sur(servo_acisina_cevir(aci));
      Serial.print("OK ");
      Serial.println(aci, 2);
      return;
    }
  }
  Serial.print("ERR ");
  Serial.println(satir);
}

void setup() {
  Serial.begin(BAUD);
  servo.attach(SERVO_PINI, SERVO_US_MIN, SERVO_US_MAX);
  servoyu_sur(servo_acisina_cevir(PALA_ACI_MIN));  // açılışta en düşük açıda bekle
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      tampon[tampon_uzunluk] = '\0';
      if (tampon_uzunluk > 0) satiri_isle(tampon);
      tampon_uzunluk = 0;
    } else if (tampon_uzunluk < (int)sizeof(tampon) - 1) {
      tampon[tampon_uzunluk++] = c;
    }
  }
}
