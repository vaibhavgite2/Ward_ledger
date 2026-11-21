"""Neutral, trilingual text for notifications and automated checks in the live workflow.

Same style guide as rules/text.py: describe what the records show; never accuse.
"""
from __future__ import annotations

from rules import text as T

LANGS = ("en", "mr", "hi")

REJECT_REASON = {
    "not_bmc_road": {"en": "the road is not maintained by BMC", "mr": "हा रस्ता BMC च्या देखभालीखाली नाही", "hi": "यह सड़क BMC के रखरखाव में नहीं है"},
    "not_road_issue": {"en": "it is not a road, drain or footpath problem", "mr": "ही रस्ता, गटार किंवा पदपथाची समस्या नाही", "hi": "यह सड़क, नाली या फुटपाथ की समस्या नहीं है"},
    "insufficient_info": {"en": "there was not enough information to find the problem", "mr": "समस्या शोधण्यासाठी पुरेशी माहिती नव्हती", "hi": "समस्या खोजने के लिए पर्याप्त जानकारी नहीं थी"},
    "duplicate": {"en": "the same problem is already reported", "mr": "हीच समस्या आधीच नोंदवली आहे", "hi": "यही समस्या पहले से दर्ज है"},
    "other": {"en": "see the officer's note", "mr": "अधिकाऱ्याची टीप पहा", "hi": "अधिकारी की टिप्पणी देखें"},
}

NOTIFY = {
    "ticket_submitted": {
        "en": "Your complaint {ticket_id} was received. A ward officer will verify it.",
        "mr": "तुमची तक्रार {ticket_id} प्राप्त झाली. प्रभाग अधिकारी तिची पडताळणी करतील.",
        "hi": "आपकी शिकायत {ticket_id} प्राप्त हुई। वार्ड अधिकारी इसकी जाँच करेंगे।",
    },
    "new_ticket": {
        "en": "New complaint {ticket_id} ({category}) in ward {ward} is waiting for verification.",
        "mr": "प्रभाग {ward} मधील नवीन तक्रार {ticket_id} ({category}) पडताळणीसाठी प्रतीक्षेत आहे.",
        "hi": "वार्ड {ward} की नई शिकायत {ticket_id} ({category}) जाँच की प्रतीक्षा में है।",
    },
    "ticket_verified": {
        "en": "Your complaint {ticket_id} was verified by the ward officer.",
        "mr": "तुमची तक्रार {ticket_id} प्रभाग अधिकाऱ्यांनी पडताळली.",
        "hi": "आपकी शिकायत {ticket_id} की वार्ड अधिकारी ने पुष्टि की।",
    },
    "ticket_rejected": {
        "en": "Your complaint {ticket_id} was not accepted because {reason}.",
        "mr": "तुमची तक्रार {ticket_id} स्वीकारली गेली नाही, कारण {reason}.",
        "hi": "आपकी शिकायत {ticket_id} स्वीकार नहीं हुई, क्योंकि {reason}।",
    },
    "ticket_duplicate": {
        "en": "Your complaint {ticket_id} is being tracked together with {parent_id}, which reports the same problem.",
        "mr": "तुमची तक्रार {ticket_id} हीच समस्या नोंदवणाऱ्या {parent_id} सोबत ट्रॅक केली जात आहे.",
        "hi": "आपकी शिकायत {ticket_id} उसी समस्या वाली {parent_id} के साथ ट्रैक की जा रही है।",
    },
    "ticket_assigned": {
        "en": "Your complaint {ticket_id} was assigned to {contractor} under task {task_id}.",
        "mr": "तुमची तक्रार {ticket_id} काम {task_id} अंतर्गत {contractor} यांना सोपवली.",
        "hi": "आपकी शिकायत {ticket_id} कार्य {task_id} के तहत {contractor} को सौंपी गई।",
    },
    "task_assigned": {
        "en": "New task {task_id}: {n} complaint(s) in ward {ward}, due {due}.",
        "mr": "नवीन काम {task_id}: प्रभाग {ward} मधील {n} तक्रारी, मुदत {due}.",
        "hi": "नया कार्य {task_id}: वार्ड {ward} की {n} शिकायतें, समय सीमा {due}।",
    },
    "work_started": {
        "en": "Work has started on your complaint {ticket_id}.",
        "mr": "तुमच्या तक्रारी {ticket_id} वर काम सुरू झाले आहे.",
        "hi": "आपकी शिकायत {ticket_id} पर काम शुरू हो गया है।",
    },
    "report_submitted": {
        "en": "{contractor} submitted a repair report for task {task_id}. Please review it.",
        "mr": "{contractor} यांनी काम {task_id} साठी दुरुस्ती अहवाल सादर केला. कृपया तपासा.",
        "hi": "{contractor} ने कार्य {task_id} की मरम्मत रिपोर्ट जमा की। कृपया जाँचें।",
    },
    "task_approved": {
        "en": "Your repair report for task {task_id} was approved.",
        "mr": "काम {task_id} साठीचा तुमचा दुरुस्ती अहवाल मंजूर झाला.",
        "hi": "कार्य {task_id} की आपकी मरम्मत रिपोर्ट स्वीकृत हुई।",
    },
    "task_rework": {
        "en": "Your repair report for task {task_id} needs more work: {reason}",
        "mr": "काम {task_id} साठीच्या दुरुस्ती अहवालावर आणखी काम हवे: {reason}",
        "hi": "कार्य {task_id} की मरम्मत रिपोर्ट पर और काम चाहिए: {reason}",
    },
    "task_cancelled": {
        "en": "Task {task_id} was cancelled by the ward officer.",
        "mr": "काम {task_id} प्रभाग अधिकाऱ्यांनी रद्द केले.",
        "hi": "कार्य {task_id} वार्ड अधिकारी ने रद्द किया।",
    },
    "task_overdue": {
        "en": "Task {task_id} (ward {ward}) passed its deadline of {due} and is not completed yet. Please submit the repair report.",
        "mr": "काम {task_id} (प्रभाग {ward}) ची {due} ही मुदत संपली आहे आणि ते अजून पूर्ण झालेले नाही. कृपया दुरुस्ती अहवाल सादर करा.",
        "hi": "कार्य {task_id} (वार्ड {ward}) की {due} की समय सीमा बीत चुकी है और वह अभी पूरा नहीं हुआ है। कृपया मरम्मत रिपोर्ट जमा करें।",
    },
    "task_overdue_officer": {
        "en": "Task {task_id} ({contractor}, ward {ward}) is past its deadline of {due}; the contractor was reminded.",
        "mr": "काम {task_id} ({contractor}, प्रभाग {ward}) ची {due} ही मुदत संपली आहे; कंत्राटदाराला स्मरणपत्र पाठवले.",
        "hi": "कार्य {task_id} ({contractor}, वार्ड {ward}) की {due} की समय सीमा बीत चुकी है; ठेकेदार को अनुस्मारक भेजा गया।",
    },
    "ticket_resolved": {
        "en": "Your complaint {ticket_id} has been resolved. If the problem comes back, please report it again.",
        "mr": "तुमची तक्रार {ticket_id} निकाली निघाली. समस्या परत आल्यास कृपया पुन्हा नोंदवा.",
        "hi": "आपकी शिकायत {ticket_id} का समाधान हो गया। समस्या लौटे तो कृपया फिर से दर्ज करें।",
    },
}

STATUS = {
    "submitted": {"en": "waiting for verification", "mr": "पडताळणीच्या प्रतीक्षेत", "hi": "जाँच की प्रतीक्षा में"},
    "verified": {"en": "verified, waiting to be assigned", "mr": "पडताळली, सोपवण्याच्या प्रतीक्षेत", "hi": "पुष्टि हुई, सौंपे जाने की प्रतीक्षा में"},
    "assigned": {"en": "assigned to a contractor", "mr": "कंत्राटदाराला सोपवली", "hi": "ठेकेदार को सौंपी गई"},
    "in_progress": {"en": "work in progress", "mr": "काम सुरू आहे", "hi": "काम चल रहा है"},
    "work_submitted": {"en": "work reported done, under officer review", "mr": "काम पूर्ण झाल्याचा अहवाल, अधिकारी तपासत आहेत", "hi": "काम पूरा होने की रिपोर्ट, अधिकारी जाँच रहे हैं"},
    "resolved": {"en": "resolved", "mr": "निकाली निघाली", "hi": "समाधान हो गया"},
    "rejected": {"en": "not accepted", "mr": "स्वीकारली नाही", "hi": "स्वीकार नहीं हुई"},
    "duplicate": {"en": "tracked with an earlier complaint", "mr": "आधीच्या तक्रारीसोबत ट्रॅक केली जात आहे", "hi": "पहले की शिकायत के साथ ट्रैक की जा रही है"},
}

TICKET_ANSWER = {
    "head": {"en": "Complaint {id} ({category}, ward {ward}) was raised on {date}. Status: {status}.",
             "mr": "तक्रार {id} ({category}, प्रभाग {ward}) {date} रोजी नोंदवली. स्थिती: {status}.",
             "hi": "शिकायत {id} ({category}, वार्ड {ward}) {date} को दर्ज हुई। स्थिति: {status}।"},
    "task": {"en": " It is assigned to {contractor} under task {task}.", "mr": " ती काम {task} अंतर्गत {contractor} यांना सोपवली आहे.",
             "hi": " यह कार्य {task} के तहत {contractor} को सौंपी गई है।"},
    "cost": {"en": " The approved bill is ₹{cost}.", "mr": " मंजूर बिल ₹{cost} आहे.", "hi": " स्वीकृत बिल ₹{cost} है।"},
}

CHECK = {
    "ct_sla": {
        "en": "Finished on time in {sla}% of past repairs (about {exp}% is expected for the same mix of jobs).",
        "mr": "मागील {sla}% दुरुस्त्या वेळेत पूर्ण (त्याच प्रकारच्या कामांसाठी साधारण {exp}% अपेक्षित).",
        "hi": "पिछली {sla}% मरम्मतें समय पर पूरी (उसी तरह के कामों के लिए लगभग {exp}% अपेक्षित)।",
    },
    "ct_reopen": {
        "en": "{reopen}% of past repairs were reopened within 30 days (about {exp}% is expected).",
        "mr": "मागील {reopen}% दुरुस्त्या 30 दिवसांत पुन्हा उघडल्या (साधारण {exp}% अपेक्षित).",
        "hi": "पिछली {reopen}% मरम्मतें 30 दिनों में दोबारा खुलीं (लगभग {exp}% अपेक्षित)।",
    },
    "ct_overrun": {
        "en": "{n} of {total} past bills were above the normal range of the standard rate.",
        "mr": "मागील {total} पैकी {n} बिले प्रमाण दराच्या सामान्य मर्यादेपेक्षा जास्त होती.",
        "hi": "पिछले {total} में से {n} बिल मानक दर की सामान्य सीमा से अधिक थे।",
    },
    "ct_clean": {
        "en": "Clean record in ward {ward}.",
        "mr": "प्रभाग {ward} मध्ये स्वच्छ नोंद.",
        "hi": "वार्ड {ward} में साफ़ रिकॉर्ड।",
    },
    "ct_findings": {
        "en": "Findings on record in ward {ward}: {list}.",
        "mr": "प्रभाग {ward} मधील नोंदवलेले निष्कर्ष: {list}.",
        "hi": "वार्ड {ward} में दर्ज निष्कर्ष: {list}।",
    },
    "dlp_road": {
        "en": "{road} is recorded under the original contractor's warranty (Defect Liability Period): that contractor should repair it at no cost to BMC.",
        "mr": "{road} मूळ कंत्राटदाराच्या दोष दायित्व कालावधीत असल्याची नोंद आहे: त्या कंत्राटदाराने BMC ला खर्च न लावता दुरुस्ती करावी.",
        "hi": "{road} मूल ठेकेदार के दोष दायित्व काल में दर्ज है: उस ठेकेदार को BMC को बिना लागत मरम्मत करनी चाहिए।",
    },
    "bill_over_rate": {
        "en": "Bill of ₹{bill} is {pct}% above the standard rate (₹{expected} for {qty} of {method}).",
        "mr": "₹{bill} चे बिल प्रमाण दरापेक्षा {pct}% जास्त आहे ({method}, {qty} साठी ₹{expected}).",
        "hi": "₹{bill} का बिल मानक दर से {pct}% अधिक है ({method}, {qty} के लिए ₹{expected})।",
    },
    "bill_within_rate": {
        "en": "Bill of ₹{bill} is within the normal range of the standard rate (₹{expected} for {qty} of {method}).",
        "mr": "₹{bill} चे बिल प्रमाण दराच्या सामान्य मर्यादेत आहे ({method}, {qty} साठी ₹{expected}).",
        "hi": "₹{bill} का बिल मानक दर की सामान्य सीमा में है ({method}, {qty} के लिए ₹{expected})।",
    },
    "bill_over_estimate": {
        "en": "Bill of ₹{bill} is {pct}% above the task estimate of ₹{est}.",
        "mr": "₹{bill} चे बिल कामाच्या ₹{est} अंदाजापेक्षा {pct}% जास्त आहे.",
        "hi": "₹{bill} का बिल कार्य के ₹{est} के अनुमान से {pct}% अधिक है।",
    },
    "no_photos": {
        "en": "No photo or video of the completed work is attached.",
        "mr": "पूर्ण झालेल्या कामाचा फोटो किंवा व्हिडिओ जोडलेला नाही.",
        "hi": "पूरे हुए काम की कोई फ़ोटो या वीडियो संलग्न नहीं है।",
    },
    "no_bill_file": {
        "en": "No bill document is attached.",
        "mr": "बिलाचा कोणताही दस्तऐवज जोडलेला नाही.",
        "hi": "बिल का कोई दस्तावेज़ संलग्न नहीं है।",
    },
}


TASK_STATUS = {
    "assigned": {"en": "assigned, not started", "mr": "सोपवले, सुरू केले नाही", "hi": "सौंपा गया, शुरू नहीं हुआ"},
    "in_progress": {"en": "work in progress", "mr": "काम सुरू आहे", "hi": "काम चल रहा है"},
    "rework": {"en": "sent back for more work", "mr": "आणखी कामासाठी परत पाठवले", "hi": "और काम के लिए वापस भेजा गया"},
}

# E-mails: a subject and a list of lines. A line starting with "{key?}" is dropped when `key` is missing or empty.
MAIL = {
    "ticket_resolved": {
        "subject": {"en": "Your complaint {ticket_id} has been resolved",
                    "mr": "तुमची तक्रार {ticket_id} निकाली निघाली आहे",
                    "hi": "आपकी शिकायत {ticket_id} का समाधान हो गया है"},
        "lines": {
            "en": ["Hello,",
                   "Complaint {ticket_id} ({category}, ward {ward}) was marked resolved on {date}.",
                   "Status: resolved. The repair was reported done and approved by the ward officer.",
                   "{contractor?}Work carried out by: {contractor} (task {task_id}).",
                   "{cost?}Approved bill: ₹{cost}.",
                   "{parent_id?}Your complaint was tracked together with {parent_id}, which reports the same problem.",
                   "See the full history: {url}",
                   'If the problem comes back, please report it again, or support the earlier complaint with the "Me too" button.',
                   "- The Ward Ledger (automated message, please do not reply)"],
            "mr": ["नमस्कार,",
                   "तक्रार {ticket_id} ({category}, प्रभाग {ward}) {date} रोजी निकाली निघाल्याची नोंद झाली.",
                   "स्थिती: निकाली. दुरुस्ती पूर्ण झाल्याचा अहवाल आला आणि प्रभाग अधिकाऱ्यांनी तो मंजूर केला.",
                   "{contractor?}काम करणारे कंत्राटदार: {contractor} (काम {task_id}).",
                   "{cost?}मंजूर बिल: ₹{cost}.",
                   "{parent_id?}तुमची तक्रार हीच समस्या नोंदवणाऱ्या {parent_id} सोबत ट्रॅक केली जात होती.",
                   "संपूर्ण इतिहास पहा: {url}",
                   'समस्या परत आल्यास कृपया पुन्हा नोंदवा, किंवा आधीच्या तक्रारीला "मलाही" बटणाने पाठिंबा द्या.',
                   "- द वॉर्ड लेजर (स्वयंचलित संदेश, कृपया उत्तर देऊ नका)"],
            "hi": ["नमस्ते,",
                   "शिकायत {ticket_id} ({category}, वार्ड {ward}) {date} को हल हुई दर्ज की गई।",
                   "स्थिति: समाधान हो गया। मरम्मत पूरी होने की रिपोर्ट आई और वार्ड अधिकारी ने उसे स्वीकृत किया।",
                   "{contractor?}काम करने वाले ठेकेदार: {contractor} (कार्य {task_id})।",
                   "{cost?}स्वीकृत बिल: ₹{cost}।",
                   "{parent_id?}आपकी शिकायत उसी समस्या वाली {parent_id} के साथ ट्रैक की जा रही थी।",
                   "पूरा इतिहास देखें: {url}",
                   'समस्या लौटे तो कृपया फिर दर्ज करें, या पहले की शिकायत को "मुझे भी" बटन से समर्थन दें।',
                   "- द वार्ड लेजर (स्वचालित संदेश, कृपया उत्तर न दें)"],
        },
    },
    "task_overdue": {
        "subject": {"en": "Task {task_id} has passed its deadline",
                    "mr": "काम {task_id} ची मुदत संपली आहे",
                    "hi": "कार्य {task_id} की समय सीमा बीत चुकी है"},
        "lines": {
            "en": ["Dear {contractor},",
                   "Task {task_id} ({title}, ward {ward}) was due on {due} and is not completed yet. "
                   "Current status: {status}. It is {days} day(s) past the deadline.",
                   "Please finish the work and submit the repair report: {url}",
                   "If the work is already done, or something stopped it (for example heavy rain or site access), "
                   "submit the report with a note or contact the ward office.",
                   "This is an automated reminder based on the task record.",
                   "- The Ward Ledger"],
            "mr": ["प्रिय {contractor},",
                   "काम {task_id} ({title}, प्रभाग {ward}) {due} पर्यंत पूर्ण व्हायचे होते आणि ते अजून पूर्ण झालेले नाही. "
                   "सध्याची स्थिती: {status}. मुदतीला {days} दिवस उलटले आहेत.",
                   "कृपया काम पूर्ण करून दुरुस्ती अहवाल सादर करा: {url}",
                   "काम आधीच झाले असल्यास, किंवा काही कारणाने (उदा. अतिवृष्टी, जागेवर प्रवेश) थांबले असल्यास, "
                   "टिपेसह अहवाल सादर करा किंवा प्रभाग कार्यालयाशी संपर्क साधा.",
                   "हे कामाच्या नोंदीवर आधारित स्वयंचलित स्मरणपत्र आहे.",
                   "- द वॉर्ड लेजर"],
            "hi": ["प्रिय {contractor},",
                   "कार्य {task_id} ({title}, वार्ड {ward}) {due} तक पूरा होना था और अभी पूरा नहीं हुआ है। "
                   "वर्तमान स्थिति: {status}। समय सीमा को {days} दिन बीत चुके हैं।",
                   "कृपया काम पूरा करके मरम्मत रिपोर्ट जमा करें: {url}",
                   "यदि काम हो चुका है, या किसी कारण (जैसे भारी बारिश, साइट पर पहुँच) से रुका है, "
                   "तो टिप्पणी के साथ रिपोर्ट जमा करें या वार्ड कार्यालय से संपर्क करें।",
                   "यह कार्य के रिकॉर्ड पर आधारित स्वचालित अनुस्मारक है।",
                   "- द वार्ड लेजर"],
        },
    },
}


def render_mail(kind: str, params: dict, lang: str) -> tuple[str, str]:
    """(subject, body) in the reader's language. Lines marked `{key?}` are dropped when `key` is empty."""
    lang = lang if lang in LANGS else "en"
    p = dict(params or {})
    if "category" in p:
        p["category"] = T.category(p["category"], lang)
    if isinstance(p.get("cost"), (int, float)):
        p["cost"] = T.inr(p["cost"])
    if p.get("status") in TASK_STATUS:
        p["status"] = TASK_STATUS[p["status"]][lang]
    spec = MAIL[kind]
    safe = {k: ("" if v is None else v) for k, v in p.items()}
    lines = []
    for line in spec["lines"][lang]:
        if line.startswith("{") and "?}" in line:
            key, line = line[1:].split("?}", 1)
            if not p.get(key):
                continue
        lines.append(line.format_map(safe))
    return spec["subject"][lang].format_map(safe), "\n\n".join(lines) + "\n"


def render(table: dict, kind: str, params: dict, lang: str) -> str:
    lang = lang if lang in LANGS else "en"
    p = dict(params or {})
    if "category" in p:
        p["category"] = T.category(p["category"], lang)
    if "reason" in p and p["reason"] in REJECT_REASON:
        p["reason"] = REJECT_REASON[p["reason"]][lang]
    for k in ("bill", "expected", "est"):
        if isinstance(p.get(k), (int, float)):
            p[k] = T.inr(p[k])
    try:
        return table[kind][lang].format(**p)
    except (KeyError, IndexError):
        return table.get(kind, {}).get("en", kind)
