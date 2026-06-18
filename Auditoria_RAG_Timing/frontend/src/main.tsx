import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "./index.css";
import { AppLayout } from "./components/AppLayout";
import { LoginPage } from "./features/auth/LoginPage";
import { DashboardPage } from "./features/audits/DashboardPage";
import { TargetsPage } from "./features/targets/TargetsPage";
import { DatasetsPage } from "./features/datasets/DatasetsPage";
import { NewAuditPage } from "./features/audits/NewAuditPage";
import { TermInferencePage } from "./features/term-inference/TermInferencePage";
import { NewTermInferencePage } from "./features/term-inference/NewTermInferencePage";
import { api } from "./api/client";

const queryClient = new QueryClient();
const ResultsPage = React.lazy(() =>
  import("./features/audits/ResultsPage").then((module) => ({ default: module.ResultsPage }))
);
const TermInferenceResultsPage = React.lazy(() =>
  import("./features/term-inference/TermInferenceResultsPage").then((module) => ({ default: module.TermInferenceResultsPage }))
);

function Protected({ children }: { children: React.ReactNode }) {
  const session = useQuery({
    queryKey: ["current-user"],
    queryFn: api.me,
    retry: false
  });
  if (session.isPending) return <div className="min-h-screen grid place-items-center">Checking session...</div>;
  if (session.isError) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <Protected>
                <AppLayout />
              </Protected>
            }
          >
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="targets" element={<TargetsPage />} />
            <Route path="datasets" element={<DatasetsPage />} />
            <Route path="audits/new" element={<NewAuditPage />} />
            <Route path="audits/running/:id" element={<Navigate to="/dashboard" replace />} />
            <Route path="term-inference" element={<TermInferencePage />} />
            <Route path="term-inference/new" element={<NewTermInferencePage />} />
            <Route
              path="term-inference/results/:id"
              element={
                <React.Suspense fallback={<div className="grid min-h-64 place-items-center text-sm text-slate-500">Loading term inference...</div>}>
                  <TermInferenceResultsPage />
                </React.Suspense>
              }
            />
            <Route
              path="audits/results/:id"
              element={
                <React.Suspense fallback={<div className="grid min-h-64 place-items-center text-sm text-slate-500">Loading report...</div>}>
                  <ResultsPage />
                </React.Suspense>
              }
            />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
