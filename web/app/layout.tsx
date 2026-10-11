import type { Metadata } from "next";
import type { ReactNode } from "react";

import { SessionProvider } from "@/components/session-provider";
import { TestProductLabel } from "@/components/test-product-label";

import "./globals.css";

export const metadata: Metadata = {
  title: "UW Analyzer",
  description: "Verified external research for human-led credit underwriting.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <SessionProvider>
          <TestProductLabel />
          {children}
        </SessionProvider>
      </body>
    </html>
  );
}
