import os
import chromadb
from chromadb.utils import embedding_functions

# Proje dizininde chroma_db klasörü
CHROMA_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chroma_db")
COLLECTION_NAME = "su_kriz_hafizasi"

# PersistentClient (kalıcı db) oluştur
client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

# Yerel embedding modeli (all-MiniLM-L6-v2) - OpenAI API'sine ihtiyaç duymaz,
# internet olmadan çalışır (Zero-Trust)
default_ef = embedding_functions.DefaultEmbeddingFunction()

def get_collection():
    """Koleksiyonu getirir veya yoksa oluşturur"""
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=default_ef
    )

def search_rag_memory(query_text: str, n_results: int = 2) -> list[str]:
    """
    Verilen metinle semantik arama yaparak geçmişteki en benzer vakaları getirir.
    """
    collection = get_collection()
    
    # Veritabanında kayıt yoksa boş dön
    if collection.count() == 0:
        return []
    
    results = collection.query(
        query_texts=[query_text],
        n_results=min(n_results, collection.count())
    )
    
    # Eşleşen dökümanları döndür
    if not results or not results["documents"] or not results["documents"][0]:
        return []
        
    return results["documents"][0]

def preload_rag_model():
    """
    RAG embedding modelini sunucu başlarken (startup) yükleyerek 
    ilk istekteki 50-60 saniyelik gecikmeyi (soğuk başlangıç) önler.
    """
    print("[RAG] Hafıza modeli (all-MiniLM-L6-v2) önbelleğe alınıyor...")
    try:
        # Dummy bir metin vererek modeli zorla indir ve belleğe yükle
        default_ef(["preload_test"])
        print("[RAG] Hafıza modeli başarıyla yüklendi ve hazır!")
    except Exception as e:
        print(f"[RAG] Model ön yükleme hatası: {e}")
