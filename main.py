import io
import os
import json
import traceback
import torch
import torch.nn.functional as F
from fastapi import FastAPI, UploadFile, File, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel
from PIL import Image
import torchvision.transforms as transforms
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "AgriShield ML Engine is running"}

api_key = os.environ.get("GROQ_API_KEY")
client = AsyncOpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

class WeatherPayload(BaseModel):
    data: dict
    farms: list = []

# Enable CORS so your React frontend can communicate with the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins; narrow this down in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Model Initialization on Startup
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
MODEL_PATH = "models/agrishield_model.pt"

try:
    model = torch.load(MODEL_PATH, map_location=device, weights_only=False)
    model.eval()
    with open("data/class_names.json", "r") as f:
        class_names = json.load(f)
    print(f"[+] ML Engine Online: Active Model Loaded on {device}.")
except Exception as e:
    raise RuntimeError(f"Engine failed to initialize: {e}")

# 2. Pre-processing pipeline
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

@app.post("/api/v1/predict")
async def predict(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid image file.")
    
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        # 1. Generate 5 square crops (TL, TR, BL, BR, Center)
        w, h = image.size
        crop_size = min(w, h)
        five_crop = transforms.FiveCrop(crop_size)
        crops = five_crop(image)
        
        # 2. Resize each to 224x224, apply normalization, and stack to (5, 3, 224, 224)
        tensors = [transform(c) for c in crops]
        batch_tensor = torch.stack(tensors).to(device)
        
        # 3. Forward pass on this batch of 5
        with torch.no_grad():
            outputs = model(batch_tensor)
            probabilities = F.softmax(outputs, dim=1)
            confidences, predicted_idxs = torch.max(probabilities, 1)
        
        # 4. Aggregation Logic
        predictions = []
        for i in range(5):
            idx = str(predicted_idxs[i].item())
            conf = float(confidences[i].item())
            cls_name = class_names[idx]
            predictions.append({"disease": cls_name, "confidence": conf})
            
        DISEASE_THRESHOLD = 0.40
        valid_diseased_results = [
            p for p in predictions 
            if "healthy" not in p["disease"].lower() and p["confidence"] >= DISEASE_THRESHOLD
        ]
        
        if valid_diseased_results:
            best_pred = max(valid_diseased_results, key=lambda x: x["confidence"])
        else:
            best_pred = max(predictions, key=lambda x: x["confidence"])
        
        return {
            "disease": best_pred["disease"],
            "confidence": round(best_pred["confidence"] * 100, 2),
            "mocked": False
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference failed: {str(e)}")

@app.get("/health")
async def health():
    return {"status": "operational", "device": str(device)}

@app.post("/api/v1/agronomic-insights")
async def get_agronomic_insights(payload: WeatherPayload):
    try:
        response = await client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {
                    "role": "system", 
                    "content": "You are the Agronomic Intelligence Engine for AgriShield. You will receive real-time weather data AND a list of specific farms (crop + soil type) owned by the user. Generate 3 highly technical, actionable agronomic instructions. IF farm data is provided, you MUST tailor the advice specifically to those exact crops and soil combinations based on the weather parameters. IF no farm data is provided, give general high-level advice for the Saurashtra region. Return ONLY a valid JSON object with exactly one key named 'insights' containing an array of 3 strings."
                },
                {
                    "role": "user", 
                    "content": f"Weather Telemetry: {json.dumps(payload.data)}\nUser Farms: {json.dumps(payload.farms)}"
                }
            ],
            response_format={"type": "json_object"}
        )
        # --- FAANG-LEVEL LLM SANITIZATION BLOCK ---
        raw_content = response.choices[0].message.content
        if not raw_content:
            raise ValueError("Groq returned an empty or null response body.")
            
        # Strip unexpected markdown backticks that LLMs often inject
        sanitized_content = raw_content.replace("```json", "").replace("```", "").strip()
        
        return json.loads(sanitized_content)
    except Exception as e:
        print(f"🛑 CRITICAL LLM EXCEPTION: {e}")
        traceback.print_exc()  # This prints the exact file line number where it failed
        return {"insights": ["AI advisory system is temporarily syncing. Adhere to standard crop protocols."]}