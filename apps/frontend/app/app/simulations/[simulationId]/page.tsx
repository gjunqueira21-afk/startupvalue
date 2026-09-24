import type { Metadata } from "next";
import { SimulationResultView } from "@/components/simulation-result-view";

export const metadata: Metadata = { title: "Resultado da simulação" };

export default async function SimulationPage({
  params,
}: {
  params: Promise<{ simulationId: string }>;
}) {
  const { simulationId } = await params;
  return <SimulationResultView simulationId={simulationId} />;
}
