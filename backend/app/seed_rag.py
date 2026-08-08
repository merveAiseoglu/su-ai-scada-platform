import os
import sys

# App klasöründeki modüllere erişebilmek için parent dizini ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag_service import get_collection

MOCK_VERILER = [
    {
        "id": "vaka_1",
        "document": "Eyyübiye istasyonunda bulanıklık 1.5 NTU çıktığında, ana vanadaki filtre temizlenerek sorun çözüldü.",
    },
    {
        "id": "vaka_2",
        "document": "Karaköprü 2 nolu depoda serbest klor seviyesi 0.1 mg/L'ye düştüğünde klorlama dozaj pompası debisi artırılarak 0.3 mg/L seviyesine çekildi.",
    },
    {
        "id": "vaka_3",
        "document": "Haliliye şebeke hattında pH 9.8 ölçüldüğünde, bölgedeki yıkama vanası açılarak 2 saat hatta ters yıkama uygulandı ve pH 7.8'e normale döndü.",
    },
    {
        "id": "vaka_4",
        "document": "Birecik su deposunda iletkenlik 2600 µS/cm seviyesine ulaştığında kuyu karışım oranı değiştirilerek iletkenlik 1800 µS/cm seviyesine indirildi.",
    },
    {
        "id": "vaka_5",
        "document": "Siverek merkez istasyonunda sıcaklık 28°C ve klor 0.05 mg/L tespit edildiğinde, sıcaklığa bağlı klor uçuculuğu saptanmış ve ek şok klorlama yapılmıştır.",
    },
]


def run_seed():
    print("ChromaDB yerel model yükleniyor ve kurumsal hafıza tohumlanıyor...")

    collection = get_collection()

    documents = [v["document"] for v in MOCK_VERILER]
    ids = [v["id"] for v in MOCK_VERILER]

    # Verileri ekle (id varsa günceller)
    collection.upsert(documents=documents, ids=ids)

    print(f"Başarıyla {collection.count()} adet kurumsal hafıza kaydı eklendi/güncellendi!")


if __name__ == "__main__":
    run_seed()
