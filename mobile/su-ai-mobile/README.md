# Su-AI Mobil Uygulaması (React Native / Expo)

Şanlıurfa Su ve Kanalizasyon İdaresi (ŞUSKİ) Su Kalitesi İzleme ve Karar Destek Mobil Uygulaması.

## Backend Bağlantısı ve IP Yapılandırması

Mobil uygulama backend API sunucusuna `app.json` dosyasındaki merkezi yapılandırma üzerinden bağlanır.

### Yerel Ağ IP Değişikliği:
Geliştirme ortamında veya fiziksel cihaz testlerinde backend sunucunuzun yerel ağ IP'si değiştiğinde, **kod içinde hiçbir dosyayı değiştirmenize gerek yoktur**. Sadece `app.json` içerisindeki `extra.apiBaseUrl` değerini güncellemeniz yeterlidir:

```json
{
  "expo": {
    ...
    "extra": {
      "apiBaseUrl": "http://<YENI_IP_ADRESI>:8080"
    }
  }
}
```

Uygulama çalışma anında `expo-constants` (`Constants.expoConfig.extra.apiBaseUrl`) üzerinden bu değeri otomatik olarak okur.

## Kurulum ve Çalıştırma

```bash
# Bağımlılıkları yükleyin
npm install

# Expo geliştirme sunucusunu başlatın
npx expo start
```
