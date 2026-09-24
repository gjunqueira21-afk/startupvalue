import Link from "next/link";
import { Brand } from "./brand";
import { BuildingIcon, ChartIcon, FileIcon, GridIcon } from "./icons";
import { SessionSummary } from "./session-summary";

const navigation = [
  ["/app", "Visão geral", GridIcon],
  ["/app#empresas", "Empresas", BuildingIcon],
  ["/app#analises", "Análises", ChartIcon],
  ["/app#relatorios", "Relatórios", FileIcon],
] as const;

export function AppShell({ children, active = "/app" }: { children: React.ReactNode; active?: string }) {
  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <Brand />
        <SessionSummary />
        <nav aria-label="Área do produto">
          {navigation.map(([href, label, Icon]) => (
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
