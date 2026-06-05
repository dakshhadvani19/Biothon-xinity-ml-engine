---
title: AgriShield ML Engine
emoji: 🌿
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
---

# AgriShield ML Engine
This is the PyTorch Backend for AgriShield, powered by FastAPI.

## Local Setup Instructions

If you want to run this Machine Learning engine locally on your own computer, follow these steps:

### 1. Prerequisites
- Ensure you have **Python 3.9 or higher** installed.
- Ensure you have Git installed (optional, for cloning).

### 2. Create a Virtual Environment
It's highly recommended to use a virtual environment to avoid dependency conflicts. Open your terminal in the `agrishield-ml-engine` folder and run:
```bash
python -m venv venv
```

### 3. Activate the Virtual Environment
**On Windows:**
```powershell
venv\Scripts\activate
```
**On Mac/Linux:**
```bash
source venv/bin/activate
```

### 4. Install Dependencies
With the virtual environment active, install the required Python packages (like PyTorch, FastAPI, and Uvicorn):
```bash
pip install -r requirements.txt
```

### 5. Run the Server
Start the Uvicorn local development server:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Verify it works
Open your browser and navigate to:
- **Health Check:** `http://localhost:8000/health`
- **Interactive API Docs:** `http://localhost:8000/docs`
