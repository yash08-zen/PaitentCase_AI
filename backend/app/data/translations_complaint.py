"""
data/translations_complaint.py
------------------------------
Localized text for the complaint-driven questionnaire (free-text reason for
visit + symptom modules). Merged over QUESTION_TRANSLATIONS in translations.py.

Choice convention (as in translations.py): Hindi/Marathi choices end with the
English value in brackets, e.g. "हां (Yes)". The interview engine compares the
English value, so branching works in every language.
"""
from typing import Any, Dict


def _q(en_text, en_help, hi_text, hi_help, mr_text, mr_help, choices=None):
    """choices: list of (en, hi, mr) tuples or None."""
    def ch(i):
        if not choices:
            return []
        if i == 0:
            return [c[0] for c in choices]
        return [f"{c[i]} ({c[0]})" for c in choices]

    return {
        "en": {"text": en_text, "help": en_help, "spoken_prompt": en_text, "choices": ch(0)},
        "hi": {"text": hi_text, "help": hi_help, "spoken_prompt": hi_text, "choices": ch(1)},
        "mr": {"text": mr_text, "help": mr_help, "spoken_prompt": mr_text, "choices": ch(2)},
    }


YES_NO_UNSURE = [("Yes", "हां", "होय"), ("No", "नहीं", "नाही"), ("Not sure", "पक्का नहीं", "खात्री नाही")]
YES_NO = [("Yes", "हां", "होय"), ("No", "नहीं", "नाही")]
SELECT_ALL_HI = "जो भी लागू हों, सभी चुनें।"
SELECT_ALL_MR = "लागू असलेले सर्व निवडा."

COMPLAINT_TRANSLATIONS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "chief_complaint": _q(
        "What is the main reason for your visit today? Please describe it in your own words.",
        "Write what you are feeling, where, and since when. The next questions are chosen from what you write.",
        "आज आप किस मुख्य कारण से आए हैं? कृपया अपने शब्दों में बताएं।",
        "क्या महसूस हो रहा है, कहाँ और कब से — लिखें। आगे के प्रश्न आपके जवाब के आधार पर चुने जाएंगे।",
        "आज तुम्ही कोणत्या मुख्य कारणासाठी आला आहात? कृपया तुमच्या शब्दांत सांगा.",
        "काय जाणवत आहे, कुठे आणि कधीपासून — लिहा. पुढील प्रश्न तुमच्या उत्तरावरून निवडले जातील.",
    ),
    "symptom_onset": _q(
        "How did this problem start?", "Choose the closest answer.",
        "यह समस्या कैसे शुरू हुई?", "सबसे नज़दीकी उत्तर चुनें।",
        "हा त्रास कसा सुरू झाला?", "सर्वात जवळचे उत्तर निवडा.",
        [("Suddenly", "अचानक", "अचानक"),
         ("Gradually over hours or days", "धीरे-धीरे, घंटों या दिनों में", "हळूहळू, काही तास किंवा दिवसांत"),
         ("Not sure", "पक्का नहीं", "खात्री नाही")],
    ),
    "symptom_course": _q(
        "Since it started, is the problem...", None,
        "शुरू होने के बाद से समस्या...", None,
        "सुरू झाल्यापासून त्रास...", None,
        [("Getting worse", "बढ़ रही है", "वाढत आहे"),
         ("Getting better", "कम हो रही है", "कमी होत आहे"),
         ("About the same", "लगभग वैसी ही है", "साधारण तसाच आहे"),
         ("Comes and goes", "आती-जाती रहती है", "येतो-जातो")],
    ),
    "symptom_triggers": _q(
        "Does anything make it better or worse?", "Leave blank if nothing changes it.",
        "क्या किसी चीज़ से यह बेहतर या बदतर होती है?", "अगर किसी चीज़ से फर्क नहीं पड़ता तो खाली छोड़ दें।",
        "कशामुळे हा त्रास कमी किंवा जास्त होतो का?", "कशानेही फरक पडत नसेल तर रिकामे ठेवा.",
    ),
    "previous_episodes": _q(
        "Have you had this same problem before?", None,
        "क्या आपको पहले भी यही समस्या हुई है?", None,
        "तुम्हाला पूर्वीही हाच त्रास झाला होता का?", None,
        YES_NO_UNSURE,
    ),
    "pain_location": _q(
        "Where exactly do you feel the pain or discomfort?", "Choose the closest area.",
        "दर्द या तकलीफ ठीक कहाँ महसूस होती है?", "सबसे नज़दीकी जगह चुनें।",
        "वेदना किंवा त्रास नेमका कुठे जाणवतो?", "सर्वात जवळचा भाग निवडा.",
        [("Head", "सिर", "डोके"), ("Face / jaw", "चेहरा / जबड़ा", "चेहरा / जबडा"),
         ("Throat / neck", "गला / गर्दन", "घसा / मान"), ("Chest", "छाती", "छाती"),
         ("Upper abdomen", "ऊपरी पेट", "पोटाचा वरचा भाग"), ("Lower abdomen", "निचला पेट", "पोटाचा खालचा भाग"),
         ("Back", "पीठ / कमर", "पाठ / कंबर"), ("Arm / shoulder", "हाथ / कंधा", "हात / खांदा"),
         ("Leg / knee / foot", "पैर / घुटना / पंजा", "पाय / गुडघा / तळपाय"),
         ("Many joints", "कई जोड़", "अनेक सांधे"), ("Other", "अन्य", "इतर")],
    ),
    "pain_character": _q(
        "How would you describe the pain?", None,
        "दर्द कैसा है?", None,
        "वेदना कशा प्रकारच्या आहेत?", None,
        [("Sharp / stabbing", "तेज़ / चुभने वाला", "तीव्र / टोचल्यासारखी"),
         ("Dull / aching", "हल्का / लगातार दुखना", "मंद / सतत दुखणे"),
         ("Burning", "जलन", "जळजळ"), ("Throbbing", "धड़कन जैसा", "ठणका"),
         ("Pressing / tight", "दबाव / जकड़न", "दाब / आवळल्यासारखी"),
         ("Cramping", "ऐंठन", "पेटके / मुरडा"), ("Not sure", "पक्का नहीं", "खात्री नाही")],
    ),
    "pain_radiation": _q(
        "Does the pain spread to any other part of the body?", None,
        "क्या दर्द शरीर के किसी और हिस्से में फैलता है?", None,
        "वेदना शरीराच्या इतर भागात पसरतात का?", None,
        YES_NO_UNSURE,
    ),
    "worse_with_activity": _q(
        "Does it get worse with physical effort, like walking or climbing stairs?", None,
        "क्या चलने या सीढ़ियाँ चढ़ने जैसी मेहनत से यह बढ़ता है?", None,
        "चालणे किंवा जिना चढणे अशा श्रमाने हा त्रास वाढतो का?", None,
        YES_NO_UNSURE,
    ),
    "chest_symptoms": _q(
        "Do you have any of these?", "Select all that apply.",
        "क्या आपको इनमें से कुछ है?", SELECT_ALL_HI,
        "यापैकी काही आहे का?", SELECT_ALL_MR,
        [("Shortness of breath", "सांस फूलना", "धाप लागणे"), ("Sweating", "पसीना आना", "घाम येणे"),
         ("Pain spreading to arm, jaw or back", "दर्द हाथ, जबड़े या पीठ तक फैलना", "वेदना हात, जबडा किंवा पाठीकडे पसरणे"),
         ("Racing or irregular heartbeat", "तेज़ या अनियमित धड़कन", "जलद किंवा अनियमित धडधड"),
         ("Fainting or near-fainting", "बेहोशी या बेहोशी जैसा लगना", "बेशुद्ध होणे किंवा तसे वाटणे"),
         ("Swelling of feet", "पैरों में सूजन", "पायांना सूज"), ("None", "कोई नहीं", "काहीही नाही")],
    ),
    "cough_type": _q(
        "Do you have a cough?", None,
        "क्या आपको खांसी है?", None,
        "तुम्हाला खोकला आहे का?", None,
        [("Dry cough", "सूखी खांसी", "कोरडा खोकला"), ("Cough with phlegm", "बलगम वाली खांसी", "कफ असलेला खोकला"),
         ("Cough with blood", "खांसी में खून", "खोकल्यात रक्त"), ("No cough", "खांसी नहीं", "खोकला नाही")],
    ),
    "breathlessness_level": _q(
        "Do you feel breathless?", None,
        "क्या आपकी सांस फूलती है?", None,
        "तुम्हाला धाप लागते का?", None,
        [("No breathlessness", "सांस नहीं फूलती", "धाप लागत नाही"),
         ("Only on exertion", "सिर्फ मेहनत करने पर", "फक्त श्रम केल्यावर"),
         ("Even at rest", "आराम में भी", "विश्रांतीतही")],
    ),
    "fever_highest_temp": _q(
        "If you measured it, what was the highest temperature?", "Leave blank if you did not measure it.",
        "अगर नापा हो, तो सबसे ज़्यादा तापमान कितना था?", "अगर नहीं नापा तो खाली छोड़ दें।",
        "मोजले असल्यास, सर्वात जास्त ताप किती होता?", "मोजले नसल्यास रिकामे ठेवा.",
    ),
    "fever_pattern": _q(
        "How does the fever behave?", None,
        "बुखार कैसे आता है?", None,
        "ताप कसा येतो?", None,
        [("Continuous", "लगातार", "सतत"),
         ("Comes and goes with chills or shivering", "ठंड या कंपकंपी के साथ आता-जाता है", "थंडी किंवा हुडहुडीसह येतो-जातो"),
         ("Mostly in the evening or night", "ज़्यादातर शाम या रात में", "बहुतेक संध्याकाळी किंवा रात्री"),
         ("Not sure", "पक्का नहीं", "खात्री नाही")],
    ),
    "gi_symptoms": _q(
        "Do you have any of these?", "Select all that apply.",
        "क्या आपको इनमें से कुछ है?", SELECT_ALL_HI,
        "यापैकी काही आहे का?", SELECT_ALL_MR,
        [("Vomiting", "उल्टी", "उलटी"), ("Loose stools / diarrhoea", "दस्त", "जुलाब"),
         ("Constipation", "कब्ज", "बद्धकोष्ठता"), ("Blood in vomit or stool", "उल्टी या मल में खून", "उलटी किंवा शौचात रक्त"),
         ("Black stools", "काला मल", "काळी शौच"), ("Loss of appetite", "भूख न लगना", "भूक न लागणे"),
         ("Bloating or gas", "पेट फूलना या गैस", "पोट फुगणे किंवा गॅस"), ("None", "कोई नहीं", "काहीही नाही")],
    ),
    "food_related": _q(
        "Is the problem related to eating or to certain foods?", None,
        "क्या समस्या खाने या किसी खास भोजन से जुड़ी है?", None,
        "हा त्रास जेवणाशी किंवा विशिष्ट पदार्थांशी संबंधित आहे का?", None,
        YES_NO_UNSURE,
    ),
    "neuro_symptoms": _q(
        "Do you have any of these?", "Select all that apply.",
        "क्या आपको इनमें से कुछ है?", SELECT_ALL_HI,
        "यापैकी काही आहे का?", SELECT_ALL_MR,
        [("Blurred or double vision", "धुंधला या दोहरा दिखना", "अंधुक किंवा दुहेरी दिसणे"),
         ("Weakness of face, arm or leg", "चेहरे, हाथ या पैर में कमजोरी", "चेहरा, हात किंवा पायात अशक्तपणा"),
         ("Difficulty speaking", "बोलने में कठिनाई", "बोलण्यात अडचण"),
         ("Numbness or tingling", "सुन्नपन या झनझनाहट", "बधिरपणा किंवा मुंग्या"),
         ("Fainting or blackout", "बेहोशी", "बेशुद्ध पडणे"), ("Fits / seizures", "दौरे / झटके", "फिट / झटके"),
         ("Vomiting", "उल्टी", "उलटी"), ("None", "कोई नहीं", "काहीही नाही")],
    ),
    "urinary_symptoms": _q(
        "Do you have any of these?", "Select all that apply.",
        "क्या आपको इनमें से कुछ है?", SELECT_ALL_HI,
        "यापैकी काही आहे का?", SELECT_ALL_MR,
        [("Burning while passing urine", "पेशाब में जलन", "लघवी करताना जळजळ"),
         ("Passing urine very often", "बार-बार पेशाब आना", "वारंवार लघवी होणे"),
         ("Blood in urine", "पेशाब में खून", "लघवीत रक्त"), ("Passing less urine", "कम पेशाब आना", "कमी लघवी होणे"),
         ("Pain in the side or lower back", "बगल या कमर में दर्द", "कुशीत किंवा कंबरेत दुखणे"),
         ("Fever with chills", "ठंड के साथ बुखार", "थंडी वाजून ताप"), ("None", "कोई नहीं", "काहीही नाही")],
    ),
    "skin_details": _q(
        "Do you have any of these?", "Select all that apply.",
        "क्या आपको इनमें से कुछ है?", SELECT_ALL_HI,
        "यापैकी काही आहे का?", SELECT_ALL_MR,
        [("Itching", "खुजली", "खाज"), ("Spreading quickly", "तेज़ी से फैल रहा है", "झपाट्याने पसरत आहे"),
         ("Blisters", "छाले", "फोड"), ("Pus or discharge", "मवाद या रिसाव", "पू किंवा स्राव"),
         ("Swelling of lips, face or throat", "होंठ, चेहरे या गले में सूजन", "ओठ, चेहरा किंवा घशाला सूज"),
         ("Started after a new medicine or food", "नई दवा या भोजन के बाद शुरू हुआ", "नवीन औषध किंवा पदार्थानंतर सुरू झाले"),
         ("None", "कोई नहीं", "काहीही नाही")],
    ),
    "injury_how": _q(
        "Did this start after an injury, fall or strain? If yes, how did it happen?", None,
        "क्या यह चोट, गिरने या खिंचाव के बाद शुरू हुआ? अगर हाँ, तो कैसे हुआ?", None,
        "हे दुखापत, पडणे किंवा ताण आल्यानंतर सुरू झाले का? असल्यास कसे घडले?", None,
    ),
    "mobility_affected": _q(
        "Can you move or use the affected part normally?", None,
        "क्या आप प्रभावित हिस्से को सामान्य रूप से हिला या इस्तेमाल कर पाते हैं?", None,
        "त्रास असलेला भाग तुम्ही नेहमीसारखा हलवू किंवा वापरू शकता का?", None,
        [("Yes, normally", "हां, सामान्य रूप से", "होय, नेहमीसारखा"),
         ("With some difficulty", "कुछ कठिनाई के साथ", "थोड्या अडचणीने"),
         ("Not at all", "बिल्कुल नहीं", "अजिबात नाही")],
    ),
    "mood_sleep": _q(
        "Over the last two weeks, have you had any of these?", "Select all that apply. Your answers are private to your doctor.",
        "पिछले दो हफ्तों में क्या आपको इनमें से कुछ हुआ है?", "जो भी लागू हों, सभी चुनें। आपके उत्तर केवल आपके डॉक्टर देखेंगे।",
        "गेल्या दोन आठवड्यांत यापैकी काही जाणवले का?", "लागू असलेले सर्व निवडा. तुमची उत्तरे फक्त तुमचे डॉक्टर पाहतील.",
        [("Low mood most of the day", "दिन भर उदासी", "दिवसभर उदास वाटणे"),
         ("Worry or anxiety", "चिंता या घबराहट", "काळजी किंवा अस्वस्थता"),
         ("Poor sleep", "नींद ठीक न आना", "झोप नीट न येणे"),
         ("Loss of interest in daily activities", "रोज़ के कामों में रुचि खत्म होना", "रोजच्या कामांत रस न वाटणे"),
         ("Thoughts of harming yourself", "खुद को नुकसान पहुँचाने के विचार", "स्वतःला इजा करण्याचे विचार"),
         ("None", "कोई नहीं", "काहीही नाही")],
    ),
    "pregnancy_status": _q(
        "Is there any chance you could be pregnant?", None,
        "क्या आपके गर्भवती होने की कोई संभावना है?", None,
        "तुम्ही गरोदर असण्याची काही शक्यता आहे का?", None,
        [("Yes", "हां", "होय"), ("No", "नहीं", "नाही"), ("Not sure", "पक्का नहीं", "खात्री नाही"),
         ("Not applicable", "लागू नहीं", "लागू नाही")],
    ),
    "last_period": _q(
        "When did your last menstrual period start?", "Leave blank if not applicable.",
        "आपका पिछला मासिक धर्म कब शुरू हुआ था?", "लागू न हो तो खाली छोड़ दें।",
        "तुमची मागील मासिक पाळी कधी सुरू झाली?", "लागू नसल्यास रिकामे ठेवा.",
    ),
    "has_fever": _q(
        "Have you had a fever or felt feverish?", None,
        "क्या आपको बुखार हुआ है या बुखार जैसा लगा है?", None,
        "तुम्हाला ताप आला आहे का किंवा तापासारखे वाटले का?", None,
        [("Yes", "हां", "होय"), ("No", "नहीं", "नाही"), ("Not measured", "नापा नहीं", "मोजला नाही")],
    ),
    "associated_symptoms": _q(
        "Do you have any of these along with your main problem?", "Select all that apply.",
        "क्या मुख्य समस्या के साथ आपको इनमें से कुछ है?", SELECT_ALL_HI,
        "मुख्य त्रासासोबत यापैकी काही आहे का?", SELECT_ALL_MR,
        [("Tiredness", "थकान", "थकवा"), ("Weight loss", "वज़न कम होना", "वजन कमी होणे"),
         ("Loss of appetite", "भूख न लगना", "भूक न लागणे"), ("Nausea", "जी मिचलाना", "मळमळ"),
         ("Dizziness", "चक्कर", "चक्कर"), ("Shortness of breath", "सांस फूलना", "धाप लागणे"),
         ("Sweating", "पसीना", "घाम"), ("None", "कोई नहीं", "काहीही नाही")],
    ),
    "has_chronic_conditions": _q(
        "Do you have any long-term or chronic medical conditions?", None,
        "क्या आपको कोई लंबी या पुरानी बीमारी है?", None,
        "तुम्हाला कोणताही दीर्घकालीन आजार आहे का?", None,
        YES_NO_UNSURE,
    ),
    "chronic_conditions_detail": _q(
        "Which chronic conditions have you been diagnosed with?", "Select all that apply.",
        "आपको कौन-सी पुरानी बीमारियाँ बताई गई हैं?", SELECT_ALL_HI,
        "तुम्हाला कोणते दीर्घकालीन आजार असल्याचे निदान झाले आहे?", SELECT_ALL_MR,
        [("Hypertension", "उच्च रक्तचाप", "उच्च रक्तदाब"), ("Diabetes (Type 1 or 2)", "मधुमेह", "मधुमेह"),
         ("Asthma / Respiratory", "दमा / सांस की बीमारी", "दमा / श्वसनाचा आजार"),
         ("Thyroid disorder", "थायरॉइड", "थायरॉईड"), ("Heart disease", "हृदय रोग", "हृदयरोग"),
         ("Kidney disease", "किडनी की बीमारी", "मूत्रपिंडाचा आजार"), ("Other", "अन्य", "इतर")],
    ),
    "current_medications": _q(
        "Are you currently taking any prescription medicines, supplements, or regular tablets?",
        "Include blood pressure, diabetes, thyroid, or daily vitamins.",
        "क्या आप वर्तमान में कोई नियमित दवाइयां, गोलियां या सप्लीमेंट्स ले रहे हैं?",
        "बीपी, शुगर, थायरॉइड या दैनिक विटामिन शामिल करें।",
        "तुम्ही सध्या काही नियमित औषधे, गोळ्या किंवा सप्लिमेंट्स घेत आहात का?",
        "बीपी, मधुमेह, थायरॉईड किंवा नियमित जीवनसत्त्वे यांचा समावेश करा.",
        YES_NO,
    ),
    "has_allergies": _q(
        "Do you have any known allergies to medicines, food, or other substances?", None,
        "क्या आपको किसी दवा, भोजन या अन्य चीज़ से एलर्जी है?", None,
        "तुम्हाला कोणत्याही औषध, अन्न किंवा इतर पदार्थाची ॲलर्जी आहे का?", None,
        YES_NO_UNSURE,
    ),
    "previous_surgery": _q(
        "Have you had any surgery or hospital admission before?", None,
        "क्या पहले कभी आपकी सर्जरी हुई है या आप अस्पताल में भर्ती हुए हैं?", None,
        "तुमची पूर्वी कधी शस्त्रक्रिया झाली आहे का किंवा रुग्णालयात दाखल झाला होता का?", None,
        YES_NO,
    ),
    "family_history": _q(
        "Does anyone in your immediate family have heart disease, diabetes, or cancer?", None,
        "क्या आपके परिवार में किसी को हृदय रोग, मधुमेह या कैंसर है?", None,
        "तुमच्या जवळच्या कुटुंबात कोणाला हृदयरोग, मधुमेह किंवा कर्करोग आहे का?", None,
        YES_NO_UNSURE,
    ),
}
