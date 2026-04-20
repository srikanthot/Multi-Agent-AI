import type { Metadata } from "next";
import AuthGate from "@/components/auth/AuthGate";
import ErrorBoundary from "@/components/ErrorBoundary";
import "./globals.css";
import { PreferencesProvider } from "@/contexts/preferencesContext";
 
export const metadata: Metadata = {
  title: "PSEG Tech Manual Chatbot",
  description: "Enterprise AI assistant for technical documentation",
};
 
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
 
      </head>
      <body>
        <AuthGate>
          <PreferencesProvider>
            {children}
          </PreferencesProvider>
        </AuthGate>
      </body>
    </html>
  );
}
 
 