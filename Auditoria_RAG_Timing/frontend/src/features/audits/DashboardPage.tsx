import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import { Button, Card } from "../../components/ui";

export function DashboardPage() {
  const audits = useQuery({ queryKey: ["audits"], queryFn: api.audits });
  const recent = audits.data ?? [];
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
            <div className="text-2xl font-semibold">{recent.filter((a) => a.status === status).length}</div>
          </Card>
        ))}
      </div>
      <Card>
        <h2 className="font-semibold mb-3">Recent audits</h2>
        <div className="divide-y divide-slate-100">
          {recent.slice(0, 8).map((audit) => (
            <div key={audit.id} className="py-2 flex justify-between items-center gap-3 text-sm">
              <span className="truncate">{audit.id}</span>
              <div className="flex items-center gap-2">
                <span className="font-medium">{audit.status}</span>
                {audit.status === "COMPLETED" || audit.status === "FAILED" || audit.status === "ABORTED" ? (
                  <Link to={`/audits/results/${audit.id}`} className="text-slate-700 underline">Results</Link>
                ) : (
                  <Link to={`/audits/running/${audit.id}`} className="text-slate-700 underline">Monitor</Link>
                )}
                {audit.status !== "PENDING" && audit.status !== "RUNNING" && audit.status !== "ABORT_REQUESTED" && (
                  <button
                    className="text-red-700 underline"
                    onClick={async () => {
                      if (!window.confirm("Delete this audit and its results?")) return;
                      await api.deleteAudit(audit.id);
                      audits.refetch();
                    }}
                  >
                    Delete
                  </button>
                )}
              </div>
            </div>
          ))}
          {!recent.length && <div className="text-sm text-slate-500">No audits yet.</div>}
        </div>
      </Card>
    </div>
  );
}
