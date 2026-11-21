"use client";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "./api";
import { wardSlug } from "./format";

export type Role = "citizen" | "officer" | "contractor";
export type User = {
  user_id: string;
  role: Role;
  login: string;
  display_name: string | null;
  ward_code: string | null;
  designation: string | null;
  contractor_id: string | null;
  contractor_name?: string | null;
  can_act: boolean;
  email?: string | null;
  mail_lang?: string;
  unread_notifications?: number;
};

const KEY = "wl.session";
// Module-level copy so api() can attach it without a React context.
let currentToken: string | null = null;
export const getToken = () => currentToken;

type Ctx = {
  user: User | null;
  token: string | null;
  ready: boolean;
  login: (role: Role, login: string, password: string) => Promise<User>;
  register: (mobile: string, password: string, displayName: string, consent: boolean, email?: string, lang?: string) => Promise<User>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};
const AuthCtx = createContext<Ctx>({
  user: null,
  token: null,
  ready: false,
  login: async () => {
    throw new Error("no provider");
  },
  register: async () => {
    throw new Error("no provider");
  },
  logout: async () => {},
  refresh: async () => {},
});

/** Where each role lands after logging in (their own panel). */
export function homeFor(u: User): string {
  if (u.role === "officer") return `/officer/${wardSlug(u.ward_code || "K/E")}/complaints`;
  if (u.role === "contractor") return "/tasks";
  return "/me";
}

/** Only allow same-site relative redirects after login (no open redirect). */
export function safeNext(next: string | null): string | null {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setTokenState] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  const setToken = (t: string | null) => {
    currentToken = t;
    setTokenState(t);
    if (t) localStorage.setItem(KEY, t);
    else localStorage.removeItem(KEY);
  };

  const refresh = useCallback(async () => {
    if (!currentToken) return;
    try {
      setUser(await api<User>("/auth/me"));
    } catch {
      setToken(null);
      setUser(null);
    }
  }, []);

  useEffect(() => {
    const saved = localStorage.getItem(KEY);
    if (saved) {
      currentToken = saved;
      setTokenState(saved);
      refresh().finally(() => setReady(true));
    } else setReady(true);
    const expired = () => {
      setToken(null);
      setUser(null);
    };
    window.addEventListener("wl:session-expired", expired);
    return () => window.removeEventListener("wl:session-expired", expired);
  }, [refresh]);

  const login = async (role: Role, login: string, password: string) => {
    const r = await api<{ token: string; user: User }>(`/auth/${role}/login`, { method: "POST", body: { login, password } });
    setToken(r.token);
    setUser(r.user);
    return r.user;
  };
  const register = async (mobile: string, password: string, displayName: string, consent: boolean, email?: string, lang?: string) => {
    const r = await api<{ token: string; user: User }>("/auth/citizen/register", {
      method: "POST",
      body: { mobile, password, display_name: displayName || null, consent, email: email?.trim() || null, lang: lang || "en" },
    });
    setToken(r.token);
    setUser(r.user);
    return r.user;
  };
  const logout = async () => {
    try {
      await api("/auth/logout", { method: "POST" });
    } catch {}
    setToken(null);
    setUser(null);
  };
  return <AuthCtx.Provider value={{ user, token, ready, login, register, logout, refresh }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
