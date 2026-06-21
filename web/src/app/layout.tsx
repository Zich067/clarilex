import type { Metadata } from "next";
import { Fredoka, DM_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";

const fredoka = Fredoka({
  variable: "--font-fredoka",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "租賃／買賣法律文件智慧分析與風險評估系統｜國立臺中科技大學 資訊工程系 碩士學位論文",
  description:
    "國立臺中科技大學資訊工程系碩士論文：基於檢索增強生成（RAG）與大型語言模型之租賃／買賣法律文件風險評估系統。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-Hant"
      className={`${fredoka.variable} ${dmSans.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col scrollbar-candy">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
