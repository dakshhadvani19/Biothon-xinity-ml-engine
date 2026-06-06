import json
import os
import traceback
import io
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# Load .env file manually from the root directory if it exists (helps local Windows development)
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(env_path):
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        key = parts[0].strip().strip('"').strip("'")
                        val = parts[1].strip().strip('"').strip("'")
                        os.environ[key] = val
    except Exception as e:
        print(f"[WARNING] Error loading .env file manually: {e}")
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Response
import httpx
from pydantic import BaseModel
from openai import AsyncOpenAI
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional

# ReportLab PDF imports
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class WeatherPayload(BaseModel):
    data: dict
    farms: list = []

class SuitabilityPayload(BaseModel):
    crop_name: str
    lat: float
    lon: float
    soil_type: str
    current_temp: Optional[float] = 0.0
    current_condition: Optional[str] = "Unknown"

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatPayload(BaseModel):
    messages: List[ChatMessage]
    context: Optional[dict] = None
    farms: Optional[list] = []
    weather: Optional[dict] = None
    user_name: Optional[str] = None

# Preference Schema for automated daily PDF reports
class ReportSettingsPayload(BaseModel):
    email: str
    phone: str
    delivery_mode: str = "SMS" # "SMS", "WhatsApp", "Email", or "Telegram"
    enabled: bool = True
    lat: float = 22.3039
    lon: float = 70.8022
    crops: list = [] # Array of dicts like [{"crop": "Cotton", "soil": "Black"}]
    twilio_sid: Optional[str] = None
    twilio_token: Optional[str] = None
    twilio_from: Optional[str] = None
    custom_smtp_host: Optional[str] = None
    custom_smtp_port: Optional[int] = None
    custom_smtp_user: Optional[str] = None
    custom_smtp_pass: Optional[str] = None
    custom_smtp_from: Optional[str] = None
    custom_telegram_bot_token: Optional[str] = None
    custom_telegram_chat_id: Optional[str] = None

class NutritionPayload(BaseModel):
    name: Optional[str] = ""
    image: Optional[str] = None
    filename: Optional[str] = None

# Memory cache for generated report PDF binary data
PDF_REPORTS_CACHE = {}

# File path config for registered reports persistence
REGISTRATIONS_FILE = os.path.join(os.path.dirname(__file__), "registrations.json")

def load_registrations():
    if os.path.exists(REGISTRATIONS_FILE):
        try:
            with open(REGISTRATIONS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    # Fallback to temp dir for Vercel
    tmp_path = "/tmp/registrations.json"
    if os.path.exists(tmp_path):
        try:
            with open(tmp_path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_registrations(data):
    try:
        with open(REGISTRATIONS_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception:
        # Fallback to temp dir for Vercel
        try:
            with open("/tmp/registrations.json", "w") as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass

# Branded PDF generator
def generate_pdf_report(email, phone, coords, crops, weather):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    styles = getSampleStyleSheet()
    
    # Custom color palette
    primary_color = colors.HexColor("#1b5e20")   # Dark forest green
    secondary_color = colors.HexColor("#2e7d32") # Mid green
    text_color = colors.HexColor("#333333")      # Dark gray
    bg_light = colors.HexColor("#f1f8e9")        # Light green banner
    
    # Text styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=primary_color,
        alignment=1, # Center
        spaceAfter=15
    )
    
    section_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=secondary_color,
        spaceBefore=14,
        spaceAfter=8
    )
    
    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=text_color,
        spaceAfter=6
    )
    
    bullet_style = ParagraphStyle(
        'BulletCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=text_color,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4
    )
    
    story = []
    
    # Document Header Title
    story.append(Paragraph("AGRISHIELD AGRICULTURAL INTELLIGENCE SYSTEM", ParagraphStyle('Sub', fontName='Helvetica-Bold', fontSize=8, textColor=secondary_color, alignment=1, spaceAfter=2)))
    story.append(Paragraph("Daily Crop Health & Action Advisory", title_style))
    story.append(Spacer(1, 5))
    
    # Info Banner
    current_time = datetime.now().strftime("%Y-%m-%d %I:%M %p")
    info_data = [
        [Paragraph("<b>Report Issued:</b>", body_style), Paragraph(current_time, body_style),
         Paragraph("<b>GPS Coordinates:</b>", body_style), Paragraph(f"{coords.get('lat')}, {coords.get('lon')}", body_style)],
        [Paragraph("<b>Farmer Email:</b>", body_style), Paragraph(email, body_style),
         Paragraph("<b>Mobile Number:</b>", body_style), Paragraph(phone, body_style)]
    ]
    info_table = Table(info_data, colWidths=[100, 160, 110, 160])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), bg_light),
        ('PADDING', (0,0), (-1,-1), 8),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor("#c5e1a5")),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 12))
    
    # 1. Weather Context
    story.append(Paragraph("1. Regional Weather Parameters", section_style))
    temp = weather.get("currentTemp", 28)
    cond = weather.get("condition", "Partly Cloudy")
    rain_chance = "15%"
    wind = "10 kph"
    
    if weather.get("hourlyForecast") and len(weather["hourlyForecast"]) > 0:
        rain_chance = f"{weather['hourlyForecast'][0].get('rainChance', '15')}%"
        wind = f"{weather['hourlyForecast'][0].get('windSpeed', '10')} kph"
        
    weather_text = f"Today's temperature is <b>{temp}°C</b> with weather status <b>{cond}</b>. Local wind speeds are around <b>{wind}</b>, and there is a <b>{rain_chance}</b> chance of precipitation today. Based on these readings, soil evapotranspiration holds normal index values."
    story.append(Paragraph(weather_text, body_style))
    story.append(Spacer(1, 8))
    
    # 2. Crop Health
    story.append(Paragraph("2. Custom Crop Health Analysis", section_style))
    if not crops:
        story.append(Paragraph("No crop configurations loaded for this farmer profile yet. Configure crops under profile view to enable targeted AI checks.", body_style))
    else:
        for idx, item in enumerate(crops):
            crop_name = item.get("crop", "Unknown") if isinstance(item, dict) else item
            soil_name = item.get("soil", "Black Soil") if isinstance(item, dict) else "Black Soil"
            
            is_rainy = "rain" in cond.lower() or "drizzle" in cond.lower() or "shower" in cond.lower()
            
            status = "Optimal"
            recs = []
            
            if is_rainy:
                status = "Rain Warning (Elevated Humidity)"
                recs = [
                    "Withhold nitrogen top-dressing to prevent atmospheric runoff.",
                    "Check drain passages to secure root zones from fungal spores."
                ]
            else:
                if temp > 34:
                    status = "Heat Stress Precaution"
                    recs = [
                        "Supply irrigation in evening cycles to avoid transpiration burn.",
                        "Inspect crops for red spider mite colonies typical of hot weather."
                    ]
                else:
                    status = "Healthy (Baseline Growth)"
                    recs = [
                        "Maintain steady watering quantities.",
                        "Prune yellowing foliage to direct nutrients to seedheads."
                    ]
                    
            crop_header = f"<b>Plot #{idx+1}: {crop_name}</b> (Soil: {soil_name}) — Status: <font color='{'red' if 'Stress' in status or 'Warning' in status else 'green'}'><b>{status}</b></font>"
            story.append(Paragraph(crop_header, body_style))
            
            for r in recs:
                story.append(Paragraph(f"• {r}", bullet_style))
            story.append(Spacer(1, 6))
            
    story.append(Spacer(1, 8))
    
    # 3. Action checklist
    story.append(Paragraph("3. Daily Farmer Checklist", section_style))
    actions = [
        "Audit drip lateral nozzles to confirm equal water output.",
        "Take a leaf sample from plot #1 to inspect for rust spots.",
        "Update regional fertilizer inventory in Appwrite database."
    ]
    for act in actions:
        story.append(Paragraph(f"[  ] {act}", bullet_style))
        
    story.append(Spacer(1, 20))
    story.append(Paragraph("<i>Disclaimer: This PDF report compiles AI recommendations based on meteorological telemetry. Consult agricultural authorities for specific chemical dosages.</i>", ParagraphStyle('Foot', fontName='Helvetica-Oblique', fontSize=7.5, textColor=colors.HexColor("#666666"), alignment=1)))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

async def identify_plant_from_image(client, base64_image: str) -> Optional[str]:
    # Extract clean base64 data if it is a data URI
    if "," in base64_image:
        base64_image = base64_image.split(",", 1)[1]
    
    # Try different vision models in order of likelihood
    vision_models = [
        "llama-3.2-11b-vision-preview",
        "llama-3.2-90b-vision-preview",
        "meta-llama/llama-4-scout-17b-16e-instruct"
    ]
    
    for model in vision_models:
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text", 
                                "text": "Identify the plant, vegetable, or fruit in this image. Return ONLY the common name of the plant, vegetable, or fruit in English (e.g. 'Moringa', 'Spinach', 'Avocado', 'Garlic', 'Pomegranate', 'Apple', 'Banana'). Do not include any other words, punctuation, or formatting."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=20,
                temperature=0.1
            )
            name = response.choices[0].message.content.strip()
            if name:
                name = name.replace("`", "").replace('"', "").replace("'", "").replace(".", "").strip()
                return name
        except Exception as e:
            print(f"[WARNING] Failed to identify image using model {model}: {e}")
            continue
            
    return None

class MessageDispatcher:
    @staticmethod
    def send_report(
        email: str,
        phone: str,
        delivery_mode: str,
        pdf_bytes: bytes,
        config: dict
    ) -> tuple[bool, str]:
        mode = delivery_mode.lower()
        
        # Setup downloadable url
        if os.environ.get("VERCEL_URL"):
            pdf_url = f"https://{os.environ.get('VERCEL_URL')}/api/v1/pdf/{email}"
        else:
            pdf_url = f"http://127.0.0.1:8000/api/v1/pdf/{email}"
            
        body_text = f"AgriShield Daily Report for {email}: Here is your automated crop health PDF: {pdf_url}"
        
        if mode == 'sms':
            return MessageDispatcher._send_twilio_sms(phone, body_text, pdf_url, config)
        elif mode == 'whatsapp':
            return MessageDispatcher._send_twilio_whatsapp(phone, body_text, pdf_url, config)
        elif mode == 'email':
            return MessageDispatcher._send_email(email, pdf_bytes, pdf_url, config)
        elif mode == 'telegram':
            return MessageDispatcher._send_telegram(email, body_text, pdf_bytes, pdf_url, config)
        else:
            return False, f"Unsupported delivery mode: {delivery_mode}"

    @staticmethod
    def _send_twilio_sms(phone: str, body_text: str, pdf_url: str, config: dict) -> tuple[bool, str]:
        account_sid = config.get("twilio_sid") or os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = config.get("twilio_token") or os.environ.get("TWILIO_AUTH_TOKEN")
        from_number = config.get("twilio_from") or os.environ.get("TWILIO_FROM_NUMBER")
        
        is_valid = MessageDispatcher._validate_twilio(account_sid, auth_token, from_number)
        if is_valid:
            try:
                import requests
                url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
                payload = {
                    "From": from_number,
                    "To": phone,
                    "Body": body_text
                }
                resp = requests.post(url, data=payload, auth=(account_sid, auth_token))
                if resp.status_code in [200, 201]:
                    return True, "Report sent via Twilio SMS successfully."
                else:
                    return False, f"Twilio API error: {resp.text}"
            except Exception as e:
                return False, f"Twilio SMS sender exception: {str(e)}"
        else:
            mock_output = (
                f"\n--- [MOCK SMS SENT] ---\n"
                f"Recipient: {phone}\n"
                f"Message: {body_text}\n"
                f"PDF URL: {pdf_url}\n"
                f"Status: Mock Success (Configure Twilio settings to activate live dispatch)\n"
                f"-------------------------\n"
            )
            print(mock_output)
            return True, f"[MOCK MODE] Twilio credentials not set. Report SMS logged. PDF: {pdf_url}"

    @staticmethod
    def _send_twilio_whatsapp(phone: str, body_text: str, pdf_url: str, config: dict) -> tuple[bool, str]:
        account_sid = config.get("twilio_sid") or os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = config.get("twilio_token") or os.environ.get("TWILIO_AUTH_TOKEN")
        from_number = config.get("twilio_from") or os.environ.get("TWILIO_FROM_NUMBER")
        
        is_valid = MessageDispatcher._validate_twilio(account_sid, auth_token, from_number)
        if is_valid:
            try:
                import requests
                url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
                to_num = phone if phone.startswith('whatsapp:') else f"whatsapp:{phone}"
                from_num = from_number if from_number.startswith('whatsapp:') else f"whatsapp:{from_number}"
                payload = {
                    "From": from_num,
                    "To": to_num,
                    "Body": body_text,
                    "MediaUrl": pdf_url
                }
                resp = requests.post(url, data=payload, auth=(account_sid, auth_token))
                if resp.status_code in [200, 201]:
                    return True, "Report sent via Twilio WhatsApp successfully."
                else:
                    return False, f"Twilio API error: {resp.text}"
            except Exception as e:
                return False, f"Twilio WhatsApp sender exception: {str(e)}"
        else:
            mock_output = (
                f"\n--- [MOCK WHATSAPP SENT] ---\n"
                f"Recipient: whatsapp:{phone}\n"
                f"Message: {body_text}\n"
                f"PDF URL: {pdf_url}\n"
                f"Status: Mock Success (Configure Twilio settings to activate live dispatch)\n"
                f"---------------------------------\n"
            )
            print(mock_output)
            return True, f"[MOCK MODE] Twilio credentials not set. Report WhatsApp logged. PDF: {pdf_url}"

    @staticmethod
    def _send_email(email: str, pdf_bytes: bytes, pdf_url: str, config: dict) -> tuple[bool, str]:
        smtp_host = config.get("custom_smtp_host") or os.environ.get("SMTP_HOST")
        smtp_port = config.get("custom_smtp_port") or os.environ.get("SMTP_PORT") or 587
        smtp_user = config.get("custom_smtp_user") or os.environ.get("SMTP_USER")
        smtp_pass = config.get("custom_smtp_pass") or os.environ.get("SMTP_PASSWORD")
        smtp_from = config.get("custom_smtp_from") or os.environ.get("SMTP_FROM") or "reports@agrishield.com"
        
        is_valid = smtp_host and smtp_user and smtp_pass and "placeholder" not in smtp_host.lower()
        if is_valid:
            try:
                port = int(smtp_port)
                server = smtplib.SMTP(smtp_host, port)
                server.starttls()
                server.login(smtp_user, smtp_pass)
                
                msg = MIMEMultipart()
                msg['From'] = smtp_from
                msg['To'] = email
                msg['Subject'] = "AgriShield Daily Crop Health & Action Advisory Report"
                
                body = (
                    f"Hello,\n\n"
                    f"Please find attached your AgriShield Daily Crop Health & Action Advisory Report.\n\n"
                    f"You can also view it online here: {pdf_url}\n\n"
                    f"Best regards,\n"
                    f"AgriShield Agricultural Intelligence Team"
                )
                msg.attach(MIMEText(body, 'plain'))
                
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(pdf_bytes)
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename="AgriShield_Report_{email}.pdf"')
                msg.attach(part)
                
                server.sendmail(smtp_from, email, msg.as_string())
                server.quit()
                return True, f"Report sent via SMTP Email to {email} successfully."
            except Exception as e:
                return False, f"Email SMTP send failed: {str(e)}"
        else:
            mock_output = (
                f"\n--- [MOCK EMAIL SENT] ---\n"
                f"Recipient Email: {email}\n"
                f"Sender: {smtp_from}\n"
                f"Subject: AgriShield Daily Crop Health & Action Advisory Report\n"
                f"PDF URL: {pdf_url}\n"
                f"Status: Mock Success (Configure SMTP settings to activate live dispatch)\n"
                f"---------------------------------\n"
            )
            print(mock_output)
            return True, f"[MOCK MODE] SMTP credentials not set. Report email logged. PDF: {pdf_url}"

    @staticmethod
    def _send_telegram(email: str, body_text: str, pdf_bytes: bytes, pdf_url: str, config: dict) -> tuple[bool, str]:
        bot_token = config.get("custom_telegram_bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = config.get("custom_telegram_chat_id") or os.environ.get("TELEGRAM_CHAT_ID")
        
        is_valid = bot_token and chat_id and "placeholder" not in bot_token.lower() and "chat_id" not in chat_id.lower()
        if is_valid:
            try:
                import requests
                # 1. Send text message
                text_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                text_payload = {"chat_id": chat_id, "text": body_text}
                requests.post(text_url, json=text_payload)
                
                # 2. Send PDF document
                doc_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
                files = {"document": (f"AgriShield_Report_{email}.pdf", pdf_bytes, "application/pdf")}
                doc_payload = {"chat_id": chat_id, "caption": "AgriShield Daily advisory Report PDF"}
                resp = requests.post(doc_url, data=doc_payload, files=files)
                if resp.status_code in [200, 201]:
                    return True, "Report sent via Telegram successfully."
                else:
                    return False, f"Telegram API error: {resp.text}"
            except Exception as e:
                return False, f"Telegram sender exception: {str(e)}"
        else:
            mock_output = (
                f"\n--- [MOCK TELEGRAM SENT] ---\n"
                f"Recipient Chat ID: {chat_id}\n"
                f"Message: {body_text}\n"
                f"PDF URL: {pdf_url}\n"
                f"Status: Mock Success (Configure Telegram settings to activate live dispatch)\n"
                f"---------------------------------\n"
            )
            print(mock_output)
            return True, f"[MOCK MODE] Telegram credentials not set. Report logged. PDF: {pdf_url}"

    @staticmethod
    def _validate_twilio(sid: str, token: str, from_num: str) -> bool:
        return bool(
            sid and sid.startswith("AC") and len(sid) == 34 and
            "xxxx" not in sid.lower() and "placeholder" not in sid.lower() and
            not sid.startswith("your_") and not sid.startswith("your-") and
            token and len(token) == 32 and
            "xxxx" not in token.lower() and "placeholder" not in token.lower() and
            "token" not in token.lower() and
            not token.startswith("your_") and not token.startswith("your-") and
            from_num and "xxxx" not in from_num.lower() and
            "placeholder" not in from_num.lower() and
            not from_num.startswith("your_") and not from_num.startswith("your-") and
            len(from_num) >= 9
        )

@app.post("/api/v1/register-report-settings")
async def register_report_settings(payload: ReportSettingsPayload):
    try:
        regs = load_registrations()
        regs[payload.email] = {
            "phone": payload.phone,
            "delivery_mode": payload.delivery_mode,
            "enabled": payload.enabled,
            "lat": payload.lat,
            "lon": payload.lon,
            "crops": payload.crops,
            "twilio_sid": payload.twilio_sid,
            "twilio_token": payload.twilio_token,
            "twilio_from": payload.twilio_from,
            "custom_smtp_host": payload.custom_smtp_host,
            "custom_smtp_port": payload.custom_smtp_port,
            "custom_smtp_user": payload.custom_smtp_user,
            "custom_smtp_pass": payload.custom_smtp_pass,
            "custom_smtp_from": payload.custom_smtp_from,
            "custom_telegram_bot_token": payload.custom_telegram_bot_token,
            "custom_telegram_chat_id": payload.custom_telegram_chat_id
        }
        save_registrations(regs)
        return {"status": "success", "message": "Notification preferences updated."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/v1/pdf/{email}")
async def get_pdf_report(email: str):
    pdf_bytes = PDF_REPORTS_CACHE.get(email)
    if not pdf_bytes:
        # Generate on the fly
        regs = load_registrations()
        user_reg = regs.get(email)
        default_weather = {"currentTemp": 28, "condition": "Partly Cloudy", "hourlyForecast": []}
        
        if user_reg:
            pdf_bytes = generate_pdf_report(
                email,
                user_reg.get("phone", "+919876543210"),
                {"lat": user_reg.get("lat", 22.3039), "lon": user_reg.get("lon", 70.8022)},
                user_reg.get("crops", []),
                default_weather
            )
        else:
            pdf_bytes = generate_pdf_report(email, "+919876543210", {"lat": 22.3039, "lon": 70.8022}, [], default_weather)
            
    return Response(content=pdf_bytes, media_type="application/pdf", headers={
        "Content-Disposition": f"inline; filename=AgriShield_Report_{email}.pdf"
    })

@app.post("/api/v1/send-test-report")
async def send_test_report(payload: ReportSettingsPayload):
    try:
        # Generate PDF report bytes
        weather = {"currentTemp": 31, "condition": "Sunny", "hourlyForecast": [{"temp": 31, "rainChance": 5, "windSpeed": 14}]}
        pdf_bytes = generate_pdf_report(
            payload.email,
            payload.phone,
            {"lat": payload.lat, "lon": payload.lon},
            payload.crops,
            weather
        )
        
        # Save bytes in cache
        PDF_REPORTS_CACHE[payload.email] = pdf_bytes
        
        # Trigger sending
        config = payload.model_dump() if hasattr(payload, "model_dump") else (payload.dict() if hasattr(payload, "dict") else payload)
        success, msg = MessageDispatcher.send_report(
            payload.email,
            payload.phone,
            payload.delivery_mode,
            pdf_bytes,
            config
        )
        
        return {
            "status": "success" if success else "warning",
            "message": msg,
            "pdf_url": f"/api/v1/pdf/{payload.email}"
        }
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": f"Test report failed: {str(e)}"}

@app.get("/api/v1/send-daily-reports")
async def send_daily_reports():
    try:
        regs = load_registrations()
        results = []
        default_weather = {"currentTemp": 27, "condition": "Humid / Overcast", "hourlyForecast": [{"temp": 27, "rainChance": 60, "windSpeed": 16}]}
        
        for email, config in regs.items():
            if not config.get("enabled", True):
                continue
                
            phone = config.get("phone")
            coords = {"lat": config.get("lat", 22.3039), "lon": config.get("lon", 70.8022)}
            crops = config.get("crops", [])
            mode = config.get("delivery_mode", "SMS")
            
            try:
                pdf_bytes = generate_pdf_report(email, phone, coords, crops, default_weather)
                PDF_REPORTS_CACHE[email] = pdf_bytes
                
                success, msg = MessageDispatcher.send_report(
                    email,
                    phone,
                    mode,
                    pdf_bytes,
                    config
                )
                results.append({"email": email, "success": success, "message": msg})
            except Exception as ex:
                results.append({"email": email, "success": False, "message": str(ex)})
                
        return {"status": "success", "processed": results}
    except Exception as e:
        return {"status": "error", "message": str(e)}

class DiagnosisItem(BaseModel):
    """
    A single pre-diagnosed image entry sent from the React frontend.
    The disease label comes from the diagnostic_logs DB — no re-inference needed.
    """
    file_id: str
    image_url: Optional[str] = None
    disease: str          # e.g. "Tomato___Early_blight"
    confidence: float     # e.g. 0.94

class NutritionRequest(BaseModel):
    """
    Flow A — By Image (text-only path):
    React sends the already-diagnosed items from diagnostic_logs.
    We skip image download / re-inference entirely and go straight to Groq.
    This eliminates CORS, JWT, HuggingFace timeout, and Vercel size issues.
    """
    diagnoses: List[DiagnosisItem]

class FarmItem(BaseModel):
    farm_id: str
    crop: str
    soil: str

class FarmNutritionRequest(BaseModel):
    farms: List[FarmItem]

HF_PREDICT_URL = "https://dakshhadvani19-agrishield.hf.space/api/v1/predict"

@app.post("/api/v1/nutrition-guide")
async def get_nutrition_guide(payload: NutritionRequest):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return {"error": "GROQ_API_KEY not set", "results": []}

    if not payload.diagnoses:
        return {"error": "No diagnoses provided", "results": []}

    # Build Groq prompt from already-diagnosed disease labels
    diagnosis_text = "\n".join(
        f"Image {i + 1} (index {i}): {d.disease.replace('___', ' — ').replace('_', ' ')} "
        f"(confidence: {round(d.confidence * 100, 1)}%)"
        for i, d in enumerate(payload.diagnoses)
    )

    groq_client = AsyncOpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

    system_prompt = """You are AgriNutrition AI, a world-class agronomic nutrition specialist.
You receive crop disease diagnoses from a computer vision model.
For EACH image, generate an INDIVIDUAL, HIGHLY SPECIFIC nutrition and treatment guide.
Be precise, scientific, and practical. Tailor every recommendation to the exact disease.

Return ONLY a valid JSON object:
{
  "results": [
    {
      "image_index": 0,
      "crop_label": "Human-friendly label e.g. 'Tomato — Early Blight'",
      "severity": "Low|Moderate|High",
      "summary": "2-3 sentences: why this disease causes nutritional imbalance and what it depletes",
      "npk": {
        "nitrogen":   { "value": 80, "unit": "kg/ha", "tip": "One specific application sentence" },
        "phosphorus": { "value": 40, "unit": "kg/ha", "tip": "One specific application sentence" },
        "potassium":  { "value": 60, "unit": "kg/ha", "tip": "One specific application sentence" }
      },
      "organic_amendments": [
        "Specific amendment 1 with dose and timing",
        "Specific amendment 2 with dose and timing",
        "Specific amendment 3 with dose and timing"
      ],
      "weekly_schedule": [
        "Week 1: specific action",
        "Week 2: specific action",
        "Week 3: specific action",
        "Week 4: specific action"
      ]
    }
  ]
}"""

    user_prompt = (
        f"The AgriShield vision model diagnosed the following:\n\n{diagnosis_text}\n\n"
        "Generate an individual nutrition guide for EACH image.\n"
        "The 'image_index' must match the index shown (0-based).\n"
        "Be disease-specific — do NOT give generic advice."
    )

    try:
        groq_response = await groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,   # Very low = maximum factual accuracy
        )
        raw = groq_response.choices[0].message.content or "{}"
        parsed = json.loads(raw.replace("```json", "").replace("```", "").strip())

        # Enrich Groq results with image URLs and confidence from input
        groq_results = parsed.get("results", [])
        for r in groq_results:
            idx = r.get("image_index", -1)
            if 0 <= idx < len(payload.diagnoses):
                d = payload.diagnoses[idx]
                r["image_url"]   = d.image_url
                r["raw_disease"] = d.disease
                r["confidence"]  = d.confidence * 100
                r["mocked"]      = False

        return {"results": groq_results}

    except Exception as e:
        error_msg = str(e)
        print(f"[NutritionGuide] 🛑 Groq failed: {error_msg}")
        traceback.print_exc()
        # Fallback: return stubs with the disease labels at least
        return {
            "error": f"Groq synthesis failed: {error_msg}",
            "results": [
                {
                    "image_index":  i,
                    "image_url":    d.image_url,
                    "crop_label":   d.disease.replace("___", " — ").replace("_", " "),
                    "raw_disease":  d.disease,
                    "confidence":   d.confidence * 100,
                    "severity":     "Unknown",
                    "summary":      "AI synthesis temporarily unavailable.",
                    "npk":          {},
                    "organic_amendments": [],
                    "weekly_schedule":    [],
                }
                for i, d in enumerate(payload.diagnoses)
            ],
        }

@app.post("/api/v1/farm-nutrition-guide")
async def get_farm_nutrition_guide(payload: FarmNutritionRequest):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return {"error": "GROQ_API_KEY not set", "results": []}

    if not payload.farms:
        return {"error": "No farms provided", "results": []}

    farm_text = "\n".join(
        f"Farm {i + 1} (index {i}): {f.crop} grown in {f.soil} soil"
        for i, f in enumerate(payload.farms)
    )

    groq_client = AsyncOpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

    system_prompt = """You are AgriNutrition AI, a world-class agronomic nutrition specialist.
You receive a list of farms (crop and soil type) from a farmer.
For EACH farm, generate an INDIVIDUAL, HIGHLY SPECIFIC soil nutrition and fertilizer guide.
Be precise, scientific, and practical. Tailor every recommendation to the exact crop and soil type.

Return ONLY a valid JSON object:
{
  "results": [
    {
      "image_index": 0,
      "crop_label": "Human-friendly label e.g. 'Cotton in Black Soil'",
      "severity": "Low",
      "summary": "2-3 sentences: what this crop requires in this specific soil type",
      "npk": {
        "nitrogen":   { "value": 80, "unit": "kg/ha", "tip": "One specific application sentence" },
        "phosphorus": { "value": 40, "unit": "kg/ha", "tip": "One specific application sentence" },
        "potassium":  { "value": 60, "unit": "kg/ha", "tip": "One specific application sentence" }
      },
      "organic_amendments": [
        "Specific amendment 1 with dose and timing",
        "Specific amendment 2 with dose and timing",
        "Specific amendment 3 with dose and timing"
      ],
      "weekly_schedule": []
    }
  ]
}"""

    user_prompt = (
        f"The user has the following farms:\n\n{farm_text}\n\n"
        "Generate an individual nutrition guide for EACH farm.\n"
        "The 'image_index' must match the index shown (0-based).\n"
        "Be crop and soil-specific — do NOT give generic advice."
    )

    try:
        groq_response = await groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        raw = groq_response.choices[0].message.content or "{}"
        parsed = json.loads(raw.replace("```json", "").replace("```", "").strip())

        groq_results = parsed.get("results", [])
        for r in groq_results:
            idx = r.get("image_index", -1)
            if 0 <= idx < len(payload.farms):
                f = payload.farms[idx]
                r["image_url"]   = None
                r["raw_disease"] = f"{f.crop} in {f.soil} Soil"
                r["mocked"]      = False

        return {"results": groq_results}

    except Exception as e:
        error_msg = str(e)
        print(f"[FarmNutritionGuide] 🛑 Groq failed: {error_msg}")
        traceback.print_exc()
        return {
            "error": f"Groq synthesis failed: {error_msg}",
            "results": [
                {
                    "image_index":  i,
                    "image_url":    None,
                    "crop_label":   f"{f.crop} in {f.soil} Soil",
                    "raw_disease":  f.crop,
                    "severity":     "Unknown",
                    "summary":      "AI synthesis temporarily unavailable.",
                    "npk":          {},
                    "organic_amendments": [],
                    "weekly_schedule":    [],
                }
                for i, f in enumerate(payload.farms)
            ],
        }

@app.post("/api/v1/agronomic-insights")
async def get_agronomic_insights(payload: WeatherPayload):
    try:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set on Vercel.")
            
        client = AsyncOpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
        
        response = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
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
        raw_content = response.choices[0].message.content
        if not raw_content:
            raise ValueError("Groq returned an empty response body.")
            
        sanitized_content = raw_content.replace("```json", "").replace("```", "").strip()
        return json.loads(sanitized_content)
    except Exception as e:
        print(f"[ERROR] CRITICAL LLM EXCEPTION: {e}")
        traceback.print_exc()
        return {"insights": ["AI advisory system is temporarily syncing. Adhere to standard crop protocols."]}

@app.post("/api/v1/check-suitability")
async def check_crop_suitability(payload: SuitabilityPayload):
    try:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set on Vercel.")
            
        client = AsyncOpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
        
        system_content = (
            "You are the AgriShield Crop Suitability Engine. Analyze if a user-supplied crop "
            "is suitable to grow in their current location, matching coordinates (latitude/longitude), "
            "soil type, and current weather. Determine if this crop is viable, considering typical yearly seasons "
            "for this region. Return ONLY a valid JSON object with exactly the following keys: "
            "'suitable' (string: 'Highly Suitable', 'Moderately Suitable', or 'Unsuitable'), "
            "'suitability_score' (integer: 0-100), "
            "'weather_analysis' (string summarizing weather/climate constraints or benefits), "
            "'soil_analysis' (string detailing soil-crop compatibility), "
            "'yearly_climate_analysis' (string summarizing typical yearly weather conditions and whether they fit), "
            "'recommendations' (array of strings detailing agronomic suggestions), and "
            "'precautions' (array of strings listing risks and warnings)."
        )
        
        user_content = (
            f"Crop: {payload.crop_name}\n"
            f"Location coordinates: latitude {payload.lat}, longitude {payload.lon}\n"
            f"Soil Type: {payload.soil_type}\n"
            f"Current Weather Telemetry: {payload.current_temp}°C, {payload.current_condition}"
        )
        
        response = await client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"}
        )
        
        raw_content = response.choices[0].message.content
        if not raw_content:
            raise ValueError("Groq returned an empty response body.")
            
        sanitized_content = raw_content.replace("```json", "").replace("```", "").strip()
        return json.loads(sanitized_content)
    except Exception as e:
        print(f"[ERROR] CRITICAL LLM EXCEPTION: {e}")
        traceback.print_exc()
        return {
            "suitable": "Moderately Suitable",
            "suitability_score": 60,
            "weather_analysis": "Local weather parameters are currently within normal baseline ranges for standard cultivation.",
            "soil_analysis": f"The soil profile ({payload.soil_type}) supports root growth under proper moisture regulation.",
            "yearly_climate_analysis": "Regional yearly precipitation patterns show suitability, though seasonal variations require active irrigation.",
            "recommendations": [
                "Verify soil nutrient index before initiating planting cycle.",
                "Utilize drip irrigation to optimize water delivery systems."
            ],
            "precautions": [
                "Monitor local weather forecasts for unseasonal rainfall alerts.",
                "Ensure proper drainage channels are maintained."
            ]
        }

@app.post("/api/v1/chat")
async def chat_suggestions(payload: ChatPayload):
    try:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set on Vercel.")
            
        client = AsyncOpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
        
        # --- Build rich context from farmer's data ---
        farms_context = ""
        if payload.farms:
            farm_lines = [
                f"  - Farm {i+1}: {f.get('crop', 'Unknown')} crop in {f.get('soil', 'Unknown')} soil"
                for i, f in enumerate(payload.farms)
            ]
            farms_context = "FARMER'S REGISTERED FARMS:\n" + "\n".join(farm_lines)
        else:
            farms_context = "FARMER'S REGISTERED FARMS: None registered yet (give general farming advice)."

        weather_context = ""
        if payload.weather:
            w = payload.weather
            temp = w.get("currentTemp", "N/A")
            condition = w.get("condition", "N/A")
            humidity = w.get("humidity", "N/A")
            wind = w.get("windSpeed", "N/A")
            weather_context = (
                f"CURRENT WEATHER TELEMETRY:\n"
                f"  - Temperature: {temp}°C\n"
                f"  - Condition: {condition}\n"
                f"  - Humidity: {humidity}%\n"
                f"  - Wind Speed: {wind} kph"
            )
        else:
            weather_context = "CURRENT WEATHER TELEMETRY: Not available. Assume typical regional conditions."

        farmer_name = payload.user_name or "Farmer"

        # --- Precision system prompt ---
        system_content = f"""You are AgriShield AI — a world-class agronomic expert built exclusively for farmers.
Your job is to provide highly accurate, practical, and immediately actionable farming advice.

{farms_context}

{weather_context}

FARMER NAME: {farmer_name}

CORE RULES — FOLLOW STRICTLY:
1. FARMING TOPICS ONLY: You answer ONLY questions related to agriculture, farming, crops, soil, irrigation, fertilizers, pesticides, pest control, companion planting, harvesting, weather-crop interactions, post-harvest storage, market-ready tips, and farm economics.
2. USE REAL DATA FIRST: Always reference the farmer's specific crops, soil types, and current weather when giving advice. Be specific — name exact fertilizer doses (kg/ha), irrigation intervals, pesticide names.
3. GENERAL FARMING FALLBACK: If the farmer asks a farming question you don't have direct data for, you STILL answer confidently using established agronomic knowledge. Aim for practical, research-backed advice. State if the advice is general vs farm-specific.
4. OUT-OF-SCOPE HANDLING: If a question is completely unrelated to farming (e.g., cricket scores, politics, movies, coding), respond with ONLY this message — do NOT add anything else:
   "🌾 I'm designed to assist exclusively with farming and agriculture. This question is outside my field of expertise. Please ask me anything about your crops, soil, irrigation, or farm management — I'm here to help your farm thrive!"
5. ACCURACY OVER COMPLETENESS: If you are unsure about a highly specific regional or regulatory detail, say so clearly and provide the closest scientifically accurate answer you can. Never fabricate numbers or product names.
6. FORMAT: Use bullet points for multi-step answers. Bold key terms. Keep answers concise but complete. Start directly — no "Great question!" filler.
7. WEATHER-AWARE: Always factor the current weather telemetry into your recommendations where relevant (e.g., don't recommend irrigation if it's raining, warn about fungal risk in high humidity).
"""

        messages = [{"role": "system", "content": system_content}]
        
        # Filter out the initial welcome message (assistant role at index 0) to save tokens
        user_messages = [m for m in payload.messages if not (m.role == "assistant" and "Welcome to AgriShield" in m.content)]
        for msg in user_messages:
            messages.append({"role": msg.role, "content": msg.content})
            
        response = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.3,       # Low temperature = factual, consistent answers
            max_tokens=800,        # Enough for a thorough answer, not wasteful
        )
        
        assistant_reply = response.choices[0].message.content
        return {"content": assistant_reply}
    except Exception as e:
        print(f"[ERROR] CRITICAL CHAT LLM EXCEPTION: {e}")
        traceback.print_exc()
        return {"content": "🌾 I'm temporarily unavailable. Please try again in a moment — your farm can't wait!"}

@app.post("/api/v1/analyze-nutrition")
async def analyze_nutrition(payload: NutritionPayload):
    target_name = payload.name or ""
    detected_from_image = False
    try:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set on Vercel.")
            
        client = AsyncOpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
        
        if payload.image:
            try:
                identified = await identify_plant_from_image(client, payload.image)
                if identified:
                    target_name = identified
                    detected_from_image = True
                    print(f"[INFO] Detected plant name from image: {target_name}")
            except Exception as e:
                print(f"[ERROR] Error identifying plant from image: {e}")
                
        # Fallback if no target name was found or supplied
        if not target_name or not target_name.strip():
            if payload.filename:
                base_name = os.path.splitext(payload.filename)[0]
                target_name = base_name.replace("_", " ").replace("-", " ").strip()
                print(f"[INFO] Extracted name from filename: {target_name}")
            else:
                target_name = "Spinach"
                
        system_content = (
            "You are the AgriShield Nutritional Intelligence Engine. Analyze the nutritional composition "
            "and health benefits of the given plant or fruit. Return ONLY a valid JSON object with the following keys: "
            "'name' (string), "
            "'calories' (string, e.g., '52 kcal per 100g'), "
            "'macronutrients' (object with keys 'carbs', 'protein', 'fat', 'fiber' - where each key is an object containing 'value' e.g. '14g' and 'percentage' e.g. 12 as % Daily Value), "
            "'vitamins' (array of strings, e.g., ['Vitamin C (14%)', 'Vitamin B6 (5%)']), "
            "'minerals' (array of strings, e.g., ['Potassium (4%)', 'Iron (2%)']), "
            "'health_benefits' (array of objects with keys 'title' and 'description' explaining the health benefits), "
            "'usage_tips' (array of strings detailing usage or preparation recommendations for maximum nutrition)."
        )
        
        response = await client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": f"Analyze: {target_name}"}
            ],
            response_format={"type": "json_object"}
        )
        
        raw_content = response.choices[0].message.content
        if not raw_content:
            raise ValueError("Groq returned an empty response body.")
            
        sanitized_content = raw_content.replace("```json", "").replace("```", "").strip()
        result_json = json.loads(sanitized_content)
        
        # Override name if detected from image or empty
        if detected_from_image or not payload.name:
            result_json["name"] = target_name
            
        if detected_from_image:
            result_json["detected_from_image"] = True
            
        return result_json
    except Exception as e:
        print(f"[ERROR] NUTRITION LLM EXCEPTION: {e}")
        fallback_name = target_name or payload.name or "Spinach"
        res = {
            "name": fallback_name,
            "calories": "N/A",
            "macronutrients": {
                "carbs": {"value": "N/A", "percentage": 0},
                "protein": {"value": "N/A", "percentage": 0},
                "fat": {"value": "N/A", "percentage": 0},
                "fiber": {"value": "N/A", "percentage": 0}
            },
            "vitamins": ["Information temporarily syncing"],
            "minerals": ["Information temporarily syncing"],
            "health_benefits": [
                {"title": "Nutritional Value", "description": "Provides essential dietary nutrients and fibers supporting digestive health."}
            ],
            "usage_tips": ["Consume fresh or as part of a balanced diet."]
        }
        if detected_from_image:
            res["detected_from_image"] = True
        return res

@app.post("/api/v1/predict")
async def mock_predict(file: UploadFile = File(...)):
    return {
        "disease": "Apple___Apple_scab",
        "confidence": 0.99,
        "mocked": True
    }
