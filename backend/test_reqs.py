import httpx
import sys

base_url = "http://localhost:8000"

print("1. Login as personel1...")
r_login = httpx.post(f"{base_url}/token", data={"username": "personel1@suski.gov.tr", "password": "pers123"})
r_login.raise_for_status()
token = r_login.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("Login successful.")

print("2. Get istasyonlar...")
r_ist = httpx.get(f"{base_url}/istasyonlar/", headers=headers)
r_ist.raise_for_status()
print(f"Found {len(r_ist.json())} istasyonlar.")

print("3. Post su-olcumu with pH 9.5...")
payload = {
    "istasyon_id": 1,
    "ph": 9.5,
    "serbest_klor": 0.5,
    "bulaniklik": 0.5,
    "iletkenlik": 500.0,
    "sicaklik": 20.0
}
r_su = httpx.post(f"{base_url}/su-olcumu", json=payload, headers=headers)
if r_su.status_code in [200, 201]:
    print("Su olcumu posted successfully.")
else:
    print(f"Su olcumu failed: {r_su.text}")

print("4. Trigger admin simulator...")
r_admin_login = httpx.post(f"{base_url}/token", data={"username": "admin@suski.gov.tr", "password": "admin123"})
r_admin_login.raise_for_status()
admin_token = r_admin_login.json()["access_token"]
admin_headers = {"Authorization": f"Bearer {admin_token}"}

r_sim = httpx.post(f"{base_url}/api/sim/tetikle?istasyon_id=1&mod=anomali", headers=admin_headers)
if r_sim.status_code in [200, 201]:
    print("Simulator triggered successfully.")
else:
    print(f"Simulator failed: {r_sim.text}")
