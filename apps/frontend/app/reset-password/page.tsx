import type { Metadata } from "next";
import { Brand } from "@/components/brand";
import { PasswordRecoveryForm } from "@/components/password-recovery-form";

export const metadata: Metadata = { title: "Redefinir senha" };

export default function ResetPasswordPage() {
  return (
    <main id="main-content" className="auth-page">
      <section className="auth-panel">
        <Brand />
        <div className="auth-copy">
          <p className="eyebrow"><span /> ACESSO SEGURO</p>
          <h1>Uma nova senha. Seus dados preservados.</h1>
          <p>Após a troca, todas as sessões anteriores serão encerradas.</p>
        </div>
        <p className="auth-panel-footer">Links de recuperação expiram em 30 minutos e são de uso único.</p>
      </section>
      <section className="auth-card-wrap">
        <div className="auth-card">
          <div className="auth-card-heading">
            <p>REDEFINIÇÃO DE SENHA</p>
            <h2>Crie sua nova senha</h2>
            <span>Use pelo menos 12 caracteres.</span>
          </div>
          <PasswordRecoveryForm mode="reset" />
        </div>
      </section>
    </main>
  );
}
