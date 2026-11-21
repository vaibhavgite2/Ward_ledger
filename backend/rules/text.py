"""Neutral, template-rendered text for public findings (SPEC §6.4), in en / mr / hi.

Style guide (enforced by tests): describe what the records show; never use verdict words
(fraud, scam, suspicious, corrupt ...). "Risk flag" wording exists only in OFFICER_LABEL.
"""
from __future__ import annotations

LANGS = ["en", "mr", "hi"]

_DEV_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")


def inr(n) -> str:
    """Indian digit grouping: 1234567 -> 12,34,567"""
    n = int(round(float(n)))
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return ("-" if n < 0 else "") + s


TEMPLATES: dict[str, dict[str, str]] = {
    "rate_card_overrun": {
        "en": "Billed ₹{cost}, which is {pct}% above the standard rate of ₹{expected} for {method}.",
        "mr": "{method} साठी ₹{expected} या प्रमाण दरापेक्षा {pct}% जास्त, म्हणजे ₹{cost} बिल केले गेले.",
        "hi": "{method} के लिए ₹{expected} की मानक दर से {pct}% अधिक, यानी ₹{cost} का बिल बनाया गया।",
    },
    "possible_double_billing": {
        "en": "Two repairs of the same type were billed on this road within {days} days of each other; the second has no linked complaint.",
        "mr": "या रस्त्यावर एकाच प्रकारची दोन कामे {days} दिवसांच्या आत बिल केली गेली; दुसऱ्या कामाशी कोणतीही तक्रार जोडलेली नाही.",
        "hi": "इस सड़क पर एक ही प्रकार के दो काम {days} दिनों के भीतर बिल किए गए; दूसरे काम से कोई शिकायत जुड़ी नहीं है।",
    },
    "dlp_breach": {
        "en": "This road is recorded as still under the original contractor's warranty (Defect Liability Period); this repair was billed to BMC at ₹{cost}.",
        "mr": "हा रस्ता मूळ कंत्राटदाराच्या दोष दायित्व कालावधीत (Defect Liability Period) असल्याची नोंद आहे; तरीही हे काम ₹{cost} ला BMC कडे बिल केले गेले.",
        "hi": "इस सड़क के मूल ठेकेदार के दोष दायित्व काल (Defect Liability Period) में होने की प्रविष्टि है; फिर भी यह मरम्मत ₹{cost} पर BMC को बिल की गई।",
    },
    "sla_missed": {
        "en": "Completed {hours} hours after the complaint, against a target of {sla} hours.",
        "mr": "तक्रारीनंतर {hours} तासांत काम पूर्ण झाले; लक्ष्य {sla} तासांचे होते.",
        "hi": "शिकायत के {hours} घंटे बाद काम पूरा हुआ; लक्ष्य {sla} घंटे का था।",
    },
    "failed_within_30d": {
        "en": "This repair failed within 30 days and the problem was reported again.",
        "mr": "ही दुरुस्ती 30 दिवसांच्या आत अपयशी ठरली आणि समस्या पुन्हा नोंदवली गेली.",
        "hi": "यह मरम्मत 30 दिनों के भीतर विफल हो गई और समस्या फिर से दर्ज हुई।",
    },
    "estimate_drift": {
        "en": "Cost of ₹{unit} {per} compared with ₹{median} typical for {method} in this ward.",
        "mr": "या प्रभागात {method} साठी नेहमीच्या ₹{median} च्या तुलनेत ₹{unit} {per_mr}.",
        "hi": "इस वार्ड में {method} के सामान्य ₹{median} की तुलना में ₹{unit} {per_hi}।",
    },
    "never_fixed": {
        "en": "No repair has been linked to this complaint {days} days after it was filed.",
        "mr": "ही तक्रार नोंदवल्यानंतर {days} दिवसांनीही कोणतीही दुरुस्ती जोडलेली नाही.",
        "hi": "यह शिकायत दर्ज होने के {days} दिन बाद भी कोई मरम्मत जुड़ी नहीं है।",
    },
    "clean_record": {
        "en": "Clean record in ward {ward}: {n} completed repairs, billed within the standard rate, on time and holding up.",
        "mr": "प्रभाग {ward} मध्ये स्वच्छ नोंद: {n} पूर्ण झालेली कामे, प्रमाण दरात, वेळेत आणि टिकाऊ.",
        "hi": "वार्ड {ward} में साफ़ रिकॉर्ड: {n} पूरे किए गए काम, मानक दर में, समय पर और टिकाऊ।",
    },
}

# Officer framing only (never serialised to public endpoints)
OFFICER_LABEL = {
    "rate_card_overrun": "Risk flag: cost above rate card",
    "possible_double_billing": "Risk flag: possible double billing",
    "dlp_breach": "Risk flag: billed on road under DLP",
    "sla_missed": "SLA missed",
    "failed_within_30d": "Repair failed within 30 days",
    "estimate_drift": "Risk flag: estimate drift vs ward median",
    "never_fixed": "Complaint with no linked repair",
    "clean_record": "Clean record (positive)",
}

CATEGORY_L = {
    "Pothole": {"en": "Pothole", "mr": "खड्डा", "hi": "गड्ढा"},
    "Waterlogging": {"en": "Waterlogging", "mr": "पाणी साचणे", "hi": "जलभराव"},
    "Open or broken manhole": {"en": "Open or broken manhole", "mr": "उघडे/तुटलेले मॅनहोल", "hi": "खुला/टूटा मैनहोल"},
    "Choked drain / nullah overflow": {"en": "Choked drain / nullah overflow", "mr": "तुंबलेली गटारे / नाला ओव्हरफ्लो", "hi": "जाम नाली / नाला ओवरफ्लो"},
    "Road cave-in": {"en": "Road cave-in", "mr": "रस्ता खचणे", "hi": "सड़क धंसना"},
    "Broken paver blocks": {"en": "Broken paver blocks", "mr": "तुटलेले पेव्हर ब्लॉक", "hi": "टूटे पेवर ब्लॉक"},
    "Other": {"en": "Other", "mr": "इतर", "hi": "अन्य"},
}


def category(cat: str, lang: str) -> str:
    return CATEGORY_L.get(cat, {}).get(lang, cat)


PER = {"sqm": ("per sqm", "प्रति चौ.मी.", "प्रति वर्ग मीटर"), "job": ("per job", "प्रति काम", "प्रति कार्य")}

RULE_TITLES = {
    "rate_card_overrun": {"en": "Billed above standard rate", "mr": "प्रमाण दरापेक्षा जास्त बिल", "hi": "मानक दर से अधिक बिल"},
    "possible_double_billing": {"en": "Possible repeat billing", "mr": "पुन्हा बिल केल्याची शक्यता", "hi": "दोबारा बिल की संभावना"},
    "dlp_breach": {"en": "Road under warranty", "mr": "रस्ता वॉरंटीमध्ये", "hi": "सड़क वारंटी में"},
    "sla_missed": {"en": "Slower than target", "mr": "लक्ष्यापेक्षा उशीर", "hi": "लक्ष्य से देर"},
    "failed_within_30d": {"en": "Repair did not hold", "mr": "दुरुस्ती टिकली नाही", "hi": "मरम्मत टिकी नहीं"},
    "estimate_drift": {"en": "Cost above ward norm", "mr": "प्रभागाच्या सरासरीपेक्षा जास्त खर्च", "hi": "वार्ड औसत से अधिक लागत"},
    "never_fixed": {"en": "No repair linked", "mr": "दुरुस्ती जोडलेली नाही", "hi": "कोई मरम्मत जुड़ी नहीं"},
    "clean_record": {"en": "Clean record", "mr": "स्वच्छ नोंद", "hi": "साफ़ रिकॉर्ड"},
}


def render(rule: str, lang: str, **kw) -> str:
    t = TEMPLATES[rule][lang]
    return t.format(**kw)


def render_all(rule: str, **kw) -> dict[str, str]:
    return {lang: render(rule, lang, **kw) for lang in LANGS}
