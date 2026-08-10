import asyncio
import httpx
import os

BASE_URL = os.getenv("BENCH_URL", "http://localhost:8080")
ADMIN_USER = os.getenv("BENCH_USER", "admin@suski.gov.tr")
ADMIN_PASS = os.getenv("BENCH_PASS", "AdminPass123!")

async def main():
    async with httpx.AsyncClient() as client:
        print("Getting token...")
        resp = await client.post(
            f"{BASE_URL}/token",
            data={"username": ADMIN_USER, "password": ADMIN_PASS},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        token = resp.json()["access_token"]
        
        print("Fetching monthly report (default current month)...")
        resp_pdf = await client.get(
            f"{BASE_URL}/admin/reports/monthly",
            headers={"Authorization": f"Bearer {token}"}
        )
        resp_pdf.raise_for_status()
        
        with open("monthly_report.pdf", "wb") as f:
            f.write(resp_pdf.content)
            
        print(f"Saved monthly_report.pdf ({len(resp_pdf.content)} bytes)")

if __name__ == "__main__":
    asyncio.run(main())
