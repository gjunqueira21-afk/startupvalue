import Link from "next/link";
import { Brand } from "./brand";

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="container footer-grid">
        <div className="footer-brand">
          <Brand />
          <p>Valuation inteligente para a sua empresa.</p>
          <p className="fine-print">Estimativas condicionadas às premissas informadas. Não constituem recomendação de investimento.</p>
        </div>
        <div>
          <h2>Produto</h2>
          <Link href="/#como-funciona">Como funciona</Link>
          <Link href="/pricing">Planos</Link>
          <Link href="/methodology">Metodologia</Link>
        </div>
        <div>
          <h2>Conta</h2>
          <Link href="/login">Entrar</Link>
          <Link href="/signup">Criar conta</Link>
          <Link href="/app">Preview do produto</Link>
        </div>
        <div>
          <h2>Institucional</h2>
          <span>Privacidade e LGPD</span>
          <span>Termos</span>
          <span>Segurança</span>
        </div>
      </div>
      <div className="container footer-bottom">
        <span>© 2026 QuantoVale</span>
        <span>Transparência · Probabilidade · Decisão</span>
      </div>
    </footer>
  );
}
