# BioPass 360

DEKATHON 2026 için hazırladığımız ideathon projesi. Etkinliği DEPARK BAMBU GO ile DB Tarımsal Enerji birlikte düzenliyor. Seçtiğimiz çağrı: **01 · Biyoyakıt hammaddelerinde dijital izlenebilirlik ve MRV**.

## Problem

Biyodizel tesisine gelen atık yağın (UCO) gerçekten atık yağ olup olmadığını kapıda hızlıca anlamak zor. AB mevzuatında UCO teşvikli bir hammadde (RED II/III, Annex IX Part B). Bu yüzden içine palm yağı karıştırıp UCO diye satma riski var. Laboratuvar analizi saatler sürüyor ve tanker o sürede kapıda bekliyor.

Bunun yanında her partinin sera gazı tasarrufunun hesaplanıp belgelenmesi gerekiyor. 2021 sonrası kurulan tesislerde bu oranın RED III'e göre en az %65 olması lazım.

## Fikrimiz

Üç parçadan oluşuyor:

1. **Kapıda hızlı kontrol:** El tipi bir NIR spektrometreyle numune taranır. Tağşiş şüphesi varsa parti durdurulur.
2. **Dijital pasaport:** Kabul edilen partiye kaynağı, ağırlığı ve tarama sonucuyla birlikte imzalı bir pasaport verilir.
3. **Otomatik sera gazı hesabı:** Pasaporttaki verilerden partinin sera gazı tasarrufu hesaplanır.

## Bugün ne var, ne yok

| Parça | Durum |
|---|---|
| Sera gazı hesabı (`src/biopass360/mrv/lca_engine.py`) | Çalışıyor, testleri geçiyor. Bugün yalnız FAME biyodizel hesaplanıyor, SAF (HEFA) hesabı yok. |
| Dijital pasaport ve Ed25519 imza (`src/biopass360/passport/`) | Çalışıyor. İmza doğrulamasında bildiğimiz bir açık var, düzeltiyoruz. |
| Tağşiş tespiti (`src/biopass360/spectral/`) | Elimizde spektrometre yok. Sentetik spektrumla simülasyon yapıyoruz. Dedektör şu an 2 testte yanlış sonuç veriyor, üzerinde çalışıyoruz. |
| API (`src/biopass360/api/endpoints.py`) | Uç nokta fonksiyonları yazıldı, ama henüz çalışan bir FastAPI uygulaması yok. |
| Merkle kütüğü, IoT bağlantıları, operatör arayüzü | Plan aşamasında, kodu yok. |
| [biopass360.onrender.com](https://biopass360.onrender.com) | Mimari diyagramı. Çalışan bir demo değil. |

## Çalıştırma

Python 3.10 veya üstü gerekiyor.

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py"
```

Şu an 11 testten 2'si başarısız (tağşiş dedektörü). Gerçek Ed25519 imzası için `pip install cryptography` gerekiyor. Paket kurulu değilse imza modülü test amaçlı bir HMAC yöntemine düşüyor.

## Belgeler

- `docs/vizyon/`: Uzun vadeli hedef tasarım (mimari, arayüz, proje dosyası). Oradaki teknoloji yığını ve rakamların çoğu hedef ya da varsayım. Bugünkü kapsam yukarıdaki tabloda.
- `docs/biopass360_summary.html` ve `docs/BioPass360_DEKATHON2026_Proje_Ozeti.pdf`: Kısa proje özeti.
- [Tanıtım videosu](https://cdn.jsdelivr.net/gh/cirutsohtorik/biopass360@ee43730/docs/brag.mp4)

## Kaynaklar

- THY'nin DB Tarımsal Enerji'ye yaklaşık 42 milyon $ yatırım kararı (Nisan 2026): [Bloomberg HT](https://www.bloomberght.com/thy-den-db-tarimsal-enerji-ye-42-milyon-dolarlik-yatirim-3773513)
- 2025 UCO fiyatları: [Eco-Business / MPOB](https://www.eco-business.com/ms/news/malaysian-palm-oil-board-to-roll-out-used-cooking-oil-reference-price-to-boost-transparency-drive-circularity/)
