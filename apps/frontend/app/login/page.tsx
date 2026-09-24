import type { Metadata } from "next";
import { AuthLayout } from "@/components/auth-layout";

export const metadata: Metadata = { title: "Entrar" };
export default function LoginPage() { return <AuthLayout mode="login" />; }
