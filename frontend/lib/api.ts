"use client";
import { useCallback, useEffect, useState } from "react";
import { useLang } from "./i18n";
import { useRole, type Role } from "./role";

export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export type ApiOpts = { role?: Role; lang?: string; method?: "GET" | "POST"; body?: unknown; user?: string };

export async function api<T = any>(path: string, opts: ApiOpts = {}): Promise<T> {
  let url = API + path;
  if (opts.lang && !/[?&]lang=/.test(url)) url += (url.includes("?") ? "&" : "?") + "lang=" + opts.lang;
  const headers: Record<string, string> = { "X-Role": opts.role || "public" };
  if (opts.user) headers["X-User"] = opts.user;
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(url, {
    method: opts.method || "GET",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = typeof j.detail === "string" ? j.detail : msg;
    } catch {}
    throw new ApiError(res.status, msg);
  }
  return res.json();
}

/** Fetch a path with the current role + language; refetches when either changes. Pass null to skip. */
export function useApi<T = any>(path: string | null, deps: unknown[] = []) {
  const { lang } = useLang();
  const { role } = useRole();
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
    let live = true;
    setLoading(true);
    setError(null);
    api<T>(path, { role, lang })
      .then((d) => live && setData(d))
      .catch((e) => live && setError(e))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, lang, role, tick, ...deps]);
  return { data, error, loading, reload };
}
