from fastapi import FastAPI

app = FastAPI(title="Cadence Engine")


@app.get("/ping")
def ping() -> dict[str, str]:
    return {"status": "ok"}
