"""RTI Draft Generator (SPEC §6.8): a printable Section 6(1) application, Marathi + English.

Template-driven and lawful: it only requests documents "for citizen verification" and never asserts
wrongdoing. The applicant's name/address are left blank (nothing personal is stored or logged).
"""
from __future__ import annotations

from datetime import date, timedelta

import db
from agents import facts as Fx
from rules import text as T

FEE_INR = 10

DISCLAIMER = {
    "en": "Please verify the current Public Information Officer's name and address with the ward office before filing; these details change.",
    "mr": "अर्ज दाखल करण्यापूर्वी जन माहिती अधिकाऱ्याचे सध्याचे नाव व पत्ता वॉर्ड कार्यालयात तपासा; हे तपशील बदलतात.",
    "hi": "आवेदन दाख़िल करने से पहले जन सूचना अधिकारी का वर्तमान नाम व पता वार्ड कार्यालय से जाँच लें; ये विवरण बदलते रहते हैं।",
}

DOCS_WORK = {
    "en": ["Tender notice / work order and sanctioned estimate for the work",
           "Measurement book entries for the work",
           "Completion certificate and the inspection / site report",
           "Bill and payment record, including the amount paid to the contractor",
           "The contractor's Defect Liability Period obligations for this road, and any record of a repair done under them",
           "Any record of penalty / liquidated damages levied, or of an extension of time granted"],
    "mr": ["कामाची निविदा सूचना / कार्यादेश आणि मंजूर अंदाजपत्रक",
           "कामाच्या मोजमाप पुस्तिकेतील नोंदी",
           "पूर्णत्व प्रमाणपत्र आणि तपासणी / स्थळ अहवाल",
           "देयक व अदा रक्कम नोंद (कंत्राटदाराला दिलेली रक्कम)",
           "या रस्त्यासाठी कंत्राटदाराचे दोष दायित्व कालावधीतील बंधन आणि त्याअंतर्गत केलेल्या दुरुस्तीची नोंद",
           "दंड / नुकसानभरपाई आकारल्याची किंवा मुदतवाढ दिल्याची कोणतीही नोंद"],
}
DOCS_COMPLAINT = {
    "en": ["Action-taken report on the complaint",
           "Site inspection report / note, with the date of inspection",
           "Work order issued for this location, if any, with its status",
           "The reason for any delay and the expected date of completion"],
    "mr": ["तक्रारीवर केलेल्या कार्यवाहीचा अहवाल",
           "स्थळ तपासणी अहवाल / टिपण, तपासणीच्या तारखेसह",
           "या ठिकाणासाठी काढलेला कार्यादेश (असल्यास) आणि त्याची स्थिती",
           "उशिराचे कारण आणि काम पूर्ण होण्याची अपेक्षित तारीख"],
}

BODY = {
    "en": """To,
The Public Information Officer,
{office},
Brihanmumbai Municipal Corporation, Mumbai

Subject: Application under Section 6(1) of the Right to Information Act, 2005 - request for documents relating to {subject}

Sir / Madam,

1. Name and address of the applicant: ______________________________ (to be filled in by the applicant)

2. Particulars of the information required (for citizen verification):
   {particulars}

3. Documents requested:
{docs}

4. Period to which the information relates: {period}

5. The application fee of Rs. {fee} is paid by ____________ (cash / Indian Postal Order / court-fee stamp). A person below the poverty line is exempt from the fee on attaching proof.

6. I request the information within 30 days of receipt of this application (if filed on {today}, by {due}). If any part is withheld, please state the section relied upon.

7. I understand that if I am not satisfied with the reply I may file a first appeal under Section 19(1) of the Act before the First Appellate Authority within 30 days.

Date: ______________      Place: Mumbai      Signature: ______________

(Note: {disclaimer})""",
    "mr": """प्रति,
जन माहिती अधिकारी,
{office},
बृहन्मुंबई महानगरपालिका, मुंबई

विषय: माहितीचा अधिकार अधिनियम, 2005 च्या कलम 6(1) अन्वये अर्ज - {subject} संबंधित कागदपत्रांची मागणी

महोदय / महोदया,

1. अर्जदाराचे नाव व पत्ता: ______________________________ (अर्जदाराने भरावे)

2. आवश्यक माहितीचा तपशील (नागरिक पडताळणीसाठी):
   {particulars}

3. मागितलेली कागदपत्रे:
{docs}

4. माहिती ज्या कालावधीशी संबंधित आहे: {period}

5. अर्जाची फी रु. {fee} ____________ द्वारे (रोख / भारतीय पोस्टल ऑर्डर / कोर्ट-फी स्टॅम्प) भरली आहे. दारिद्र्यरेषेखालील व्यक्तीने पुरावा जोडल्यास फी माफ आहे.

6. हा अर्ज मिळाल्यापासून 30 दिवसांत माहिती मिळावी, ही विनंती (आज {today} रोजी दाखल केल्यास {due} पर्यंत). माहितीचा काही भाग नाकारल्यास, कृपया संबंधित कलम नमूद करावे.

7. उत्तराने समाधान न झाल्यास, कायद्याच्या कलम 19(1) अन्वये 30 दिवसांत प्रथम अपील प्राधिकरणाकडे प्रथम अपील करता येते, याची मला जाणीव आहे.

दिनांक: ______________      ठिकाण: मुंबई      सही: ______________

(टीप: {disclaimer})""",
}


def _particulars(conn, kind: str, ident: str):
    """-> (subject, particulars_en, particulars_mr, period, docs_kind, ward_code, meta)"""
    if kind == "work":
        w = Fx.work_detail(conn, ident, "en", officer=False)
        if not w:
            return None
        road = w["road"] or {}
        extra_en, extra_mr = [], []
        if road.get("under_dlp"):
            extra_en.append("the records I have seen list this road as being under a Defect Liability Period")
            extra_mr.append("मी पाहिलेल्या नोंदींमध्ये हा रस्ता दोष दायित्व कालावधीत असल्याचे दिसते")
        if w["reopened_within_30d"]:
            extra_en.append("the repair is recorded as reopened within 30 days")
            extra_mr.append("ही दुरुस्ती 30 दिवसांत पुन्हा उघडल्याची नोंद आहे")
        if any(f["rule"] == "possible_double_billing" for f in w["findings"]):
            extra_en.append("a repair of the same type is recorded on the same road within a few days")
            extra_mr.append("त्याच रस्त्यावर काही दिवसांत त्याच प्रकारची दुरुस्ती नोंदलेली आहे")
        if any(f["rule"] == "rate_card_overrun" for f in w["findings"]):
            extra_en.append(f"the billed amount of Rs. {T.inr(w['cost_inr'])} is shown as above the standard rate card")
            extra_mr.append(f"बिल केलेली रक्कम रु. {T.inr(w['cost_inr'])} प्रमाण दर सूचीपेक्षा जास्त दिसते")
        en = (f"Work order {ident} ({w['work_type']}; {w['repair_method']}) on {road.get('road_name', w['road_id'])} ({w['road_id']}), "
              f"ward {w['ward_code']}, assigned {w['assigned_at'][:10]}, completed {w['completed_at'][:10]}, billed Rs. {T.inr(w['cost_inr'])}, "
              f"contractor {w['contractor_name']}." + (f" For clarity: {'; '.join(extra_en)}." if extra_en else ""))
        mr = (f"कामाचा आदेश {ident} ({w['work_type']}; {w['repair_method']}) - {road.get('road_name', w['road_id'])} ({w['road_id']}), "
              f"प्रभाग {w['ward_code']}, नेमणूक {w['assigned_at'][:10]}, पूर्ण {w['completed_at'][:10]}, बिल रु. {T.inr(w['cost_inr'])}, "
              f"कंत्राटदार {w['contractor_name']}." + (f" स्पष्टतेसाठी: {'; '.join(extra_mr)}." if extra_mr else ""))
        return (f"work order {ident}", en, mr, f"{w['assigned_at'][:10]} to {w['completed_at'][:10]}", "work", w["ward_code"],
                {"type": "work", "id": ident})
    if kind == "complaint":
        t = Fx.complaint_timeline(conn, ident, "en")
        if not t:
            return None
        if t["work"]:
            r = _particulars(conn, "work", t["work"]["work_order_id"])
            return r
        loc = t["location"]["locality"] or "-"
        en = (f"Complaint {ident} filed on {t['received_at'][:10]} ({t['category']}) at {loc}, ward {t['location']['ward_code']}. "
              f"No work order is linked to it in the records available to me.")
        mr = (f"तक्रार {ident}, {t['received_at'][:10]} रोजी नोंदवली ({T.category(t['category'], 'mr')}), ठिकाण {loc}, प्रभाग {t['location']['ward_code']}. "
              f"माझ्याकडील नोंदींमध्ये यासाठी कोणताही कार्यादेश जोडलेला नाही.")
        return (f"complaint {ident}", en, mr, f"{t['received_at'][:10]} to date", "complaint", t["location"]["ward_code"],
                {"type": "complaint", "id": ident})
    if kind == "road":
        r = Fx.road_card(conn, ident)
        if not r:
            return None
        en = (f"Road {r['road_name']} (segment {r['segment_no']}, {ident}), ward {r['ward_code']}: all repair work orders, bills and any "
              f"Defect Liability Period records for this segment this season ({r['repairs']} repairs are recorded).")
        mr = (f"रस्ता {r['road_name']} (भाग {r['segment_no']}, {ident}), प्रभाग {r['ward_code']}: या हंगामातील सर्व दुरुस्ती कार्यादेश, देयके आणि "
              f"दोष दायित्व कालावधीच्या नोंदी ({r['repairs']} दुरुस्त्या नोंदलेल्या).")
        return (f"road {ident}", en, mr, "2025-06-01 to date", "work", r["ward_code"], {"type": "road", "id": ident})
    return None


def draft(conn, kind: str, ident: str, today: date | None = None) -> dict | None:
    today = today or date.today()
    p = _particulars(conn, kind, ident)
    if not p:
        return None
    subject, part_en, part_mr, period, docs_kind, ward, meta = p
    ward_row = db.one(conn, "SELECT assistant_commissioner_office FROM wards WHERE ward_code=?", (ward,))
    office = ward_row["assistant_commissioner_office"] if ward_row else "Ward Office"
    docs_en = DOCS_WORK["en"] if docs_kind == "work" else DOCS_COMPLAINT["en"]
    docs_mr = DOCS_WORK["mr"] if docs_kind == "work" else DOCS_COMPLAINT["mr"]
    fmt = lambda items: "\n".join(f"   ({chr(97 + i)}) {d}" for i, d in enumerate(items))
    due = today + timedelta(days=30)
    common = dict(office=office, fee=FEE_INR, today=today.isoformat(), due=due.isoformat(), period=period)
    text_en = BODY["en"].format(subject=subject, particulars=part_en, docs=fmt(docs_en), disclaimer=DISCLAIMER["en"], **common)
    text_mr = BODY["mr"].format(subject=subject, particulars=part_mr, docs=fmt(docs_mr), disclaimer=DISCLAIMER["mr"], **common)
    return {
        "subject": meta, "text_en": text_en, "text_mr": text_mr, "pio": {"office": office, "name": None,
                                                                         "note": DISCLAIMER["en"]},
        "fee_inr": FEE_INR, "reply_due_days": 30, "due_date_if_filed_today": due.isoformat(),
        "first_appeal": {"section": "19(1)", "within_days": 30, "to": "First Appellate Authority"},
        "disclaimer": DISCLAIMER, "demo_notice": "Demo data: this draft is generated from synthetic records and is not for filing.",
    }
