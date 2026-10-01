"""
Bütün uçuş zarfı testi.

Tablodaki her irtifa–sıcaklık için üç devrin ortak hız aralığında 5 kt arayla seçilen her hızda,
algoritmanın bulduğu devirdeki yakıt referans en düşük yakıttan en fazla 0,5 PPH fazla olmalı.
Koşullar ve çözüm analiz/adim5.py ile aynı; referans tarama yavaş olduğu için paralel çözülür
(birkaç dakika sürebilir).
"""
import pytest

from analiz.adim5 import ALT_LIMIT, TOLERANS_PPH, UST_LIMIT, basarisiz_detayi, zarf_kosullari, zarfi_coz

pytestmark = pytest.mark.slow  # bütün zarfı tarar (birkaç dakika)


@pytest.fixture(scope="module")
def zarf():
    kosullar, _ = zarf_kosullari()
    return zarfi_coz(kosullar)


def test_zarfta_yakit_farki(zarf):
    basarisizlar = [s for s in zarf if s["yakit_farki_pph"] > TOLERANS_PPH]
    # Başarısız koşullar varsa koşul, referans, bulunan ve denenen devirlerle listelenir
    assert not basarisizlar, (f"{len(basarisizlar)}/{len(zarf)} koşulda fark > {TOLERANS_PPH} PPH:\n"
                              + "\n".join(basarisiz_detayi(s) for s in basarisizlar))


def test_zarfta_devir_limitlerde(zarf):
    disarida = [s for s in zarf if not ALT_LIMIT <= s["bulunan_devir_rpm"] <= UST_LIMIT]
    assert not disarida, "\n".join(basarisiz_detayi(s) for s in disarida)
