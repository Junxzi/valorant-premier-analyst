import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Header } from "@/components/Header";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "120ping-FTW",
  description: "vlr.gg-style dashboard for a Valorant Premier team.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="ja"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-bg text-text">
        <Header />
        <main className="flex-1">{children}</main>
        <footer className="border-t border-border px-6 py-4 text-center text-xs text-muted">
          Data via{" "}
          <a
            className="hover:text-text"
            href="https://docs.henrikdev.xyz"
            target="_blank"
            rel="noopener noreferrer"
          >
            HenrikDev API
          </a>
          . Not affiliated with Riot Games.
        </footer>
      </body>
    </html>
  );
}
