import { FormEvent, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { Button, Card, Input, Select, Textarea } from "../../components/ui";

const DEFAULT_TERMS_JSON = JSON.stringify({
  terms: ["bitcoin", "playstation", "gutenberg"],
  negative_controls: ["zenthorium", "qrevanta"]
}, null, 2);

export function NewTermInferencePage() {
  const targets = useQuery({ queryKey: ["targets"], queryFn: api.targets });
  const audits = useQuery({ queryKey: ["audits"], queryFn: api.audits });
  const completedAudits = useMemo(() => (audits.data ?? []).filter((audit) => audit.status === "COMPLETED"), [audits.data]);
  const [targetId, setTargetId] = useState("");
  const [sourceMode, setSourceMode] = useState<"audit" | "csv">("audit");
  const [sourceAuditId, setSourceAuditId] = useState("");
  const [summaryCsv, setSummaryCsv] = useState<File | null>(null);
  const [termsJson, setTermsJson] = useState(DEFAULT_TERMS_JSON);
  const [probesPerRound, setProbesPerRound] = useState(6);
  const [maxProbes, setMaxProbes] = useState(30);
  const [seed, setSeed] = useState("");
  const [error, setError] = useState("");
  const [isLaunching, setIsLaunching] = useState(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const parsedPreview = useMemo(() => {
    try {
      const parsed = JSON.parse(termsJson) as { terms?: string[]; negative_controls?: string[] };
      return {
        terms: Array.isArray(parsed.terms) ? parsed.terms : [],
        controls: Array.isArray(parsed.negative_controls) ? parsed.negative_controls : []
      };
    } catch {
      return null;
    }
  }, [termsJson]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setIsLaunching(true);
    try {
      JSON.parse(termsJson);
      const form = new FormData();
      form.append("target_id", targetId);
      form.append("terms_payload", termsJson);
      form.append("probes_per_round", String(probesPerRound));
      form.append("max_probes_per_term", String(maxProbes));
      if (seed) form.append("random_seed", seed);
      if (sourceMode === "audit") {
        form.append("source_audit_id", sourceAuditId);
      } else if (summaryCsv) {
        form.append("summary_csv", summaryCsv);
      }
      const response = await api.startTermInference(form);
      await queryClient.invalidateQueries({ queryKey: ["term-inference"] });
      navigate(`/term-inference/results/${response.session_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start term inference");
    } finally {
      setIsLaunching(false);
    }
  }

  return (
    <div className="max-w-5xl space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">New Term Inference</h1>
        <p className="mt-1 text-sm text-slate-500">Use a previous timing profile to infer whether short terms appear present.</p>
      </div>
      <Card>
        <form onSubmit={submit} className="space-y-5">
          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-1">
              <span className="text-sm font-medium">Target system</span>
              <Select value={targetId} onChange={(event) => setTargetId(event.target.value)} required>
                <option value="">Select target</option>
                {(targets.data ?? []).map((target) => <option key={target.id} value={target.id}>{target.name}</option>)}
              </Select>
              <span className="block text-xs text-slate-500">The same endpoint family used during calibration is recommended.</span>
            </label>
            <label className="space-y-1">
              <span className="text-sm font-medium">Calibration source</span>
              <Select value={sourceMode} onChange={(event) => setSourceMode(event.target.value as "audit" | "csv")}>
                <option value="audit">Completed audit</option>
                <option value="csv">Summary CSV</option>
              </Select>
              <span className="block text-xs text-slate-500">Calibration uses only short high/low groups.</span>
            </label>
          </div>

          {sourceMode === "audit" ? (
            <label className="block space-y-1">
              <span className="text-sm font-medium">Completed audit</span>
              <Select value={sourceAuditId} onChange={(event) => setSourceAuditId(event.target.value)} required>
                <option value="">Select completed audit</option>
                {completedAudits.map((audit) => <option key={audit.id} value={audit.id}>{audit.id} · seed {audit.random_seed}</option>)}
              </Select>
            </label>
          ) : (
            <label className="block space-y-1">
              <span className="text-sm font-medium">Summary CSV</span>
              <Input type="file" accept=".csv,text/csv" onChange={(event) => setSummaryCsv(event.target.files?.[0] ?? null)} required />
              <span className="block text-xs text-slate-500">Upload the Summary CSV, not the raw request CSV.</span>
            </label>
          )}

          <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
            <label className="space-y-1">
              <span className="text-sm font-medium">Terms JSON</span>
              <Textarea rows={13} value={termsJson} onChange={(event) => setTermsJson(event.target.value)} />
            </label>
            <div className="rounded-md border border-slate-200 p-4 text-sm">
              <div className="font-medium">Preview</div>
              {!parsedPreview ? (
                <p className="mt-2 text-red-700">Invalid JSON</p>
              ) : (
                <div className="mt-2 space-y-3">
                  <div>
                    <div className="text-xs uppercase text-slate-500">Terms</div>
                    <div className="mt-1 text-2xl font-semibold">{parsedPreview.terms.length}</div>
                    <p className="mt-1 text-xs text-slate-500">{parsedPreview.terms.slice(0, 5).join(", ")}</p>
                  </div>
                  <div>
                    <div className="text-xs uppercase text-slate-500">Negative controls</div>
                    <div className="mt-1 text-2xl font-semibold">{parsedPreview.controls.length || "default"}</div>
                    <p className="mt-1 text-xs text-slate-500">{parsedPreview.controls.slice(0, 5).join(", ") || "Internal controls will be used."}</p>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <label className="space-y-1">
              <span className="text-sm font-medium">Probes per round</span>
              <Input type="number" min={1} max={30} value={probesPerRound} onChange={(event) => setProbesPerRound(Number(event.target.value))} />
              <span className="block text-xs text-slate-500">Each active term receives this many probes per adaptive round.</span>
            </label>
            <label className="space-y-1">
              <span className="text-sm font-medium">Max probes</span>
              <Input type="number" min={1} max={100} value={maxProbes} onChange={(event) => setMaxProbes(Number(event.target.value))} />
              <span className="block text-xs text-slate-500">Hard limit per term before it remains inconclusive.</span>
            </label>
            <label className="space-y-1">
              <span className="text-sm font-medium">Random seed</span>
              <Input type="number" min={1} max={2147483647} value={seed} onChange={(event) => setSeed(event.target.value)} placeholder="Auto" />
              <span className="block text-xs text-slate-500">Leave empty to generate a new reproducible seed.</span>
            </label>
          </div>
          {error && <p className="text-sm text-red-700">{error}</p>}
          <Button disabled={isLaunching}>{isLaunching ? "Launching..." : "Launch inference"}</Button>
        </form>
      </Card>
    </div>
  );
}
