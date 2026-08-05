from fastapi import FastAPI

app = FastAPI(title="Agent Reliability Infrastructure")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
