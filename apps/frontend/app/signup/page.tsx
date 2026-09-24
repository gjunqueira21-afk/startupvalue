import type { Metadata } from "next";
import { AuthLayout } from "@/components/auth-layout";

export const metadata: Metadata = { title: "Criar conta" };
export default function SignupPage() { return <AuthLayout mode="signup" />; }
