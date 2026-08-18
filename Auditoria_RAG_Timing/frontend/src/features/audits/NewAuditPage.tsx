import { FormEvent, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { Button, Card, Input, Select } from "../../components/ui";

export function NewAuditPage() {
  const targets = useQuery({ queryKey: ["targets"], queryFn: api.targets });
  const datasets = useQuery({ queryKey: ["datasets"], queryFn: api.datasets });
  const [targetId, setTargetId] = useState("");
  const [datasetId, setDatasetId] = useState("");
  const [calibration, setCalibration] = useState(3);
  const [seed, setSeed] = useState("");
  const [error, setError] = useState("");
  const [isLaunching, setIsLaunching] = useState(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const selectedTarget = targets.data?.find((target) => target.id === targetId);
  const selectedDataset = datasets.data?.find((dataset) => dataset.id === datasetId);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setIsLaunching(true);
    try {
      const payload: Record<string, unknown> = {
        target_id: targetId,
        dataset_id: datasetId,
        calibration_requests: calibration
      };
      if (seed) payload.random_seed = Number(seed);
      await api.startAudit(payload);
      await queryClient.invalidateQueries({ queryKey: ["audit-dashboard"] });
      navigate("/audits");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start audit");
    } finally {
      setIsLaunching(false);
    }
  }

  return (
    <div className="space-y-4 max-w-4xl">
      <h1 className="text-2xl font-semibold">New Audit</h1>
      <Card>
        <form onSubmit={submit} className="space-y-5">
          <div className="grid grid-cols-2 gap-4">
            <label className="space-y-1">
              <span className="text-sm font-medium">Target system</span>
              <Select value={targetId} onChange={(e) => setTargetId(e.target.value)} required>
                <option value="">Select target</option>
                {(targets.data ?? []).map((target) => <option key={target.id} value={target.id}>{target.name}</option>)}
              </Select>
              <span className="block text-xs text-slate-500">The RAG endpoint that will receive the audit queries.</span>
            </label>
            <label className="space-y-1">
              <span className="text-sm font-medium">Query dataset</span>
              <Select value={datasetId} onChange={(e) => setDatasetId(e.target.value)} required>
                <option value="">Select dataset</option>
                {(datasets.data ?? []).map((dataset) => <option key={dataset.id} value={dataset.id}>{dataset.name} ({dataset.total_queries} queries)</option>)}
              </Select>
              <span className="block text-xs text-slate-500">All validated queries in the selected dataset will be executed once.</span>
            </label>
          </div>
          {(selectedTarget || selectedDataset) && (
            <div className="grid grid-cols-2 gap-4 border-y border-slate-200 py-4 text-sm">
              <div>
                <div className="text-slate-500">Selected endpoint</div>
                <div className="mt-1 break-all font-medium">{selectedTarget?.endpoint_url ?? "Select a target"}</div>
              </div>
              <div>
                <div className="text-slate-500">Requests in this audit</div>
                <div className="mt-1 font-medium">{selectedDataset?.total_queries ?? 0} measured queries</div>
              </div>
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <label className="space-y-1">
              <span className="text-sm font-medium">Warm-up requests</span>
              <Input type="number" min={1} max={100} value={calibration} onChange={(e) => setCalibration(Number(e.target.value))} required />
              <span className="block text-xs text-slate-500">
                Requests sent before measurement to establish and warm the HTTP connection. At least 3 are recommended.
              </span>
            </label>
            <label className="space-y-1">
              <span className="text-sm font-medium">Random seed</span>
              <Input
                type="number"
                min={1}
                max={2147483647}
                value={seed}
                onChange={(e) => setSeed(e.target.value)}
                placeholder="Generated automatically"
              />
              <span className="block text-xs text-slate-500">
                Controls query shuffling. Reuse a seed to reproduce the same execution order.
              </span>
            </label>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <Button disabled={isLaunching}>{isLaunching ? "Launching..." : "Launch audit"}</Button>
        </form>
      </Card>
    </div>
  );
}
