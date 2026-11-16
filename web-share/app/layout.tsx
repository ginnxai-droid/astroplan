import type { ReactNode } from "react";

export const metadata = {
  title: "Astroplan (KUF) — Verifiable Chart Share",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}