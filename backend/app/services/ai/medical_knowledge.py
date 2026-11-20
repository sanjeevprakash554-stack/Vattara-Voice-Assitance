"""Medically Reviewed Clinical Knowledge Base and Triage Engine for Vattara AI Voice Receptionist.

Grounds clinical responses in established clinical practice guidelines:
- World Health Organization (WHO) Guidelines & Emergency Triage Protocols.
- Ministry of Health & Family Welfare (MoHFW) India Clinical Protocols.
- Indian Council of Medical Research (ICMR) Guidelines for Diabetes & Hypertension.
- National Health Mission (NHM) Primary Healthcare Treatment Workflows.

Safety Principles:
1. NEVER diagnose definitively or declare diseases based on partial symptom descriptions.
2. NEVER prescribe medications, specific dosages, or dosing schedules.
3. CLEARLY distinguish general medical information from personalized medical advice.
4. IMMEDIATELY route acute life-threatening warning signs to emergency services (108).
5. ALIGN symptom triage with active tenant clinic departments, doctors, and services.
"""

from dataclasses import dataclass, field
from difflib import SequenceMatcher
import re
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MedicalTopic:
    """Encapsulates a verified clinical topic with multilingual symptom aliases and guidance."""
    id: str
    category: str
    name_en: str
    name_ta: str
    name_tanglish: str
    aliases: list[str]
    explanation_en: str
    explanation_ta: str
    explanation_tanglish: str
    home_care_en: str
    home_care_ta: str
    home_care_tanglish: str
    red_flags_en: list[str]
    red_flags_ta: list[str]
    red_flags_tanglish: list[str]
    triage_question_en: str
    triage_question_ta: str
    triage_question_tanglish: str
    recommended_specialty: str
    relevant_service_keywords: list[str]
    relevant_tests: list[str] = field(default_factory=list)
    is_emergency: bool = False
    source_attribution: str = "WHO & ICMR Guidelines"


# ==============================================================================
# Medically Reviewed Clinical Knowledge Directory (16 Core Clinical Topics)
# ==============================================================================

MEDICAL_TOPICS_CATALOG: list[MedicalTopic] = [
    # 1. Fever & Viral Infections
    MedicalTopic(
        id="fever_infection",
        category="infections",
        name_en="Fever & Viral Infection",
        name_ta="காய்ச்சல் மற்றும் வைரஸ் தொற்று",
        name_tanglish="Fever & Infection",
        aliases=[
            "fever", "high temperature", "chills", "shivering", "mild fever", "high fever",
            "kaachal", "kaisal", "kacsal", "jwaram", "soodu", "odambu soodu", "fever adikkudhu",
            "fever vandhuchu", "fever irukku", "fever varudhu", "temperature irukku",
            "காய்ச்சல்", "உடம்பு சூடு", "சூடு", "ஜுரம்", "குளிர் காய்ச்சல்",
            "jwaram undi", "jvaram", "ontlo vedam",
        ],
        explanation_en="Fever is the body's natural defense against infection, commonly caused by viral or bacterial illnesses.",
        explanation_ta="காய்ச்சல் என்பது தொற்றை எதிர்த்து உடல் போராடும் இயல்பான எதிர்ப்பு நிலை, பொதுவாக வைரஸ் அல்லது பாக்டீரியாவால் ஏற்படுகிறது.",
        explanation_tanglish="Fever enbadhu infection-ai edhirthu body fight pandra natural response, viral illa bacterial kaaranam-aga varalaam.",
        home_care_en="Stay well hydrated with water, ORS, or warm soups, get plenty of rest, and sponge with lukewarm water if temperature rises.",
        home_care_ta="போதுமான தண்ணீர், கஞ்சி அல்லது நீர்ச்சத்து எடுத்துக்கொள்ளுங்கள், ஓய்வெடுங்கள்.",
        home_care_tanglish="Nallaa water, kanji kudinga, dehydrate aagama rest edukunga.",
        red_flags_en=["Fever above 102°F lasting more than 3 days", "Stiff neck", "Persistent vomiting", "Severe breathing difficulty", "Skin rash"],
        red_flags_ta=["3 நாட்களுக்கு மேல் நீடிக்கும் காய்ச்சல்", "கழுத்து விறைப்பு", "தொடர் வாந்தி", "மூச்சுத் திணறல்"],
        red_flags_tanglish=["Fever 3 naalaiku mela irundha", "Kazhuthu vali", "Thodar vaandhi", "Moochu vida kashtam"],
        triage_question_en="How many days have you had the fever, and do you have chills or body pain?",
        triage_question_ta="காய்ச்சல் எத்தனை நாட்களாக இருக்கிறது? உடல் வலி அல்லது குளிர் நடுக்கம் உள்ளதா?",
        triage_question_tanglish="Fever ethana naala irukku, udambu vali illa kulir irukka?",
        recommended_specialty="General Physician",
        relevant_service_keywords=["General Physician Consultation", "General Medicine", "Doctor Consultation", "Fever"],
        relevant_tests=["Complete Blood Count (CBC)", "Dengue Serology", "Typhoid Widal/Typhidot"],
        source_attribution="WHO IMAI & MoHFW Clinical Guidelines",
    ),

    # 2. Common Cold & Cough
    MedicalTopic(
        id="cold_cough",
        category="respiratory",
        name_en="Common Cold & Cough",
        name_ta="சளி மற்றும் இருமல்",
        name_tanglish="Cold & Cough",
        aliases=[
            "cold", "cough", "runny nose", "blocked nose", "sore throat", "throat pain",
            "sneezing", "dry cough", "wet cough", "phlegm", "congestion",
            "sali", "irumal", "thonda vali", "thondai vali", "mooku ozhukudhu", "mookadaipu",
            "varattu irumal", "sali irukku", "thondai erichal", "cough syrup venum",
            "சளி", "இருமல்", "தொண்டை வலி", "மூக்கடைப்பு", "மூக்கு ஒழுகுதல்", "வறட்டு இருமல்",
            "daggu", "jalubu", "gonthu noppi",
        ],
        explanation_en="Colds and coughs are usually upper respiratory viral infections affecting the nose, throat, and bronchial passages.",
        explanation_ta="சளி மற்றும் இருமல் என்பது மூக்கு மற்றும் தொண்டையைப் பாதிக்கும் பொதுவான மேல் சுவாசக்குழாய் வைரஸ் தொற்று.",
        explanation_tanglish="Cold and cough sadharanam-aga upper respiratory viral infection, mooku thondai-la inflammation undaakum.",
        home_care_en="Drink warm water, take steam inhalation, do warm salt water gargles for throat irritation, and rest.",
        home_care_ta="வெதுவெதுப்பான நீர் அருந்துங்கள், ஆவி பிடியுங்கள், உப்பு நீரில் வாய் கொப்பளிக்கவும்.",
        home_care_tanglish="Warm water kudinga, steam inhalation edunga, warm salt water-la gargle pannunga.",
        red_flags_en=["Cough lasting over 2 to 3 weeks", "Coughing up blood", "Severe chest congestion", "Shortness of breath"],
        red_flags_ta=["2 வாரங்களுக்கு மேல் நீடிக்கும் இருமல்", "இருமலில் ரத்தம்", "மூச்சுத் திணறல்"],
        red_flags_tanglish=["Cough 2 weeks-ku mela irundha", "Irumalla raththam vandha", "Moochu thinaral"],
        triage_question_en="Is it a dry cough or with phlegm, and how many days has it been present?",
        triage_question_ta="இது வறட்டு இருமலா அல்லது சளியுடன் கூடிய இருமலா? எத்தனை நாட்களாக உள்ளது?",
        triage_question_tanglish="Idhu dry cough-ah illa sali irukka, ethana naala irukku?",
        recommended_specialty="General Physician",
        relevant_service_keywords=["General Physician Consultation", "General Medicine"],
        relevant_tests=["Chest X-Ray", "Complete Blood Count (CBC)"],
        source_attribution="WHO Acute Respiratory Infections Guidelines",
    ),

    # 3. Headache & Migraine
    MedicalTopic(
        id="headache",
        category="neurology",
        name_en="Headache & Migraine",
        name_ta="தலைவலி மற்றும் ஒற்றைத் தலைவலி",
        name_tanglish="Headache & Migraine",
        aliases=[
            "headache", "head pain", "migraine", "severe headache", "tension headache",
            "thala vali", "thalavali", "thala valikudhu", "thala bama irukku", "thala baram",
            "thala bayangarama valikudhu", "ottrai thala vali", "migraine vali",
            "தலைவலி", "தலையில் வலி", "ஒற்றைத் தலைவலி", "தலை பாரம்",
            "thala noppi", "thalanoppi",
        ],
        explanation_en="Headaches are commonly triggered by tension, eye strain, dehydration, stress, lack of sleep, or migraine.",
        explanation_ta="தலைவலி பொதுவாக மன அழுத்தம், கண் சோர்வு, நீர்ச்சத்து குறைவு அல்லது ஒற்றைத் தலைவலியால் ஏற்படுகிறது.",
        explanation_tanglish="Headache stress, thookaminmai, dehydration, kann strain illa migraine kaaranama varalaam.",
        home_care_en="Rest in a quiet dark room, stay hydrated with plenty of water, avoid screen time, and apply a cool compress.",
        home_care_ta="அமைதியான இருண்ட அறையில் ஓய்வெடுங்கள், தண்ணீர் குடியுங்கள், திரைகளைப் பார்ப்பதைத் தவிர்க்கவும்.",
        home_care_tanglish="Quiet dark room-la rest edukunga, nallaa water kudinga, phone screen paarkadhaeenga.",
        red_flags_en=["Sudden explosive 'thunderclap' headache", "Headache with one-sided numbness or speech difficulty", "Headache with stiff neck and high fever", "Headache following head injury"],
        red_flags_ta=["திடீரென ஏற்படும் தாங்க முடியாத தலைவலி", "கை கால் மரத்துப்போதல்", "கழுத்து விறைப்புடன் காய்ச்சல்"],
        red_flags_tanglish=["Thideerunu bayangarama thalavali vandha", "Kai kaal marathu ponum", "Kazhuthu vali-yodu fever"],
        triage_question_en="Is the pain on one side or all over, and do you feel nausea or sensitivity to light?",
        triage_question_ta="வலி தலையின் ஒரு பக்கத்தில் உள்ளதா அல்லது முழுவதும் உள்ளதா? வாந்தி உணர்வு உள்ளதா?",
        triage_question_tanglish="Vali oru pakkam irukka illa muzhuvadhum irukka, vaandhi maadhiri irukka?",
        recommended_specialty="General Physician",
        relevant_service_keywords=["General Physician Consultation", "General Medicine"],
        source_attribution="WHO Neurological Disorders Management",
    ),

    # 4. Body, Muscle & Joint Pain
    MedicalTopic(
        id="body_joint_pain",
        category="musculoskeletal",
        name_en="Body & Joint Pain",
        name_ta="உடல் மற்றும் மூட்டு வலி",
        name_tanglish="Body & Joint Pain",
        aliases=[
            "body pain", "body ache", "muscle pain", "joint pain", "back pain", "knee pain",
            "shoulder pain", "neck pain", "arthritis", "sprain", "odambu vali", "udambu vali",
            "mutti vali", "mudhughe vali", "mudhugu vali", "kaal vali", "kai vali", "valikudhu",
            "உடம்பு வலி", "மூட்டு வலி", "முதுகு வலி", "கால் வலி", "கை வலி",
            "ontlo noppulu", "keella noppulu", "naddumu noppi",
        ],
        explanation_en="Body and joint aches can result from physical fatigue, viral fevers, muscle strain, or joint inflammation.",
        explanation_ta="உடல் மற்றும் மூட்டு வலி உடல் சோர்வு, வைரஸ் காய்ச்சல், தசைப் பிடிப்பு அல்லது மூட்டு அழற்சியால் ஏற்படலாம்.",
        explanation_tanglish="Body and joint pain udambu exhaustion, viral fever, muscle strain illa joint inflammation aala varalaam.",
        home_care_en="Take adequate bed rest, avoid heavy physical strain, use warm water compression, and maintain good posture.",
        home_care_ta="நன்றாக ஓய்வெடுங்கள், அதிக எடையைத் தூக்குவதைத் தவிர்க்கவும், வெதுவெதுப்பான ஒத்தடம் கொடுக்கவும்.",
        home_care_tanglish="Nallaa rest edukunga, weight thookadhaeenga, warm compress kudunga.",
        red_flags_en=["Severe joint swelling with redness and hot skin", "Inability to bear weight on the leg", "Back pain with urinary incontinence or limb weakness"],
        red_flags_ta=["மூட்டுகளில் கடுமையான வீக்கம் மற்றும் சிவந்து போதல்", "நிற்க முடியாத நிலை"],
        red_flags_tanglish=["Joints romba veengi sevandhu pochu", "Kaal vechu nadakka mudiyala"],
        triage_question_en="Which joints or muscles hurt, and did this start after injury or fever?",
        triage_question_ta="எந்தப் பகுதியில் வலி உள்ளது? அடிபட்டதா அல்லது காய்ச்சலுக்குப் பின் தொடங்கியதா?",
        triage_question_tanglish="Endha idathula vali irukku, adi pattudha illa fever vandhu vandhucha?",
        recommended_specialty="General Physician",
        relevant_service_keywords=["General Physician Consultation", "General Medicine"],
        relevant_tests=["Uric Acid", "RA Factor", "ESR / CRP"],
        source_attribution="MoHFW Musculoskeletal Clinical Care Guidelines",
    ),

    # 5. Diabetes & Blood Sugar
    MedicalTopic(
        id="diabetes_blood_sugar",
        category="metabolic",
        name_en="Diabetes & Blood Sugar",
        name_ta="சர்க்கரை நோய் மற்றும் ரத்த சர்க்கரை அளவு",
        name_tanglish="Diabetes & Blood Sugar",
        aliases=[
            "diabetes", "blood sugar", "sugar", "high sugar", "low sugar", "sugar test",
            "fasting sugar", "postprandial sugar", "hba1c", "frequent urination", "excessive thirst",
            "sugar irukku", "sugar checkup", "sugar level", "sugar eppadi irukanum",
            "சர்க்கரை நோய்", "சர்க்கரை அளவு", "சுகர்", "ரத்த சர்க்கரை",
            "madhumeham", "sugar undi", "sugar test",
        ],
        explanation_en="Diabetes is a metabolic condition where blood glucose is elevated. Normal fasting glucose is typically 70 to 99 mg/dL; postprandial under 140 mg/dL.",
        explanation_ta="சர்க்கரை நோய் என்பது ரத்தத்தில் குளுக்கோஸ் அளவு அதிகரிக்கும் நிலை. வெறும் வயிற்றில் சர்க்கரை அளவு 70 முதல் 99 mg/dL வரை இருப்பது வழக்கம்.",
        explanation_tanglish="Diabetes rathathula sugar level koodum metabolic condition. Normal fasting sugar 70 to 99 mg/dL, sapta apram 140 mg/dL kulla irukanum.",
        home_care_en="Follow a balanced low-sugar diet rich in green vegetables and fiber, walk 30 minutes daily, and monitor your glucose levels regularly.",
        home_care_ta="சர்க்கரை, இனிப்புகளைத் தவிர்க்கவும், நார்ச்சத்துள்ள காய்கறிகள் உண்ணுங்கள், தினமும் நடைப்பயிற்சி செய்யுங்கள்.",
        home_care_tanglish="Sugar sweets thavirkavum, fiber vegetable saapdunga, daily 30 minutes walking ponga.",
        red_flags_en=["Hypoglycemia (sugar < 70 with sweating, trembling, confusion - take glucose/sugar immediately!)", "Extremely high sugar > 300 with vomiting, deep rapid breathing, or confusion (DKA emergency)"],
        red_flags_ta=["சர்க்கரை குறைதல் (வியர்வை, நடுக்கம், மயக்கம் - உடனே சர்க்கரை அல்லது குளுக்கோஸ் சாப்பிடவும்)", "மிக அதிக சர்க்கரையுடன் வாந்தி மற்றும் மயக்கம்"],
        red_flags_tanglish=["Sugar romba koranju viyarvai nadukkam vandha udane sugar/chocolate saapdunga", "Sugar 300-ku mela poi vaandhi mayakkam vandha"],
        triage_question_en="What was your latest fasting or post-meal blood sugar reading, and are you currently on medication?",
        triage_question_ta="உங்கள் தற்போதைய ரத்த சர்க்கரை அளவு எவ்வளவு? ஏற்கனவே மாத்திரை சாப்பிடுகிறீர்களா?",
        triage_question_tanglish="Unga latest fasting illa post-meal sugar level evlo, tablet eduthukureengala?",
        recommended_specialty="General Physician",
        relevant_service_keywords=["General Physician Consultation", "Full Body Blood Diagnostics"],
        relevant_tests=["Fasting Blood Sugar (FBS)", "Postprandial Blood Sugar (PPBS)", "HbA1c (3-Month Sugar Average)"],
        source_attribution="ICMR Guidelines for Management of Type 2 Diabetes",
    ),

    # 6. Blood Pressure & Hypertension
    MedicalTopic(
        id="hypertension_blood_pressure",
        category="cardiovascular",
        name_en="Blood Pressure & Hypertension",
        name_ta="ரத்த அழுத்தம் மற்றும் உயர் ரத்த அழுத்தம்",
        name_tanglish="Blood Pressure (BP)",
        aliases=[
            "blood pressure", "bp", "high bp", "low bp", "hypertension", "bp checkup",
            "pressure", "preasure", "giddiness bp", "bp eriduchu", "bp koranjiruchu",
            "bp level", "bp check pannanum", "thalasuthal bp",
            "ரத்த அழுத்தம்", "உயர் ரத்த அழுத்தம்", "பிபி", "இரத்த அழுத்தம்", "தலைச்சுற்றல்",
            "raktha potu", "bp undi", "high bp",
        ],
        explanation_en="Blood pressure measures the force of blood against arterial walls. Ideal resting BP is around 120/80 mmHg; consistently above 130/80 mmHg indicates hypertension.",
        explanation_ta="ரத்த அழுத்தம் என்பது ரத்த நாளங்களில் ரத்தம் செலுத்தும் விசை. இயல்பான அளவு 120/80 mmHg. 130/80-க்கு மேல் நீடித்தால் அது உயர் ரத்த அழுத்தம்.",
        explanation_tanglish="Blood pressure rathanaalathula blood thallura pressure. Normal reading 120/80 mmHg. 130/80-ku mela irundha hypertension.",
        home_care_en="Reduce dietary salt/sodium, manage stress, engage in daily brisk walking, avoid smoking and alcohol, and check BP regularly.",
        home_care_ta="உணவில் உப்பைக் குறைக்கவும், மன அழுத்தத்தைத் தவிர்க்கவும், தினமும் நடைப்பயிற்சி செய்யுங்கள்.",
        home_care_tanglish="Food-la salt korainga, stress thavirkavum, regular walking ponga, BP-ai track pannunga.",
        red_flags_en=["BP over 180/120 mmHg (Hypertensive Crisis)", "Severe headache with chest discomfort or visual blurriness", "Sudden weakness or numbness on one side"],
        red_flags_ta=["BP 180/120-க்கு மேல் இருத்தல்", "கடுமையான தலைவலியுடன் மார்பு வலி அல்லது பார்வை மங்குதல்"],
        red_flags_tanglish=["BP 180/120-ku mela irundha", "Kadu thalavali-yodu nenju vali illa kannu theriyala-na"],
        triage_question_en="What was your last blood pressure reading, and are you taking BP tablets regularly?",
        triage_question_ta="கடைசியாக எடுத்த ரத்த அழுத்த அளவு என்ன? வழக்கமாக பிபி மாத்திரை சாப்பிடுகிறீர்களா?",
        triage_question_tanglish="Last-ah check panna BP reading evlo, regular-ah tablet edukureengala?",
        recommended_specialty="Cardiologist",
        relevant_service_keywords=["Cardiology Consultation & ECG", "General Physician Consultation"],
        relevant_tests=["Blood Pressure Monitoring", "Lipid Profile", "ECG", "Serum Creatinine"],
        source_attribution="ICMR Guidelines for Management of Hypertension",
    ),

    # 7. Heart Health & Palpitations
    MedicalTopic(
        id="heart_health",
        category="cardiovascular",
        name_en="Heart Health & Palpitations",
        name_ta="இதய நலம் மற்றும் படபடப்பு",
        name_tanglish="Heart Health & Palpitations",
        aliases=[
            "heart health", "palpitations", "rapid heartbeat", "heart beating fast",
            "irregular heartbeat", "heart checkup", "nenju padapadapu", "padapadapu",
            "nenju adichikudhu", "heart rate", "pulse adhigama irukku",
            "இதய படபடப்பு", "படபடப்பு", "இதய நலம்", "நெஞ்சு படபடப்பு",
            "gunde kottukovadam", "gunde thakudu",
        ],
        explanation_en="Heart palpitations are sensations of a racing, fluttering, or pounding heart, caused by anxiety, caffeine, dehydration, thyroid issues, or arrhythmias.",
        explanation_ta="இதய படபடப்பு என்பது இதயம் வேகமாக அல்லது சீரற்ற முறையில் துடிப்பது போன்ற உணர்வு; பதட்டம், காபி, நீர்ச்சத்து குறைவு அல்லது இதய கோளாறுகளால் வரலாம்.",
        explanation_tanglish="Palpitations heart vegama illa irregular-ah thudikira unarvu, anxiety, dehydration, thyroid illa cardiac rhythm aala varalaam.",
        home_care_en="Sit down calmly, take deep slow breaths, drink a glass of water, and avoid caffeine, tobacco, and stress.",
        home_care_ta="அமைதியாக அமர்ந்து மெதுவாக மூச்சை உள்ளிழுத்து விடுங்கள், தண்ணீர் அருந்துங்கள், காபியைத் தவிர்க்கவும்.",
        home_care_tanglish="Amaidhiya ukaarndhu deep breath edunga, water kudinga, coffee avoid pannunga.",
        red_flags_en=["Acute chest pain radiating to left arm, neck, or jaw", "Palpitations accompanied by fainting, severe dizziness, or shortness of breath (EMERGENCY - Call 108!)"],
        red_flags_ta=["இடது கை அல்லது தாடைக்கு பரவும் நெஞ்சு வலி", "படபடப்புடன் மயக்கம் அல்லது மூச்சுத் திணறல் (அவசர உதவி 108 அழைக்கவும்!)"],
        red_flags_tanglish=["Idadhu kai illa kazhuthukku paravura nenju vali", "Padapadapu-yodu mayakkam vandha (Emergency - 108 call pannunga!)"],
        triage_question_en="Does the racing heartbeat happen with dizziness or chest pain, and how long does it last?",
        triage_question_ta="படபடப்புடன் தலைசுற்றல் அல்லது நெஞ்சு வலி உள்ளதா? எவ்வளவு நேரம் நீடிக்கிறது?",
        triage_question_tanglish="Padapadapu thalasuthal illa nenju vali-yodu varudha, evlo neram irukku?",
        recommended_specialty="Cardiologist",
        relevant_service_keywords=["Cardiology Consultation & ECG"],
        relevant_tests=["ECG (Electrocardiogram)", "2D Echocardiogram", "Thyroid Profile (TSH)", "Serum Electrolytes"],
        source_attribution="WHO Cardiovascular Diseases Management Protocols",
    ),

    # 8. Respiratory Problems & Asthma
    MedicalTopic(
        id="respiratory_asthma",
        category="respiratory",
        name_en="Respiratory Health & Asthma",
        name_ta="சுவாசக் கோளாறு மற்றும் ஆஸ்துமா",
        name_tanglish="Breathing & Asthma",
        aliases=[
            "breathing problem", "shortness of breath", "wheezing", "asthma", "breathlessness",
            "moochu vida kashtam", "moochu thinaral", "wheezing irukku", "inhaler",
            "moochu muttudhu", "moochu vaangudhu", "asthma problem",
            "சுவாசக் கோளாறு", "மூச்சுத் திணறல்", "ஆஸ்துமா", "இழுப்பு", "சுவாசிப்பதில் சிரமம்",
            "oopiri aadatledu", "aayasam", "asthma",
        ],
        explanation_en="Breathing difficulties or wheezing occur when airways narrow or inflame due to asthma, allergies, dust, smoke, or respiratory infections.",
        explanation_ta="ஆஸ்துமா, தூசு, புகை அல்லது ஒவ்வாமை காரணமாக மூச்சுக்குழாய் சுருங்குவதால் மூச்சுத் திணறல் மற்றும் இழுப்பு ஏற்படுகிறது.",
        explanation_tanglish="Asthma, allergy, thoosi kaaranama moochukuzhai surunguradhala moochu thinaral and wheezing varum.",
        home_care_en="Sit upright, avoid dust, smoke, and cold air, use prescribed rescue inhalers if previously advised by a doctor, and keep calm.",
        home_care_ta="நேராக அமரவும், தூசி, புகை மற்றும் குளிர்ந்த காற்றைத் தவிர்க்கவும், மருத்துவர் பரிந்துரைத்த இன்ஹேலரை பயன்படுத்தவும்.",
        home_care_tanglish="Nera ukarunga, thoosi smoke avoid pannunga, doctor prescribe panna inhaler irundha eduthukonga.",
        red_flags_en=["Severe struggling to breathe or gasping", "Bluish tint on lips or fingernails", "Inability to speak words without pausing for breath (EMERGENCY - Call 108!)"],
        red_flags_ta=["பேச முடியாத அளவுக்கு கடுமையான மூச்சுத் திணறல்", "உதடுகள் நீல நிறமாதல் (அவசர உதவி 108 அழைக்கவும்!)"],
        red_flags_tanglish=["Pesa mudiyadha alavukku bayangara moochu thinaral", "Udhhadu blue aana (Emergency - 108 call pannunga!)"],
        triage_question_en="Do you have a known history of asthma or allergies, and does the wheezing worsen at night?",
        triage_question_ta="உங்களுக்கு ஏற்கனவே ஆஸ்துமா அல்லது ஒவ்வாமை உள்ளதா? இரவில் இழுப்பு அதிகமாகிறதா?",
        triage_question_tanglish="Unga-lukku munnadiye asthma illa allergy irukka, night-la adhigam aagudha?",
        recommended_specialty="General Physician",
        relevant_service_keywords=["General Physician Consultation", "Cardiology Consultation & ECG"],
        relevant_tests=["Spirometry (PFT)", "Chest X-Ray", "Pulse Oximetry (SpO2)"],
        source_attribution="WHO Chronic Respiratory Diseases Management",
    ),

    # 9. Digestive Problems: Acidity, GERD & Gastritis
    MedicalTopic(
        id="digestive_acidity_gerd",
        category="gastrointestinal",
        name_en="Acidity, GERD & Gastric Problems",
        name_ta="அசிடிட்டி, நெஞ்செரிச்சல் மற்றும் வாயுத் தொல்லை",
        name_tanglish="Acidity, Gas & Heartburn",
        aliases=[
            "acidity", "gas", "gas trouble", "gerd", "acid reflux", "heartburn", "indigestion",
            "bloating", "erichal", "nenjerichal", "nenju erichal", "vayiru erichal", "gastric",
            "gastric problem", "vayiru baram", "vayiru vali gas", "belching", "sour burps",
            "அசிடிட்டி", "நெஞ்செரிச்சல்", "வாயுத் தொல்லை", "செரிமானக் கோளாறு", "புளித்த ஏப்பம்",
            "gas problem", "kallu noppi", "acid reflux",
        ],
        explanation_en="Acidity occurs when stomach acid irritates the stomach lining or flows back into the food pipe, causing burning in the chest or upper abdomen.",
        explanation_ta="வயிற்று அமிலம் உணவுப் பாதைக்குள் பின்னோக்கி வருவதால் நெஞ்செரிச்சல், வாயு மற்றும் வயிற்றெரிச்சல் ஏற்படுகிறது.",
        explanation_tanglish="Stomach acid food pipe-la mela varadhala nenjerichal, gas and vayiru erichal varudhu.",
        home_care_en="Eat smaller frequent meals, avoid lying down for 2 hours after eating, avoid spicy and oily foods, and drink adequate water.",
        home_care_ta="காரமான மற்றும் எண்ணெயில் பொரித்த உணவுகளைத் தவிர்க்கவும், சாப்பிட்ட உடன் படுக்க வேண்டாம், சீரான இடைவெளியில் உண்ணவும்.",
        home_care_tanglish="Kaaram, oily food thavirkavum, saapta udane padukadhaeenga, konjam konjama saapdunga.",
        red_flags_en=["Difficulty swallowing food", "Black tarry stools or vomiting blood", "Severe crushing chest pain (must rule out heart attack!)"],
        red_flags_ta=["உணவை விழுங்குவதில் சிரமம்", "கருப்பு நிற மலம் அல்லது ரத்த வாந்தி", "கடுமையான நெஞ்சு வலி"],
        red_flags_tanglish=["Food vizhunguradhula kashtam", "Karuppa stool povadhu illa raththa vaandhi", "Kadu nenju vali"],
        triage_question_en="Do you feel the burning mostly after meals or when lying down, and is there any stomach pain?",
        triage_question_ta="சாப்பிட்ட பிறகு நெஞ்செரிச்சல் அதிகமாகிறதா? படுக்கும்போது ஏற்படுகிறதா?",
        triage_question_tanglish="Saapta apram nenjerichal varudha illa padukum bodhu varudha, vayiru vali irukka?",
        recommended_specialty="General Physician",
        relevant_service_keywords=["General Physician Consultation"],
        relevant_tests=["Ultrasound Abdomen", "Endoscopy if chronic", "H. Pylori Serology"],
        source_attribution="MoHFW Clinical Pathways for Dyspepsia & GERD",
    ),

    # 10. Digestive Problems: Diarrhea, Vomiting & Food Poisoning
    MedicalTopic(
        id="digestive_diarrhea_vomiting",
        category="gastrointestinal",
        name_en="Diarrhea, Vomiting & Stomach Infection",
        name_ta="வயிற்றுப்போக்கு, வாந்தி மற்றும் தொற்று",
        name_tanglish="Loose Motion & Vomiting",
        aliases=[
            "diarrhea", "loose motion", "loose stools", "vomiting", "stomach upset", "food poisoning",
            "stomach infection", "watery stools", "gastroenteritis", "loose motion aagudhu",
            "vaandhi", "bhedhi", "vayiru sari illa", "vayiru valikudhu loose motion",
            "வயிற்றுப்போக்கு", "வாந்தி", "சீதபேதி", "வயிற்று வலி", "உணவு நச்சு",
            "virochanalu", "vanthulu", "kadupu noppi",
        ],
        explanation_en="Diarrhea and vomiting are commonly caused by acute viral, bacterial, or foodborne gastrointestinal infections, risking dehydration.",
        explanation_ta="வயிற்றுப்போக்கு மற்றும் வாந்தி என்பது அசுத்தமான உணவு அல்லது நீரால் ஏற்படும் குடல் தொற்று, இதனால் நீர்ச்சத்து இழப்பு ஏற்படலாம்.",
        explanation_tanglish="Loose motion and vomiting contaminated food illa water aala varra stomach infection, dehydrate aaga chance irukku.",
        home_care_en="Drink Oral Rehydration Salts (ORS) solution regularly after each loose stool, have tender coconut water or rice congee, and avoid milk and spicy foods.",
        home_care_ta="ஒவ்வொரு முறையும் ORS குளுக்கோஸ் கரைசல் அல்லது இளநீர், கஞ்சி அருந்துங்கள், பால் உணவுகளைத் தவிர்க்கவும்.",
        home_care_tanglish="Ovvoru muraiyum ORS solution illa ilaneer, kanji kudinga, paal tea oily food avoid pannunga.",
        red_flags_en=["Inability to retain any liquids", "Blood in stools", "High fever with severe dehydration (extreme dry mouth, no urine for 8+ hours, sunken eyes)"],
        red_flags_ta=["தண்ணீர் கூட குடிக்க முடியாத வாந்தி", "மலத்தில் ரத்தம்", "8 மணி நேரத்திற்கு மேல் சிறுநீர் வெளியேறாமை"],
        red_flags_tanglish=["Thanni kooda kudinga mudiyama vaandhi", "Stool-la raththam", "8 maninerama urine pogala"],
        triage_question_en="How many episodes of loose stools have you had today, and are you able to drink water?",
        triage_question_ta="இன்று எத்தனை முறை வயிற்றுப்போக்கு ஏற்பட்டது? தண்ணீர் குடிக்க முடிகிறதா?",
        triage_question_tanglish="Iniku ethana thadava loose motion aachu, water kooda retain panna mudiyudha?",
        recommended_specialty="General Physician",
        relevant_service_keywords=["General Physician Consultation"],
        relevant_tests=["Stool Routine & Microscopy", "Serum Electrolytes"],
        source_attribution="WHO Diarrhoeal Disease Fact Sheets & IMAI Guidelines",
    ),

    # 11. Skin Conditions, Rashes & Allergies
    MedicalTopic(
        id="skin_conditions_allergy",
        category="dermatology",
        name_en="Skin Conditions, Rashes & Allergies",
        name_ta="தோல் நோய், அரிப்பு மற்றும் ஒவ்வாமை",
        name_tanglish="Skin Rash, Itching & Allergy",
        aliases=[
            "skin rash", "skin allergy", "itching", "itching skin", "skin doctor", "dermatologist",
            "hives", "fungal infection", "ringworm", "eczema", "pimples", "acne", "boils",
            "arippu", "thadippu", "skin problem", "skin infection", "skin doctor irukaara",
            "தோல் அரிப்பு", "தடிப்பு", "தோல் நோய்", "படை", "முகப்பரு", "ஒவ்வாமை",
            "chirma vyadhi", "dula", "rash",
        ],
        explanation_en="Skin rashes and itching are commonly triggered by allergic reactions, fungal infections, eczema, insect bites, or heat rash.",
        explanation_ta="தோல் அரிப்பு மற்றும் தடிப்பு என்பது ஒவ்வாமை, பூஞ்சை தொற்று அல்லது எக்ஸிமா போன்ற காரணங்களால் ஏற்படுகிறது.",
        explanation_tanglish="Skin rash and arippu allergy, fungal infection, padai illa eczema aala vara koodiya dermatological issues.",
        home_care_en="Keep the skin clean and dry, wear loose breathable cotton clothing, avoid scratching the lesions, and avoid harsh scented soaps.",
        home_care_ta="தோலை சுத்தமாகவும் உலர்வாகவும் வையுங்கள், பருத்தி ஆடைகளை அணியுங்கள், சொறிவதைத் தவிர்க்கவும்.",
        home_care_tanglish="Skin clean and dry-ah vechikonga, loose cotton dress podunga, soriyadhaeenga.",
        red_flags_en=["Rapidly spreading rash with fever or facial/lip swelling (Anaphylaxis emergency!)", "Blistering covering large areas of the body", "Pus oozing with severe local heat and pain"],
        red_flags_ta=["முகத்தில் வீக்கம் மற்றும் மூச்சுத் திணறலுடன் பரவும் தடிப்பு", "தோல் கொப்புளங்கள் மற்றும் சீழ் வடிதல்"],
        red_flags_tanglish=["Mugam veengi moochu thinaral-odu rash vandha", "Koppulam vandhu seel vadinja"],
        triage_question_en="Where on the body is the rash located, and did it appear after using any new product or food?",
        triage_question_ta="தடிப்பு உடலின் எந்தப் பகுதியில் உள்ளது? புதிதாக ஏதேனும் உணவு அல்லது மருந்து சாப்பிட்டீர்களா?",
        triage_question_tanglish="Rash udambula enga irukku, pudhidha edhavadhu food saaptingala?",
        recommended_specialty="Dermatologist",
        relevant_service_keywords=["General Physician Consultation", "Doctor Consultation"],
        source_attribution="MoHFW Standard Treatment Guidelines in Dermatology",
    ),

    # 12. Children's Health & Pediatric Care
    MedicalTopic(
        id="pediatric_child_health",
        category="pediatrics",
        name_en="Children's Health & Pediatric Care",
        name_ta="குழந்தை நலம் மற்றும் பராமரிப்பு",
        name_tanglish="Pediatric & Child Health",
        aliases=[
            "child fever", "baby fever", "child cough", "baby cold", "kid sick", "baby not well",
            "pediatrician", "child specialist", "baby doctor", "kulandhai maruthuvar",
            "kulandhai ku kaachal", "paapa ku kaachal", "paapa ku udambu mudiyala",
            "baby vaandhi", "baby loose motion", "kulandhai doctor",
            "குழந்தைக்கு காய்ச்சல்", "குழந்தை நலம்", "குழந்தை மருத்துவர்", "குழந்தைக்கு சளி",
            "pillala doctor", "biddaku jwaram", "pediatrician",
        ],
        explanation_en="Children have developing immune systems; pediatric illness requires gentle supportive hydration, fever monitoring, and timely pediatric consultation.",
        explanation_ta="குழந்தைகளின் நோய் எதிர்ப்பு சக்தி வளர்ச்சியடையும் நிலை; கவனமான பராமரிப்பு, காய்ச்சல் கண்காணிப்பு மற்றும் குழந்தை மருத்துவர் ஆலோசனை அவசியம்.",
        explanation_tanglish="Kuzhandhaigalukku immune system valarndhu varum stage; fever and hydration-ai kavanama monitor panni pediatrician-ai paarpadhu mukkiyam.",
        home_care_en="Offer frequent small sips of fluids (breast milk for infants, water/ORS for older kids), dress in light clothes. CRITICAL: NEVER give Aspirin to children due to fatal Reye's syndrome risk!",
        home_care_ta="தொடர்ந்து தாய்ப்பால் அல்லது திரவ உணவுகள் கொடுங்கள், லேசான பருத்தி ஆடைகளை அணிவியுங்கள். குழந்தைகளுக்கு ஒருபோதும் ஆஸ்பிரின் மருந்து கொடுக்கக்கூடாது!",
        home_care_tanglish="Thodarnthu fluids/paal kudunga, light cotton dress podunga. Mukkiyama kuzhandhaigalukku Aspirin tablet eppodhume tharakoodadhu!",
        red_flags_en=["Baby is unusually lethargic, unresponsive, or difficult to wake", "Rapid breathing with chest caving in (retractions)", "Child refuses all fluids and passes no urine for 6+ hours", "High fever with purplish rash"],
        red_flags_ta=["குழந்தை சோர்வாகவோ அல்லது சுயநினைவற்றோ இருத்தல்", "வேகமாக மூச்சு வாங்குதல்", "தண்ணீர் கூட குடிக்க மறுத்தல்"],
        red_flags_tanglish=["Kulandhai romba thalarnthu mayakkama irundha", "Vegama moochu vaanguna", "Water kooda kudikka mudiyama azhudha"],
        triage_question_en="How old is the child, and are they active and taking fluids normally?",
        triage_question_ta="குழந்தைக்கு என்ன வயது? சுறுசுறுப்பாக விளையாடுகிறாரா, பால் அல்லது தண்ணீர் குடிக்கிறாரா?",
        triage_question_tanglish="Kuzhandhaiku enna vayasu, active-ah irukaangala, fluids eduthukuraangala?",
        recommended_specialty="Pediatrician",
        relevant_service_keywords=["Pediatric Health Checkup", "Pediatrician"],
        relevant_tests=["Pediatric Blood Count", "Urine Examination"],
        source_attribution="WHO Pocket Book of Hospital Care for Children",
    ),

    # 13. Women's Health & Pregnancy Precautions
    MedicalTopic(
        id="womens_health_pregnancy",
        category="gynecology",
        name_en="Women's Health & Pregnancy",
        name_ta="பெண்கள் நலம் மற்றும் கர்ப்ப கால பராமரிப்பு",
        name_tanglish="Women's Health & Pregnancy",
        aliases=[
            "period pain", "menstrual cramps", "irregular periods", "pcos", "pregnancy",
            "pregnant", "morning sickness", "gynecologist", "womens doctor", "lady doctor",
            "maadhavidhaai vali", "vayiru vali periods", "periods problem", "pregnancy checkup",
            "மாதவிடாய் வலி", "பெண்கள் மருத்துவர்", "கர்ப்ப கால பராமரிப்பு", "ஒழுங்கற்ற மாதவிடாய்",
            "periods noppi", "garbhavathi", "gynecologist",
        ],
        explanation_en="Women's health covers menstrual wellness, hormonal balance like PCOS, reproductive wellness, and antenatal care.",
        explanation_ta="பெண்கள் நலம் என்பது மாதவிடாய் சுகாதாரம், ஹார்மோன் சமநிலை, கருவுறுதல் மற்றும் கர்ப்ப கால ஆரோக்கியத்தை உள்ளடக்கியது.",
        explanation_tanglish="Women's health menstrual health, PCOS hormonal balance and pregnancy antenatal care patriyadhagum.",
        home_care_en="For normal menstrual cramps: apply a warm water heating pad to the lower abdomen, stay well hydrated, and do gentle walking.",
        home_care_ta="மாதவிடாய் வலிக்கு அடிவயிற்றில் வெந்நீர் ஒத்தடம் கொடுக்கலாம், தண்ணீர் அதிகம் அருந்தவும்.",
        home_care_tanglish="Normal periods pain-ku warm water bag vekkalaam, nallaa water kudinga.",
        red_flags_en=["Any vaginal bleeding or severe abdominal cramping during pregnancy (EMERGENCY!)", "Severe pelvic pain with high fever", "Sudden heavy bleeding soaking more than 2 pads per hour"],
        red_flags_ta=["கர்ப்ப காலத்தில் ரத்தப்போக்கு அல்லது கடுமையான வயிற்று வலி (உடனடி அவசர சிகிச்சை தேவை!)", "கடுமையான உதிரப்போக்கு"],
        red_flags_tanglish=["Pregnancy time-la raththa pokku illa bayangara vayiru vali vandha (Emergency - udane hospital ponga!)"],
        triage_question_en="Are you experiencing severe cramping or irregular cycles, and is there any chance of pregnancy?",
        triage_question_ta="மாதவிடாய் சுழற்சியில் மாற்றம் உள்ளதா? கர்ப்பமாக இருக்க வாய்ப்புள்ளதா?",
        triage_question_tanglish="Periods cycle irregular-ah irukka, pregnancy edhavadhu irukka?",
        recommended_specialty="Gynecologist",
        relevant_service_keywords=["General Physician Consultation", "Doctor Consultation"],
        relevant_tests=["Pelvic Ultrasound", "Beta-hCG", "Thyroid & Prolactin Profile", "Hemoglobin"],
        source_attribution="WHO Antenatal Care Guidelines & MoHFW Maternal Health Standards",
    ),

    # 14. Common Diagnostic Tests & Preparation
    MedicalTopic(
        id="diagnostic_tests",
        category="diagnostics",
        name_en="Common Diagnostic Tests & Preparation",
        name_ta="மருத்துவப் பரிசோதனைகள் மற்றும் தயாரிப்பு",
        name_tanglish="Medical Blood Tests & Diagnostics",
        aliases=[
            "blood test", "cbc", "complete blood count", "sugar test", "fasting test",
            "hba1c", "lipid profile", "cholesterol test", "ecg", "urine test",
            "thyroid test", "tsh", "ultrasound", "scan", "test timing", "fasting irukanuma",
            "blood test eppadi edukannum", "lab test", "lab timing",
            "ரத்தப் பரிசோதனை", "பரிசோதனை விவரங்கள்", "ஈசிஜி", "ஸ்கேன்", "சிறுநீர் பரிசோதனை",
            "blood test", "sugar test", "lab tests",
        ],
        explanation_en="Diagnostic tests evaluate organ function and screen for health conditions: Fasting Sugar requires 8-10 hours fasting; Lipid Profile requires 10-12 hours; HbA1c and CBC do not require fasting.",
        explanation_ta="மருத்துவப் பரிசோதனை விவரங்கள்: வெறும் வயிற்று சர்க்கரைக்கு 8-10 மணி நேரம், கொலஸ்ட்ரால் பரிசோதனைக்கு 10-12 மணி நேரம் விரதம் தேவை; CBC மற்றும் HbA1c-க்கு விரதம் தேவையில்லை.",
        explanation_tanglish="Diagnostic tests: Fasting sugar-ku 8-10 hours fasting thevai, Lipid profile-ku 10-12 hours fasting thevai; CBC and HbA1c-ku fasting thevaillai.",
        home_care_en="Drink plain water during fasting periods to stay hydrated, take regular morning blood pressure medicines unless instructed otherwise by the doctor.",
        home_care_ta="விரதத்தின் போது தண்ணீர் மட்டும் குடிக்கலாம், மருத்துவர் கூறியபடி வழக்கமான பிபி மருந்துகளை எடுத்துக்கொள்ளலாம்.",
        home_care_tanglish="Fasting time-la normal water kooda kudikalaam, regular BP tablets eduthukolaam.",
        red_flags_en=["Severe dizziness or fainting during blood draw", "Critically abnormal lab values like potassium > 6.0 or hemoglobin < 7.0"],
        red_flags_ta=["ரத்தம் எடுக்கும் போது அதிக மயக்கம்", "அபாயகரமான அளவு முடிவுகள்"],
        red_flags_tanglish=["Blood edukumbodhu mayakkam", "Reports-la critical abnormal values"],
        triage_question_en="Which specific medical test did your doctor advise, and do you know if fasting is needed?",
        triage_question_ta="மருத்துவர் எந்தப் பரிசோதனையை பரிந்துரைத்தார்? விரதம் இருக்க வேண்டுமா என்று தெரியுமா?",
        triage_question_tanglish="Doctor endha test panna sonnaanga, fasting thevaiya nu theriyuma?",
        recommended_specialty="General Physician",
        relevant_service_keywords=["Full Body Blood Diagnostics", "Cardiology Consultation & ECG"],
        relevant_tests=["CBC", "FBS", "PPBS", "HbA1c", "Lipid Profile", "Thyroid Profile", "Urine Routine", "ECG"],
        source_attribution="ICMR Standards for Clinical Diagnostic Laboratories",
    ),

    # 15. General Medicine Information & Drug Classes
    MedicalTopic(
        id="general_medicine_info",
        category="pharmacotherapy",
        name_en="General Medicine Information & Safety",
        name_ta="மருந்துகள் மற்றும் பாதுகாப்பு விவரங்கள்",
        name_tanglish="General Medicine Info & Safety",
        aliases=[
            "paracetamol", "dolo", "tablet", "medicine", "antibiotic", "painkiller",
            "cough syrup", "antacid", "gelusil", "pantoprazole", "cetirizine", "tablet podalama",
            "enna maathirai podalam", "tablet eppo podanum", "medicine name",
            "மாத்திரை", "மருந்து", "பாராசிட்டமால்", "வலி நிவாரணி", "ஆன்டிபயாடிக்",
            "mandhulu", "tablet", "paracetamol",
        ],
        explanation_en="Common generic drug classes include Antipyretics (e.g. Paracetamol) for fever/pain, Antacids/PPIs for stomach acid, ORS for dehydration, and Antihistamines for allergies. As an AI receptionist, I cannot prescribe medicines or dosages.",
        explanation_ta="பொதுவான மருந்துகள்: காய்ச்சல் மற்றும் வலிக்கு பாராசிட்டமால், அசிடிட்டிக்கு அமில எதிர்ப்பு மருந்துகள், நீர்ச்சத்து இழப்பிற்கு ORS. AI என்பதால் மாத்திரை பரிந்துரைக்க இயலாது.",
        explanation_tanglish="Common medicines: Fever-ku Paracetamol, acidity-ku Antacid, dehydration-ku ORS. Aana AI receptionist aala direct tablet prescribe panna mudiyadhu.",
        home_care_en="Always take medications exactly as prescribed by your doctor. Never take leftover antibiotics without a doctor's prescription.",
        home_care_ta="மருத்துவர் பரிந்துரைத்தபடி மட்டுமே மருந்துகளை உண்ணவும், பழைய ஆன்டிபயாடிக் மருந்துகளை சுயமாக உட்கொள்ளக் கூடாது.",
        home_care_tanglish="Doctor sonna maadhiri mattume tablet saapdunga, self-medication thavirkavum.",
        red_flags_en=["Adverse drug reaction (facial swelling, body rash, difficulty breathing)", "Accidental overdose or poisoning (Call 108 immediately!)"],
        red_flags_ta=["மருந்து சாப்பிட்டதும் உடலில் ஒவ்வாமை தடிப்பு அல்லது மூச்சுத் திணறல் ஏற்படுதல்", "அதிக அளவு மருந்து உட்கொள்ளுதல் (அவசர உதவி 108 அழைக்கவும்!)"],
        red_flags_tanglish=["Tablet saaptadhum allergy aagi mugam veengina (Emergency - 108 call pannunga!)"],
        triage_question_en="What symptoms are you looking to treat, and do you have any drug allergies?",
        triage_question_ta="எந்த பிரச்சனைக்காக மருந்து கேட்கிறீர்கள்? உங்களுக்கு ஏதேனும் மருந்து ஒவ்வாமை உள்ளதா?",
        triage_question_tanglish="Endha symptom-ku tablet kekureenga, edhavadhu medicine allergy irukka?",
        recommended_specialty="General Physician",
        relevant_service_keywords=["General Physician Consultation", "Doctor Consultation"],
        source_attribution="WHO Essential Medicines List & MoHFW Rational Drug Use Guidelines",
    ),

    # 16. Preventive Healthcare & Wellness
    MedicalTopic(
        id="preventive_wellness",
        category="preventive",
        name_en="Preventive Healthcare & Wellness",
        name_ta="தடுப்பு ஆரோக்கியம் மற்றும் நல்வாழ்வு",
        name_tanglish="Preventive Health & Wellness",
        aliases=[
            "health checkup", "master health checkup", "preventive care", "routine checkup",
            "annual checkup", "wellness", "diet tips", "general health", "full body checkup",
            "முழு உடல் பரிசோதனை", "உடல் நலம்", "வருடாந்திர பரிசோதனை", "ஆரோக்கிய குறிப்புகள்",
            "master health checkup", "health checkup",
        ],
        explanation_en="Preventive healthcare focuses on early detection of diabetes, hypertension, and heart disease through regular screening, healthy nutrition, and exercise.",
        explanation_ta="தடுப்பு ஆரோக்கியம் என்பது வருடாந்திர பரிசோதனை, ஆரோக்கிய உணவு மற்றும் உடற்பயிற்சி மூலம் வாழ்க்கை முறை நோய்களை ஆரம்பத்திலேயே கண்டறிவதாகும்.",
        explanation_tanglish="Preventive care enbadhu annual checkup, healthy food and exercise moolam BP, sugar, heart problem-ai early-ah kandupidipadhu aagum.",
        home_care_en="Engage in 30 minutes of moderate exercise daily, consume a balanced diet rich in whole grains and vegetables, sleep 7-8 hours, and undergo annual wellness screening.",
        home_care_ta="தினமும் 30 நிமிடம் நடைப்பயிற்சி செய்யுங்கள், காய்கறி கீரைகளை அதிகம் உண்ணுங்கள், 7-8 மணி நேரம் தூங்குங்கள்.",
        home_care_tanglish="Daily 30 mins walking ponga, fresh vegetables saapdunga, 7-8 hours nallaa thoongunga.",
        red_flags_en=["Unexplained rapid weight loss", "Persistent unexplained fatigue", "Chronic changes in bowel or bladder habits"],
        red_flags_ta=["காரணமின்றி உடல் எடை குறைதல்", "நீடித்த கடுமையான சோர்வு"],
        red_flags_tanglish=["Kaaranam illama udambu edai koranjirundha", "Thodarndhu bayangara tired-ah irundha"],
        triage_question_en="When was your last comprehensive health checkup, and would you like to schedule one?",
        triage_question_ta="கடைசியாக எப்போது முழு உடல் பரிசோதனை செய்தீர்கள்? எங்கள் கிளினிக்கில் முன்பதிவு செய்யவா?",
        triage_question_tanglish="Last-ah eppo full body health checkup panninga, namma clinic-la arrange pannava?",
        recommended_specialty="General Physician",
        relevant_service_keywords=["Full Body Blood Diagnostics", "General Physician Consultation"],
        relevant_tests=["CBC", "Lipid Profile", "Liver Function", "Kidney Function", "HbA1c", "ECG"],
        source_attribution="WHO Non-Communicable Diseases Prevention Framework",
    ),
]

CLINICAL_KNOWLEDGE_TOPICS: list[MedicalTopic] = MEDICAL_TOPICS_CATALOG


# ==============================================================================
# Clinical Knowledge Query & Match Engine
# ==============================================================================

def query_medical_knowledge(query_text: str, caller_language: str = "en-IN") -> MedicalTopic | None:
    """Match caller speech against medically reviewed topics using exact, token, and fuzzy similarity.

    Supports code-mixed Tanglish, pure Tamil Unicode script, and conversational English.
    """
    if not query_text or not query_text.strip():
        return None

    clean_query = query_text.lower().strip()
    # Normalize punctuation
    clean_norm = re.sub(r"[^\w\s\u0B80-\u0BFF\u0C00-\u0C7F]", " ", clean_query)
    tokens = [t for t in clean_norm.split() if len(t) >= 2]

    best_match: MedicalTopic | None = None
    best_score = 0.0

    for topic in MEDICAL_TOPICS_CATALOG:
        score = 0.0

        for alias in topic.aliases:
            alias_lower = alias.lower()

            # 1. Exact phrase substring match (highest confidence)
            if alias_lower in clean_query:
                # Give higher weight to longer matches
                match_weight = len(alias_lower.split()) * 3.0
                if match_weight > score:
                    score = match_weight

            # 2. Token overlap
            alias_tokens = alias_lower.split()
            matched_tokens = sum(1 for t in tokens if t in alias_tokens)
            if matched_tokens > 0:
                token_score = matched_tokens * 1.5
                if token_score > score:
                    score = token_score

            # 3. Fuzzy ratio for slightly misspelled spoken words
            if len(alias_lower) >= 4 and len(clean_query) >= 4:
                ratio = SequenceMatcher(None, alias_lower, clean_query).ratio()
                if ratio >= 0.75:
                    fuzzy_score = ratio * 2.0
                    if fuzzy_score > score:
                        score = fuzzy_score

            # Demographic and clinical context boosts
            if topic.id == "diabetes_blood_sugar" and any(p in clean_norm for p in ["sugar", "diabetes", "diabetic", "சர்க்கரை", "sugar level", "blood sugar"]):
                score += 5.0
            elif topic.id == "hypertension_blood_pressure" and any(p in clean_norm for p in ["blood pressure", "bp", "இரத்த அழுத்தம்", "high bp", "low bp"]):
                score += 5.0
            elif topic.id == "digestive_acidity_gerd" and any(p in clean_norm for p in ["reflux", "acid", "heartburn", "acidity", "நெஞ்செரிச்சல்"]):
                score += 5.0
            elif topic.id == "pediatric_child_health" and any(p in clean_norm for p in ["baby", "child", "kulandhai", "paapa", "குழந்தை", "பாப்பா", "kid", "pillala"]):
                score += 5.0
            elif topic.id == "womens_health_pregnancy" and any(p in clean_norm for p in ["pregnant", "pregnancy", "period", "periods", "மாதவிடாய்", "கர்ப்ப"]):
                score += 5.0
            elif topic.id == "general_medicine_info" and any(p in clean_norm for p in ["paracetamol", "dolo", "antibiotic", "painkiller", "cetirizine", "pantoprazole", "tablet podalama", "tablet saapidalama", "ethana mg"]):
                score += 5.5
            elif topic.id == "preventive_wellness" and any(p in clean_norm for p in ["master health", "health checkup", "wellness", "preventive", "முழு உடல் பரிசோதனை", "routine checkup"]):
                score += 5.5
            elif topic.id == "diagnostic_tests" and any(p in clean_norm for p in ["test", "scan", "cbc", "lipid", "ecg", "ultrasound", "blood test", "பரிசோதனை"]) and not any(p in clean_norm for p in ["sugar", "diabetes", "period", "master health", "wellness"]):
                score += 3.5

        if score > best_score and score >= 2.0:
            best_score = score
            best_match = topic

    if best_match:
        logger.info(
            "Medical knowledge matched query '%s' to topic '%s' (score=%.2f, specialty=%s)",
            query_text[:40],
            best_match.id,
            best_score,
            best_match.recommended_specialty,
        )
    return best_match


def get_medical_guidance_for_response(
    topic: MedicalTopic,
    language: str = "en-IN",
    matching_services: list[dict[str, Any]] | None = None,
    matching_doctors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compile structured, medically responsible guidance for conversational telephony delivery.

    Returns:
    - explanation: 1 concise sentence explaining the symptom/condition.
    - home_care: 1 simple, safe home care action (hydration, rest).
    - red_flags: list of danger signs requiring immediate physical examination.
    - triage_question: exactly ONE relevant follow-up question.
    - recommended_service: matched tenant service name & price if available.
    - recommended_doctor: matched tenant doctor schedule if available.
    - disclaimer: clear statement that an examination by a doctor is required.
    """
    lang = (language or "en-IN").strip()

    if lang == "ta-Latn":
        explanation = topic.explanation_tanglish
        home_care = topic.home_care_tanglish
        red_flags = topic.red_flags_tanglish
        triage_q = topic.triage_question_tanglish
        disclaimer = "General educational info mattum thaan, doctor kitta consult pannuvadhu mukkiyam."
    elif lang.startswith("ta"):
        explanation = topic.explanation_ta
        home_care = topic.home_care_ta
        red_flags = topic.red_flags_ta
        triage_q = topic.triage_question_ta
        disclaimer = "இது பொதுவான தகவல் மட்டுமே. மருத்துவரிடம் முறையான பரிசோதனை பெறுவது அவசியம்."
    else:
        explanation = topic.explanation_en
        home_care = topic.home_care_en
        red_flags = topic.red_flags_en
        triage_q = topic.triage_question_en
        disclaimer = "This is general medical information. An in-person consultation with a doctor is necessary for accurate diagnosis and prescription."

    # Identify matching service from tenant catalog
    matched_service_info = None
    if matching_services:
        for s in matching_services:
            s_name = s.get("name", "")
            if any(k.lower() in s_name.lower() for k in topic.relevant_service_keywords):
                matched_service_info = s
                break
        if not matched_service_info and matching_services:
            # Fall back to general physician consultation
            matched_service_info = next(
                (s for s in matching_services if "general" in s.get("name", "").lower()),
                matching_services[0],
            )

    # Identify matching doctor from tenant staff schedule
    matched_doctor_info = None
    if matching_doctors:
        for d in matching_doctors:
            d_name = d.get("name", "")
            d_avail = d.get("availability", "")
            if topic.recommended_specialty.lower() in d_name.lower() or topic.recommended_specialty.lower() in d_avail.lower():
                matched_doctor_info = d
                break
        if not matched_doctor_info and matching_doctors:
            matched_doctor_info = next(
                (d for d in matching_doctors if "general" in d.get("name", "").lower() or "physician" in d.get("name", "").lower()),
                matching_doctors[0],
            )

    return {
        "topic_id": topic.id,
        "category": topic.category,
        "specialty": topic.recommended_specialty,
        "explanation": explanation,
        "home_care": home_care,
        "red_flags": red_flags,
        "triage_question": triage_q,
        "matched_service": matched_service_info,
        "matched_doctor": matched_doctor_info,
        "disclaimer": disclaimer,
        "relevant_tests": topic.relevant_tests,
        "source": topic.source_attribution,
    }


def format_medical_guidance_for_prompt(topic: MedicalTopic) -> str:
    """Format a matched clinical topic into a concise prompt guidance block for the LLM."""
    parts = [
        f"Topic: {topic.name_en} ({topic.name_tanglish} / {topic.name_ta})",
        f"Category: {topic.category}",
        f"Clinical Overview: {topic.explanation_en}",
        f"Supportive Home Care: {topic.home_care_en}",
        f"Red Flags requiring emergency escalation: {', '.join(topic.red_flags_en)}",
        f"Recommended Department / Doctor: {topic.recommended_specialty}",
    ]
    if topic.relevant_tests:
        parts.append(f"Relevant Tests: {', '.join(topic.relevant_tests)}")
    parts.append(f"Clinical Source: {topic.source_attribution}")
    return "\n".join(parts)
