"use client";
import { useCallback, useEffect, useState } from "react";
import { useLang } from "./i18n";
import { getToken, useAuth } from "./auth";

export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

/** Absolute URL for a path the API returned (e.g. "/media/m_x/public"). */
export const apiUrl = (p: string | null | undefined) => (p ? API + p : "");

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export type ApiOpts = { lang?: string; method?: "GET" | "POST"; body?: unknown; form?: FormData };

/** Fetch JSON from the API. Sends the session token if there is one (browsing never needs one). */
export async function api<T = any>(path: string, opts: ApiOpts = {}): Promise<T> {
  let url = API + path;
  if (opts.lang && !/[?&]lang=/.test(url)) url += (url.includes("?") ? "&" : "?") + "lang=" + opts.lang;
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(url, {
    method: opts.method || (opts.body !== undefined || opts.form ? "POST" : "GET"),
    headers,
    body: opts.form ?? (opts.body !== undefined ? JSON.stringify(opts.body) : undefined),
  });
  if (!res.ok) {
    let msg = res.statusText;
    let code: string | undefined;
    try {
      const j = await res.json();
      if (typeof j.detail === "string") msg = j.detail;
      else if (Array.isArray(j.detail) && j.detail[0]?.msg) msg = j.detail[0].msg;
      code = j.code;
    } catch {}
    if (res.status === 401 && token) window.dispatchEvent(new Event("wl:session-expired"));
    throw new ApiError(res.status, msg, code);
  }
  return res.json();
}

/**
 * Fetch a path with the current language and session; refetches when either changes. Pass null to skip.
 * Waits until a saved session (if any) has been restored, so the first request already carries it instead of
 * going out anonymously, bouncing off a protected endpoint with a 401 and then being repeated.
 */
export function useApi<T = any>(path: string | null, deps: unknown[] = []) {
  const { lang } = useLang();
  const { token, ready } = useAuth();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(!!path);
  const [tick, setTick] = useState(0);
  const reload = useCallback(() => setTick((t) => t + 1), []);
  useEffect(() => {
    if (!path) {
      setLoading(false);
      return;
    }
    if (!ready) return; // still restoring the saved session; `loading` stays true until the real request runs
    let live = true;
    setLoading(true);
    setError(null);
    api<T>(path, { lang })
      .then((d) => live && setData(d))
      .catch((e) => live && setError(e))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, lang, token, ready, tick, ...deps]);
  return { data, error, loading, reload };
}
