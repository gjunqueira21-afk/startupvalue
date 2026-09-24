import type { Metadata } from "next";
import { Brand } from "@/components/brand";
import { PasswordRecoveryForm } from "@/components/password-recovery-form";

export const metadata: Metadata = { title: "Recuperar senha" };

export default function ForgotPasswordPage() {
  return (
    <main id="main-content" className="auth-page">
      <section className="auth-panel">
        <Brand />
        <div className="auth-copy">
          <p className="eyebrow"><span /> ACESSO SEGURO</p>
          <h1>Retome sua análise com segurança.</h1>
          <p>Solicite um link temporário para criar uma nova senha da sua conta StartupValue.</p>
        </div>
        <p className="auth-panel-footer">O link expira em 30 minutos e pode ser usado uma única vez.</p>
      </section>
      <section className="auth-card-wrap">
        <div className="auth-card">
          <div className="auth-card-heading">
            <p>RECUPERAÇÃO DE CONTA</p>
            <h2>Esqueceu sua senha?</h2>
            <span>Informe o e-mail cadastrado para receber as instruções.</span>
          </div>
          <PasswordRecoveryForm mode="request" />
        </div>
      </section>
    </main>
  );
}
