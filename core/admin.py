from fastapi import FastAPI, Depends, HTTPException
from config import settings

app = FastAPI(title="Lunch Ledger Admin Panel")

# Пример эндпоинта для проверки доступа
@app.get("/admin/check")
def check_admin(secret: str):
    if secret != settings.ADMIN_PANEL_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"status": "ok"}
