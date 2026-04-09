import os
import time
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Custom module imports
from vision import analyze_image
from calculator import calculate
from logger import init_log_db, log_request
from cache import init_cache_db

load_dotenv()


ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE_MB = 20

# 2. SECURITY (API KEY) PROTECTION
API_SECRET_KEY = os.getenv("API_SECRET_KEY")

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid API Key")
    return x_api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_log_db()
    init_cache_db()
    yield
    
app = FastAPI(title="Nutrient Analysis Service", lifespan=lifespan)

# 1. CORS CONFIGURATION (Allows web/mobile application connections)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "message": "System is up and running 24/7!"}

# 4. PROTECTED MAIN ENDPOINT
@app.post("/analyze", dependencies=[Depends(verify_api_key)])
async def analyze(
    image: UploadFile = File(...),
    note: str = Form(default="")
):
    # Start the execution timer
    start_time = time.time()
    
    # File Type Validation
    if image.content_type not in ALLOWED_TYPES:
        error_msg = f"Unsupported file type: {image.content_type}. Use JPEG, PNG or WEBP."
        log_request("/analyze", note, "error", error_msg, time.time() - start_time)
        raise HTTPException(status_code=400, detail=error_msg)

    image_bytes = await image.read()
    
    # File Size Validation
    if len(image_bytes) > MAX_SIZE_MB * 1024 * 1024:
        error_msg = f"Image too large. Max {MAX_SIZE_MB}MB."
        log_request("/analyze", note, "error", error_msg, time.time() - start_time)
        raise HTTPException(status_code=400, detail=error_msg)
    
    try:
        # Step 1: Vision Result (Extract ingredients and grams)
        vision_result = await analyze_image(image_bytes, note, image.content_type or "image/jpeg")
        used_model = vision_result.pop("model_used", "unknown")
        
        # Step 2: AI Reranker & Asynchronous Nutritional Calculation
        calc_result = await calculate(vision_result["ingredients"], user_note=note)
        
        # Log successful execution (Including execution time and model used)
        process_time = time.time() - start_time
        log_request("/analyze", note, "success", "", process_time, used_model)
        
        return {
            "dish_name": vision_result["dish_name"],
            "totals":    calc_result["totals"],
            "breakdown": calc_result["breakdown"],
            "not_found": calc_result["not_found"],
        }

    # Log and handle error conditions
    except ValueError as e:
        error_msg = f"Could not parse Gemini response: {e}"
        log_request("/analyze", note, "error", error_msg, time.time() - start_time, "failed")
        raise HTTPException(status_code=422, detail=error_msg)
    except Exception as e:
        error_msg = str(e)
        log_request("/analyze", note, "error", error_msg, time.time() - start_time, "failed")
        raise HTTPException(status_code=500, detail=error_msg)