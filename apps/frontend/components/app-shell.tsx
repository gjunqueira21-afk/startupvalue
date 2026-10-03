"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getEntitlements } from "@/lib/api/branding";
import { Brand } from "./brand";
import { BuildingIcon, ChartIcon, FileIcon, GridIcon, PaletteIcon } from "./icons";
import { SessionSummary } from "./session-summary";

const navigation = [
  ["/app", "Visão geral", GridIcon],
  ["/app#empresas", "Empresas", BuildingIcon],
  ["/app#analises", "Análises", ChartIcon],
  ["/app#relatorios", "Relatórios", FileIcon],
] as const;

const BRANDING_LINK = ["/app/settings/branding", "Marca do relatório", PaletteIcon] as const;

export function AppShell({ children, active = "/app" }: { children: React.ReactNode; active?: string }) {
  // Only consultor/escritório plans see the branding settings link — the page
  // itself re-checks entitlements (and the role requirement) server-side, so
  // this is purely a nav-visibility convenience, not an access control.
  const [whiteLabel, setWhiteLabel] = useState(false);

  useEffect(() => {
    let mounted = true;
    getEntitlements()
      .then((entitlements) => {
        if (mounted) setWhiteLabel(entitlements.white_label);
      })
      .catch(() => {
        if (mounted) setWhiteLabel(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const items = whiteLabel ? [...navigation, BRANDING_LINK] : navigation;

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <Brand />
        <SessionSummary />
        <nav aria-label="Área do produto">
          {items.map(([href, label, Icon]) => (
            <Link className={active === href ? "active" : ""} href={href} key={label}>
              <Icon />
              {label}
            </Link>
          ))}
        </nav>
      </aside>
      <div className="app-main">{children}</div>
    </div>
  );
}
