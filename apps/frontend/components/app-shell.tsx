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

// Session-scoped cache so repeat /app page loads render the branding nav
// link immediately instead of popping in once the entitlements fetch
// resolves. Guarded by try/catch: sessionStorage can throw (private
// browsing, disabled storage) or simply not exist (server-side render).
const WHITE_LABEL_CACHE_KEY = "qv.whiteLabel";

function cachedWhiteLabel(): boolean {
  try {
    return sessionStorage.getItem(WHITE_LABEL_CACHE_KEY) === "1";
  } catch {
    return false;
  }
}

function cacheWhiteLabel(value: boolean): void {
  try {
    sessionStorage.setItem(WHITE_LABEL_CACHE_KEY, value ? "1" : "0");
  } catch {
    // Ignore — the link just won't be cached for next load.
  }
}

export function AppShell({ children, active = "/app" }: { children: React.ReactNode; active?: string }) {
  // Only consultor/escritório plans see the branding settings link — the page
  // itself re-checks entitlements (and the role requirement) server-side, so
  // this is purely a nav-visibility convenience, not an access control.
  // Seeded from the sessionStorage cache above: only the very first load in a
  // session (no cache yet) can still show the link popping in after the
  // fetch resolves.
  const [whiteLabel, setWhiteLabel] = useState(cachedWhiteLabel);

  useEffect(() => {
    let mounted = true;
    getEntitlements()
      .then((entitlements) => {
        cacheWhiteLabel(entitlements.white_label);
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
