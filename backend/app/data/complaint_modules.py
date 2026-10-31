"""
data/complaint_modules.py
-------------------------
Maps the patient's free-text reason for visit to symptom modules.

The adaptive interview asks generic questions (onset, duration, severity,
course, triggers) for every complaint, and adds the questions of each module
whose keywords appear in the patient's own words. A question in
question_bank.json opts into a module with
  {"show_if": {"question_key": "chief_complaint", "module": "<name>"}}
or out of one with "not_module".

Keywords cover English, common transliterated Hindi/Marathi and Devanagari.
Latin keywords match at a word start ("cough" matches "coughing"); Devanagari
keywords match anywhere. Matching is deterministic and case-insensitive.
"""
import re
from typing import Dict, List, Set

COMPLAINT_MODULES: Dict[str, List[str]] = {
    "pain": [
        "pain", "ache", "aching", "hurt", "sore", "cramp", "burning", "tender", "sting",
        "headache", "migraine", "toothache", "stomachache", "stomach ache", "backache", "earache",
        "dard", "dukh", "दर्द", "दुख", "वेदना", "दुखणे", "दुखत", "कळ", "जलन", "जळजळ",
    ],
    "chest": [
        "chest", "heart", "palpitat", "breathless", "short of breath", "shortness of breath",
        "seena", "chhati", "सीने", "सीना", "छाती", "धड़कन", "धडधड", "छातीत", "दम लाग",
    ],
    "respiratory": [
        "cough", "breath", "wheez", "phlegm", "sputum", "cold", "throat", "sneez", "congest",
        "runny nose", "khansi", "khokla", "खांसी", "खाँसी", "सांस", "साँस", "गला", "सर्दी",
        "खोकला", "श्वास", "घसा", "कफ", "बलगम",
    ],
    "fever": [
        "fever", "temperature", "chill", "shiver", "bukhar", "taap", "बुखार", "ताप", "थंडी",
        "कंपकंपी", "ठंड लग",
    ],
    "gi": [
        "stomach", "abdomen", "abdominal", "belly", "vomit", "nausea", "diarrh", "loose motion",
        "loose stool", "constipat", "acidity", "indigestion", "heartburn", "jaundice", "pet dard",
        "पेट", "उल्टी", "दस्त", "कब्ज", "एसिडिटी", "पोट", "उलटी", "जुलाब", "मळमळ", "अपचन",
        "बद्धकोष्ठ", "पीलिया", "कावीळ",
    ],
    "neuro": [
        "headache", "head ache", "head", "migraine", "dizz", "giddi", "vertigo", "faint", "numb",
        "tingl", "weakness", "seizure", "convuls", "paralys", "blurred", "vision", "sir dard",
        "सिर", "चक्कर", "बेहोश", "सुन्न", "कमजोरी", "डोके", "डोकं", "अशक्त", "मुंग्या", "झटका",
        "धूसर",
    ],
    "urinary": [
        "urin", "pee", "bladder", "kidney", "peshab", "pishab", "laghvi", "पेशाब", "मूत्र",
        "लघवी", "किडनी", "मूत्रपिंड",
    ],
    "skin": [
        "rash", "itch", "skin", "pimple", "acne", "blister", "wound", "boil", "hives", "allergic",
        "khujli", "खुजली", "त्वचा", "दाने", "चकत्ते", "खाज", "पुरळ", "फोड", "जखम",
    ],
    "injury": [
        "injur", "fall", "fell", "fracture", "sprain", "twist", "accident", "joint", "knee",
        "shoulder", "back", "neck", "swelling", "swollen", "chot", "चोट", "गिर", "जोड़", "घुटन",
        "कमर", "दुखापत", "पडल", "सांधे", "गुडघ", "कंबर", "सूज",
    ],
    "mental": [
        "stress", "anxi", "worr", "sad", "depress", "sleep", "insomnia", "tension", "panic",
        "mood", "तनाव", "चिंता", "नींद", "उदास", "घबराहट", "ताण", "झोप", "काळजी", "नैराश्य",
    ],
    "womens_health": [
        "period", "menstru", "pregnan", "vaginal", "white discharge", "pcod", "pcos", "masik",
        "मासिक", "गर्भ", "पाळी", "गरोदर",
    ],
}

_LATIN = re.compile(r"[a-z]")


def match_modules(text: str) -> Set[str]:
    """Return the modules whose keywords appear in the free-text complaint."""
    if not text:
        return set()
    low = text.lower()
    found: Set[str] = set()
    for module, keywords in COMPLAINT_MODULES.items():
        for kw in keywords:
            if _LATIN.match(kw):
                if re.search(rf"(?<![a-z]){re.escape(kw)}", low):
                    found.add(module)
                    break
            elif kw in text:
                found.add(module)
                break
    return found
