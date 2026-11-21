/** Public, neutral titles for each finding rule (mirrors backend rules/text.py RULE_TITLES). */
export const RULE_LABEL: Record<string, Record<string, string>> = {
  rate_card_overrun: { en: "Billed above standard rate", mr: "प्रमाण दरापेक्षा जास्त बिल", hi: "मानक दर से अधिक बिल" },
  possible_double_billing: { en: "Possible repeat billing", mr: "पुन्हा बिल केल्याची शक्यता", hi: "दोबारा बिल की संभावना" },
  dlp_breach: { en: "Road under warranty", mr: "रस्ता वॉरंटीमध्ये", hi: "सड़क वारंटी में" },
  sla_missed: { en: "Slower than target", mr: "लक्ष्यापेक्षा उशीर", hi: "लक्ष्य से देर" },
  failed_within_30d: { en: "Repair did not hold", mr: "दुरुस्ती टिकली नाही", hi: "मरम्मत टिकी नहीं" },
  estimate_drift: { en: "Cost above ward norm", mr: "प्रभागाच्या सरासरीपेक्षा जास्त खर्च", hi: "वार्ड औसत से अधिक लागत" },
  never_fixed: { en: "No repair linked", mr: "दुरुस्ती जोडलेली नाही", hi: "कोई मरम्मत जुड़ी नहीं" },
  clean_record: { en: "Clean record", mr: "स्वच्छ नोंद", hi: "साफ़ रिकॉर्ड" },
};
