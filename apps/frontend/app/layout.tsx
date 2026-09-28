import type { Metadata } from "next";
import "./globals.css";
import "./result-enhancements.css";

export const metadata: Metadata = {
  title: {
    default: "QuantoVale — Quanto vale a sua empresa",
    template: "%s — QuantoVale",
  },
  description:
    "Transforme projeções financeiras em uma distribuição probabilística de valuation com Monte Carlo, DCF e Venture Capital Method.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body>
        <a className="skip-link" href="#main-content">
          Ir para o conteúdo
        </a>
        {children}
      </body>
    </html>
  );
}
