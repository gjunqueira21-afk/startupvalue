import Link from "next/link";
import { AuthForm } from "./auth-form";
import { Brand } from "./brand";
import { Check } from "./icons";

export function AuthLayout({ mode }: { mode: "login" | "signup" }) {
  const isSignup = mode === "signup";
  return (
    <main id="main-content" className="auth-page">
      <section className="auth-panel">
        <Brand />
        <div className="auth-copy">
          <p className="eyebrow"><span /> VALUATION COM TRANSPARÊNCIA</p>
          <h1>Milhares de futuros.<br /><em>Uma tese mais clara.</em></h1>
          <p>Construa cenários, explicite incertezas e transforme projeções em decisões auditáveis.</p>
          <ul>
            <li><Check /> DCF e Venture Capital Method</li>
            <li><Check /> Simulações com seed reproduzível</li>
            <li><Check /> Drivers e análise de meta</li>
          </ul>
        </div>
        <p className="auth-panel-footer">Seus dados financeiros merecem isolamento, rastreabilidade e acesso autenticado.</p>
      </section>
      <section className="auth-card-wrap">
        <div className="auth-card">
          <div className="auth-card-heading">
            <p>ACESSO SEGURO</p>
            <h2>{isSignup ? "Crie sua conta" : "Bem-vindo de volta"}</h2>
            <span>{isSignup ? "Comece sua primeira análise de valuation." : "Acesse suas empresas, cenários e relatórios."}</span>
          </div>
          <div className="foundation-notice">
            <strong>SESSÃO SEGURA</strong>
            <span>O acesso usa senha com hash Argon2id e cookie HttpOnly emitido pela API.</span>
          </div>
          <AuthForm mode={mode} />
          <p className="auth-switch">
            {isSignup ? "Já possui uma conta?" : "Ainda não possui uma conta?"}{" "}
            <Link href={isSignup ? "/login" : "/signup"}>{isSignup ? "Entrar" : "Criar conta"}</Link>
          </p>
          <Link className="back-home" href="/">← Voltar para a página inicial</Link>
        </div>
      </section>
    </main>
  );
}
