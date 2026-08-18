import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, TermInferenceListItem } from "../../api/client";
import { Button, Card, ConfirmDialog } from "../../components/ui";

const ACTIVE_STATUSES = new Set(["PENDING", "RUNNING", "ABORT_REQUESTED"]);

function progressPercent(item: TermInferenceListItem) {
  return item.progress_total ? Math.round((item.progress_current / item.progress_total) * 100) : 0;
}

function countByStatus(items: TermInferenceListItem[], status: string) {
  return items.filter((item) => item.status === status).length;
}

export function TermInferencePage() {
  const queryClient = useQueryClient();
  const [abortItem, setAbortItem] = useState<TermInferenceListItem | null>(null);
  const [deleteItem, setDeleteItem] = useState<TermInferenceListItem | null>(null);
  const sessions = useQuery({
    queryKey: ["term-inference"],
    queryFn: api.termInferences,
    refetchInterval: (query) => {
      const data = query.state.data as TermInferenceListItem[] | undefined;
      return data?.some((item) => ACTIVE_STATUSES.has(item.status)) ? 2000 : false;
    }
  });
  const items = sessions.data ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Term Inference</h1>
        </div>
        <Link to="/term-inference/new"><Button>New inference</Button></Link>
      </div>
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        {["PENDING", "RUNNING", "COMPLETED", "FAILED"].map((status) => (
          <Card key={status}>
            <div className="text-sm text-slate-500">{status}</div>
            <div className="text-2xl font-semibold">{countByStatus(items, status)}</div>
          </Card>
        ))}
      </div>
      <div className="space-y-3">
        {items.map((item) => {
          const percent = progressPercent(item);
          const isActive = ACTIVE_STATUSES.has(item.status);
          return (
            <Card key={item.id}>
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">{item.target_name}</span>
                    <span className="rounded bg-slate-100 px-2 py-1 text-xs font-medium">{item.status}</span>
                  </div>
                  <div className="mt-1 text-sm text-slate-500">
                    {item.source_type === "audit" ? "Audit calibration" : "CSV calibration"} - {item.result_count} terms - seed {item.random_seed}
                  </div>
                  <div className="mt-1 truncate text-xs text-slate-400">{item.source_label}</div>
                </div>
                <div className="flex shrink-0 gap-2">
                  {isActive && <Button onClick={() => setAbortItem(item)}>Abort</Button>}
                  <Link to={`/term-inference/results/${item.id}`}><Button variant="secondary">Open results</Button></Link>
                  {!isActive && <Button onClick={() => setDeleteItem(item)}>Delete</Button>}
                </div>
              </div>
              <div className="mt-4 flex justify-between text-sm">
                <span>Progress</span>
                <span>{item.progress_current}/{item.progress_total} ({percent}%)</span>
              </div>
              <div className="mt-2 h-3 rounded bg-slate-200">
                <div className="h-3 rounded bg-slate-900" style={{ width: `${percent}%` }} />
              </div>
              {item.warning_message && <p className="mt-3 text-sm text-amber-700">{item.warning_message}</p>}
              {item.error_message && <p className="mt-3 text-sm text-red-700">{item.error_message}</p>}
            </Card>
          );
        })}
        {!items.length && <Card><p className="text-sm text-slate-500">No term inference sessions yet.</p></Card>}
        {sessions.isError && <Card><p className="text-sm text-red-700">Could not load term inference sessions.</p></Card>}
      </div>
      <ConfirmDialog
        open={abortItem !== null}
        title="Abort term inference"
        description={`Stop this term inference session after its current request finishes?`}
        confirmLabel="Abort"
        pendingLabel="Aborting..."
        onClose={() => setAbortItem(null)}
        onConfirm={async () => {
          if (!abortItem) return;
          await api.abortTermInference(abortItem.id);
          await queryClient.invalidateQueries({ queryKey: ["term-inference"] });
        }}
      />
      <ConfirmDialog
        open={deleteItem !== null}
        title="Delete term inference"
        description="Delete this term inference session and all its stored measurements? This action cannot be undone."
        onClose={() => setDeleteItem(null)}
        onConfirm={async () => {
          if (!deleteItem) return;
          await api.deleteTermInference(deleteItem.id);
          await queryClient.invalidateQueries({ queryKey: ["term-inference"] });
        }}
      />
    </div>
  );
}
