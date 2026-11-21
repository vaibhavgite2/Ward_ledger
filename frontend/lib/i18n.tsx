"use client";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import en from "@/messages/en.json";
import mr from "@/messages/mr.json";
import hi from "@/messages/hi.json";
import enO from "@/messages/officer.en.json";
import mrO from "@/messages/officer.mr.json";
import hiO from "@/messages/officer.hi.json";

export type Lang = "mr" | "en" | "hi";
export const DEFAULT_LANG: Lang = "en";
export const LANGS: { code: Lang; label: string }[] = [
  { code: "en", label: "English" },
  { code: "mr", label: "मराठी" },
  { code: "hi", label: "हिन्दी" },
];
const DICT: Record<Lang, Record<string, string>> = {
  en: { ...en, ...enO },
  mr: { ...mr, ...mrO },
  hi: { ...hi, ...hiO },
};

type Vars = Record<string, string | number | null | undefined>;
const Ctx = createContext<{ lang: Lang; setLang: (l: Lang) => void; t: (k: string, v?: Vars) => string }>({
  lang: DEFAULT_LANG,
  setLang: () => {},
  t: (k) => k,
});

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(DEFAULT_LANG);
  useEffect(() => {
    const l = localStorage.getItem("wl.lang") as Lang | null;
    if (l === "en" || l === "hi" || l === "mr") setLangState(l);
  }, []);
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  const setLang = (l: Lang) => {
    localStorage.setItem("wl.lang", l);
    setLangState(l);
  };
  // Missing keys fall back to English, then to the key itself (never a blank label).
  const t = (k: string, v?: Vars) => {
    let s = DICT[lang][k] ?? DICT.en[k] ?? k;
    if (v) for (const [a, b] of Object.entries(v)) s = s.replaceAll(`{${a}}`, String(b ?? ""));
    return s;
  };
  return <Ctx.Provider value={{ lang, setLang, t }}>{children}</Ctx.Provider>;
}
export const useLang = () => useContext(Ctx);
