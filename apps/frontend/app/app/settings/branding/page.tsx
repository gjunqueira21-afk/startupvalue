import type { Metadata } from "next";
import { BrandingSettingsView } from "@/components/branding-settings-view";

export const metadata: Metadata = { title: "Marca do relatório" };

export default function BrandingSettingsPage() {
  return <BrandingSettingsView />;
}
