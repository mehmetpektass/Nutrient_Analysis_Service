import os
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from vision import analyze_image
from calculator import calculate

load_dotenv()

app = FastAPI(title="Nutrient Analysis Service")

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE_MB = 20

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/analyze")
async def analyze(
    image: UploadFile = File(...),
    note: str = Form(default="")
):
    
    # File type check
    if image.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {image.content_type}. Use JPEG, PNG or WEBP."
        )

    image_bytes = await image.read()
    
    # File size check
    if len(image_bytes) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"Image too large. Max {MAX_SIZE_MB}MB."
        )
    
    try:
        # 1. Vision Result — ingredients and grams
        vision_result = await analyze_image(image_bytes, note, image.content_type or "image/jpeg")
        
        # 2. Deterministic calorie calculation
        calc_result = calculate(vision_result["ingredients"])
        
        return {
            "dish_name": vision_result["dish_name"],
            "totals":    calc_result["totals"],
            "breakdown": calc_result["breakdown"],
            "not_found": calc_result["not_found"],
        }

    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Could not parse Gemini response: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
