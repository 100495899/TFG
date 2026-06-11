import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, AuditDashboardItem } from "../../api/client";
import { Button, Card, ConfirmDialog } from "../../components/ui";

const ACTIVE_STATUSES = new Set(["PENDING", "RUNNING", "ABORT_REQUESTED"]);

function progressPercent(audit: AuditDashboardItem) {
  return audit.progress_total ? Math.round((audit.progress_current / audit.progress_total) * 100) : 0;
}

export function DashboardPage() {
  const queryClient = useQueryClient();
  const [auditToAbort, setAuditToAbort] = useState<AuditDashboardItem | null>(null);
  const [auditToDelete, setAuditToDelete] = useState<AuditDashboardItem | null>(null);
  const audits = useQuery({
    queryKey: ["audit-dashboard"],
    queryFn: api.auditDashboard,
    refetchInterval: (query) => {
      const data = query.state.data as AuditDashboardItem[] | undefined;
      return data?.some((audit) => ACTIVE_STATUSES.has(audit.status)) ? 2000 : false;
    }
  });
  const allAudits = audits.data ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <Link to="/audits/new"><Button>New Audit</Button></Link>
      </div>
      <div className="grid grid-cols-4 gap-4">
        {["PENDING", "RUNNING", "COMPLETED", "FAILED"].map((status) => (
          <Card key={status}>
            <div className="text-sm text-slate-500">{status}</div>
            <div className="text-2xl font-semibold">{allAudits.filter((audit) => audit.status === status).length}</div>
          </Card>
        ))}
      </div>
      <div>
        <h2 className="mb-3 font-semibold">Audits</h2>
        <div className="space-y-3">
          {allAudits.map((audit) => {
            const percent = progressPercent(audit);
            const isActive = ACTIVE_STATUSES.has(audit.status);
            return (
              <Card key={audit.id}>
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">{audit.target_name}</span>
                      <span className="rounded bg-slate-100 px-2 py-1 text-xs font-medium">{audit.status}</span>
                    </div>
                    <div className="mt-1 text-sm text-slate-500">
                      {audit.dataset_name} · seed {audit.random_seed} · {audit.calibration_requests} warm-up requests
                    </div>
                    <div className="mt-1 truncate text-xs text-slate-400">{audit.id}</div>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    {isActive && <Button onClick={() => setAuditToAbort(audit)}>Abort</Button>}
                    <Link to={`/audits/results/${audit.id}`}><Button variant="secondary">Open results</Button></Link>
                    {!isActive && <Button onClick={() => setAuditToDelete(audit)}>Delete</Button>}
                  </div>
                </div>
                <div className="mt-4 flex justify-between text-sm">
                  <span>Progress</span>
                  <span>{audit.progress_current}/{audit.progress_total} ({percent}%)</span>
                </div>
                <div className="mt-2 h-3 rounded bg-slate-200">
                  <div className="h-3 rounded bg-slate-900" style={{ width: `${percent}%` }} />
                </div>
                <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
                  <div className="border border-slate-200 rounded p-3">
                    <div className="text-slate-500">Errors</div>
                    <div className="font-semibold">{audit.error_count}</div>
                  </div>
                  <div className="border border-slate-200 rounded p-3">
                    <div className="text-slate-500">Mean TTFB</div>
                    <div className="font-semibold">{audit.mean_ttfb_ms?.toFixed(2) ?? "-"} ms</div>
                  </div>
                  <div className="border border-slate-200 rounded p-3">
                    <div className="text-slate-500">Mean full response</div>
                    <div className="font-semibold">{audit.mean_full_response_ms?.toFixed(2) ?? "-"} ms</div>
                  </div>
                </div>
                {audit.error_message && <p className="mt-3 text-sm text-red-700">{audit.error_message}</p>}
              </Card>
            );
          })}
          {!allAudits.length && (
            <Card>
              <p className="text-sm text-slate-500">No audits yet.</p>
            </Card>
          )}
          {audits.isError && (
            <Card>
              <p className="text-sm text-red-700">Could not load audits.</p>
            </Card>
          )}
        </div>
      </div>
      <ConfirmDialog
        open={auditToAbort !== null}
        title="Abort audit"
        description={`Stop the audit against "${auditToAbort?.target_name ?? ""}" after its current request finishes?`}
        confirmLabel="Abort audit"
        pendingLabel="Aborting..."
        onClose={() => setAuditToAbort(null)}
        onConfirm={async () => {
          if (!auditToAbort) return;
          await api.abortAudit(auditToAbort.id);
          await queryClient.invalidateQueries({ queryKey: ["audit-dashboard"] });
        }}
      />
      <ConfirmDialog
        open={auditToDelete !== null}
        title="Delete audit"
        description={`Delete this audit and all its stored results? This action cannot be undone.`}
        onClose={() => setAuditToDelete(null)}
        onConfirm={async () => {
          if (!auditToDelete) return;
          await api.deleteAudit(auditToDelete.id);
          await queryClient.invalidateQueries({ queryKey: ["audit-dashboard"] });
        }}
      />
    </div>
  );
}
