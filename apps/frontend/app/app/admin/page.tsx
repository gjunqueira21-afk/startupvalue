import type { Metadata } from "next";
import { AdminView } from "@/components/admin-view";

export const metadata: Metadata = { title: "Painel administrativo" };

export default function AdminPage() {
  return <AdminView />;
}
