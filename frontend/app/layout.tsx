import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { LangProvider } from "@/lib/i18n";
import { RoleProvider } from "@/lib/role";
import Shell from "@/components/Shell";

export const metadata: Metadata = {
  title: "The Ward Ledger",
  description: "Follow the rupee: where Mumbai monsoon road repair money went. Demo data: all records are synthetic.",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="mr">
      <body>
        <LangProvider>
          <RoleProvider>
            <Shell>{children}</Shell>
          </RoleProvider>
        </LangProvider>
      </body>
    </html>
  );
}
