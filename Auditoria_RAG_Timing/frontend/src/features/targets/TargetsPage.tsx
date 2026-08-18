import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, Target } from "../../api/client";
import { Button, Card, ConfirmDialog, Input, Modal, Textarea } from "../../components/ui";

type TargetForm = {
  name: string;
  endpoint: string;
  headers: string;
  payload: string;
  timeout: number;
  verifyTls: boolean;
};

const emptyForm: TargetForm = {
  name: "",
  endpoint: "",
  headers: '{"Content-Type":"application/json"}',
  payload: '{"question":"{{QUERY}}"}',
  timeout: 30,
  verifyTls: true
};

function formFromTarget(target: Target): TargetForm {
  return {
    name: target.name,
    endpoint: target.endpoint_url,
    headers: JSON.stringify(target.headers ?? {}, null, 2),
    payload: JSON.stringify(target.payload_template, null, 2),
    timeout: target.timeout_seconds,
    verifyTls: target.verify_tls
  };
}

function targetPayload(form: TargetForm) {
  return {
    name: form.name,
    endpoint_url: form.endpoint,
    headers: JSON.parse(form.headers || "{}"),
    payload_template: JSON.parse(form.payload || "{}"),
    timeout_seconds: form.timeout,
    verify_tls: form.verifyTls
  };
}

function TargetFormFields({
  form,
  setForm,
  compact = false
}: {
  form: TargetForm;
  setForm: React.Dispatch<React.SetStateAction<TargetForm>>;
  compact?: boolean;
}) {
  return (
    <div className={`grid grid-cols-2 ${compact ? "gap-3" : "gap-4"}`}>
      <label className="space-y-1">
        <span className="text-sm font-medium">Name</span>
        <Input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} required />
      </label>
      <div className="space-y-1">
        <span className="text-sm font-medium">HTTP method</span>
        <div className="flex h-[38px] items-center">
          <span className="rounded bg-emerald-100 px-2 py-1 text-xs font-semibold text-emerald-800">POST</span>
          <span className="ml-2 text-xs text-slate-500">Requests are sent as JSON.</span>
        </div>
      </div>
      <label className="col-span-2 space-y-1">
        <span className="text-sm font-medium">Endpoint URL</span>
        <Input value={form.endpoint} onChange={(event) => setForm((current) => ({ ...current, endpoint: event.target.value }))} required />
      </label>
      <label className="space-y-1">
        <span className="text-sm font-medium">Timeout seconds</span>
        <Input
          type="number"
          min={1}
          max={300}
          value={form.timeout}
          onChange={(event) => setForm((current) => ({ ...current, timeout: Number(event.target.value) }))}
          required
        />
      </label>
      <label className="flex items-center gap-2 self-end pb-2 text-sm">
        <input
          type="checkbox"
          checked={form.verifyTls}
          onChange={(event) => setForm((current) => ({ ...current, verifyTls: event.target.checked }))}
        />
        Verify TLS
      </label>
      <label className="space-y-1">
        <span className="text-sm font-medium">Headers</span>
        <Textarea rows={compact ? 4 : 5} value={form.headers} onChange={(event) => setForm((current) => ({ ...current, headers: event.target.value }))} />
      </label>
      <label className="space-y-1">
        <span className="text-sm font-medium">Payload template</span>
        <Textarea rows={compact ? 4 : 5} value={form.payload} onChange={(event) => setForm((current) => ({ ...current, payload: event.target.value }))} />
        <span className="block text-xs text-slate-500">Use {"{{QUERY}}"} where the query should be injected.</span>
      </label>
    </div>
  );
}

export function TargetsPage() {
  const qc = useQueryClient();
  const targets = useQuery({ queryKey: ["targets"], queryFn: api.targets });
  const [createForm, setCreateForm] = useState<TargetForm>(emptyForm);
  const [editingTarget, setEditingTarget] = useState<Target | null>(null);
  const [editForm, setEditForm] = useState<TargetForm>(emptyForm);
  const [targetToDelete, setTargetToDelete] = useState<Target | null>(null);
  const [message, setMessage] = useState("");
  const [editMessage, setEditMessage] = useState("");
  const [testMessage, setTestMessage] = useState("");
  const createTarget = useMutation({
    mutationFn: api.createTarget,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["targets"] });
      setMessage("Target saved");
      setCreateForm(emptyForm);
    },
    onError: (err) => setMessage(err instanceof Error ? err.message : "Error")
  });
  const updateTarget = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: unknown }) => api.updateTarget(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["targets"] });
      setEditingTarget(null);
      setEditMessage("");
      setTestMessage("Target updated");
    },
    onError: (err) => setEditMessage(err instanceof Error ? err.message : "Could not update target")
  });

  function submitCreate(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    try {
      createTarget.mutate(targetPayload(createForm));
    } catch {
      setMessage("Headers or payload JSON is invalid");
    }
  }

  function submitEdit(event: FormEvent) {
    event.preventDefault();
    if (!editingTarget) return;
    setEditMessage("");
    try {
      updateTarget.mutate({ id: editingTarget.id, payload: targetPayload(editForm) });
    } catch {
      setEditMessage("Headers or payload JSON is invalid");
    }
  }

  function openEdit(target: Target) {
    setEditingTarget(target);
    setEditForm(formFromTarget(target));
    setEditMessage("");
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Targets</h1>
      <Card>
        <h2 className="mb-4 font-semibold">Add target</h2>
        <form onSubmit={submitCreate}>
          <TargetFormFields form={createForm} setForm={setCreateForm} />
          {message && <div className="mt-3 text-sm text-slate-600">{message}</div>}
          <Button className="mt-4 w-fit" disabled={createTarget.isPending}>
            {createTarget.isPending ? "Saving..." : "Save target"}
          </Button>
        </form>
      </Card>
      <Card>
        <h2 className="font-semibold mb-3">Configured targets</h2>
        {testMessage && <p className="text-sm text-slate-600 mb-3">{testMessage}</p>}
        <div className="divide-y divide-slate-100">
          {(targets.data ?? []).map((target) => (
            <div key={target.id} className="py-3 flex justify-between gap-4 text-sm">
              <div>
                <div className="font-medium">{target.name}</div>
                <div className="text-slate-500">POST {target.endpoint_url}</div>
                <div className="text-xs text-slate-400">timeout {target.timeout_seconds}s - TLS {target.verify_tls ? "on" : "off"}</div>
              </div>
              <div className="flex gap-2">
                <Button className="bg-slate-700" onClick={() => openEdit(target)}>Edit</Button>
                <Button
                  className="bg-slate-700"
                  onClick={async () => {
                    setTestMessage("Testing target...");
                    try {
                      const result = await api.testTarget(target.id, "time");
                      setTestMessage(`Target test OK: ${result.ttfb_ms?.toFixed(2) ?? "-"} ms TTFB`);
                    } catch (err) {
                      setTestMessage(err instanceof Error ? err.message : "Target test failed");
                    }
                  }}
                >
                  Test
                </Button>
                <Button
                  onClick={() => setTargetToDelete(target)}
                >
                  Delete
                </Button>
              </div>
            </div>
          ))}
        </div>
      </Card>
      <Modal open={editingTarget !== null} title={`Edit target: ${editingTarget?.name ?? ""}`} onClose={() => setEditingTarget(null)}>
        <form onSubmit={submitEdit}>
          <TargetFormFields form={editForm} setForm={setEditForm} compact />
          {editMessage && <div className="mt-3 text-sm text-red-700">{editMessage}</div>}
          <div className="mt-4 flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => setEditingTarget(null)}>
              Cancel
            </Button>
            <Button disabled={updateTarget.isPending}>
              {updateTarget.isPending ? "Updating..." : "Update target"}
            </Button>
          </div>
        </form>
      </Modal>
      <ConfirmDialog
        open={targetToDelete !== null}
        title="Delete target"
        description={`Delete "${targetToDelete?.name ?? ""}"? This action cannot be undone.`}
        onClose={() => setTargetToDelete(null)}
        onConfirm={async () => {
          if (!targetToDelete) return;
          try {
            await api.deleteTarget(targetToDelete.id);
            await qc.invalidateQueries({ queryKey: ["targets"] });
          } catch (err) {
            setTestMessage(err instanceof Error ? err.message : "Could not delete target");
            throw err;
          }
        }}
      />
    </div>
  );
}
