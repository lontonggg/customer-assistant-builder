import type { Metadata } from "next";
import { Space_Grotesk } from "next/font/google";
import Image from "next/image";
import "./globals.css";

const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "",
  description: "Design and launch AI agents with guided configuration.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${spaceGrotesk.variable} antialiased bg-[var(--color-surface)] text-[var(--color-ink)]`}
      >
        {children}
        <footer className="fixed inset-x-0 bottom-0 z-50 border-t border-zinc-200 bg-white/95 backdrop-blur">
          <div className="mx-auto flex max-w-6xl items-center justify-center gap-2 px-4 py-2 text-xs text-zinc-700 sm:text-sm">
            <span>Powered by</span>
            <a
              href="https://mistral.ai"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center rounded-md px-1 py-0.5 hover:bg-zinc-100"
            >
              <Image src="/mistral-ai.png" alt="Mistral AI" width={72} height={16} className="h-4 w-auto" />
            </a>
            <span>and</span>
            <a
              href="https://elevenlabs.io"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center rounded-md px-1 py-0.5 hover:bg-zinc-100"
            >
              <Image src="/elevenlabs.png" alt="ElevenLabs" width={88} height={16} className="h-4 w-auto" />
            </a>
          </div>
        </footer>
      </body>
    </html>
  );
}
