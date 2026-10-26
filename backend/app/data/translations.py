"""
translations.py
---------------
Canonical localized question texts, prompts, choices, and speech parsing rules
for English, Hindi (हिंदी), and Marathi (मराठी) (Milestone M12 / FR-12).
"""

from typing import Dict, Any, List, Optional, Tuple

SUPPORTED_LANGUAGES = [
    {
        "code": "en",
        "name": "English",
        "native_name": "English",
        "locale": "en-IN",
        "tts_voice": "en-IN",
        "status": "verified",
    },
    {
        "code": "hi",
        "name": "Hindi",
        "native_name": "हिंदी",
        "locale": "hi-IN",
        "tts_voice": "hi-IN",
        "status": "verified",
    },
    {
        "code": "mr",
        "name": "Marathi",
        "native_name": "मराठी",
        "locale": "mr-IN",
        "tts_voice": "mr-IN",
        "status": "verified",
    },
]

# Localized question prompts and choices
QUESTION_TRANSLATIONS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "chief_complaint": {
        "en": {
            "text": "What is troubling you the most today?",
            "help": "Choose the closest match or select Other to describe your symptom.",
            "spoken_prompt": "What is troubling you the most today? You may say headache, abdominal pain, fever, cough, or describe your symptom.",
            "choices": ["Headache", "Abdominal pain", "Chest discomfort", "Fever", "Cough", "Back pain", "Other"],
        },
        "hi": {
            "text": "आज आपको सबसे ज्यादा क्या परेशानी या तकलीफ हो रही है?",
            "help": "सबसे मिलता-जुलता लक्षण चुनें या अपना लक्षण बताएं।",
            "spoken_prompt": "आज आपको सबसे ज्यादा क्या तकलीफ हो रही है? आप सिरदर्द, पेट दर्द, बुखार या खांसी बता सकते हैं।",
            "choices": ["सिरदर्द (Headache)", "पेट दर्द (Abdominal pain)", "सीने में बेचैनी (Chest discomfort)", "बुखार (Fever)", "खांसी (Cough)", "पीठ दर्द (Back pain)", "अन्य (Other)"],
        },
        "mr": {
            "text": "आज तुम्हाला सर्वात जास्त काय त्रास किंवा समस्या जाणवत आहे?",
            "help": "सर्वात जवळचा पर्याय निवडा किंवा आपले लक्षण सांगा.",
            "spoken_prompt": "आज तुम्हाला सर्वात जास्त काय त्रास होत आहे? आपण डोकेदुखी, पोटदुखी, ताप किंवा खोकला सांगू शकता.",
            "choices": ["डोकेदुखी (Headache)", "पोटदुखी (Abdominal pain)", "छातीत अस्वस्थता (Chest discomfort)", "ताप (Fever)", "खोकला (Cough)", "पाठदुखी (Back pain)", "इतर (Other)"],
        },
    },
    "symptom_duration": {
        "en": {
            "text": "How long have you had this problem?",
            "help": "Approximate duration helps determine acute vs chronic presentation.",
            "spoken_prompt": "How long have you had this problem? For example, less than a day, one to three days, or more than a week.",
            "choices": ["Less than a day", "1 to 3 days", "4 to 7 days", "More than a week", "Months or longer"],
        },
        "hi": {
            "text": "यह समस्या आपको कितने समय से है?",
            "help": "अनुमानित समय से यह समझने में मदद मिलती है कि बीमारी नई है या पुरानी।",
            "spoken_prompt": "यह समस्या आपको कितने समय से है? जैसे एक दिन से कम, एक से तीन दिन, या एक सप्ताह से अधिक।",
            "choices": ["एक दिन से कम (Less than a day)", "1 से 3 दिन (1 to 3 days)", "4 से 7 दिन (4 to 7 days)", "एक सप्ताह से अधिक (More than a week)", "महीनों या उससे अधिक (Months or longer)"],
        },
        "mr": {
            "text": "हा त्रास तुम्हाला किती दिवसांपासून किंवा वेळेपासून आहे?",
            "help": "अंदाजे कालावधीमुळे आजाराचे स्वरूप समजण्यास मदत होते.",
            "spoken_prompt": "हा त्रास तुम्हाला किती दिवसांपासून आहे? उदा. एका दिवसापेक्षा कमी, एक ते तीन दिवस, किंवा आठवड्यापेक्षा जास्त.",
            "choices": ["एका दिवसापेक्षा कमी (Less than a day)", "१ ते ३ दिवस (1 to 3 days)", "४ ते ७ दिवस (4 to 7 days)", "आठवड्यापेक्षा जास्त (More than a week)", "काही महिने किंवा अधिक (Months or longer)"],
        },
    },
    "symptom_severity": {
        "en": {
            "text": "How severe is your discomfort right now?",
            "help": "1 is very mild, 10 is the worst pain imaginable.",
            "spoken_prompt": "On a scale from 1 to 10, how severe is your discomfort right now?",
            "choices": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
        },
        "hi": {
            "text": "इस समय आपकी तकलीफ कितनी गंभीर है?",
            "help": "1 बहुत हल्का है, 10 असहनीय दर्द है।",
            "spoken_prompt": "1 से 10 के पैमाने पर, आपकी तकलीफ कितनी गंभीर है?",
            "choices": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
        },
        "mr": {
            "text": "सध्या तुमचा त्रास किती तीव्र आहे?",
            "help": "१ म्हणजे अगदी सौम्य, १० म्हणजे असह्य वेदना.",
            "spoken_prompt": "१ ते १० च्या प्रमाणात, तुमचा त्रास सध्या किती तीव्र आहे?",
            "choices": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
        },
    },
    "current_medications": {
        "en": {
            "text": "Are you currently taking any prescription medicines, supplements, or regular tablets?",
            "help": "Include blood pressure, diabetes, thyroid, or daily vitamins.",
            "spoken_prompt": "Are you currently taking any prescription medicines, supplements, or regular tablets? You can say yes or no.",
            "choices": ["No, none", "Yes, regularly", "Yes, occasionally"],
        },
        "hi": {
            "text": "क्या आप वर्तमान में कोई नियमित दवाइयां, गोलियां या सप्लीमेंट्स ले रहे हैं?",
            "help": "बीपी, शुगर, थायरॉइड या दैनिक विटामिन शामिल करें।",
            "spoken_prompt": "क्या आप इस समय कोई नियमित दवाइयां या गोलियां ले रहे हैं? आप हां या नहीं कह सकते हैं।",
            "choices": ["नहीं, कोई नहीं (No, none)", "हां, नियमित रूप से (Yes, regularly)", "हां, कभी-कभी (Yes, occasionally)"],
        },
        "mr": {
            "text": "तुम्ही सध्या काही नियमित औषधे, गोळ्या किंवा सप्लिमेंट्स घेत आहात का?",
            "help": "बीपी, मधुमेह, थायरॉईड किंवा नियमित जीवनसत्त्वे यांचा समावेश करा.",
            "spoken_prompt": "तुम्ही सध्या कोणतीही नियमित औषधे किंवा गोळ्या घेत आहात का? हो किंवा नाही सांगा.",
            "choices": ["नाही, काहीही नाही (No, none)", "होय, नियमितपणे (Yes, regularly)", "होय, कधीतरी (Yes, occasionally)"],
        },
    },
    "has_allergies": {
        "en": {
            "text": "Do you have any known allergies to medicines, food, or other substances?",
            "help": "For example penicillin, sulfa, peanuts, contrast dye, dust.",
            "spoken_prompt": "Do you have any known allergies to medicines, food, or other substances? You can say yes or no.",
            "choices": ["No known allergies", "Yes, to medicines", "Yes, to food or other substances", "Not sure"],
        },
        "hi": {
            "text": "क्या आपको किसी दवा, भोजन या अन्य पदार्थ से कोई एलर्जी है?",
            "help": "जैसे पेनिसिलिन, सल्फा, मूंगफली या धूल।",
            "spoken_prompt": "क्या आपको किसी दवा या भोजन से कोई एलर्जी है? आप हां या नहीं कह सकते हैं।",
            "choices": ["कोई ज्ञात एलर्जी नहीं (No known allergies)", "हां, दवाइयों से (Yes, to medicines)", "हां, भोजन या अन्य से (Yes, to food or other)", "पक्का पता नहीं (Not sure)"],
        },
        "mr": {
            "text": "तुम्हाला कोणत्याही औषधाची, अन्नाची किंवा इतर गोष्टीची ॲलर्जी आहे का?",
            "help": "उदा. पेनिसिलिन, शेंगदाणे, धूळ इत्यादी.",
            "spoken_prompt": "तुम्हाला कोणत्याही औषधाची किंवा अन्नाची ॲलर्जी आहे का? हो किंवा नाही सांगा.",
            "choices": ["माहित असलेली ॲलर्जी नाही (No known allergies)", "होय, औषधांची (Yes, to medicines)", "होय, अन्नाची किंवा इतर (Yes, to food or other)", "नक्की सांगता येत नाही (Not sure)"],
        },
    },
    "has_chronic_conditions": {
        "en": {
            "text": "Do you have any long-term or chronic medical conditions?",
            "help": "Hypertension, diabetes, asthma, thyroid disease, or heart conditions.",
            "spoken_prompt": "Do you have any long-term or chronic medical conditions like diabetes or blood pressure?",
            "choices": ["None", "Hypertension (High BP)", "Type 2 Diabetes", "Asthma", "Hypothyroidism", "Heart disease", "Other"],
        },
        "hi": {
            "text": "क्या आपको कोई पुरानी या दीर्घकालिक बीमारी है?",
            "help": "जैसे बीपी, शुगर, अस्थमा, थायरॉइड या हृदय रोग।",
            "spoken_prompt": "क्या आपको कोई पुरानी बीमारी है जैसे शुगर या हाई बीपी?",
            "choices": ["कोई नहीं (None)", "हाई बीपी (High BP)", "डायबिटीज (Type 2 Diabetes)", "अस्थमा (Asthma)", "थायरॉइड (Hypothyroidism)", "हृदय रोग (Heart disease)", "अन्य (Other)"],
        },
        "mr": {
            "text": "तुम्हाला कोणता जुनाट किंवा दीर्घकालीन आजार आहे का?",
            "help": "उदा. रक्तदाब, मधुमेह, दमा, थायरॉईड किंवा हृदयाचा आजार.",
            "spoken_prompt": "तुम्हाला कोणताही जुनाट आजार आहे का जसे की मधुमेह किंवा उच्च रक्तदाब?",
            "choices": ["काहीही नाही (None)", "उच्च रक्तदाब (High BP)", "मधुमेह (Type 2 Diabetes)", "दमा (Asthma)", "थायरॉईड (Hypothyroidism)", "हृदयरोग (Heart disease)", "इतर (Other)"],
        },
    },
    "pain_location": {
        "en": {
            "text": "Where exactly is the pain or discomfort located?",
            "help": "Specific anatomical location provides key clinical context.",
            "spoken_prompt": "Where exactly is the pain or discomfort located?",
            "choices": ["Upper abdomen", "Lower right abdomen", "Lower left abdomen", "Around the navel", "Left chest", "Center chest", "Forehead / temples", "Entire head", "Lower back", "Other location"],
        },
        "hi": {
            "text": "दर्द या तकलीफ शरीर में ठीक किस जगह पर हो रही है?",
            "help": "सटीक जगह बताने से डॉक्टर को जांच में आसानी होती है।",
            "spoken_prompt": "दर्द शरीर में किस जगह पर हो रहा है? जैसे पेट के ऊपरी हिस्से में, सीने में, या सिर में।",
            "choices": ["पेट का ऊपरी हिस्सा (Upper abdomen)", "पेट का निचला दायां हिस्सा (Lower right abdomen)", "पेट का निचला बायां हिस्सा (Lower left abdomen)", "नाभि के आसपास (Around the navel)", "सीने के बाईं ओर (Left chest)", "सीने के बीच में (Center chest)", "माथा / कनपटी (Forehead / temples)", "पूरा सिर (Entire head)", "पीठ का निचला हिस्सा (Lower back)", "अन्य स्थान (Other location)"],
        },
        "mr": {
            "text": "वेदना किंवा त्रास शरीरात नक्की कोणत्या ठिकाणी जाणवत आहे?",
            "help": "नक्की जागा सांगितल्याने डॉक्टरांना तपासणी करणे सोपे होते.",
            "spoken_prompt": "त्रास नक्की कुठे होत आहे? उदा. पोटाच्या वरच्या भागात, छातीत किंवा डोक्यात.",
            "choices": ["पोटाचा वरचा भाग (Upper abdomen)", "पोटाचा उजवा खालचा भाग (Lower right abdomen)", "पोटाचा डावा खालचा भाग (Lower left abdomen)", "बेंबीच्या भोवती (Around the navel)", "छातीचा डावा भाग (Left chest)", "छातीच्या मध्यभागी (Center chest)", "कपाळ / कानशिले (Forehead / temples)", "संपूर्ण डोके (Entire head)", "कमरेचा भाग (Lower back)", "इतर जागा (Other location)"],
        },
    },
    "worse_with_activity": {
        "en": {
            "text": "Does the discomfort increase with physical exertion or activity?",
            "help": "Helps differentiate musculoskeletal and cardiac patterns.",
            "spoken_prompt": "Does the discomfort increase with physical exertion or activity? You can say yes or no.",
            "choices": ["No, unchanged with activity", "Yes, definitely worse with exertion", "Relieved by rest", "Not sure"],
        },
        "hi": {
            "text": "क्या चलने-फिरने या मेहनत का काम करने से तकलीफ बढ़ जाती है?",
            "help": "इससे दर्द का कारण (मांसपेशी या हृदय) समझने में मदद मिलती है।",
            "spoken_prompt": "क्या शारीरिक मेहनत करने से तकलीफ बढ़ती है? आप हां या नहीं कह सकते हैं।",
            "choices": ["नहीं, कोई बदलाव नहीं (No, unchanged)", "हां, मेहनत करने पर बढ़ती है (Yes, definitely worse)", "आराम करने पर राहत मिलती है (Relieved by rest)", "पक्का पता नहीं (Not sure)"],
        },
        "mr": {
            "text": "हालचाल किंवा शारीरिक श्रमाने त्रास अधिक वाढतो का?",
            "help": "यावरून दुखण्याचे अचूक स्वरूप समजण्यास मदत होते.",
            "spoken_prompt": "हालचाल किंवा श्रम केल्याने त्रास वाढतो का? हो किंवा नाही सांगा.",
            "choices": ["नाही, फरक पडत नाही (No, unchanged)", "होय, श्रमाने नक्कीच वाढतो (Yes, definitely worse)", "विश्रांती घेतल्यास बरे वाटते (Relieved by rest)", "नक्की माहित नाही (Not sure)"],
        },
    },
    "symptom_frequency": {
        "en": {
            "text": "How frequently do you experience this symptom?",
            "help": "Temporal frequency distinguishes episodic from continuous complaints.",
            "spoken_prompt": "How frequently do you experience this symptom? Constant, daily, or occasional?",
            "choices": ["Constant / continuous", "Daily episodes", "A few times a week", "Occasional / rare"],
        },
        "hi": {
            "text": "यह तकलीफ आपको कितनी बार महसूस होती है?",
            "help": "लगातार या कभी-कभी होने वाले लक्षणों को समझने के लिए।",
            "spoken_prompt": "यह तकलीफ कितनी बार होती है? लगातार, रोज़ाना या कभी-कभी?",
            "choices": ["लगातार / हर समय (Constant)", "रोज़ाना कुछ समय (Daily episodes)", "हफ्ते में कुछ बार (A few times a week)", "कभी-कभार (Occasional / rare)"],
        },
        "mr": {
            "text": "हा त्रास तुम्हाला किती वेळा किंवा किती अंतराने होतो?",
            "help": "त्रास सतत होतो की अधूनमधून हे समजण्यासाठी.",
            "spoken_prompt": "हा त्रास किती वेळा होतो? सतत, दररोज की कधीतरी?",
            "choices": ["सतत / अखंड (Constant)", "दररोज काही वेळा (Daily episodes)", "आठवड्यातून काही वेळा (A few times a week)", "कधीतरीच (Occasional / rare)"],
        },
    },
    "associated_symptoms": {
        "en": {
            "text": "Do you have any of these additional symptoms along with it?",
            "help": "Select all that apply.",
            "spoken_prompt": "Do you have any symptoms like nausea, vomiting, dizziness, sweating, or breathlessness?",
            "choices": ["Nausea", "Vomiting", "Dizziness / lightheadedness", "Cold sweating", "Shortness of breath", "None of these"],
        },
        "hi": {
            "text": "क्या इसके साथ आपको इनमें से कोई अन्य लक्षण भी महसूस हो रहे हैं?",
            "help": "जो भी लक्षण हों, उन्हें चुनें।",
            "spoken_prompt": "क्या आपको उल्टी, जी मिचलाना, चक्कर, पसीना या सांस फूलने की समस्या भी है?",
            "choices": ["जी मिचलाना (Nausea)", "उल्टी (Vomiting)", "चक्कर आना (Dizziness)", "ठंडा पसीना आना (Cold sweating)", "सांस फूलना (Shortness of breath)", "इनमें से कोई नहीं (None of these)"],
        },
        "mr": {
            "text": "या त्रासासोबत तुम्हाला खालीलपैकी कोणती लक्षणे जाणवत आहेत का?",
            "help": "लागू पडणारे सर्व पर्याय निवडा.",
            "spoken_prompt": "तुम्हाला मळमळ, उलट्या, चक्कर, घाम येणे किंवा धाप लागणे असा त्रास होतोय का?",
            "choices": ["मळमळ (Nausea)", "उलटी (Vomiting)", "चक्कर येणे (Dizziness)", "थंड घाम येणे (Cold sweating)", "धाप लागणे (Shortness of breath)", "यांपैकी काहीही नाही (None of these)"],
        },
    },
    "has_fever": {
        "en": {
            "text": "Have you had a fever or elevated body temperature?",
            "help": "Indicates active infection or inflammatory process.",
            "spoken_prompt": "Have you had a fever or chills? You can say yes or no.",
            "choices": ["No fever", "Yes, mild fever", "Yes, high fever with chills", "Feverish feeling, not measured"],
        },
        "hi": {
            "text": "क्या आपको बुखार या शरीर गर्म होने का अहसास हुआ है?",
            "help": "संक्रमण या सूजन की स्थिति समझने के लिए।",
            "spoken_prompt": "क्या आपको बुखार या ठंड लग रही है? आप हां या नहीं कह सकते हैं।",
            "choices": ["बुखार नहीं है (No fever)", "हां, हल्का बुखार है (Yes, mild fever)", "हां, कंपकंपी के साथ तेज बुखार (High fever with chills)", "बुखार जैसा लग रहा है, नापा नहीं (Feverish feeling)"],
        },
        "mr": {
            "text": "तुम्हाला ताप आला आहे का किंवा अंग गरम वाटते का?",
            "help": "संसर्ग किंवा जंतुसंसर्ग समजण्यास मदत होते.",
            "spoken_prompt": "तुम्हाला ताप किंवा थंडी वाजून येते का? हो किंवा नाही सांगा.",
            "choices": ["ताप नाही (No fever)", "होय, सौम्य ताप आहे (Yes, mild fever)", "होय, भरून येणारा तीव्र ताप (High fever with chills)", "अंग तापल्यासारखे वाटते (Feverish feeling)"],
        },
    },
    "chronic_conditions_detail": {
        "en": {
            "text": "Which chronic conditions have you been diagnosed with?",
            "help": "Select all confirmed past medical diagnoses.",
            "spoken_prompt": "Which chronic conditions do you have? You may mention diabetes, blood pressure, asthma, or thyroid.",
            "choices": ["Hypertension (High BP)", "Type 2 Diabetes", "Asthma", "COPD", "Hypothyroidism", "Coronary artery disease", "Other"],
        },
        "hi": {
            "text": "आपको कौन सी पुरानी या नियमित बीमारियां बताई गई हैं?",
            "help": "डॉक्टर द्वारा बताई गई सभी पुरानी बीमारियां चुनें।",
            "spoken_prompt": "आपको कौन सी पुरानी बीमारियां हैं? जैसे शुगर, बीपी, दमा या थायरॉइड।",
            "choices": ["हाई ब्लड प्रेशर (Hypertension)", "शुगर / डायबिटीज (Type 2 Diabetes)", "दमा / अस्थमा (Asthma)", "सीओपीडी (COPD)", "थायरॉइड (Hypothyroidism)", "दिल की बीमारी (Heart disease)", "अन्य (Other)"],
        },
        "mr": {
            "text": "तुम्हाला कोणते जुनाट आजार असल्याचे डॉक्टरांनी सांगितले आहे?",
            "help": "माहित असलेले सर्व जुनाट आजार निवडा.",
            "spoken_prompt": "तुम्हाला कोणते जुनाट आजार आहेत? उदा. मधुमेह, बीपी किंवा थायरॉईड.",
            "choices": ["उच्च रक्तदाब (High BP)", "मधुमेह (Type 2 Diabetes)", "दमा (Asthma)", "सीओपीडी (COPD)", "थायरॉईड (Hypothyroidism)", "हृदयविकार (Heart disease)", "इतर (Other)"],
        },
    },
    "medication_details": {
        "en": {
            "text": "Which medicines are you taking?",
            "help": "List tablet names, injections, or syrups (e.g., Metformin, Amlodipine).",
            "spoken_prompt": "Which medicines or tablets are you taking regularly?",
            "choices": [],
        },
        "hi": {
            "text": "आप इस समय कौन सी दवाइयां ले रहे हैं?",
            "help": "दवाइयों के नाम लिखें (जैसे मेटफॉर्मिन, एम्लोडिपिन)।",
            "spoken_prompt": "आप रोज़ाना कौन सी दवाइयां या गोलियां लेते हैं?",
            "choices": [],
        },
        "mr": {
            "text": "तुम्ही सध्या कोणती औषधे किंवा गोळ्या घेत आहात?",
            "help": "औषधांची नावे लिहा (उदा. मेटफॉर्मिन, एमलोडिपिन).",
            "spoken_prompt": "तुम्ही नियमितपणे कोणती औषधे किंवा गोळ्या घेता?",
            "choices": [],
        },
    },
    "medication_dosage": {
        "en": {
            "text": "What is the dose, and how often do you take it?",
            "help": "For example: 500 mg twice daily, or 5 mg once in the morning.",
            "spoken_prompt": "What is the dose and how often do you take it?",
            "choices": [],
        },
        "hi": {
            "text": "दवा की मात्रा (डोज़) क्या है, और दिन में कितनी बार लेते हैं?",
            "help": "जैसे: 500 मि.ग्रा. दिन में दो बार, या सुबह एक गोली।",
            "spoken_prompt": "दवा की मात्रा कितनी है और दिन में कितनी बार लेते हैं?",
            "choices": [],
        },
        "mr": {
            "text": "औषधाचा डोस किती आहे आणि दिवसातून किती वेळा घेता?",
            "help": "उदा. ५०० मिग्रॅ दिवसातून दोनदा, किंवा सकाळी एक गोळी.",
            "spoken_prompt": "औषधाचा डोस किती आहे आणि दिवसातून किती वेळा घेता?",
            "choices": [],
        },
    },
    "allergy_details": {
        "en": {
            "text": "What substance or medicine are you allergic to?",
            "help": "For example: Penicillin, Sulfa drugs, Peanuts, Aspirin.",
            "spoken_prompt": "What medicine or substance are you allergic to?",
            "choices": ["Penicillin", "Sulfa drugs", "Aspirin / NSAIDs", "Peanuts", "Dust / Pollen", "Other substance"],
        },
        "hi": {
            "text": "आपको किस दवा, खाने की चीज़ या पदार्थ से एलर्जी है?",
            "help": "जैसे: पेनिसिलिन, सल्फा, एस्पिरिन, मूंगफली या धूल।",
            "spoken_prompt": "आपको किस दवा या चीज़ से एलर्जी है?",
            "choices": ["पेनिसिलिन (Penicillin)", "सल्फा दवाइयां (Sulfa)", "एस्पिरिन / दर्द निवारक (Aspirin)", "मूंगफली (Peanuts)", "धूल / परागकण (Dust/Pollen)", "अन्य पदार्थ (Other)"],
        },
        "mr": {
            "text": "तुम्हाला कोणत्या औषधाची किंवा पदार्थाची ॲलर्जी आहे?",
            "help": "उदा. पेनिसिलिन, सल्फा, ॲस्पिरिन किंवा शेंगदाणे.",
            "spoken_prompt": "तुम्हाला कोणत्या औषधाची किंवा पदार्थाची ॲलर्जी आहे?",
            "choices": ["पेनिसिलिन (Penicillin)", "सल्फा औषधे (Sulfa)", "ॲस्पिरिन / पेनकिलर (Aspirin)", "शेंगदाणे (Peanuts)", "धूळ / परागकण (Dust/Pollen)", "इतर पदार्थ (Other)"],
        },
    },
    "allergy_reaction": {
        "en": {
            "text": "What happens when you are exposed to this allergen?",
            "help": "Helps clinical team differentiate adverse reactions from severe anaphylaxis.",
            "spoken_prompt": "What reaction do you get? Skin rash, facial swelling, or breathing trouble?",
            "choices": ["Skin rash / hives", "Facial or lip swelling", "Difficulty breathing / wheezing", "Stomach upset / nausea", "Severe anaphylaxis", "Not sure"],
        },
        "hi": {
            "text": "उस चीज़ या दवा के संपर्क में आने पर शरीर पर क्या प्रतिक्रिया होती है?",
            "help": "त्वचा पर चकत्ते, सूजन या सांस लेने में परेशानी।",
            "spoken_prompt": "एलर्जी होने पर क्या होता है? खुजली, चेहरे पर सूजन या सांस फूलना?",
            "choices": ["त्वचा पर दाने / खुजली (Rash/Hives)", "चेहरे या होंठों पर सूजन (Facial swelling)", "सांस लेने में तकलीफ (Breathing difficulty)", "पेट खराब / उल्टी (Stomach upset)", "गंभीर एनाफिलेक्सिस (Severe anaphylaxis)", "पक्का पता नहीं (Not sure)"],
        },
        "mr": {
            "text": "त्या औषधाच्या किंवा पदार्थाच्या संपर्कात आल्यावर काय त्रास होतो?",
            "help": "अंगावर पुरळ, खाज, सूज किंवा श्वास घेण्यास अडचण.",
            "spoken_prompt": "ॲलर्जी झाल्यावर काय होते? अंगावर पुरळ, सूज किंवा धाप लागणे?",
            "choices": ["अंगावर पुरळ किंवा खाज (Rash/Hives)", "चेहऱ्यावर किंवा ओठांवर सूज (Facial swelling)", "श्वास घेण्यास अडचण (Breathing difficulty)", "पोट बिघडणे / मळमळ (Stomach upset)", "अतिगंभीर ॲनाफिलेक्सिस (Severe anaphylaxis)", "नक्की माहित नाही (Not sure)"],
        },
    },
    "previous_surgery": {
        "en": {
            "text": "Have you had any surgery or hospital admission before?",
            "help": "Includes major operations, cesarean section, gallbladder, appendix, etc.",
            "spoken_prompt": "Have you had any surgery or hospital admission before? You can say yes or no.",
            "choices": ["No previous surgeries", "Yes, had surgery before"],
        },
        "hi": {
            "text": "क्या पहले कभी आपका कोई ऑपरेशन (सर्जरी) या अस्पताल में भर्ती होना पड़ा है?",
            "help": "जैसे अपेंडिक्स, पित्त की थैली, सी-सेक्शन या कोई अन्य ऑपरेशन।",
            "spoken_prompt": "क्या पहले कभी आपका कोई ऑपरेशन हुआ है? आप हां या नहीं कह सकते हैं।",
            "choices": ["कोई ऑपरेशन नहीं हुआ (No previous surgery)", "हां, पहले ऑपरेशन हुआ है (Yes, had surgery)"],
        },
        "mr": {
            "text": "यापूर्वी तुमची कोणती शस्त्रक्रिया (ऑपरेशन) किंवा हॉस्पिटलमध्ये ॲडमिट व्हावे लागले आहे का?",
            "help": "उदा. ॲपेंडिक्स, पित्ताशय, सिझेरियन किंवा इतर शस्त्रक्रिया.",
            "spoken_prompt": "यापूर्वी तुमचे कोणते ऑपरेशन झाले आहे का? हो किंवा नाही सांगा.",
            "choices": ["कोणतेही ऑपरेशन झालेले नाही (No previous surgery)", "होय, यापूर्वी ऑपरेशन झाले आहे (Yes, had surgery)"],
        },
    },
    "surgery_details": {
        "en": {
            "text": "What surgery did you have and in which year?",
            "help": "For example: Appendectomy in 2019, Cesarean delivery in 2021.",
            "spoken_prompt": "What surgery did you have and in which year?",
            "choices": [],
        },
        "hi": {
            "text": "कौन सा ऑपरेशन हुआ था और किस साल में हुआ था?",
            "help": "जैसे: अपेंडिक्स का ऑपरेशन 2019 में, या पथरी का 2021 में।",
            "spoken_prompt": "कौन सा ऑपरेशन किस साल में हुआ था?",
            "choices": [],
        },
        "mr": {
            "text": "कोणती शस्त्रक्रिया झाली होती आणि कोणत्या वर्षी झाली होती?",
            "help": "उदा. ॲपेंडिक्स शस्त्रक्रिया २०१९ मध्ये, किंवा सिझेरियन २०२१ मध्ये.",
            "spoken_prompt": "कोणते ऑपरेशन आणि कोणत्या वर्षी झाले होते?",
            "choices": [],
        },
    },
    "family_history": {
        "en": {
            "text": "Does anyone in your immediate family have heart disease, diabetes, or cancer?",
            "help": "Parents, siblings, or grandparents.",
            "spoken_prompt": "Does anyone in your family have heart disease, diabetes, or cancer? You can say yes or no.",
            "choices": ["No significant family history", "Yes, diabetes", "Yes, heart disease", "Yes, both heart disease and diabetes", "Yes, cancer", "Not sure"],
        },
        "hi": {
            "text": "क्या आपके परिवार में किसी को दिल की बीमारी, शुगर (डायबिटीज) या कैंसर रहा है?",
            "help": "माता-पिता, भाई-बहन या दादा-दादी।",
            "spoken_prompt": "क्या परिवार में किसी को शुगर, दिल की बीमारी या कैंसर है? आप हां या नहीं कह सकते हैं।",
            "choices": ["परिवार में कोई गंभीर बीमारी नहीं (No significant history)", "हां, शुगर / डायबिटीज (Yes, diabetes)", "हां, दिल की बीमारी (Yes, heart disease)", "हां, दिल की बीमारी और शुगर दोनों (Both)", "हां, कैंसर (Yes, cancer)", "पक्का पता नहीं (Not sure)"],
        },
        "mr": {
            "text": "तुमच्या जवळच्या कुटुंबात कोणाला हृदयविकार, मधुमेह (शुगर) किंवा कर्करोग (कॅन्सर) आहे का?",
            "help": "आई-वडील, बहीण-भाऊ किंवा आजी-आजोबा.",
            "spoken_prompt": "कुटुंबात कोणाला हृदयविकार, मधुमेह किंवा कॅन्सर आहे का? हो किंवा नाही सांगा.",
            "choices": ["कुटुंबात कोणताही गंभीर आजार नाही (No significant history)", "होय, मधुमेह (Yes, diabetes)", "होय, हृदयविकार (Yes, heart disease)", "होय, हृदयविकार व मधुमेह दोन्ही (Both)", "होय, कर्करोग (Yes, cancer)", "नक्की माहित नाही (Not sure)"],
        },
    },
    "additional_information": {
        "en": {
            "text": "Is there anything else you would like the doctor to know about your health or this visit?",
            "help": "Any additional concerns, lifestyle changes, or questions.",
            "spoken_prompt": "Is there anything else you would like the doctor to know?",
            "choices": [],
        },
        "hi": {
            "text": "क्या आप अपने स्वास्थ्य या इस जांच के बारे में डॉक्टर को कुछ और बताना चाहते हैं?",
            "help": "कोई अन्य परेशानी, खान-पान या आपकी कोई शंका।",
            "spoken_prompt": "क्या आप डॉक्टर को अपने स्वास्थ्य के बारे में कुछ और बताना चाहते हैं?",
            "choices": [],
        },
        "mr": {
            "text": "आपल्या आरोग्याविषयी किंवा त्रासाविषयी डॉक्टरांना अजून काही सांगायचे आहे का?",
            "help": "कोणतीही इतर तक्रार, जीवनशैलीतील बदल किंवा प्रश्न.",
            "spoken_prompt": "आरोग्याविषयी डॉक्टरांना अजून काही सांगायचे आहे का?",
            "choices": [],
        },
    },
}

# Utterance normalization maps for speech-to-text resolution
SPEECH_SYNONYMS: Dict[str, Dict[str, str]] = {
    # Scale Numbers (1 to 10) in EN, HI, MR and phonetic transliterations
    "numbers": {
        "one": "1", "1": "1", "एक": "1", "ek": "1",
        "two": "2", "2": "2", "दो": "2", "दोन": "2", "do": "2", "don": "2",
        "three": "3", "3": "3", "तीन": "3", "teen": "3",
        "four": "4", "4": "4", "चार": "4", "char": "4",
        "five": "5", "5": "5", "पांच": "5", "पाच": "5", "panch": "5",
        "six": "6", "6": "6", "छह": "6", "सहा": "6", "chhah": "6", "saha": "6",
        "seven": "7", "7": "7", "सात": "7", "saat": "7",
        "eight": "8", "8": "8", "आठ": "8", "aath": "8",
        "nine": "9", "9": "9", "नौ": "9", "nau": "9",
        "ten": "10", "10": "10", "दस": "10", "दहा": "10", "das": "10", "daha": "10",
    },
    # Yes / No intent
    "affirmative": {
        "yes": "yes", "yeah": "yes", "yep": "yes", "sure": "yes", "regularly": "yes",
        "daily": "yes", "regular": "yes", "suru": "yes",
        "हां": "yes", "हाँ": "yes", "जी हां": "yes", "बिल्कुल": "yes", "haan": "yes",
        "हो": "yes", "होय": "yes", "आहे": "yes", "ho": "yes", "aahe": "yes",
    },
    "negative": {
        "no": "no", "nope": "no", "none": "no", "nothing": "no", "not": "no",
        "नहीं": "no", "ना": "no", "कुछ नहीं": "no", "nahi": "no", "nahin": "no",
        "नाही": "no", "काही नाही": "no", "nakkich": "no",
    },
    # Chief complaint mappings
    "symptoms": {
        "headache": "Headache", "head pain": "Headache", "sir dard": "Headache",
        "सिर दर्द": "Headache", "सिरदर्द": "Headache", "डोकेदुखी": "Headache",
        "डोके": "Headache", "severe headache": "Headache",
        "stomach pain": "Abdominal pain", "abdominal pain": "Abdominal pain",
        "pet dard": "Abdominal pain", "पेट दर्द": "Abdominal pain", "पोटदुखी": "Abdominal pain",
        "chest pain": "Chest discomfort", "chest discomfort": "Chest discomfort",
        "seene me dard": "Chest discomfort", "छातीत दुखणे": "Chest discomfort", "छातीत": "Chest discomfort",
        "fever": "Fever", "temperature": "Fever", "bukhar": "Fever", "बुखार": "Fever", "ताप": "Fever",
        "cough": "Cough", "cold": "Cough", "khasi": "Cough", "खांसी": "Cough", "खोकला": "Cough",
        "back pain": "Back pain", "peeth dard": "Back pain", "पाठदुखी": "Back pain",
        "nausea": "Nausea", "vomiting": "Vomiting", "उल्टी": "Vomiting",
    },
    # Duration mappings
    "durations": {
        "less than a day": "less than a day", "today": "less than a day", "aaj se": "less than a day",
        "आज से": "less than a day", "आजपासून": "less than a day",
        "one to three days": "1 to 3 days", "1 to 3 days": "1 to 3 days", "two days": "2 days",
        "2 days": "2 days", "3 days": "3 days", "दो दिन": "2 days", "तीन दिन": "3 days",
        "दोन दिवस": "2 days", "तीन दिवस": "3 days", "दिवस": "days",
        "2 divasapasun": "2 days", "3 divasapasun": "3 days",
        "four to seven days": "4 to 7 days", "4 to 7 days": "4 to 7 days", "a week": "1 week",
        "एक हफ्ता": "1 week", "एक आठवडा": "1 week",
        "more than a week": "more than a week", "two weeks": "2 weeks",
        "हफ्ते से ज्यादा": "more than a week", "आठवड्यापेक्षा जास्त": "more than a week",
    },
}


def detect_speech_dialect(transcript: str, selected_lang: str = "en") -> Tuple[str, bool]:
    """
    Detects whether an utterance is mono-lingual or code-mixed (Hinglish / Marathish).
    Returns (dialect_name, is_code_mixed).
    """
    t_lower = transcript.lower()

    # Characteristic Hinglish markers
    hinglish_markers = [" hai", " se ", " aur ", " ki ", " me ", " chal ", " chal rahi", " leta", " hoon", " hota"]
    # Characteristic Marathish markers
    marathish_markers = [" aahe", " aani ", " tras ", " hoto", " divasapasun", " chi ", " suru ", " mala ", " nakkich"]
    # Common English words often mixed
    english_medical_words = ["headache", "chest pain", "pain", "fever", "cough", "days", "tablet", "medicine", "doctor", "allergy", "severity", "level", "drugs", "bp", "sugar"]

    has_english = any(w in t_lower for w in english_medical_words)
    has_hinglish = any(m in t_lower for m in hinglish_markers)
    has_marathish = any(m in t_lower for m in marathish_markers)

    if has_english and has_hinglish:
        return "hinglish", True
    if has_english and has_marathish:
        return "marathish", True

    if selected_lang == "hi":
        return "standard_hindi", False
    if selected_lang == "mr":
        return "standard_marathi", False
    return "standard_english", False


def get_translation_for_question(question_key: str, lang: str = "en") -> Dict[str, Any]:
    """Retrieve localized question text, choices, and spoken prompt."""
    lang = lang.lower() if lang else "en"
    if lang not in ["en", "hi", "mr"]:
        lang = "en"

    q_data = QUESTION_TRANSLATIONS.get(question_key, {})
    if not q_data:
        return {}

    return q_data.get(lang, q_data.get("en", {}))
