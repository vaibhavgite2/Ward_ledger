"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { homeFor, safeNext, useAuth, type Role } from "@/lib/auth";
import { useLang } from "@/lib/i18n";
import { PageTitle } from "@/components/Ui";

/** One login panel (DFD 1.1 / 1.2 / 1.3). Each posts only to its own role's endpoint. */
export default function LoginForm({ role }: { role: Role }) {
  const { t, lang } = useLang();
  const { user, login, register, logout } = useAuth();
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const [mode, setMode] = useState<"login" | "register">("login");
  const [id, setId] = useState("");
  const [pw, setPw] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (user && user.role !== role) {
    return (
      <div className="mx-auto max-w-md">
        <PageTitle>{t(`auth.title.${role}`)}</PageTitle>
        <div className="card text-sm">
          <p>{t("auth.otherRole", { role: t(`auth.role.${user.role}`) })}</p>
          <button className="btn btn-ghost mt-3" onClick={() => logout()}>
            {t("auth.logout")}
          </button>
        </div>
      </div>
    );
  }
  if (user && user.role === role) {
    return (
      <div className="mx-auto max-w-md">
        <PageTitle>{t(`auth.title.${role}`)}</PageTitle>
        <div className="card text-sm">
          <p>{t("auth.already", { name: user.display_name || user.login })}</p>
          <Link href={next || homeFor(user)} className="btn btn-primary mt-3">
            {t("auth.continue")}
          </Link>
        </div>
      </div>
    );
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (mode === "register" && !consent) return setErr(t("auth.consentNeeded"));
    setBusy(true);
    try {
      const u = mode === "register" ? await register(id, pw, name, consent, email, lang) : await login(role, id, pw);
      router.push(next || homeFor(u));
    } catch (e: any) {
      setErr(e?.message || t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  const idLabel = role === "citizen" ? t("auth.mobile") : role === "officer" ? t("auth.employeeId") : t("auth.contractorId");
  return (
    <div className="mx-auto max-w-md">
      <PageTitle sub={t(`auth.sub.${role}`)}>{t(`auth.title.${role}`)}</PageTitle>
      {role === "citizen" && (
        <div className="mb-3 flex gap-2" role="tablist">
          {(["login", "register"] as const).map((m) => (
            <button
              key={m}
              role="tab"
              aria-selected={mode === m}
              onClick={() => {
                setMode(m);
                setErr(null);
              }}
              className={`btn ${mode === m ? "btn-primary" : "btn-ghost"}`}
            >
              {t(m === "login" ? "auth.tabLogin" : "auth.tabRegister")}
            </button>
          ))}
        </div>
      )}
      <form onSubmit={submit} className="card space-y-3 text-sm">
        <label className="block">
          <span className="font-semibold">{idLabel}</span>
          <input
            value={id}
            onChange={(e) => setId(e.target.value)}
            required
            autoComplete="username"
            inputMode={role === "citizen" ? "tel" : "text"}
            placeholder={role === "citizen" ? "98XXXXXXXX" : role === "officer" ? "ae-4471" : "ct05"}
            className="mt-1 min-h-[44px] w-full rounded-md border border-ledger-200 px-3"
          />
        </label>
        {mode === "register" && (
          <label className="block">
            <span className="font-semibold">{t("auth.name")}</span>
            <input value={name} onChange={(e) => setName(e.target.value)} maxLength={60} autoComplete="name" className="mt-1 min-h-[44px] w-full rounded-md border border-ledger-200 px-3" />
          </label>
        )}
        {mode === "register" && (
          <label className="block">
            <span className="font-semibold">{t("auth.email")}</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              maxLength={120}
              autoComplete="email"
              placeholder={t("mail.placeholder")}
              className="mt-1 min-h-[44px] w-full rounded-md border border-ledger-200 px-3"
            />
            <span className="text-xs text-ink/60">{t("auth.emailHelp")}</span>
          </label>
        )}
        <label className="block">
          <span className="font-semibold">{t("auth.password")}</span>
          <input
            type="password"
            value={pw}
            onChange={(e) => setPw(e.target.value)}
            required
            minLength={mode === "register" ? 8 : 1}
            autoComplete={mode === "register" ? "new-password" : "current-password"}
            aria-describedby={mode === "register" ? "pw-rule" : undefined}
            className="mt-1 min-h-[44px] w-full rounded-md border border-ledger-200 px-3"
          />
        </label>
        {mode === "register" && (
          <p id="pw-rule" className="-mt-2 text-xs text-ink/60">
            {t("auth.pwRule")}
          </p>
        )}
        {mode === "register" && (
          <label className="flex items-start gap-2 text-xs">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-0.5 h-4 w-4" />
            <span>{t("auth.consent")}</span>
          </label>
        )}
        {err && (
          <p role="alert" className="rounded border border-red-200 bg-red-50 p-2 text-red-900">
            {err}
          </p>
        )}
        <button className="btn btn-primary w-full" disabled={busy}>
          {busy ? t("common.loading") : t(mode === "register" ? "auth.createAccount" : "auth.login")}
        </button>
      </form>
      <p className="mt-3 text-xs text-ink/70">{t("auth.noLoginNeeded")}</p>
      <p className="mt-2 text-xs">
        <Link href="/login" className="underline">
          {t("auth.otherPanels")}
        </Link>
      </p>
    </div>
  );
}
