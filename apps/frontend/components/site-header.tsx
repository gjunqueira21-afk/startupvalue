import Link from "next/link";
import { Brand } from "./brand";

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="container header-inner">
        <Brand />
        <nav className="desktop-nav" aria-label="Navegação principal">
          <Link href="/#como-funciona">Como funciona</Link>
          <Link href="/methodology">Metodologia</Link>
          <Link href="/pricing">Planos</Link>
        </nav>
        <div className="header-actions">
          <Link className="text-link header-login" href="/login">Entrar</Link>
          <Link className="button button-small button-primary" href="/signup">Começar análise</Link>
        </div>
      </div>
    </header>
  );
}
