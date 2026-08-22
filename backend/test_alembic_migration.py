import os
import sys
import subprocess
import psycopg2

DB_NAME = "su_ai_alembic_test"
DB_HOST = "postgres"
DB_USER = "postgres"
DB_PASS = "merve-dev-password"

def run_test():
    print("=" * 60)
    print("ALEMBIC MIGRATION TEST: 47ab31706e6f_add_predictive_engine_columns")
    print("=" * 60)

    # 1. Recreate clean test database
    admin_conn = psycopg2.connect(dbname="postgres", user=DB_USER, password=DB_PASS, host=DB_HOST, port=5432)
    admin_conn.autocommit = True
    cur = admin_conn.cursor()
    cur.execute(f"DROP DATABASE IF EXISTS {DB_NAME};")
    cur.execute(f"CREATE DATABASE {DB_NAME};")
    cur.close()
    admin_conn.close()
    print(f"[1] Temiz test veritabanı '{DB_NAME}' oluşturuldu.")

    # 2. Create initial base schema (without the 4 columns) & organizations / istasyonlar
    db_conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=5432)
    db_conn.autocommit = True
    cur = db_conn.cursor()
    
    cur.execute("""
    CREATE TABLE organizations (
        id UUID PRIMARY KEY,
        name VARCHAR NOT NULL UNIQUE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    CREATE TABLE istasyonlar (
        id SERIAL PRIMARY KEY,
        organization_id UUID NOT NULL REFERENCES organizations(id),
        ad VARCHAR NOT NULL,
        konum VARCHAR,
        tip VARCHAR NOT NULL,
        aktif_mi BOOLEAN DEFAULT TRUE,
        enlem FLOAT,
        boylam FLOAT
    );
    CREATE TABLE su_olcumleri (
        id SERIAL PRIMARY KEY,
        istasyon_id INTEGER NOT NULL REFERENCES istasyonlar(id),
        ph FLOAT,
        serbest_klor FLOAT,
        bulaniklik FLOAT,
        iletkenlik FLOAT,
        sicaklik FLOAT,
        olcum_tarihi TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        personel_notu TEXT,
        analiz_durumu VARCHAR DEFAULT 'BEKLİYOR' NOT NULL,
        risk_seviyesi VARCHAR,
        aksiyon_onerisi TEXT
    );
    """)
    print("[2] Başlangıç 'su_olcumleri' tablosu (4 predictive kolon OLMADAN) oluşturuldu.")
    
    # 3. Stamp previous migration (fa5d990d2561)
    env = os.environ.copy()
    env["DATABASE_URL"] = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}"
    
    res_stamp = subprocess.run(["alembic", "stamp", "fa5d990d2561"], env=env, capture_output=True, text=True)
    print(f"[3] Alembic stamp (fa5d990d2561): {res_stamp.stdout.strip() or 'OK'}")

    # 4. Run alembic upgrade head
    print("[4] 'alembic upgrade head' çalıştırılıyor...")
    res_up = subprocess.run(["alembic", "upgrade", "head"], env=env, capture_output=True, text=True)
    print(res_up.stdout)
    if res_up.returncode != 0:
        print("HATA:", res_up.stderr)
        return False

    # 5. Verify columns in information_schema
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'su_olcumleri'
          AND column_name IN ('trend_risk_score', 'trend_direction', 'projected_value', 'projection_message')
        ORDER BY column_name;
    """)
    rows = cur.fetchall()
    print("[5] 'su_olcumleri' tablosuna eklenen kolonlar doğrulanıyor:")
    for r in rows:
        print(f"  - Kolon: {r[0]:<20} Tip: {r[1]:<20} Nullable: {r[2]}")

    expected = {
        'trend_risk_score': 'integer',
        'trend_direction': 'character varying',
        'projected_value': 'double precision',
        'projection_message': 'character varying'
    }
    found = {r[0]: r[1] for r in rows}
    
    assert found == expected, f"Beklenen: {expected}, Bulunan: {found}"
    print("\n>> TÜM 4 KOLON DOĞRU TİPLERLE BAŞARIYLA OLUŞTURULDU!")

    # 6. Test downgrade
    print("\n[6] 'alembic downgrade -1' test ediliyor...")
    res_down = subprocess.run(["alembic", "downgrade", "-1"], env=env, capture_output=True, text=True)
    print(res_down.stdout)
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'su_olcumleri'
          AND column_name IN ('trend_risk_score', 'trend_direction', 'projected_value', 'projection_message');
    """)
    after_downgrade = cur.fetchall()
    print(f"  Downgrade sonrası kalan predictive kolon sayısı: {len(after_downgrade)} (Beklenen: 0)")
    assert len(after_downgrade) == 0

    # 7. Upgrade back to head
    print("\n[7] 'alembic upgrade head' yeniden test ediliyor...")
    res_up2 = subprocess.run(["alembic", "upgrade", "head"], env=env, capture_output=True, text=True)
    print(res_up2.stdout)

    cur.close()
    db_conn.close()
    print(">> MİGRATİON DOĞRULAMASI %100 BAŞARILI!")
    return True

if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)
