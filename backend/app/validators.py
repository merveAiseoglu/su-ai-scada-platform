import ast


def kural_mantigi_gecerli_mi(kural_mantigi: str) -> tuple[bool, str | None]:
    """
    Bir kural_mantigi string'inin geçerli Python syntax'ına sahip olup
    olmadığını kontrol eder. (True, None) veya (False, hata_mesaji) döner.
    """
    if not isinstance(kural_mantigi, str) or not kural_mantigi.strip():
        return False, "Kural mantığı boş olamaz."
    try:
        ast.parse(kural_mantigi, mode="eval")
        return True, None
    except SyntaxError as e:
        return False, str(e)
