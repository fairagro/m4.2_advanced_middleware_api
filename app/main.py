from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from uuid import uuid4
from pathlib import Path
import json

app = FastAPI(title="FAIRagro advanced middleware API",
              description="API for handling ARCs in RO-Crate format",)

RO_CRATE_DIR = Path("ro_crates")
RO_CRATE_DIR.mkdir(exist_ok=True)

@app.post("/ro-crate")
async def receive_ro_crate(request: Request):
    try:
        crate = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Basic RO-Crate validation
    if "@context" not in crate or "@graph" not in crate:
        raise HTTPException(status_code=422, detail="Invalid RO-Crate: missing @context or @graph")

    crate_id = str(uuid4())
    path = RO_CRATE_DIR / f"{crate_id}.json"

    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(crate, f, indent=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save crate: {e}")

    return JSONResponse(status_code=201, content={"message": "RO-Crate received", "id": crate_id})
