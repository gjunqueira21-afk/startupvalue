"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getSession, logout, type SessionResponse } from "@/lib/api/auth";

function initials(name: string | undefined): string {
  if (!name) return "SV";
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((part) => part[0]?.toUpperCase() ?? "").join("") || "SV";
}

export function SessionSummary() {
  const router = useRouter();
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [checked, setChecked] = useState(false);
  const [logoutError, setLogoutError] = useState("");

  useEffect(() => {
    let active = true;
    getSession()
      .then((value) => {
        if (active) setSession(value);
      })
      .catch(() => {
        if (active) setSession(null);
      })
      .finally(() => {
        if (active) setChecked(true);
      });
    return () => {
      active = false;
    };
  }, []);

  const name = session?.name ?? "Visitante";
  async function signOut() {
    setLogoutError("");
    try {
      await logout();
      setSession(null);
      router.replace("/login");
      router.refresh();
    } catch {
      setLogoutError("Não foi possível sair. Tente novamente.");
    }
  }
  return (
    <>
      <div className="workspace-select">
        <span>WORKSPACE</span>
        <strong>{session ? "Workspace conectado" : "Sessão não verificada"}</strong>
        <small>{session ? `Role: ${session.role}` : checked ? "Entre para persistir análises" : "Verificando sessão"}</small>
      </div>
      <div className="sidebar-bottom">
        <span>{initials(session?.name)}</span>
        <div>
          <strong>{name}</strong>
          <small>{session ? session.email : "Sem sessão ativa"}</small>
          {session && <button className="sidebar-logout" type="button" onClick={signOut}>Sair da conta</button>}
          {logoutError && <small role="alert">{logoutError}</small>}
        </div>
      </div>
      {session && <button className="mobile-logout" type="button" onClick={signOut}>Sair</button>}
    </>
  );
}
