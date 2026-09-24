import { apiRequest } from "./client";

export interface DashboardAnalysis {
  simulation_id: string;
  startup_id: string;
  startup_name: string;
  currency: string;
  scenario_name: string;
  status: string;
  seed: number;
  simulation_count: number;
  model_version: string;
  created_at: string;
  p25: number | null;
  p50: number | null;
  p75: number | null;
}

export interface DashboardResponse {
  company_count: number;
  scenario_count: number;
  simulation_count: number;
  scenario_runs: number;
  report_count: number;
  recent_analyses: DashboardAnalysis[];
}

export function getDashboard() {
  return apiRequest<DashboardResponse>("/api/v1/dashboard", { method: "GET" });
}
