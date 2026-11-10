from fastapi import FastAPI

app = FastAPI(title="Nobu")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
