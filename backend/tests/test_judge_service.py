import json
import pytest
from sqlalchemy.future import select

from app import models
from app.judge_service import degerlendir_llm_ciktisi, _get_judge_prompt
from app.models import SuOlcumu, Istasyon


def test_judge_prompt_contains_rag_instruction():
    prompt = _get_judge_prompt()
    assert "Doğrulanmış Kurumsal Hafıza" in prompt
    assert "KESİNLİKLE halüsinasyon DEĞİLDİR" in prompt


@pytest.mark.asyncio
async def test_judge_service_prompt_includes_rag_context(test_db, seed_users, mocker):
    # Setup Istasyon & SuOlcumu
    istasyon = Istasyon(id=1, ad="Merkez Depo", tip="Depo", aktif_mi=True, organization_id=seed_users["org"].id)
    test_db.add(istasyon)
    await test_db.flush()

    olcum = SuOlcumu(
        id=101,
        istasyon_id=1,
        ph=7.2,
        serbest_klor=0.15,
        bulaniklik=0.5,
        risk_seviyesi="ORTA",
        analiz_durumu="BEKLİYOR"
    )
    test_db.add(olcum)
    await test_db.commit()

    captured_messages = []

    async def mock_get_llm_response(messages, **kwargs):
        captured_messages.extend(messages)
        return json.dumps({
            "uygunluk_puani": 98,
            "degerlendirme_notu": "LLM önerisi kural motoru ve RAG kurumsal hafızasıyla tam uyumludur."
        }), "mock-openai"

    mocker.patch("app.judge_service._get_llm_response", side_effect=mock_get_llm_response)

    anomali_raporu = {
        "durum": "ANOMALİ_VAR",
        "en_yuksek_risk_seviyesi": "ORTA",
        "detaylar": [{"kural": "Düşük Klor", "mesaj": "Klor seviyesi yetersiz (0.15 mg/L)", "risk": "ORTA"}]
    }

    llm_onerisi = "1. Klor dozaj pompasını kontrol edin. Daha önce Haliliye su deposunda benzer durumda dozaj valfi temizlenerek sorun giderilmişti."
    benzer_vakalar = ["Haliliye su deposunda 2025 yılında düşük klor arızası yaşanmış, dozaj valfi temizliğiyle çözülmüştür."]

    # Provide db sessionmaker factory for test_db
    class MockDbFactory:
        def __call__(self):
            return test_db_context(test_db)

    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def test_db_context(db_session):
        yield db_session

    await degerlendir_llm_ciktisi(
        olcum_id=101,
        anomali_raporu=anomali_raporu,
        llm_onerisi=llm_onerisi,
        db_factory=lambda: test_db_context(test_db),
        provider="mock-openai",
        istasyon_id=1,
        benzer_vakalar=benzer_vakalar
    )

    # 1. Assert user prompt received the RAG context block
    user_prompt = next(m["content"] for m in captured_messages if m["role"] == "user")
    assert "=== DOĞRULANMIŞ KURUMSAL HAFIZA (RAG Vaka Kayıtları) ===" in user_prompt
    assert "Haliliye su deposunda 2025 yılında" in user_prompt
    assert "halüsinasyon sayılmamalıdır" in user_prompt

    # 2. Assert AnalizMetrikleri was written to database
    res = await test_db.execute(select(models.AnalizMetrikleri).filter(models.AnalizMetrikleri.olcum_id == 101))
    metrik = res.scalars().first()
    assert metrik is not None
    assert metrik.uygunluk_puani == 98
    assert "RAG kurumsal hafızasıyla tam uyumludur" in metrik.degerlendirme_notu
