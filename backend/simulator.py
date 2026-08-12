#!/usr/bin/env python3
"""
simulator.py — Su-AI IoT Veri Akışı Simülatörü
================================================
Sahadan periyodik olarak veri akışını simüle eder.
Backend'in POST /api/sim/tetikle endpoint'ini kullanır.

Kullanım:
    python simulator.py                         # Varsayılan: 15 sn, karışık mod, sonsuz
    python simulator.py --mod anomali           # Sadece anomalili ölçümler
    python simulator.py --mod normal --adet 10  # 10 normal ölçüm
    python simulator.py --aralik 5 --istasyon 2 # Belirli istasyon, 5 sn aralık
    python simulator.py --mod karisik --aralik 10 --adet 20

Argümanlar:
    --url         Backend URL  (varsayılan: http://192.168.1.103:8000)
    --kullanici   Admin e-posta (varsayılan: admin@suski.gov.tr)
    --sifre       Admin şifre  (varsayılan: admin123)
    --istasyon    İstasyon ID  (varsayılan: tüm aktif istasyonlar döngüsel)
    --mod         normal | anomali | karisik  (varsayılan: karisik)
    --aralik      Saniye cinsinden ölçüm aralığı (varsayılan: 15)
    --adet        Toplam ölçüm sayısı; 0 = sonsuz (varsayılan: 0)
"""

import argparse
import time
import sys
import json
import random
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime

# ── Terminal renk kodları ────────────────────────────────────────────────────
R  = "\033[91m"   # Kırmızı  — KRİTİK
O  = "\033[93m"   # Sarı     — ORTA/DÜŞÜK
G  = "\033[92m"   # Yeşil    — NORMAL
B  = "\033[94m"   # Mavi     — Bilgi
D  = "\033[2m"    # Soluk    — Detay
NC = "\033[0m"    # Reset

RISK_RENK = {"KRİTİK": R, "ORTA": O, "DÜŞÜK": O, "NORMAL": G}


def zaman_damgasi():
    return datetime.now().strftime("%H:%M:%S")


def log(mesaj, renk=B):
    print(f"{D}[{zaman_damgasi()}]{NC} {renk}{mesaj}{NC}")


# ── HTTP yardımcıları ─────────────────────────────────────────────────────────

def token_al(base_url: str, kullanici: str, sifre: str) -> str:
    """Admin token'ı /token endpoint'inden alır."""
    log("🔐 Token alınıyor...", B)
    veri = urllib.parse.urlencode({"username": kullanici, "password": sifre}).encode()
    req = urllib.request.Request(
        f"{base_url}/token",
        data=veri,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as yanit:
        data = json.loads(yanit.read())
        token = data["access_token"]
        log(f"✅ Token alındı ({token[:20]}...)", G)
        return token


def aktif_istasyonlari_al(base_url: str, token: str) -> list[int]:
    """Aktif istasyon ID'lerini GIS endpoint'inden çeker."""
    req = urllib.request.Request(
        f"{base_url}/api/gis/istasyonlar",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as yanit:
        istasyonlar = json.loads(yanit.read())
        idler = [i["id"] for i in istasyonlar if i.get("aktif_mi", True)]
        log(f"📍 {len(idler)} aktif istasyon bulundu: {idler}", B)
        return idler


def olcum_tetikle(base_url: str, token: str, istasyon_id: int, mod: str) -> dict:
    """POST /api/sim/tetikle çağrısı yapar."""
    url = f"{base_url}/api/sim/tetikle?istasyon_id={istasyon_id}&mod={mod}"
    req = urllib.request.Request(
        url,
        data=b"",  # POST body boş — query params kullanıyoruz
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as yanit:
        return json.loads(yanit.read())


# ── Ana simülatör döngüsü ─────────────────────────────────────────────────────

def calistir(args):
    print(f"\n{'═'*55}")
    print(f"  Su-AI IoT Simülatörü — Mod: {args.mod.upper()}")
    print(f"  Hedef: {args.url}")
    print(f"  Aralık: {args.aralik} sn | Adet: {'Sonsuz' if args.adet == 0 else args.adet}")
    print(f"{'═'*55}\n")

    # Token al
    try:
        token = token_al(args.url, args.kullanici, args.sifre)
    except Exception as e:
        log(f"❌ Token alınamadı: {e}", R)
        sys.exit(1)

    # İstasyon listesi
    if args.istasyon:
        istasyon_listesi = [args.istasyon]
    else:
        try:
            istasyon_listesi = aktif_istasyonlari_al(args.url, token)
        except Exception as e:
            log(f"❌ İstasyonlar alınamadı: {e}", R)
            istasyon_listesi = [1]  # fallback

    if not istasyon_listesi:
        log("❌ Hiç aktif istasyon bulunamadı!", R)
        sys.exit(1)

    toplam_gonderilen = 0
    ist_index = 0

    log(f"🚀 Simülasyon başlatılıyor...\n", G)

    while True:
        if args.adet > 0 and toplam_gonderilen >= args.adet:
            break

        ist_id = istasyon_listesi[ist_index % len(istasyon_listesi)]
        ist_index += 1

        try:
            yanit = olcum_tetikle(args.url, token, ist_id, args.mod)
            risk = yanit.get("risk_seviyesi", "NORMAL") or "NORMAL"
            renk = RISK_RENK.get(risk, G)

            toplam_gonderilen += 1
            log(
                f"[#{toplam_gonderilen:03d}] İstasyon {ist_id} → "
                f"pH:{yanit.get('ph','?')}  "
                f"Cl:{yanit.get('serbest_klor','?')}mg/L  "
                f"NTU:{yanit.get('bulaniklik','?')}  "
                f"Risk:{risk}",
                renk,
            )

        except urllib.error.HTTPError as e:
            hata = e.read().decode()
            log(f"⚠️  HTTP {e.code} — İstasyon {ist_id}: {hata[:80]}", O)
            # 401 gelirse token yenile
            if e.code == 401:
                try:
                    token = token_al(args.url, args.kullanici, args.sifre)
                except Exception:
                    pass
        except urllib.error.URLError as e:
            log(f"🔌 Bağlantı hatası: {e.reason} — {args.aralik} sn sonra tekrar denenecek", R)
        except Exception as e:
            log(f"❌ Beklenmeyen hata: {e}", R)

        # Sonraki döngüye kadar bekle (Ctrl+C ile kesilebilir)
        try:
            time.sleep(args.aralik)
        except KeyboardInterrupt:
            break

    print(f"\n{'─'*55}")
    log(f"✅ Simülasyon tamamlandı. Toplam {toplam_gonderilen} ölçüm gönderildi.", G)
    print(f"{'─'*55}\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Su-AI IoT Veri Akışı Simülatörü",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--url",       default="http://192.168.1.103:8000", help="Backend URL")
    parser.add_argument("--kullanici", default="admin@suski.gov.tr",        help="Admin e-posta")
    parser.add_argument("--sifre",     default="admin123",                  help="Admin şifre")
    parser.add_argument("--istasyon",  type=int, default=None,              help="Belirli istasyon ID (yoksa döngüsel)")
    parser.add_argument("--mod",       default="karisik",
                        choices=["normal", "anomali", "karisik"],           help="Veri modu")
    parser.add_argument("--aralik",    type=float, default=15.0,            help="Ölçüm aralığı (saniye)")
    parser.add_argument("--adet",      type=int,   default=0,               help="Toplam ölçüm sayısı (0=sonsuz)")

    args = parser.parse_args()

    try:
        calistir(args)
    except KeyboardInterrupt:
        log("\n🛑 Simülasyon kullanıcı tarafından durduruldu.", O)
        sys.exit(0)


if __name__ == "__main__":
    main()
