from fastapi import FastAPI

app = FastAPI(title="Lunch Ledger Admin Panel")

@app.get("/")
def root():
    return {"message": "Admin panel is running"}
