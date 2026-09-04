import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "ReviewSignal AI",
  description: "AI customer intelligence for Maple Photo Imaging",
};

const PAGES = [
  ["/overview", "Overview"],
  ["/reviews", "Reviews"],
  ["/taxonomy", "Taxonomy"],
  ["/trends", "Trends"],
  ["/insights", "Insights"],
  ["/settings", "Settings"],
] as const;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <nav className="nav">
            <span className="brand">ReviewSignal AI</span>
            {PAGES.map(([href, label]) => (
              <Link key={href} href={href}>
                {label}
              </Link>
            ))}
          </nav>
          {children}
        </div>
      </body>
    </html>
  );
}
