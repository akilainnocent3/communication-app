import type { Metadata, Viewport } from "next";
import { ThemeProvider } from "next-themes";
import { Inter } from "next/font/google";
import Providers from "@/app/providers";
import { ThemedToaster } from "@/components/shell/themed-toaster";
import { cn } from "@/utils/cn";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { template: "%s · OCM", default: "OCM" },
  description: "Manage every company communication channel (Gmail first) from one place.",
  icons: { icon: "/favicon.svg" },
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [{ media: "(prefers-color-scheme: light)", color: "#f3f4f6" }, { media: "(prefers-color-scheme: dark)", color: "#0b1120" }],
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html suppressHydrationWarning lang="en" className={cn("h-full overflow-hidden antialiased", inter.className)}>
      <body className="h-full overflow-hidden bg-background-gray-secondary_alt_2">
        <ThemeProvider attribute="data-theme" defaultTheme="system" enableSystem>
          <Providers>{children}</Providers>
          <ThemedToaster />
        </ThemeProvider>
      </body>
    </html>
  );
}
