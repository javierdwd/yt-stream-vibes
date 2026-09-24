import type { Metadata } from "next";
import { JetBrains_Mono, Syne } from "next/font/google";
import { QueryProvider } from "@/components/providers/query-provider";
import "./globals.css";

const syne = Syne({
  variable: "--font-syne",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const jetbrains = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "yt-stream-vibes",
  description:
    "Real-time YouTube Live sentiment & intent analyzer (JEV Engine)",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${syne.variable} ${jetbrains.variable} h-dvh overflow-hidden antialiased`}
    >
      <body className="flex h-dvh flex-col overflow-hidden bg-bg text-fg">
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
