import pytest
from app.rag_service import search_rag_memory

def test_search_rag_memory_with_results(mocker):
    # Mock ChromaDB client and collection
    mock_collection = mocker.MagicMock()
    mock_collection.count.return_value = 1
    mock_collection.query.return_value = {
        "documents": [["Test benzer durum belgesi"]]
    }
    
    mocker.patch("app.rag_service.get_collection", return_value=mock_collection)
    
    results = search_rag_memory("Yüksek klor", n_results=1)
    
    assert len(results) == 1
    assert results[0] == "Test benzer durum belgesi"
    mock_collection.query.assert_called_once_with(query_texts=["Yüksek klor"], n_results=1)

def test_search_rag_memory_empty(mocker):
    mock_collection = mocker.MagicMock()
    mock_collection.count.return_value = 0
    
    mocker.patch("app.rag_service.get_collection", return_value=mock_collection)
    
    results = search_rag_memory("Yüksek klor")
    
    assert results == []
    mock_collection.query.assert_not_called()
