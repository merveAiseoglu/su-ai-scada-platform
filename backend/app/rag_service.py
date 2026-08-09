import os

import logging

try:
    import chromadb
    from chromadb.utils import embedding_functions
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    logging.warning("ChromaDB not available in this environment, RAG disabled")

COLLECTION_NAME = "su_kriz_hafizasi"

_client = None


def get_client():
    if not CHROMA_AVAILABLE:
        return None
    global _client
    if _client is None:
        chroma_host = os.getenv("CHROMA_HOST", "localhost")  # default to localhost for local testing
        chroma_port = int(os.getenv("CHROMA_PORT", "8000"))
        _client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
    return _client


# Yerel embedding modeli (all-MiniLM-L6-v2) - OpenAI API'sine ihtiyaç duymaz,
# internet olmadan çalışır (Zero-Trust)
if CHROMA_AVAILABLE:
    default_ef = embedding_functions.DefaultEmbeddingFunction()
else:
    default_ef = None


def get_collection():
    """Koleksiyonu getirir veya yoksa oluşturur"""
    if not CHROMA_AVAILABLE:
        return None
    return get_client().get_or_create_collection(name=COLLECTION_NAME, embedding_function=default_ef)


def search_rag_memory(query_text: str, n_results: int = 2) -> list[str]:
    """
    Verilen metinle semantik arama yaparak geçmişteki en benzer vakaları getirir.
    """
    if not CHROMA_AVAILABLE:
        return []

    collection = get_collection()

    # Veritabanında kayıt yoksa boş dön
    if collection.count() == 0:
        return []

    results = collection.query(query_texts=[query_text], n_results=min(n_results, collection.count()))

    # Eşleşen dökümanları döndür
    if not results or not results["documents"] or not results["documents"][0]:
        return []

    return results["documents"][0]


def preload_rag_model():
    """
    RAG embedding modelini sunucu başlarken (startup) yükleyerek
    ilk istekteki 50-60 saniyelik gecikmeyi (soğuk başlangıç) önler.
    """
    if not CHROMA_AVAILABLE:
        return

    print("[RAG] Hafıza modeli (all-MiniLM-L6-v2) önbelleğe alınıyor...")
    try:
        # Dummy bir metin vererek modeli zorla indir ve belleğe yükle
        default_ef(["preload_test"])
        print("[RAG] Hafıza modeli başarıyla yüklendi ve hazır!")
    except Exception as e:
        print(f"[RAG] Model ön yükleme hatası: {e}")
