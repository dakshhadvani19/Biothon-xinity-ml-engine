"""
AgriShield Agronomic Knowledge Base
====================================
Contains scientifically accurate crop requirement data for 78+ crops
relevant to Indian agriculture. Used as the ground-truth layer for the
3-Layer Crop Suitability Intelligence Engine.

Data sources: ICAR (Indian Council of Agricultural Research), FAO crop
production guidelines, State Agriculture University publications.
"""

from datetime import datetime
from typing import Optional

# ---------------------------------------------------------------------------
# Regional Climate Profiles (based on GPS latitude bands for India)
# ---------------------------------------------------------------------------
def get_region_info(lat: float, lon: float) -> dict:
    if 8 <= lat <= 37 and 68 <= lon <= 97:
        if lat < 15:
            return {
                "zone": "tropical_south",
                "rainfall_mm": 1800,
                "name": "Tropical South India",
                "climate": "tropical, very high humidity, heavy monsoon (1500-3000mm/yr)",
                "season_note": "No true winter; warm and humid year-round.",
            }
        elif lat < 22:
            return {
                "zone": "peninsular_central",
                "rainfall_mm": 900,
                "name": "Peninsular / Central India",
                "climate": "semi-arid to sub-humid, moderate monsoon (700-1200mm/yr)",
                "season_note": "Mild winters (15-25°C), hot summers (35-42°C).",
            }
        elif lat < 28:
            return {
                "zone": "northwest_semi_arid",
                "rainfall_mm": 500,
                "name": "Northwest / Western India",
                "climate": "semi-arid, low rainfall (300-700mm/yr), hot dry summers",
                "season_note": "Cool winters (8-20°C), extreme summers (38-45°C).",
            }
        else:
            return {
                "zone": "north_igp",
                "rainfall_mm": 850,
                "name": "North India / Indo-Gangetic Plains",
                "climate": "subtropical, cold winters, hot summers (700-1100mm/yr)",
                "season_note": "Cold winters (5-15°C), very hot summers (40-45°C).",
            }
    else:
        return {
            "zone": "unknown",
            "rainfall_mm": 800,
            "name": f"Region ({lat:.1f}°N, {lon:.1f}°E)",
            "climate": "unknown regional climate profile",
            "season_note": "Regional climate data not available for this coordinate.",
        }


# ---------------------------------------------------------------------------
# Scoring Engine Functions
# ---------------------------------------------------------------------------
def score_temperature(crop_data: dict, current_temp: float) -> dict:
    t_min = crop_data["temp_min"]
    t_max = crop_data["temp_max"]
    t_opt_min = crop_data["temp_optimal_min"]
    t_opt_max = crop_data["temp_optimal_max"]

    if current_temp == 0 or current_temp is None:
        return {"score": 13, "status": "neutral",
                "reason": "Weather data unavailable. Neutral temperature score applied."}

    if t_opt_min <= current_temp <= t_opt_max:
        return {"score": 25, "status": "excellent",
                "reason": f"Current {current_temp}°C is within the ideal {t_opt_min}–{t_opt_max}°C range."}

    if t_min <= current_temp <= t_max:
        dist = min(abs(current_temp - t_opt_min), abs(current_temp - t_opt_max))
        score = max(13, int(25 - dist * 1.8))
        direction = "cooler" if current_temp < t_opt_min else "warmer"
        return {"score": score, "status": "good",
                "reason": f"Current {current_temp}°C is slightly {direction} than the optimal {t_opt_min}–{t_opt_max}°C but still within the acceptable {t_min}–{t_max}°C range."}

    if current_temp < t_min:
        gap = t_min - current_temp
        score = max(0, int(10 - gap * 1.5))
        status = "poor" if gap <= 5 else "critical"
        return {"score": score, "status": status,
                "reason": f"Current {current_temp}°C is {gap:.1f}°C below the crop's minimum survivable threshold of {t_min}°C. Cold stress or failure is likely."}
    else:
        gap = current_temp - t_max
        score = max(0, int(10 - gap * 1.5))
        status = "poor" if gap <= 5 else "critical"
        return {"score": score, "status": status,
                "reason": f"Current {current_temp}°C is {gap:.1f}°C above the maximum tolerance of {t_max}°C. Heat stress will severely impact yield."}


def score_soil(crop_data: dict, soil_type: str) -> dict:
    soil_scores = crop_data.get("soil_scores", {})
    score = soil_scores.get(soil_type, 10)
    if score >= 23:
        status, quality = "excellent", "excellent"
    elif score >= 18:
        status, quality = "good", "good"
    elif score >= 13:
        status, quality = "moderate", "moderate"
    elif score >= 8:
        status, quality = "poor", "poor"
    else:
        status, quality = "critical", "very poor"
    note = crop_data.get("soil_notes", {}).get(soil_type, "")
    reason = f"{soil_type} is a {quality} match for {crop_data['display_name']}."
    if note:
        reason += f" {note}"
    return {"score": score, "status": status, "reason": reason}


def score_rainfall(crop_data: dict, region_rainfall_mm: int) -> dict:
    r_min = crop_data["rainfall_min_mm"]
    r_max = crop_data["rainfall_max_mm"]

    if r_min <= region_rainfall_mm <= r_max:
        return {"score": 25, "status": "excellent",
                "reason": f"Regional rainfall (~{region_rainfall_mm}mm/yr) matches the ideal {r_min}–{r_max}mm/yr requirement."}

    if region_rainfall_mm < r_min:
        deficit = r_min - region_rainfall_mm
        ratio = region_rainfall_mm / r_min
        score = max(0, int(25 * (ratio ** 1.5)))
        status = "poor" if score < 12 else "moderate"
        return {"score": score, "status": status,
                "reason": f"Regional rainfall (~{region_rainfall_mm}mm/yr) is {deficit}mm below the minimum requirement ({r_min}mm/yr). Supplemental irrigation is essential."}

    excess = region_rainfall_mm - r_max
    ratio = r_max / region_rainfall_mm
    score = max(3, int(25 * ratio))
    status = "poor" if score < 12 else "moderate"
    return {"score": score, "status": status,
            "reason": f"Regional rainfall (~{region_rainfall_mm}mm/yr) is {excess}mm above the maximum tolerance ({r_max}mm/yr). Robust drainage infrastructure is critical to prevent waterlogging."}


def score_season(crop_data: dict) -> dict:
    current_month = datetime.now().month
    season_months = crop_data.get("season_months", [])
    label = crop_data.get("seasons_label", ["Year-round"])

    if not season_months:
        return {"score": 20, "status": "good",
                "reason": f"Year-round crop. Can be planted in any month with proper management. ({', '.join(label)})"}

    if current_month in season_months:
        return {"score": 25, "status": "excellent",
                "reason": f"Currently within the optimal planting/growing window. ({', '.join(label)})"}

    def month_dist(m1, m2):
        return min(abs(m1 - m2), 12 - abs(m1 - m2))

    min_dist = min(month_dist(current_month, m) for m in season_months)
    if min_dist == 1:
        score, note = 20, "just 1 month outside"
    elif min_dist == 2:
        score, note = 15, "2 months outside"
    elif min_dist == 3:
        score, note = 10, "3 months outside"
    else:
        score, note = 4, "significantly outside"

    return {"score": score, "status": "moderate" if score >= 12 else "poor",
            "reason": f"Currently {note} the optimal window ({', '.join(label)}). Off-season planting risks yield loss."}


def calculate_suitability(crop_key: str, soil_type: str, current_temp: float, lat: float, lon: float) -> dict:
    crop_data = CROP_DB[crop_key]
    region = get_region_info(lat, lon)

    temp_r = score_temperature(crop_data, current_temp)
    soil_r = score_soil(crop_data, soil_type)
    rain_r = score_rainfall(crop_data, region["rainfall_mm"])
    seas_r = score_season(crop_data)

    total = temp_r["score"] + soil_r["score"] + rain_r["score"] + seas_r["score"]
    total = min(100, total)

    if total >= 80:
        suitable = "Highly Suitable"
    elif total >= 55:
        suitable = "Moderately Suitable"
    else:
        suitable = "Unsuitable"

    return {
        "crop_key": crop_key,
        "crop_display_name": crop_data["display_name"],
        "region": region,
        "suitability_score": total,
        "suitable": suitable,
        "data_source": "knowledge_base",
        "sub_scores": {
            "temperature": temp_r,
            "soil": soil_r,
            "rainfall": rain_r,
            "season": seas_r,
        },
        "crop_facts": {
            "temp_range": f"{crop_data['temp_min']}–{crop_data['temp_max']}°C (optimal: {crop_data['temp_optimal_min']}–{crop_data['temp_optimal_max']}°C)",
            "rainfall_range": f"{crop_data['rainfall_min_mm']}–{crop_data['rainfall_max_mm']}mm/yr",
            "seasons": crop_data.get("seasons_label", ["Year-round"]),
            "growing_days": crop_data.get("growing_days"),
            "water_requirement": crop_data.get("water_requirement"),
            "key_facts": crop_data.get("key_facts", []),
            "risks": crop_data.get("risks", []),
        },
    }


def fuzzy_match_crop(crop_name: str) -> Optional[str]:
    """Returns canonical crop key if found in CROP_DB, else None."""
    normalized = crop_name.strip().lower().replace("-", " ").replace("_", " ")
    # Exact match first
    for key, data in CROP_DB.items():
        if normalized in data["aliases"]:
            return key
    # Prefix / substring match (for plurals, compound words)
    for key, data in CROP_DB.items():
        for alias in data["aliases"]:
            if len(normalized) >= 3 and (
                alias.startswith(normalized) or normalized.startswith(alias)
            ):
                return key
    return None


# ---------------------------------------------------------------------------
# Crop Database  (78 crops with scientifically accurate agronomic data)
# ---------------------------------------------------------------------------
CROP_DB = {
    # ===== CEREALS =====
    "rice": {
        "display_name": "Rice (Paddy)",
        "aliases": ["rice", "paddy", "chawal", "dhan", "dhaan", "paddy rice"],
        "temp_min": 20, "temp_max": 38, "temp_optimal_min": 25, "temp_optimal_max": 32,
        "rainfall_min_mm": 1000, "rainfall_max_mm": 2500,
        "soil_scores": {"Black Soil": 18, "Clay Soil": 25, "Sandy Loam": 7, "Red Soil": 14, "Alluvial Soil": 23},
        "soil_notes": {"Sandy Loam": "Extremely poor: drains water too fast; rice needs water-retentive soils.", "Clay Soil": "Excellent: high water retention is ideal for paddy cultivation."},
        "season_months": [6, 7, 8, 9, 10, 11],
        "seasons_label": ["Kharif (Jun–Nov)"],
        "growing_days": 100, "water_requirement": "Very High",
        "key_facts": ["Requires flooded or saturated soil during most of its growth.", "Temperatures above 35°C during flowering stage cause significant grain-set failure.", "Clay-rich soils that retain standing water are ideal."],
        "risks": ["Blast disease", "Bacterial leaf blight", "Brown plant hopper (BPH) in humid zones"],
    },
    "wheat": {
        "display_name": "Wheat",
        "aliases": ["wheat", "gehu", "gehun", "gehoon", "atta"],
        "temp_min": 5, "temp_max": 25, "temp_optimal_min": 15, "temp_optimal_max": 20,
        "rainfall_min_mm": 450, "rainfall_max_mm": 650,
        "soil_scores": {"Black Soil": 20, "Clay Soil": 17, "Sandy Loam": 10, "Red Soil": 12, "Alluvial Soil": 25},
        "soil_notes": {"Alluvial Soil": "Perfect: Indo-Gangetic alluvial plains are the natural home of Indian wheat.", "Sandy Loam": "Poor: insufficient water and nutrient retention for wheat."},
        "season_months": [10, 11, 12, 1, 2, 3],
        "seasons_label": ["Rabi (Oct–Mar)"],
        "growing_days": 120, "water_requirement": "Moderate",
        "key_facts": ["Strictly a cool-season crop. Grain filling above 28°C causes shrivelling and yield loss.", "Alluvial soils of the Indo-Gangetic plains (UP, Punjab, Haryana) are the ideal natural habitat.", "Requires vernalization: prolonged cold period for proper head development."],
        "risks": ["Yellow rust (stripe rust) — can devastate yield if unchecked", "Loose smut", "Terminal heat stress in late Rabi"],
    },
    "maize": {
        "display_name": "Maize (Corn)",
        "aliases": ["maize", "corn", "makka", "makkai", "bhutta", "makai", "corn maize"],
        "temp_min": 18, "temp_max": 35, "temp_optimal_min": 21, "temp_optimal_max": 27,
        "rainfall_min_mm": 600, "rainfall_max_mm": 1100,
        "soil_scores": {"Black Soil": 20, "Clay Soil": 14, "Sandy Loam": 22, "Red Soil": 18, "Alluvial Soil": 24},
        "soil_notes": {"Clay Soil": "Moderate: waterlogging risk — needs good drainage management.", "Sandy Loam": "Good: excellent drainage suits maize's sensitivity to waterlogging."},
        "season_months": [6, 7, 8, 9, 10],
        "seasons_label": ["Kharif (Jun–Oct)"],
        "growing_days": 90, "water_requirement": "Moderate",
        "key_facts": ["Maize is highly sensitive to waterlogging; well-drained soils are mandatory.", "In warm southern regions, a second Rabi crop (Oct–Feb) is viable.", "Requires 6–10 irrigations in regions with less than 700mm annual rainfall."],
        "risks": ["Stem borer (Chilo partellus)", "Fall armyworm (FAW) — invasive", "Downy mildew in humid conditions"],
    },
    "sorghum": {
        "display_name": "Sorghum (Jowar)",
        "aliases": ["sorghum", "jowar", "jwar", "great millet", "durra", "juwar"],
        "temp_min": 20, "temp_max": 40, "temp_optimal_min": 26, "temp_optimal_max": 34,
        "rainfall_min_mm": 300, "rainfall_max_mm": 800,
        "soil_scores": {"Black Soil": 25, "Clay Soil": 18, "Sandy Loam": 16, "Red Soil": 20, "Alluvial Soil": 22},
        "soil_notes": {"Black Soil": "Excellent: deep black cotton soils of Deccan are the natural habitat for jowar."},
        "season_months": [6, 7, 8, 9, 10, 11],
        "seasons_label": ["Kharif (Jun–Oct)", "Rabi in Deccan (Oct–Feb)"],
        "growing_days": 110, "water_requirement": "Low",
        "key_facts": ["Extremely drought-tolerant — survives dry spells that would kill maize or rice.", "Black cotton soils of Vidarbha and Marathwada are the primary sorghum belt.", "Can survive soil moisture levels as low as 2% without complete crop failure."],
        "risks": ["Shoot fly (major pest in young seedlings)", "Grain mold in humid/rainy conditions at maturity", "Charcoal rot under extreme drought stress"],
    },
    "pearl_millet": {
        "display_name": "Pearl Millet (Bajra)",
        "aliases": ["pearl millet", "bajra", "bajri", "bajara", "kambu", "millet"],
        "temp_min": 25, "temp_max": 42, "temp_optimal_min": 30, "temp_optimal_max": 35,
        "rainfall_min_mm": 250, "rainfall_max_mm": 600,
        "soil_scores": {"Black Soil": 16, "Clay Soil": 10, "Sandy Loam": 25, "Red Soil": 20, "Alluvial Soil": 18},
        "soil_notes": {"Sandy Loam": "Excellent: sandy soils of Rajasthan/Gujarat are the traditional bajra zone.", "Clay Soil": "Poor: waterlogging risk is very high in heavy clay soils."},
        "season_months": [6, 7, 8, 9],
        "seasons_label": ["Kharif (Jun–Sep)"],
        "growing_days": 75, "water_requirement": "Very Low",
        "key_facts": ["The most heat and drought-tolerant of all Indian cereals.", "Sandy soils of Rajasthan, Gujarat, and Haryana are the primary growing areas.", "Can yield 1–2 tonnes/ha with only 300mm annual rainfall — no other cereal matches this."],
        "risks": ["Downy mildew (green ear disease) — major problem", "Ergot in cool, humid flowering conditions", "Smut"],
    },
    "barley": {
        "display_name": "Barley (Jau)",
        "aliases": ["barley", "jau", "jow", "barli"],
        "temp_min": 5, "temp_max": 25, "temp_optimal_min": 12, "temp_optimal_max": 18,
        "rainfall_min_mm": 250, "rainfall_max_mm": 600,
        "soil_scores": {"Black Soil": 16, "Clay Soil": 14, "Sandy Loam": 22, "Red Soil": 15, "Alluvial Soil": 20},
        "season_months": [10, 11, 12, 1, 2, 3],
        "seasons_label": ["Rabi (Oct–Mar)"],
        "growing_days": 100, "water_requirement": "Low",
        "key_facts": ["More drought-tolerant than wheat; grows on lighter soils unsuitable for wheat.", "The most salt-tolerant cereal — useful for reclaimed saline lands.", "Requires cold winters; cannot be grown profitably in tropical or subtropical zones."],
        "risks": ["Powdery mildew", "Loose smut", "Net blotch disease in wet conditions"],
    },
    # ===== PULSES =====
    "chickpea": {
        "display_name": "Chickpea (Gram / Chana)",
        "aliases": ["chickpea", "gram", "chana", "chick pea", "garbanzo", "desi chana", "kabuli chana", "chanaa"],
        "temp_min": 15, "temp_max": 30, "temp_optimal_min": 18, "temp_optimal_max": 25,
        "rainfall_min_mm": 300, "rainfall_max_mm": 600,
        "soil_scores": {"Black Soil": 22, "Clay Soil": 12, "Sandy Loam": 18, "Red Soil": 16, "Alluvial Soil": 20},
        "soil_notes": {"Clay Soil": "Poor: excessive moisture causes Fusarium wilt — chickpea hates waterlogging.", "Black Soil": "Excellent: medium-deep black soils of MP and Maharashtra are the premium chickpea zone."},
        "season_months": [10, 11, 12, 1, 2],
        "seasons_label": ["Rabi (Oct–Feb)"],
        "growing_days": 95, "water_requirement": "Low",
        "key_facts": ["Primarily a dryland Rabi crop; excess moisture at any stage causes wilt.", "India is the world's largest producer — MP, Maharashtra, and Rajasthan lead.", "Does not tolerate waterlogging even for 24 hours."],
        "risks": ["Fusarium wilt (devastating in heavy soils)", "Ascochyta blight in cool humid weather", "Pod borer (Helicoverpa armigera)"],
    },
    "lentil": {
        "display_name": "Lentil (Masoor Dal)",
        "aliases": ["lentil", "masoor", "masur", "lentils", "red lentil", "masoor dal"],
        "temp_min": 10, "temp_max": 28, "temp_optimal_min": 18, "temp_optimal_max": 22,
        "rainfall_min_mm": 250, "rainfall_max_mm": 500,
        "soil_scores": {"Black Soil": 18, "Clay Soil": 12, "Sandy Loam": 20, "Red Soil": 16, "Alluvial Soil": 22},
        "season_months": [10, 11, 12, 1, 2],
        "seasons_label": ["Rabi (Oct–Feb)"],
        "growing_days": 85, "water_requirement": "Very Low",
        "key_facts": ["Adapted to cool, semi-arid conditions with minimal irrigation (2–3 waterings).", "Sensitive to both waterlogging and drought during flowering stage.", "Alluvial soils of eastern India (UP, Bihar, WB) are the primary producing areas."],
        "risks": ["Rust disease", "Wilt (Fusarium)", "Stem and root rot in waterlogged conditions"],
    },
    "pigeon_pea": {
        "display_name": "Pigeon Pea (Tur / Arhar Dal)",
        "aliases": ["pigeon pea", "tur", "arhar", "toor", "red gram", "cajanus", "toor dal"],
        "temp_min": 18, "temp_max": 38, "temp_optimal_min": 25, "temp_optimal_max": 30,
        "rainfall_min_mm": 600, "rainfall_max_mm": 1000,
        "soil_scores": {"Black Soil": 22, "Clay Soil": 13, "Sandy Loam": 18, "Red Soil": 20, "Alluvial Soil": 20},
        "season_months": [6, 7, 8, 9, 10, 11],
        "seasons_label": ["Kharif (Jun–Nov)"],
        "growing_days": 160, "water_requirement": "Low to Moderate",
        "key_facts": ["Deep tap roots make it highly drought-tolerant once established.", "Fixes atmospheric nitrogen — improves soil fertility for the next crop.", "Long-duration varieties (160–220 days) dominate Vidarbha and Marathwada."],
        "risks": ["Wilt (Fusarium udum)", "Sterility mosaic disease (viral, no cure)", "Pod fly"],
    },
    "black_gram": {
        "display_name": "Black Gram (Urad Dal)",
        "aliases": ["black gram", "urad", "urad dal", "black lentil", "vigna mungo", "udad"],
        "temp_min": 25, "temp_max": 40, "temp_optimal_min": 28, "temp_optimal_max": 35,
        "rainfall_min_mm": 600, "rainfall_max_mm": 1000,
        "soil_scores": {"Black Soil": 17, "Clay Soil": 12, "Sandy Loam": 21, "Red Soil": 18, "Alluvial Soil": 22},
        "season_months": [6, 7, 8, 9, 10],
        "seasons_label": ["Kharif (Jun–Oct)"],
        "growing_days": 70, "water_requirement": "Low to Moderate",
        "key_facts": ["Short crop cycle (65–75 days) ideal as a catch crop or intercrop.", "Requires warm humid conditions during vegetative growth.", "Avoid heavy clay soils; well-drained sandy loam preferred."],
        "risks": ["Yellow mosaic virus (YMV) — spread by whitefly", "Cercospora leaf spot", "Pod borer"],
    },
    "green_gram": {
        "display_name": "Green Gram (Moong Dal)",
        "aliases": ["green gram", "moong", "mung", "mung bean", "moong dal", "moong bean"],
        "temp_min": 25, "temp_max": 38, "temp_optimal_min": 28, "temp_optimal_max": 34,
        "rainfall_min_mm": 600, "rainfall_max_mm": 1000,
        "soil_scores": {"Black Soil": 15, "Clay Soil": 11, "Sandy Loam": 23, "Red Soil": 18, "Alluvial Soil": 22},
        "season_months": [3, 4, 5, 6, 7, 8, 9],
        "seasons_label": ["Zaid (Mar–Jun)", "Kharif (Jun–Sep)"],
        "growing_days": 65, "water_requirement": "Low to Moderate",
        "key_facts": ["Highly adaptable; grown in both summer and kharif seasons.", "Prefers well-drained light to medium soils; waterlogging causes root rot.", "Very short cycle (60–70 days) — excellent for intercropping systems."],
        "risks": ["Yellow mosaic disease", "Powdery mildew", "Thrips in dry conditions"],
    },
    "cowpea": {
        "display_name": "Cowpea (Lobia)",
        "aliases": ["cowpea", "lobia", "lobhia", "black-eyed pea", "vigna unguiculata", "chawli"],
        "temp_min": 20, "temp_max": 38, "temp_optimal_min": 25, "temp_optimal_max": 32,
        "rainfall_min_mm": 400, "rainfall_max_mm": 900,
        "soil_scores": {"Black Soil": 15, "Clay Soil": 11, "Sandy Loam": 22, "Red Soil": 18, "Alluvial Soil": 20},
        "season_months": [3, 4, 5, 6, 7, 8, 9, 10],
        "seasons_label": ["Kharif (Jun–Oct)", "Zaid (Mar–Jun)"],
        "growing_days": 70, "water_requirement": "Low to Moderate",
        "key_facts": ["Among the most heat and drought-tolerant legumes — grows where others fail.", "Sandy soils are no problem; excellent nitrogen-fixing capability.", "Useful as green manure, fodder, and grain crop."],
        "risks": ["Aphids", "Leaf curl virus", "Fusarium wilt in waterlogged soils"],
    },
    "kidney_bean": {
        "display_name": "Kidney Bean (Rajma)",
        "aliases": ["kidney bean", "rajma", "rajmah", "french bean", "common bean", "rajmaa"],
        "temp_min": 10, "temp_max": 28, "temp_optimal_min": 15, "temp_optimal_max": 22,
        "rainfall_min_mm": 600, "rainfall_max_mm": 1200,
        "soil_scores": {"Black Soil": 15, "Clay Soil": 12, "Sandy Loam": 20, "Red Soil": 15, "Alluvial Soil": 22},
        "season_months": [3, 4, 5, 6, 10, 11, 12],
        "seasons_label": ["Zaid (Mar–May) in hills", "Rabi in NE India (Oct–Jan)"],
        "growing_days": 90, "water_requirement": "Moderate",
        "key_facts": ["Strictly a cool-season crop; pod set fails above 30°C.", "Himalayan foothills and NE India are the natural growing zones.", "Waterlogging causes rapid root rot — well-drained loamy soils are essential."],
        "risks": ["Bean common mosaic virus", "Bacterial blight", "Root rot in heavy soils"],
    },
    # ===== OILSEEDS =====
    "groundnut": {
        "display_name": "Groundnut (Peanut / Moongphali)",
        "aliases": ["groundnut", "peanut", "moongfali", "moongphali", "arachis", "earthnut", "ground nut"],
        "temp_min": 20, "temp_max": 35, "temp_optimal_min": 25, "temp_optimal_max": 30,
        "rainfall_min_mm": 500, "rainfall_max_mm": 1200,
        "soil_scores": {"Black Soil": 14, "Clay Soil": 7, "Sandy Loam": 25, "Red Soil": 22, "Alluvial Soil": 18},
        "soil_notes": {"Sandy Loam": "Excellent: loose sandy loam allows easy pod penetration underground.", "Clay Soil": "Very poor: hard clay prevents pod expansion and makes harvesting near impossible."},
        "season_months": [6, 7, 8, 9, 10],
        "seasons_label": ["Kharif (Jun–Oct)"],
        "growing_days": 110, "water_requirement": "Moderate",
        "key_facts": ["Pods develop underground — loose, well-aerated sandy loam soils are mandatory.", "Gujarat and Andhra Pradesh produce the most groundnut on sandy loam and red soils.", "Pegging stage is critical; waterlogging even for 2 days can destroy pegs."],
        "risks": ["Tikka disease (leaf spot)", "Stem rot (Sclerotium rolfsii)", "Aflatoxin contamination in humid storage"],
    },
    "soybean": {
        "display_name": "Soybean",
        "aliases": ["soybean", "soya", "soya bean", "glycine max", "soy", "soya beans"],
        "temp_min": 20, "temp_max": 35, "temp_optimal_min": 25, "temp_optimal_max": 30,
        "rainfall_min_mm": 600, "rainfall_max_mm": 1000,
        "soil_scores": {"Black Soil": 22, "Clay Soil": 15, "Sandy Loam": 18, "Red Soil": 16, "Alluvial Soil": 22},
        "season_months": [6, 7, 8, 9, 10],
        "seasons_label": ["Kharif (Jun–Oct)"],
        "growing_days": 95, "water_requirement": "Moderate",
        "key_facts": ["Photoperiod-sensitive crop: requires short days for flowering.", "Madhya Pradesh produces ~50% of India's soybean on black cotton soils.", "Waterlogging kills nitrogen-fixing nodule bacteria — avoid heavy clay soils."],
        "risks": ["Yellow mosaic disease (YMD)", "Soybean rust", "Charcoal rot in drought-stressed fields"],
    },
    "sunflower": {
        "display_name": "Sunflower (Surajmukhi)",
        "aliases": ["sunflower", "surajmukhi", "suraj mukhi", "helianthus", "soorjmukhi"],
        "temp_min": 18, "temp_max": 35, "temp_optimal_min": 22, "temp_optimal_max": 28,
        "rainfall_min_mm": 400, "rainfall_max_mm": 800,
        "soil_scores": {"Black Soil": 22, "Clay Soil": 15, "Sandy Loam": 20, "Red Soil": 18, "Alluvial Soil": 22},
        "season_months": [1, 2, 3, 6, 7, 8, 9, 10],
        "seasons_label": ["Rabi (Jan–Apr)", "Kharif (Jun–Sep)"],
        "growing_days": 90, "water_requirement": "Moderate",
        "key_facts": ["Relatively drought-tolerant oilseed adaptable to many soils.", "Deep-rooted; can extract soil moisture from deeper layers during dry periods.", "Most sensitive to moisture stress during flowering and seed filling."],
        "risks": ["Alternaria leaf blight", "Downy mildew", "Sclerotinia head rot in cool, moist weather"],
    },
    "mustard": {
        "display_name": "Mustard / Rapeseed (Sarson)",
        "aliases": ["mustard", "sarson", "sarson ka tel", "canola", "rapeseed", "rai", "raya"],
        "temp_min": 5, "temp_max": 25, "temp_optimal_min": 10, "temp_optimal_max": 20,
        "rainfall_min_mm": 250, "rainfall_max_mm": 500,
        "soil_scores": {"Black Soil": 18, "Clay Soil": 13, "Sandy Loam": 20, "Red Soil": 14, "Alluvial Soil": 22},
        "season_months": [10, 11, 12, 1, 2],
        "seasons_label": ["Rabi (Oct–Feb)"],
        "growing_days": 95, "water_requirement": "Low",
        "key_facts": ["One of the most cold-tolerant oilseed crops; thrives in cool winters.", "Rajasthan, UP, and Haryana dominate production. Cannot grow in tropical heat.", "Only 2–3 irrigations needed; a very low water requirement crop."],
        "risks": ["Alternaria blight", "White rust", "Aphid infestations in cool weather"],
    },
    "sesame": {
        "display_name": "Sesame (Til / Gingelly)",
        "aliases": ["sesame", "til", "gingelly", "tilli", "sesamum", "tilseed"],
        "temp_min": 25, "temp_max": 40, "temp_optimal_min": 28, "temp_optimal_max": 35,
        "rainfall_min_mm": 400, "rainfall_max_mm": 700,
        "soil_scores": {"Black Soil": 15, "Clay Soil": 9, "Sandy Loam": 24, "Red Soil": 22, "Alluvial Soil": 18},
        "soil_notes": {"Sandy Loam": "Excellent: well-drained sandy loam is ideal — sesame cannot tolerate waterlogging."},
        "season_months": [6, 7, 8, 9, 10],
        "seasons_label": ["Kharif (Jun–Oct)"],
        "growing_days": 80, "water_requirement": "Low",
        "key_facts": ["An extremely heat-tolerant oilseed; performs best in hot, dry conditions.", "Waterlogging is catastrophic — well-drained sandy loam soils are essential.", "Rajasthan, Gujarat, and West Bengal are major producing states."],
        "risks": ["Phyllody disease (phytoplasma)", "Alternaria leaf spot", "Stem gall"],
    },
    "castor": {
        "display_name": "Castor (Arandi)",
        "aliases": ["castor", "castor bean", "arandi", "rendi", "ricinus", "castor plant"],
        "temp_min": 20, "temp_max": 38, "temp_optimal_min": 25, "temp_optimal_max": 30,
        "rainfall_min_mm": 500, "rainfall_max_mm": 700,
        "soil_scores": {"Black Soil": 17, "Clay Soil": 11, "Sandy Loam": 22, "Red Soil": 20, "Alluvial Soil": 20},
        "season_months": [6, 7, 8, 9, 10, 11],
        "seasons_label": ["Kharif (Jun–Nov)"],
        "growing_days": 180, "water_requirement": "Low to Moderate",
        "key_facts": ["Gujarat produces over 80% of India's castor crop on sandy loam soils.", "Drought-tolerant once established but very sensitive to waterlogging.", "Deep-rooted; can be ratooned (cut and regrown) for multiple harvests."],
        "risks": ["Leaf blight", "Capsule borer", "Root rot in waterlogged conditions"],
    },
    # ===== CASH CROPS =====
    "cotton": {
        "display_name": "Cotton (Kapas / BT Cotton)",
        "aliases": ["cotton", "kapas", "gossypium", "bt cotton", "rui", "kapas cotton"],
        "temp_min": 20, "temp_max": 40, "temp_optimal_min": 27, "temp_optimal_max": 32,
        "rainfall_min_mm": 500, "rainfall_max_mm": 1200,
        "soil_scores": {"Black Soil": 25, "Clay Soil": 18, "Sandy Loam": 15, "Red Soil": 20, "Alluvial Soil": 20},
        "soil_notes": {"Black Soil": "Excellent: deep black Vertisols of Vidarbha are the natural habitat of Indian cotton."},
        "season_months": [5, 6, 7, 8, 9, 10, 11],
        "seasons_label": ["Kharif (May–Nov)"],
        "growing_days": 165, "water_requirement": "Moderate to High",
        "key_facts": ["Black cotton soils (Vertisols) retain moisture during dry spells — critical for long-duration cotton.", "Bt cotton has largely replaced conventional varieties with the same climate requirements.", "Maharashtra, Gujarat, and Telangana are the major cotton-producing states."],
        "risks": ["Pink bollworm (Pectinophora gossypiella)", "American bollworm (Helicoverpa armigera)", "Root rot (Fusarium/Pythium) in waterlogged soils"],
    },
    "sugarcane": {
        "display_name": "Sugarcane (Ganna)",
        "aliases": ["sugarcane", "ganna", "sugar cane", "saccharum", "ganne"],
        "temp_min": 20, "temp_max": 38, "temp_optimal_min": 25, "temp_optimal_max": 32,
        "rainfall_min_mm": 1000, "rainfall_max_mm": 2000,
        "soil_scores": {"Black Soil": 18, "Clay Soil": 22, "Sandy Loam": 13, "Red Soil": 16, "Alluvial Soil": 25},
        "soil_notes": {"Alluvial Soil": "Excellent: deep, fertile alluvial soils of UP and Bihar give maximum cane yield."},
        "season_months": [1, 2, 3, 4, 5, 10, 11, 12],
        "seasons_label": ["Planted Oct–Mar; harvested 12–14 months later"],
        "growing_days": 360, "water_requirement": "Very High",
        "key_facts": ["One of the most water-intensive crops — requires 1500–2500mm/yr (irrigation supplements essential in dry areas).", "Alluvial soils of UP, Bihar, and Punjab produce best yields.", "12–14 month cycle means climate stability through an entire year is critical."],
        "risks": ["Red rot disease (most destructive)", "Sugarcane top borer", "Smut disease in humid conditions"],
    },
    "jute": {
        "display_name": "Jute (Pat)",
        "aliases": ["jute", "pat", "paat", "corchorus", "jute plant"],
        "temp_min": 25, "temp_max": 40, "temp_optimal_min": 28, "temp_optimal_max": 35,
        "rainfall_min_mm": 1200, "rainfall_max_mm": 2000,
        "soil_scores": {"Black Soil": 15, "Clay Soil": 17, "Sandy Loam": 13, "Red Soil": 13, "Alluvial Soil": 25},
        "soil_notes": {"Alluvial Soil": "Excellent: the Ganges-Brahmaputra alluvial delta is the world's finest jute habitat."},
        "season_months": [3, 4, 5, 6, 7, 8, 9],
        "seasons_label": ["Kharif (Mar–Sep)"],
        "growing_days": 120, "water_requirement": "Very High",
        "key_facts": ["West Bengal and Assam produce over 90% of India's jute on Gangetic alluvial flood plains.", "Requires annual flooding or very high monsoon rainfall.", "Cannot be grown in dry regions — one of the highest water demand crops in India."],
        "risks": ["Stem rot", "Black band disease", "Semilooper caterpillar"],
    },
    # ===== VEGETABLES =====
    "tomato": {
        "display_name": "Tomato (Tamatar)",
        "aliases": ["tomato", "tamatar", "tomatoes", "tomat"],
        "temp_min": 18, "temp_max": 35, "temp_optimal_min": 20, "temp_optimal_max": 27,
        "rainfall_min_mm": 600, "rainfall_max_mm": 1200,
        "soil_scores": {"Black Soil": 17, "Clay Soil": 13, "Sandy Loam": 22, "Red Soil": 18, "Alluvial Soil": 24},
        "season_months": list(range(1, 13)),
        "seasons_label": ["Year-round (best quality Oct–Feb)"],
        "growing_days": 70, "water_requirement": "Moderate",
        "key_facts": ["Pollen viability falls sharply above 35°C — fruit set fails in intense summer heat.", "Well-drained sandy loam soils with rich organic matter are ideal.", "Can be grown year-round in India; quality peaks in cool Rabi season."],
        "risks": ["Early blight (Alternaria)", "Late blight in cool-humid conditions", "Tomato leaf curl virus (ToLCV)"],
    },
    "potato": {
        "display_name": "Potato (Aloo)",
        "aliases": ["potato", "aloo", "alu", "potatoes", "batata"],
        "temp_min": 10, "temp_max": 28, "temp_optimal_min": 15, "temp_optimal_max": 20,
        "rainfall_min_mm": 600, "rainfall_max_mm": 1200,
        "soil_scores": {"Black Soil": 15, "Clay Soil": 8, "Sandy Loam": 25, "Red Soil": 18, "Alluvial Soil": 22},
        "soil_notes": {"Sandy Loam": "Excellent: loose sandy loam allows uniform tuber expansion and easy harvesting.", "Clay Soil": "Very poor: hard clay restricts tuber growth and causes misshapen potatoes."},
        "season_months": [10, 11, 12, 1, 2],
        "seasons_label": ["Rabi (Oct–Feb) in plains; Summer in hills"],
        "growing_days": 90, "water_requirement": "Moderate",
        "key_facts": ["Tuber formation completely stops above 29°C.", "UP and West Bengal dominate production; Himachal Pradesh produces premium seed potatoes.", "Sandy loam soils allow uniform tuber expansion and easy mechanical harvesting."],
        "risks": ["Late blight (Phytophthora infestans) — most devastating disease", "Early blight", "Black scurf (Rhizoctonia) in heavy soils"],
    },
    "onion": {
        "display_name": "Onion (Pyaaz)",
        "aliases": ["onion", "pyaaz", "pyaz", "kanda", "piaj", "onions"],
        "temp_min": 10, "temp_max": 35, "temp_optimal_min": 15, "temp_optimal_max": 25,
        "rainfall_min_mm": 500, "rainfall_max_mm": 800,
        "soil_scores": {"Black Soil": 17, "Clay Soil": 11, "Sandy Loam": 24, "Red Soil": 18, "Alluvial Soil": 22},
        "soil_notes": {"Sandy Loam": "Excellent: loose soils allow proper bulb expansion and reduce bulb deformation.", "Clay Soil": "Poor: dense clay soils deform bulbs and increase disease risk."},
        "season_months": [10, 11, 12, 1, 2, 3],
        "seasons_label": ["Rabi (Oct–Mar)", "Kharif (Jun–Sep)"],
        "growing_days": 120, "water_requirement": "Moderate",
        "key_facts": ["Bulb formation is triggered by long photoperiods and moderate temperatures.", "Maharashtra, Karnataka, and MP are the largest producers.", "Excess soil moisture near maturity causes neck rot and poor storability."],
        "risks": ["Purple blotch (Alternaria)", "Thrips infestation", "Basal rot in waterlogged conditions"],
    },
    "garlic": {
        "display_name": "Garlic (Lahsun)",
        "aliases": ["garlic", "lahsun", "lasun", "lahasun"],
        "temp_min": 8, "temp_max": 28, "temp_optimal_min": 15, "temp_optimal_max": 22,
        "rainfall_min_mm": 500, "rainfall_max_mm": 700,
        "soil_scores": {"Black Soil": 15, "Clay Soil": 9, "Sandy Loam": 24, "Red Soil": 15, "Alluvial Soil": 22},
        "season_months": [10, 11, 12, 1, 2],
        "seasons_label": ["Rabi (Oct–Feb)"],
        "growing_days": 150, "water_requirement": "Low to Moderate",
        "key_facts": ["Requires vernalization (cold period) for proper bulb development.", "Sandy loam soils allow clove expansion without deformation.", "MP is India's largest garlic producer."],
        "risks": ["Purple blotch", "Rust disease", "Basal rot in waterlogged soils"],
    },
    "chili": {
        "display_name": "Chili / Hot Pepper (Mirchi)",
        "aliases": ["chili", "chilli", "hot pepper", "mirchi", "mircha", "lal mirch", "green chili"],
        "temp_min": 18, "temp_max": 38, "temp_optimal_min": 22, "temp_optimal_max": 30,
        "rainfall_min_mm": 600, "rainfall_max_mm": 1200,
        "soil_scores": {"Black Soil": 18, "Clay Soil": 13, "Sandy Loam": 22, "Red Soil": 18, "Alluvial Soil": 22},
        "season_months": list(range(1, 13)),
        "seasons_label": ["Year-round (main seasons Kharif and Rabi)"],
        "growing_days": 90, "water_requirement": "Moderate",
        "key_facts": ["Andhra Pradesh and Telangana dominate — 'Guntur chili' is world-famous.", "Waterlogging causes Phytophthora crown rot — well-drained soils are essential.", "Flower and fruit drop occurs above 38°C."],
        "risks": ["Anthracnose (fruit rot)", "Powdery mildew", "Thrips and mite complex", "Viral diseases (ToLCV, CMV)"],
    },
    "bell_pepper": {
        "display_name": "Bell Pepper / Capsicum (Shimla Mirch)",
        "aliases": ["bell pepper", "capsicum", "shimla mirch", "sweet pepper", "green pepper"],
        "temp_min": 16, "temp_max": 32, "temp_optimal_min": 18, "temp_optimal_max": 26,
        "rainfall_min_mm": 600, "rainfall_max_mm": 1000,
        "soil_scores": {"Black Soil": 15, "Clay Soil": 11, "Sandy Loam": 22, "Red Soil": 15, "Alluvial Soil": 22},
        "season_months": [10, 11, 12, 1, 2, 3],
        "seasons_label": ["Rabi (Oct–Mar) in plains; Summer in hills"],
        "growing_days": 75, "water_requirement": "Moderate",
        "key_facts": ["More cold-sensitive than chili; requires milder temperatures for quality production.", "Under polyhouse cultivation, can be grown year-round.", "HP and Uttarakhand produce premium quality capsicum."],
        "risks": ["Phytophthora blight", "Anthracnose", "Thrips-borne TSWV virus"],
    },
    "brinjal": {
        "display_name": "Brinjal / Eggplant (Baingan)",
        "aliases": ["brinjal", "eggplant", "baingan", "begun", "aubergine", "bangan", "baigan"],
        "temp_min": 18, "temp_max": 38, "temp_optimal_min": 22, "temp_optimal_max": 30,
        "rainfall_min_mm": 600, "rainfall_max_mm": 1000,
        "soil_scores": {"Black Soil": 17, "Clay Soil": 13, "Sandy Loam": 20, "Red Soil": 18, "Alluvial Soil": 22},
        "season_months": list(range(1, 13)),
        "seasons_label": ["Year-round (main season Feb–Apr and Jun–Aug)"],
        "growing_days": 80, "water_requirement": "Moderate",
        "key_facts": ["One of the most adaptable vegetables — grows across all climate zones of India.", "Performs well in a variety of soils but prefers well-drained loamy soils.", "Bt brinjal was developed specifically to address the shoot and fruit borer problem."],
        "risks": ["Shoot and fruit borer (major pest)", "Phomopsis blight", "Little leaf disease (phytoplasma)"],
    },
    "cabbage": {
        "display_name": "Cabbage (Patta Gobhi)",
        "aliases": ["cabbage", "patta gobhi", "band gobhi", "bandha kobi"],
        "temp_min": 5, "temp_max": 22, "temp_optimal_min": 10, "temp_optimal_max": 18,
        "rainfall_min_mm": 600, "rainfall_max_mm": 1000,
        "soil_scores": {"Black Soil": 13, "Clay Soil": 13, "Sandy Loam": 18, "Red Soil": 13, "Alluvial Soil": 22},
        "season_months": [10, 11, 12, 1, 2],
        "seasons_label": ["Rabi (Oct–Feb) in plains; Summer in hills"],
        "growing_days": 85, "water_requirement": "Moderate",
        "key_facts": ["Strictly cool-season; temperatures above 25°C cause premature bolting (flowering).", "Heavy, fertile, moisture-retentive soils with good organic matter give the best yields.", "Completely unsuitable for tropical plains during summer."],
        "risks": ["Diamond back moth (DBM) — most serious pest worldwide", "Black rot disease", "Club root in acidic soils"],
    },
    "cauliflower": {
        "display_name": "Cauliflower (Phool Gobhi)",
        "aliases": ["cauliflower", "phool gobhi", "gobi", "gobhi", "cauliflower vegetable"],
        "temp_min": 5, "temp_max": 22, "temp_optimal_min": 8, "temp_optimal_max": 18,
        "rainfall_min_mm": 600, "rainfall_max_mm": 1000,
        "soil_scores": {"Black Soil": 13, "Clay Soil": 13, "Sandy Loam": 17, "Red Soil": 13, "Alluvial Soil": 22},
        "season_months": [9, 10, 11, 12, 1, 2],
        "seasons_label": ["Rabi (Sep–Feb) in plains; Summer in hills"],
        "growing_days": 90, "water_requirement": "Moderate",
        "key_facts": ["More sensitive to temperature than cabbage; loose, leafy curds form above 25°C.", "Early varieties tolerate up to 28°C; late varieties need as low as 8°C for curd initiation.", "Well-drained, fertile alluvial soils with consistent moisture are essential."],
        "risks": ["Diamond back moth", "Black rot", "Hollow stem (boron deficiency) in sandy soils"],
    },
    "spinach": {
        "display_name": "Spinach (Palak)",
        "aliases": ["spinach", "palak", "paalak", "spinach leaves", "spinacia"],
        "temp_min": 5, "temp_max": 25, "temp_optimal_min": 10, "temp_optimal_max": 18,
        "rainfall_min_mm": 500, "rainfall_max_mm": 700,
        "soil_scores": {"Black Soil": 15, "Clay Soil": 13, "Sandy Loam": 18, "Red Soil": 13, "Alluvial Soil": 22},
        "season_months": [10, 11, 12, 1, 2, 3],
        "seasons_label": ["Rabi (Oct–Mar)"],
        "growing_days": 45, "water_requirement": "Low to Moderate",
        "key_facts": ["Bolts (goes to seed) rapidly above 25°C, making leaves bitter and unmarketable.", "Short cycle (40–50 days) allows 3–4 harvests per Rabi season.", "Alluvial soils with good organic content maximize leaf yield."],
        "risks": ["Downy mildew", "Leaf miner", "Damping off in waterlogged seedbeds"],
    },
    "okra": {
        "display_name": "Okra / Bhindi (Lady's Finger)",
        "aliases": ["okra", "bhindi", "bhendi", "lady finger", "ladies finger", "bhindi vegetable"],
        "temp_min": 22, "temp_max": 40, "temp_optimal_min": 26, "temp_optimal_max": 35,
        "rainfall_min_mm": 600, "rainfall_max_mm": 1200,
        "soil_scores": {"Black Soil": 18, "Clay Soil": 13, "Sandy Loam": 22, "Red Soil": 18, "Alluvial Soil": 22},
        "season_months": [2, 3, 4, 5, 6, 7, 8, 9, 10],
        "seasons_label": ["Summer (Feb–May)", "Kharif (Jun–Oct)"],
        "growing_days": 60, "water_requirement": "Moderate",
        "key_facts": ["Loves heat — one of the most warm-season adaptable vegetables; fails below 18°C.", "Very productive in summer conditions.", "Well-drained soils are critical; waterlogging causes stem rot within days."],
        "risks": ["Yellow vein mosaic disease (YVMD) — most destructive", "Shoot and fruit borer", "Root knot nematode"],
    },
    "bitter_gourd": {
        "display_name": "Bitter Gourd (Karela)",
        "aliases": ["bitter gourd", "karela", "bitter melon", "kerala", "bittergourd"],
        "temp_min": 22, "temp_max": 38, "temp_optimal_min": 25, "temp_optimal_max": 32,
        "rainfall_min_mm": 600, "rainfall_max_mm": 1200,
        "soil_scores": {"Black Soil": 15, "Clay Soil": 11, "Sandy Loam": 22, "Red Soil": 18, "Alluvial Soil": 22},
        "season_months": [2, 3, 4, 5, 6, 7, 8, 9, 10],
        "seasons_label": ["Summer (Feb–May)", "Kharif (Jun–Oct)"],
        "growing_days": 70, "water_requirement": "Moderate",
        "key_facts": ["Warm season vine crop; thrives in hot humid conditions.", "Growth stops below 18°C; frost kills plants immediately.", "Widely adaptable across India as a nutritional, low-input crop."],
        "risks": ["Fruit fly (Bactrocera cucurbitae)", "Powdery mildew", "Mosaic virus"],
    },
    "bottle_gourd": {
        "display_name": "Bottle Gourd (Lauki / Doodhi)",
        "aliases": ["bottle gourd", "lauki", "doodhi", "ghia", "opo squash", "lau"],
        "temp_min": 20, "temp_max": 38, "temp_optimal_min": 25, "temp_optimal_max": 32,
        "rainfall_min_mm": 600, "rainfall_max_mm": 1200,
        "soil_scores": {"Black Soil": 15, "Clay Soil": 11, "Sandy Loam": 22, "Red Soil": 17, "Alluvial Soil": 22},
        "season_months": [2, 3, 4, 5, 6, 7, 8, 9, 10],
        "seasons_label": ["Summer (Feb–May)", "Kharif (Jun–Oct)"],
        "growing_days": 60, "water_requirement": "Moderate",
        "key_facts": ["One of the most widely grown cucurbit vegetables in India.", "Requires warm temperatures throughout; sensitive to cool nights.", "Sandy loam soils with rich organic matter produce maximum vine growth."],
        "risks": ["Mosaic virus", "Fruit fly", "Powdery mildew"],
    },
    "pumpkin": {
        "display_name": "Pumpkin (Kaddu)",
        "aliases": ["pumpkin", "kaddu", "kaddoo", "sitaphal", "kumra"],
        "temp_min": 18, "temp_max": 35, "temp_optimal_min": 22, "temp_optimal_max": 28,
        "rainfall_min_mm": 600, "rainfall_max_mm": 1200,
        "soil_scores": {"Black Soil": 15, "Clay Soil": 13, "Sandy Loam": 22, "Red Soil": 17, "Alluvial Soil": 22},
        "season_months": [2, 3, 4, 5, 6, 7, 8, 9, 10],
        "seasons_label": ["Summer (Feb–May)", "Kharif (Jun–Oct)"],
        "growing_days": 90, "water_requirement": "Moderate",
        "key_facts": ["Highly adaptable across a wide range of soils and climates.", "Deep-rooted; can withstand short dry spells better than most cucurbits.", "Fruits store for several months post-harvest — good for market buffering."],
        "risks": ["Powdery mildew", "Fruit fly", "Mosaic virus"],
    },
    "cucumber": {
        "display_name": "Cucumber (Kheera)",
        "aliases": ["cucumber", "kheera", "khira", "kakdi", "cucumber vegetable"],
        "temp_min": 18, "temp_max": 35, "temp_optimal_min": 20, "temp_optimal_max": 28,
        "rainfall_min_mm": 600, "rainfall_max_mm": 1200,
        "soil_scores": {"Black Soil": 13, "Clay Soil": 11, "Sandy Loam": 24, "Red Soil": 15, "Alluvial Soil": 22},
        "season_months": [2, 3, 4, 5, 6, 7, 8, 9],
        "seasons_label": ["Summer (Feb–Apr)", "Kharif (Jun–Sep)"],
        "growing_days": 55, "water_requirement": "Moderate",
        "key_facts": ["Requires consistently warm temperatures for fruit development.", "Sandy loam soils with good drainage and high organic matter give best quality fruits.", "Very short cycle — 2–3 crops per year possible in warm regions."],
        "risks": ["Downy mildew", "Powdery mildew", "Fruit fly", "Aphids transmitting viruses"],
    },
    "watermelon": {
        "display_name": "Watermelon (Tarbooz)",
        "aliases": ["watermelon", "tarbooz", "tarbuz", "tarbooj", "matira"],
        "temp_min": 22, "temp_max": 40, "temp_optimal_min": 25, "temp_optimal_max": 35,
        "rainfall_min_mm": 400, "rainfall_max_mm": 600,
        "soil_scores": {"Black Soil": 11, "Clay Soil": 7, "Sandy Loam": 25, "Red Soil": 20, "Alluvial Soil": 18},
        "soil_notes": {"Sandy Loam": "Excellent: sandy soils give the best quality — sweet, crunchy flesh.", "Clay Soil": "Very poor: causes rotting, misshapen fruits, and difficult harvesting."},
        "season_months": [2, 3, 4, 5, 6],
        "seasons_label": ["Zaid / Summer (Feb–Jun)"],
        "growing_days": 85, "water_requirement": "Moderate",
        "key_facts": ["Loves heat — one of the best drought-tolerant fruit crops available.", "Sandy loam soils of river banks (UP, Rajasthan) give the sweetest fruits.", "Quality drops dramatically in humid or rainy conditions during fruit maturity."],
        "risks": ["Fusarium wilt", "Gummy stem blight", "Fruit fly"],
    },
    "muskmelon": {
        "display_name": "Muskmelon / Cantaloupe (Kharbuja)",
        "aliases": ["muskmelon", "kharbuja", "cantaloupe", "melon", "kharbuj", "kharbooja"],
        "temp_min": 22, "temp_max": 40, "temp_optimal_min": 25, "temp_optimal_max": 35,
        "rainfall_min_mm": 400, "rainfall_max_mm": 600,
        "soil_scores": {"Black Soil": 11, "Clay Soil": 7, "Sandy Loam": 25, "Red Soil": 18, "Alluvial Soil": 20},
        "season_months": [2, 3, 4, 5, 6],
        "seasons_label": ["Zaid / Summer (Feb–Jun)"],
        "growing_days": 80, "water_requirement": "Low to Moderate",
        "key_facts": ["Requires hot, dry conditions for optimal sugar concentration in fruits.", "Sandy loam soils near river beds produce the sweetest melons.", "Fruit quality declines dramatically in humid or rainy weather during maturation."],
        "risks": ["Downy mildew", "Powdery mildew", "Aphid-transmitted mosaic viruses"],
    },
    "carrot": {
        "display_name": "Carrot (Gajar)",
        "aliases": ["carrot", "gajar", "carrots"],
        "temp_min": 8, "temp_max": 28, "temp_optimal_min": 15, "temp_optimal_max": 22,
        "rainfall_min_mm": 600, "rainfall_max_mm": 1000,
        "soil_scores": {"Black Soil": 11, "Clay Soil": 7, "Sandy Loam": 25, "Red Soil": 18, "Alluvial Soil": 22},
        "soil_notes": {"Sandy Loam": "Excellent: loose, deep sandy loam allows straight root development.", "Clay Soil": "Very poor: dense clay causes forked, stunted, and deformed roots — unmarketable."},
        "season_months": [9, 10, 11, 12, 1],
        "seasons_label": ["Rabi (Sep–Jan)"],
        "growing_days": 90, "water_requirement": "Moderate",
        "key_facts": ["Root crop requiring deep, loose, stone-free sandy loam soils for straight roots.", "Punjab, Haryana, and UP are the major producers of orange and red carrots.", "Roots become woody and fibrous in temperatures above 28°C."],
        "risks": ["Alternaria leaf blight", "Cavity spot (calcium deficiency)", "Root knot nematode in sandy soils"],
    },
    "radish": {
        "display_name": "Radish (Mooli)",
        "aliases": ["radish", "mooli", "muli", "mullangi"],
        "temp_min": 5, "temp_max": 25, "temp_optimal_min": 10, "temp_optimal_max": 18,
        "rainfall_min_mm": 500, "rainfall_max_mm": 800,
        "soil_scores": {"Black Soil": 11, "Clay Soil": 7, "Sandy Loam": 25, "Red Soil": 15, "Alluvial Soil": 20},
        "season_months": [10, 11, 12, 1, 2],
        "seasons_label": ["Rabi (Oct–Feb)"],
        "growing_days": 35, "water_requirement": "Low to Moderate",
        "key_facts": ["Extremely short duration (30–40 days) cool season root vegetable.", "Sandy loam soils are essential — clay soils cause forked, pithy roots.", "Hot temperatures above 25°C make roots pithy and excessively pungent."],
        "risks": ["White rust (Albugo candida)", "Soft rot in waterlogged conditions", "Aphids"],
    },
    "beetroot": {
        "display_name": "Beetroot (Chukandar)",
        "aliases": ["beetroot", "beet", "chukandar", "red beet", "beets"],
        "temp_min": 8, "temp_max": 25, "temp_optimal_min": 12, "temp_optimal_max": 20,
        "rainfall_min_mm": 500, "rainfall_max_mm": 800,
        "soil_scores": {"Black Soil": 13, "Clay Soil": 9, "Sandy Loam": 22, "Red Soil": 15, "Alluvial Soil": 20},
        "season_months": [10, 11, 12, 1, 2],
        "seasons_label": ["Rabi (Oct–Feb)"],
        "growing_days": 75, "water_requirement": "Moderate",
        "key_facts": ["Requires cool temperatures for good root development and deep colour.", "Sandy loam soils allow uniform root expansion; clay causes irregular shapes.", "Sensitive to boron deficiency which causes internal cavity (hollow heart)."],
        "risks": ["Cercospora leaf spot", "Boron deficiency in light sandy soils", "Root rot in waterlogged conditions"],
    },
    "peas": {
        "display_name": "Green Peas (Matar)",
        "aliases": ["peas", "matar", "green peas", "garden pea", "mutter", "pea"],
        "temp_min": 5, "temp_max": 22, "temp_optimal_min": 10, "temp_optimal_max": 18,
        "rainfall_min_mm": 400, "rainfall_max_mm": 600,
        "soil_scores": {"Black Soil": 13, "Clay Soil": 11, "Sandy Loam": 22, "Red Soil": 13, "Alluvial Soil": 22},
        "season_months": [10, 11, 12, 1, 2],
        "seasons_label": ["Rabi (Oct–Feb)"],
        "growing_days": 75, "water_requirement": "Low to Moderate",
        "key_facts": ["Strictly cool-season legume; pod set completely fails above 28°C.", "UP, MP, and HP are major producers.", "Short-duration varieties (55–65 days) provide early returns."],
        "risks": ["Powdery mildew (major constraint)", "Fusarium wilt", "Pea stem fly"],
    },
    # ===== FRUITS =====
    "banana": {
        "display_name": "Banana (Kela)",
        "aliases": ["banana", "kela", "kele", "plantain", "kadali", "bananas"],
        "temp_min": 20, "temp_max": 38, "temp_optimal_min": 27, "temp_optimal_max": 32,
        "rainfall_min_mm": 1200, "rainfall_max_mm": 2500,
        "soil_scores": {"Black Soil": 14, "Clay Soil": 20, "Sandy Loam": 9, "Red Soil": 17, "Alluvial Soil": 25},
        "soil_notes": {"Sandy Loam": "Poor: drains water too fast; banana needs consistent soil moisture.", "Alluvial Soil": "Excellent: deep, moist alluvial soils support the high water demand of banana."},
        "season_months": [],
        "seasons_label": ["Year-round (planted any time)"],
        "growing_days": 270, "water_requirement": "Very High",
        "key_facts": ["Frost-intolerant — a single frost event kills the pseudostem completely.", "Requires deep, well-drained, fertile soils with consistent high moisture.", "Maharashtra, AP, and Tamil Nadu are the largest producers."],
        "risks": ["Panama wilt (Fusarium oxysporum) — incurable, devastating", "Sigatoka leaf spot", "Banana bunchy top virus (BBTV)"],
    },
    "mango": {
        "display_name": "Mango (Aam)",
        "aliases": ["mango", "aam", "aaam", "mangoes", "mangifera", "raw mango", "keri"],
        "temp_min": 20, "temp_max": 40, "temp_optimal_min": 24, "temp_optimal_max": 30,
        "rainfall_min_mm": 750, "rainfall_max_mm": 2000,
        "soil_scores": {"Black Soil": 15, "Clay Soil": 13, "Sandy Loam": 20, "Red Soil": 20, "Alluvial Soil": 22},
        "season_months": [],
        "seasons_label": ["Perennial tree; fruiting season Feb–May"],
        "growing_days": 1825, "water_requirement": "Low to Moderate",
        "key_facts": ["Tropical/subtropical perennial fruit tree; requires a dry period before flowering.", "Rain during flowering reduces fruit set significantly — dry Deccan climate is ideal.", "UP, AP, and Bihar produce the most mangoes."],
        "risks": ["Mango hopper (key pest during flowering)", "Anthracnose fruit rot", "Powdery mildew during flowering"],
    },
    "orange": {
        "display_name": "Orange / Nagpur Mandarin (Santra)",
        "aliases": ["orange", "santra", "narangi", "oranges", "nagpur orange", "mandarin", "sweet orange"],
        "temp_min": 15, "temp_max": 35, "temp_optimal_min": 20, "temp_optimal_max": 28,
        "rainfall_min_mm": 750, "rainfall_max_mm": 1200,
        "soil_scores": {"Black Soil": 18, "Clay Soil": 11, "Sandy Loam": 22, "Red Soil": 18, "Alluvial Soil": 20},
        "soil_notes": {"Clay Soil": "Poor: waterlogging kills citrus trees — the number one cause of orchard failure."},
        "season_months": [],
        "seasons_label": ["Perennial; main harvest Nov–Jan"],
        "growing_days": 1095, "water_requirement": "Moderate",
        "key_facts": ["Nagpur mandarin is world-famous; grown in Maharashtra on black cotton soils.", "Requires well-drained soils — waterlogging kills citrus trees rapidly.", "A dry period around flowering is essential for good fruit set."],
        "risks": ["Citrus greening (HLB) — incurable", "Powdery mildew", "Fruit fly", "Phytophthora root rot in heavy soils"],
    },
    "lemon": {
        "display_name": "Lemon / Lime (Nimbu)",
        "aliases": ["lemon", "nimbu", "lime", "nimboo", "limon", "kagzi nimbu"],
        "temp_min": 15, "temp_max": 38, "temp_optimal_min": 20, "temp_optimal_max": 30,
        "rainfall_min_mm": 750, "rainfall_max_mm": 1200,
        "soil_scores": {"Black Soil": 15, "Clay Soil": 9, "Sandy Loam": 22, "Red Soil": 18, "Alluvial Soil": 20},
        "season_months": [],
        "seasons_label": ["Perennial; fruits year-round in warm climates"],
        "growing_days": 1095, "water_requirement": "Moderate",
        "key_facts": ["More drought-tolerant than sweet orange; can produce multiple crops per year.", "AP, Tamil Nadu, and Maharashtra are the major producers.", "Very sensitive to waterlogging — raised beds in heavy soil areas are essential."],
        "risks": ["Phytophthora root rot", "Citrus tristeza virus (CTV)", "Citrus greening (HLB)"],
    },
    "guava": {
        "display_name": "Guava (Amrood)",
        "aliases": ["guava", "amrood", "amrud", "peru", "jambu batu"],
        "temp_min": 15, "temp_max": 38, "temp_optimal_min": 22, "temp_optimal_max": 28,
        "rainfall_min_mm": 1000, "rainfall_max_mm": 2000,
        "soil_scores": {"Black Soil": 15, "Clay Soil": 13, "Sandy Loam": 22, "Red Soil": 18, "Alluvial Soil": 22},
        "season_months": [],
        "seasons_label": ["Perennial; two main harvests (Aug–Sep and Feb–Mar)"],
        "growing_days": 730, "water_requirement": "Low to Moderate",
        "key_facts": ["One of the hardiest fruit crops — grows in a wide range of soils and climates.", "Allahabad Safeda (UP) is the most famous variety, grown on alluvial soils.", "Two crops per year in most Indian conditions."],
        "risks": ["Fruit fly", "Wilt (Fusarium) — devastating", "Algal leaf spot", "Mealybugs"],
    },
    "papaya": {
        "display_name": "Papaya (Papita)",
        "aliases": ["papaya", "papita", "pawpaw", "papaw"],
        "temp_min": 22, "temp_max": 38, "temp_optimal_min": 25, "temp_optimal_max": 32,
        "rainfall_min_mm": 1000, "rainfall_max_mm": 2000,
        "soil_scores": {"Black Soil": 13, "Clay Soil": 8, "Sandy Loam": 24, "Red Soil": 18, "Alluvial Soil": 22},
        "soil_notes": {"Clay Soil": "Very poor: waterlogging causes crown rot and stem death within 48 hours."},
        "season_months": [],
        "seasons_label": ["Year-round (planted Feb–Mar or Jun–Jul)"],
        "growing_days": 270, "water_requirement": "Moderate",
        "key_facts": ["Extremely frost-sensitive — a single frost kills the plant.", "Well-drained light sandy loam soils are essential; waterlogging is fatal within 48 hours.", "Quick-fruiting — can produce fruit in 9–10 months from planting."],
        "risks": ["Papaya ring spot virus (PRSV) — devastating, no cure", "Phytophthora fruit rot", "Whitefly infestations"],
    },
    "pomegranate": {
        "display_name": "Pomegranate (Anar)",
        "aliases": ["pomegranate", "anar", "dadam", "punica", "anaar"],
        "temp_min": 15, "temp_max": 42, "temp_optimal_min": 25, "temp_optimal_max": 35,
        "rainfall_min_mm": 500, "rainfall_max_mm": 700,
        "soil_scores": {"Black Soil": 18, "Clay Soil": 13, "Sandy Loam": 22, "Red Soil": 20, "Alluvial Soil": 18},
        "season_months": [],
        "seasons_label": ["Perennial; main crops Feb–Apr and Sep–Nov"],
        "growing_days": 1095, "water_requirement": "Low",
        "key_facts": ["Highly drought and heat-tolerant — one of the best crops for arid and semi-arid India.", "Maharashtra's Solapur region produces the finest Bhagwa pomegranates.", "Requires a dry period before flowering; excessive rain during fruiting causes fruit cracking."],
        "risks": ["Fruit borer (Deudorix isocrates)", "Bacterial blight", "Fruit cracking in high humidity"],
    },
    "coconut": {
        "display_name": "Coconut (Nariyal)",
        "aliases": ["coconut", "nariyal", "narikel", "narel", "cocos nucifera", "naariyal"],
        "temp_min": 22, "temp_max": 37, "temp_optimal_min": 27, "temp_optimal_max": 32,
        "rainfall_min_mm": 1500, "rainfall_max_mm": 2500,
        "soil_scores": {"Black Soil": 11, "Clay Soil": 13, "Sandy Loam": 22, "Red Soil": 18, "Alluvial Soil": 20},
        "season_months": [],
        "seasons_label": ["Perennial tree; planted year-round in tropics"],
        "growing_days": 2190, "water_requirement": "High",
        "key_facts": ["Strictly a coastal tropical crop — cannot survive cold winters or frost.", "Kerala, Karnataka coastal belt, and Tamil Nadu produce most of India's coconuts.", "Sandy coastal soils with high groundwater table and good drainage are ideal."],
        "risks": ["Red palm weevil (devastating)", "Root wilt disease (phytoplasma)", "Eriophyid mite causing nut scarring"],
    },
    "grapes": {
        "display_name": "Grapes (Angoor)",
        "aliases": ["grapes", "angoor", "angur", "grape", "vitis vinifera", "vitis", "angoor"],
        "temp_min": 15, "temp_max": 38, "temp_optimal_min": 20, "temp_optimal_max": 30,
        "rainfall_min_mm": 700, "rainfall_max_mm": 900,
        "soil_scores": {"Black Soil": 15, "Clay Soil": 9, "Sandy Loam": 24, "Red Soil": 18, "Alluvial Soil": 20},
        "soil_notes": {"Sandy Loam": "Excellent: deep sandy loam with excellent drainage is the Nashik vineyard standard."},
        "season_months": [10, 11, 12, 1, 2, 3],
        "seasons_label": ["Pruning Oct–Nov; Harvest Feb–Apr"],
        "growing_days": 150, "water_requirement": "Moderate",
        "key_facts": ["Maharashtra's Nashik and Sangli districts produce 75% of India's grapes.", "Deep, well-drained sandy loam soils are essential for vine root development.", "Grapes require a distinct dry period for berry maturation; humidity causes severe fungal diseases."],
        "risks": ["Downy mildew (severe in humid conditions) — most serious", "Powdery mildew", "Anthracnose", "Grape berry moth"],
    },
    "apple": {
        "display_name": "Apple (Seb)",
        "aliases": ["apple", "seb", "apples", "malus domestica", "seb apple"],
        "temp_min": 0, "temp_max": 22, "temp_optimal_min": 10, "temp_optimal_max": 18,
        "rainfall_min_mm": 600, "rainfall_max_mm": 900,
        "soil_scores": {"Black Soil": 9, "Clay Soil": 11, "Sandy Loam": 20, "Red Soil": 11, "Alluvial Soil": 18},
        "season_months": [4, 5, 6, 7, 8, 9],
        "seasons_label": ["Summer in hills (Apr–Sep)"],
        "growing_days": 150, "water_requirement": "Moderate",
        "key_facts": ["Requires 1000–1500 chilling hours (below 7°C) during winter for dormancy break and fruiting.", "Completely unsuitable for tropical plains of India — needs temperate/high altitude zones.", "Himachal Pradesh, J&K, and Uttarakhand are the only viable commercial zones in India."],
        "risks": ["Apple scab (Venturia inaequalis)", "Fire blight (bacterial — devastating)", "Codling moth", "Premature fruit drop in warm winters"],
    },
    "strawberry": {
        "display_name": "Strawberry",
        "aliases": ["strawberry", "strawberries"],
        "temp_min": 5, "temp_max": 28, "temp_optimal_min": 12, "temp_optimal_max": 20,
        "rainfall_min_mm": 700, "rainfall_max_mm": 1200,
        "soil_scores": {"Black Soil": 11, "Clay Soil": 9, "Sandy Loam": 24, "Red Soil": 15, "Alluvial Soil": 20},
        "season_months": [9, 10, 11, 12, 1, 2, 3],
        "seasons_label": ["Rabi (Sep–Mar) in plains; Summer in hills"],
        "growing_days": 120, "water_requirement": "Moderate",
        "key_facts": ["Cool-season crop; stress and poor fruit quality occur above 30°C.", "Sandy loam soils with high organic matter and good drainage are critical.", "Mahabaleshwar (MH), HP, and Punjab are the main growing zones in India."],
        "risks": ["Botrytis fruit rot (gray mold) — major issue in humid weather", "Powdery mildew", "Root rot in heavy soils"],
    },
    "pineapple": {
        "display_name": "Pineapple (Ananas)",
        "aliases": ["pineapple", "ananas", "ananaas"],
        "temp_min": 20, "temp_max": 35, "temp_optimal_min": 23, "temp_optimal_max": 28,
        "rainfall_min_mm": 1000, "rainfall_max_mm": 1500,
        "soil_scores": {"Black Soil": 11, "Clay Soil": 9, "Sandy Loam": 22, "Red Soil": 24, "Alluvial Soil": 15},
        "soil_notes": {"Red Soil": "Excellent: laterite/red soils of Kerala and NE India are the ideal pineapple medium."},
        "season_months": [],
        "seasons_label": ["Year-round in tropical zones"],
        "growing_days": 540, "water_requirement": "Moderate",
        "key_facts": ["Requires acidic, well-drained laterite soils and warm humid tropical climate.", "Kerala, West Bengal (Darjeeling foothills), and Assam are the major states.", "Cannot survive temperatures below 10°C or frost."],
        "risks": ["Heart rot (Phytophthora)", "Mealybug wilt (virus)", "Nematodes"],
    },
    "avocado": {
        "display_name": "Avocado (Butter Fruit)",
        "aliases": ["avocado", "butter fruit", "makhanphal"],
        "temp_min": 18, "temp_max": 30, "temp_optimal_min": 22, "temp_optimal_max": 28,
        "rainfall_min_mm": 1000, "rainfall_max_mm": 2000,
        "soil_scores": {"Black Soil": 13, "Clay Soil": 7, "Sandy Loam": 22, "Red Soil": 20, "Alluvial Soil": 18},
        "soil_notes": {"Clay Soil": "Very poor: avocado is one of the most waterlogging-sensitive trees — dies within days of root saturation."},
        "season_months": [],
        "seasons_label": ["Perennial; harvest Apr–Sep depending on variety"],
        "growing_days": 1460, "water_requirement": "Moderate",
        "key_facts": ["One of the most waterlogging-sensitive tree crops — dies within days of root saturation.", "Kerala, Karnataka, and Tamil Nadu's hilly Western Ghats are the natural growing zones.", "Well-drained, deep soils mandatory; Phytophthora root rot in clay soils is catastrophic."],
        "risks": ["Phytophthora root rot (most devastating disease)", "Anthracnose fruit rot", "Avocado thrips"],
    },
    "dragon_fruit": {
        "display_name": "Dragon Fruit (Pitaya)",
        "aliases": ["dragon fruit", "pitaya", "pitahaya", "red pitaya", "dragonfruit"],
        "temp_min": 20, "temp_max": 40, "temp_optimal_min": 25, "temp_optimal_max": 32,
        "rainfall_min_mm": 400, "rainfall_max_mm": 1000,
        "soil_scores": {"Black Soil": 13, "Clay Soil": 7, "Sandy Loam": 25, "Red Soil": 20, "Alluvial Soil": 15},
        "soil_notes": {"Sandy Loam": "Excellent: cactus-type plant requiring maximum drainage — sandy loam is perfect.", "Clay Soil": "Very poor: standing water kills dragon fruit plants within days."},
        "season_months": [],
        "seasons_label": ["Year-round; main fruiting Jun–Dec"],
        "growing_days": 730, "water_requirement": "Low",
        "key_facts": ["A cactus-type plant — loves heat and drought, extremely sensitive to waterlogging.", "Sandy loam soils with excellent drainage are mandatory.", "Rapidly expanding in AP, Telangana, Gujarat as a high-value, low-water crop."],
        "risks": ["Bacterial soft rot in waterlogged conditions", "Stem rot", "Mealybugs"],
    },
    "jackfruit": {
        "display_name": "Jackfruit (Kathal)",
        "aliases": ["jackfruit", "kathal", "jack fruit", "artocarpus", "chakka"],
        "temp_min": 22, "temp_max": 38, "temp_optimal_min": 25, "temp_optimal_max": 32,
        "rainfall_min_mm": 1500, "rainfall_max_mm": 2500,
        "soil_scores": {"Black Soil": 13, "Clay Soil": 11, "Sandy Loam": 20, "Red Soil": 20, "Alluvial Soil": 22},
        "season_months": [],
        "seasons_label": ["Perennial; fruits Mar–Jun"],
        "growing_days": 1825, "water_requirement": "Moderate to High",
        "key_facts": ["Tropical perennial tree; one of the most productive food trees in the world by weight.", "Kerala, Tamil Nadu, and West Bengal are the largest producers.", "Cannot tolerate frost or temperatures below 8°C."],
        "risks": ["Fruit rot (Rhizopus)", "Bark borer", "Mealybug"],
    },
    # ===== SPICES & HERBS =====
    "turmeric": {
        "display_name": "Turmeric (Haldi)",
        "aliases": ["turmeric", "haldi", "haldee", "curcuma", "haldhi"],
        "temp_min": 20, "temp_max": 35, "temp_optimal_min": 25, "temp_optimal_max": 32,
        "rainfall_min_mm": 1200, "rainfall_max_mm": 1800,
        "soil_scores": {"Black Soil": 13, "Clay Soil": 11, "Sandy Loam": 22, "Red Soil": 18, "Alluvial Soil": 22},
        "season_months": [4, 5, 6, 7, 8, 9, 10, 11, 12],
        "seasons_label": ["Kharif (planted Apr–May; harvested Jan–Feb)"],
        "growing_days": 270, "water_requirement": "High",
        "key_facts": ["Telangana and AP produce about 80% of India's turmeric.", "Rhizomes need well-aerated soils for expansion; clay soils reduce yield.", "Very water-demanding — requires 1500mm rainfall or 25+ irrigations."],
        "risks": ["Rhizome rot (Pythium) — devastating in wet soils", "Leaf blotch", "Nematodes in sandy soils"],
    },
    "ginger": {
        "display_name": "Ginger (Adrak / Sonth)",
        "aliases": ["ginger", "adrak", "sonth", "adrakh", "zingiber", "sonth powder"],
        "temp_min": 20, "temp_max": 35, "temp_optimal_min": 25, "temp_optimal_max": 30,
        "rainfall_min_mm": 1500, "rainfall_max_mm": 3000,
        "soil_scores": {"Black Soil": 9, "Clay Soil": 9, "Sandy Loam": 24, "Red Soil": 20, "Alluvial Soil": 22},
        "soil_notes": {"Clay Soil": "Very poor: hard clay causes rhizome diseases and extremely poor drainage.", "Sandy Loam": "Excellent: well-drained sandy loam prevents rhizome rot."},
        "season_months": [4, 5, 6, 7, 8, 9, 10, 11, 12],
        "seasons_label": ["Kharif (planted Apr–May; harvested Nov–Dec)"],
        "growing_days": 240, "water_requirement": "Very High",
        "key_facts": ["Requires warm temperatures, abundant moisture, and partial shade for best yield.", "Kerala, Meghalaya, and Odisha are the main producers.", "Heavy clay soils cause devastating rhizome diseases."],
        "risks": ["Soft rot / rhizome rot (Pythium aphanidermatum) — the most destructive", "Bacterial wilt", "Nematodes"],
    },
    "cardamom": {
        "display_name": "Cardamom (Elaichi)",
        "aliases": ["cardamom", "elaichi", "elachi", "cardamon", "elettaria"],
        "temp_min": 18, "temp_max": 30, "temp_optimal_min": 20, "temp_optimal_max": 25,
        "rainfall_min_mm": 1500, "rainfall_max_mm": 4000,
        "soil_scores": {"Black Soil": 7, "Clay Soil": 11, "Sandy Loam": 18, "Red Soil": 20, "Alluvial Soil": 13},
        "season_months": [],
        "seasons_label": ["Perennial; grown in humid tropical hill forests"],
        "growing_days": 1095, "water_requirement": "Very High",
        "key_facts": ["Exclusively grown in the moist forests of Kerala, Karnataka, and Tamil Nadu's Western Ghats.", "Requires shade — cannot grow in direct full sunlight.", "Very high altitude (600–1500m), cool temperatures, and heavy rainfall are mandatory."],
        "risks": ["Katte disease (viral — devastating, no cure)", "Capsule borer", "Rhizome rot in waterlogged soils"],
    },
    "black_pepper": {
        "display_name": "Black Pepper (Kali Mirch)",
        "aliases": ["black pepper", "kali mirch", "pepper", "piper nigrum", "kalimirchi"],
        "temp_min": 20, "temp_max": 35, "temp_optimal_min": 25, "temp_optimal_max": 30,
        "rainfall_min_mm": 2000, "rainfall_max_mm": 4000,
        "soil_scores": {"Black Soil": 7, "Clay Soil": 11, "Sandy Loam": 15, "Red Soil": 22, "Alluvial Soil": 13},
        "soil_notes": {"Red Soil": "Good: laterite soils of Kerala's Western Ghats are the traditional medium."},
        "season_months": [],
        "seasons_label": ["Perennial vine; harvested Nov–Jan"],
        "growing_days": 1095, "water_requirement": "Very High",
        "key_facts": ["Kerala produces 95% of India's black pepper exclusively on the humid Western Ghats.", "Requires a live support tree and very high annual rainfall.", "Cannot tolerate drought or dry conditions for more than a few weeks."],
        "risks": ["Phytophthora foot rot (quick wilt) — most devastating disease in pepper history", "Pollu beetle", "Stunt disease"],
    },
    "coriander": {
        "display_name": "Coriander (Dhaniya / Cilantro)",
        "aliases": ["coriander", "dhaniya", "dhania", "cilantro", "coriandrum", "dhaniya seeds"],
        "temp_min": 8, "temp_max": 28, "temp_optimal_min": 15, "temp_optimal_max": 25,
        "rainfall_min_mm": 300, "rainfall_max_mm": 600,
        "soil_scores": {"Black Soil": 15, "Clay Soil": 11, "Sandy Loam": 22, "Red Soil": 15, "Alluvial Soil": 20},
        "season_months": [10, 11, 12, 1, 2],
        "seasons_label": ["Rabi (Oct–Feb)"],
        "growing_days": 60, "water_requirement": "Low",
        "key_facts": ["Rajasthan is the largest producer of dry coriander seeds.", "Cool, dry weather during grain filling gives the best quality seeds.", "Very drought-tolerant; 3–4 irrigations are sufficient."],
        "risks": ["Powdery mildew", "Wilt (Fusarium)", "Aphids in cool weather"],
    },
    "fenugreek": {
        "display_name": "Fenugreek (Methi)",
        "aliases": ["fenugreek", "methi", "methee", "trigonella", "methi seeds"],
        "temp_min": 10, "temp_max": 30, "temp_optimal_min": 15, "temp_optimal_max": 25,
        "rainfall_min_mm": 250, "rainfall_max_mm": 500,
        "soil_scores": {"Black Soil": 15, "Clay Soil": 11, "Sandy Loam": 22, "Red Soil": 15, "Alluvial Soil": 20},
        "season_months": [10, 11, 12, 1, 2],
        "seasons_label": ["Rabi (Oct–Feb)"],
        "growing_days": 55, "water_requirement": "Low",
        "key_facts": ["Very drought-tolerant cool-season herb; Rajasthan and Gujarat are the largest producers.", "Can grow on relatively poor soils; tolerates slightly alkaline conditions.", "Dual purpose — used as a leafy vegetable and as a seed spice."],
        "risks": ["Powdery mildew", "Root rot in waterlogged conditions", "Alternaria leaf spot"],
    },
    "cumin": {
        "display_name": "Cumin (Jeera)",
        "aliases": ["cumin", "jeera", "jira", "zeera", "cuminum", "jeer"],
        "temp_min": 8, "temp_max": 30, "temp_optimal_min": 15, "temp_optimal_max": 25,
        "rainfall_min_mm": 250, "rainfall_max_mm": 500,
        "soil_scores": {"Black Soil": 13, "Clay Soil": 9, "Sandy Loam": 24, "Red Soil": 15, "Alluvial Soil": 18},
        "season_months": [10, 11, 12, 1, 2],
        "seasons_label": ["Rabi (Oct–Mar)"],
        "growing_days": 90, "water_requirement": "Very Low",
        "key_facts": ["Rajasthan and Gujarat together produce 90% of India's cumin (jeera).", "Extremely drought-tolerant; only 2–3 irrigations needed for a full crop.", "Rain or humidity during pod filling completely destroys the crop."],
        "risks": ["Alternaria blight (major — devastating at pod filling)", "Powdery mildew", "Aphids"],
    },
    "fennel": {
        "display_name": "Fennel (Saunf)",
        "aliases": ["fennel", "saunf", "soanf", "foeniculum", "sweet fennel"],
        "temp_min": 8, "temp_max": 28, "temp_optimal_min": 15, "temp_optimal_max": 22,
        "rainfall_min_mm": 300, "rainfall_max_mm": 600,
        "soil_scores": {"Black Soil": 13, "Clay Soil": 11, "Sandy Loam": 22, "Red Soil": 15, "Alluvial Soil": 20},
        "season_months": [10, 11, 12, 1, 2, 3],
        "seasons_label": ["Rabi (Oct–Mar)"],
        "growing_days": 175, "water_requirement": "Low to Moderate",
        "key_facts": ["Gujarat is the largest producer of fennel seeds in India.", "Long-duration crop (170–180 days) requiring stable cool conditions through winter.", "Sensitive to high humidity during flowering and seed development."],
        "risks": ["Powdery mildew", "Aphids", "Bihar hairy caterpillar (Spilosoma obliqua)"],
    },
    # ===== OTHERS =====
    "moringa": {
        "display_name": "Moringa / Drumstick (Sahajan)",
        "aliases": ["moringa", "drumstick", "sahajan", "sahanjana", "murunga", "moringa oleifera", "drumstick tree"],
        "temp_min": 22, "temp_max": 40, "temp_optimal_min": 28, "temp_optimal_max": 35,
        "rainfall_min_mm": 500, "rainfall_max_mm": 2000,
        "soil_scores": {"Black Soil": 15, "Clay Soil": 9, "Sandy Loam": 24, "Red Soil": 20, "Alluvial Soil": 20},
        "soil_notes": {"Sandy Loam": "Excellent: any well-drained soil including poor sandy soils; moringa hates waterlogging."},
        "season_months": [],
        "seasons_label": ["Year-round (perennial in warm climates)"],
        "growing_days": 365, "water_requirement": "Low",
        "key_facts": ["Extremely drought-tolerant multipurpose tree — one of the most nutritious plants.", "Grows in any well-drained soil; only concern is waterlogging.", "AP and Tamil Nadu are the largest producers of drumstick pods."],
        "risks": ["Root rot in waterlogged soils", "Termite attack on stem base", "Leaf eating caterpillars"],
    },
    "aloe_vera": {
        "display_name": "Aloe Vera (Gwarpatha)",
        "aliases": ["aloe vera", "aloe", "gwarpatha", "ghritkumari", "gwar patha", "aloevera"],
        "temp_min": 18, "temp_max": 40, "temp_optimal_min": 25, "temp_optimal_max": 35,
        "rainfall_min_mm": 300, "rainfall_max_mm": 700,
        "soil_scores": {"Black Soil": 13, "Clay Soil": 7, "Sandy Loam": 25, "Red Soil": 20, "Alluvial Soil": 15},
        "soil_notes": {"Sandy Loam": "Excellent: succulent plant adapted to hot, dry sandy conditions.", "Clay Soil": "Very poor: waterlogging is fatal for aloe vera."},
        "season_months": [],
        "seasons_label": ["Year-round; planted Feb–Mar or Sep–Oct"],
        "growing_days": 365, "water_requirement": "Very Low",
        "key_facts": ["Succulent plant adapted to hot, dry desert conditions.", "Sandy loam soils with very high drainage are ideal.", "Rajasthan and Gujarat are the primary commercial producers."],
        "risks": ["Root rot in heavy/waterlogged soils", "Scale insects", "Leaf rot in humid conditions"],
    },
    "sweet_potato": {
        "display_name": "Sweet Potato (Shakarkandi)",
        "aliases": ["sweet potato", "shakarkandi", "shakarkand", "ipomoea batatas", "sweet potatoes"],
        "temp_min": 18, "temp_max": 35, "temp_optimal_min": 22, "temp_optimal_max": 28,
        "rainfall_min_mm": 750, "rainfall_max_mm": 1500,
        "soil_scores": {"Black Soil": 13, "Clay Soil": 7, "Sandy Loam": 25, "Red Soil": 18, "Alluvial Soil": 20},
        "soil_notes": {"Sandy Loam": "Excellent: loose sandy loam allows full tuber development underground.", "Clay Soil": "Very poor: dense clay restricts tuber growth completely."},
        "season_months": [6, 7, 8, 9, 10, 11],
        "seasons_label": ["Kharif (Jun–Nov)"],
        "growing_days": 120, "water_requirement": "Moderate",
        "key_facts": ["Odisha and West Bengal are the largest producers in India.", "Requires loose, sandy loam soils for tuber development.", "More drought-tolerant than regular potato once established."],
        "risks": ["Weevil (Cylas formicarius — most serious pest, can destroy entire crop)", "Alternaria leaf blight", "Root knot nematode"],
    },
    "linseed": {
        "display_name": "Linseed / Flaxseed (Alsi)",
        "aliases": ["linseed", "flaxseed", "flax", "alsi", "linum usitatissimum"],
        "temp_min": 5, "temp_max": 25, "temp_optimal_min": 10, "temp_optimal_max": 18,
        "rainfall_min_mm": 350, "rainfall_max_mm": 650,
        "soil_scores": {"Black Soil": 18, "Clay Soil": 13, "Sandy Loam": 18, "Red Soil": 13, "Alluvial Soil": 20},
        "season_months": [10, 11, 12, 1, 2],
        "seasons_label": ["Rabi (Oct–Feb)"],
        "growing_days": 120, "water_requirement": "Low",
        "key_facts": ["Cool-season oilseed crop; UP, MP, and Bihar are the largest producers.", "Oil content drops significantly above 28°C during grain filling.", "Can grow on relatively poor soils with minimal inputs."],
        "risks": ["Powdery mildew", "Rust (Melampsora lini)", "Alternaria blight"],
    },
    "ridge_gourd": {
        "display_name": "Ridge Gourd (Turai / Torai)",
        "aliases": ["ridge gourd", "turai", "torai", "tori", "ribbed gourd", "luffa acutangula"],
        "temp_min": 20, "temp_max": 38, "temp_optimal_min": 25, "temp_optimal_max": 32,
        "rainfall_min_mm": 600, "rainfall_max_mm": 1200,
        "soil_scores": {"Black Soil": 13, "Clay Soil": 11, "Sandy Loam": 22, "Red Soil": 15, "Alluvial Soil": 22},
        "season_months": [2, 3, 4, 5, 6, 7, 8, 9, 10],
        "seasons_label": ["Summer (Feb–May)", "Kharif (Jun–Oct)"],
        "growing_days": 65, "water_requirement": "Moderate",
        "key_facts": ["Warm-season vine crop adaptable to most tropical regions of India.", "Sandy loam to loamy soils with rich organic matter give maximum fruit yield.", "Short crop cycle (60–70 days) allows quick returns."],
        "risks": ["Powdery mildew", "Downy mildew", "Fruit fly"],
    },
    "asparagus": {
        "display_name": "Asparagus (Shatavari)",
        "aliases": ["asparagus", "shatavari", "shatavar"],
        "temp_min": 8, "temp_max": 30, "temp_optimal_min": 15, "temp_optimal_max": 22,
        "rainfall_min_mm": 600, "rainfall_max_mm": 1200,
        "soil_scores": {"Black Soil": 11, "Clay Soil": 7, "Sandy Loam": 24, "Red Soil": 13, "Alluvial Soil": 20},
        "season_months": [2, 3, 4, 9, 10, 11],
        "seasons_label": ["Spring (Feb–Apr)", "Autumn (Sep–Nov)"],
        "growing_days": 730, "water_requirement": "Moderate",
        "key_facts": ["Perennial crop; requires 2–3 years before first commercial harvest.", "Deep, well-drained sandy loam soils essential for fern root development.", "HP, Uttarakhand, and Nilgiris are the viable growing zones in India."],
        "risks": ["Asparagus beetle", "Fusarium crown and root rot", "Rust"],
    },
    "broccoli": {
        "display_name": "Broccoli",
        "aliases": ["broccoli", "hari gobhi", "italian cauliflower"],
        "temp_min": 5, "temp_max": 25, "temp_optimal_min": 10, "temp_optimal_max": 18,
        "rainfall_min_mm": 600, "rainfall_max_mm": 1000,
        "soil_scores": {"Black Soil": 11, "Clay Soil": 11, "Sandy Loam": 18, "Red Soil": 11, "Alluvial Soil": 22},
        "season_months": [9, 10, 11, 12, 1, 2],
        "seasons_label": ["Rabi (Sep–Feb) in plains; Summer in hills"],
        "growing_days": 80, "water_requirement": "Moderate",
        "key_facts": ["Cool-season brassica; head formation fails above 25°C.", "Well-drained, fertile soils rich in organic matter give the best quality heads.", "Gaining popularity as a premium vegetable in Punjab, HP, and Maharashtra."],
        "risks": ["Diamond back moth", "Club root in acidic soils", "Black rot disease"],
    },
}
