import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Narada",
  description: "Five instruments, five AI musicians, one bandleader.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen font-sans antialiased">{children}</body>
    </html>
  );
}
