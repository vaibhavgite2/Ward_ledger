"use client";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Role = "public" | "officer" | "auditor";
const Ctx = createContext<{ role: Role; setRole: (r: Role) => void; user: string }>({ role: "public", setRole: () => {}, user: "ae-demo" });

/** Demo-only role switcher (SPEC §7). Real deployments replace this with SSO. */
export function RoleProvider({ children }: { children: ReactNode }) {
  const [role, setRoleState] = useState<Role>("public");
  useEffect(() => {
    const r = localStorage.getItem("wl.role") as Role | null;
    if (r === "officer" || r === "auditor") setRoleState(r);
  }, []);
  const setRole = (r: Role) => {
    localStorage.setItem("wl.role", r);
    setRoleState(r);
  };
  return <Ctx.Provider value={{ role, setRole, user: "ae-demo" }}>{children}</Ctx.Provider>;
}
export const useRole = () => useContext(Ctx);
