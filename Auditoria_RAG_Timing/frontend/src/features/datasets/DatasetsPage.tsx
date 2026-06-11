import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { api, Dataset, DatasetPreview } from "../../api/client";
import { Button, Card, ConfirmDialog } from "../../components/ui";

const DATASET_TEMPLATE = {
  alta_frecuencia: {
    corta: [],
    media: [],
    larga: []
  },
  media_frecuencia: {
    corta: [],
    media: [],
    larga: []
  },
  baja_frecuencia: {
    corta: [],
    media: [],
    larga: []
  }
};

function downloadDatasetTemplate() {
  const content = JSON.stringify(DATASET_TEMPLATE, null, 2);
  const url = URL.createObjectURL(new Blob([content], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "dataset_template.json";
  link.click();
  URL.revokeObjectURL(url);
}

function Distribution({ title, values }: { title: string; values: Record<string, number> }) {
  const total = Object.values(values).reduce((sum, value) => sum + value, 0) || 1;
  return (
    <div>
      <h3 className="text-sm font-medium mb-2">{title}</h3>
      <div className="space-y-2">
        {Object.entries(values).map(([key, value]) => (
          <div key={key}>
            <div className="flex justify-between text-xs text-slate-500">
              <span>{key}</span>
              <span>{value}</span>
            </div>
            <div className="h-2 rounded bg-slate-100">
              <div className="h-2 rounded bg-slate-800" style={{ width: `${(value / total) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function DatasetsPage() {
  const qc = useQueryClient();
  const datasets = useQuery({ queryKey: ["datasets"], queryFn: api.datasets });
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [datasetToDelete, setDatasetToDelete] = useState<Dataset | null>(null);
  const [message, setMessage] = useState("");
  const upload = useMutation({
    mutationFn: api.uploadDataset,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["datasets"] });
      setMessage("Dataset uploaded");
    },
    onError: (err) => setMessage(err instanceof Error ? err.message : "Upload failed")
  });
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Datasets</h1>
        <Button type="button" variant="secondary" className="flex items-center gap-2" onClick={downloadDatasetTemplate}>
          <Download size={16} />
          Download template
        </Button>
      </div>
      <Card>
        <div className="border border-dashed border-slate-300 rounded-md p-6 bg-slate-50">
          <input
            type="file"
            accept="application/json"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) upload.mutate(file);
            }}
          />
          <p className="text-sm text-slate-500 mt-2">Upload a JSON dataset using the required grouped frequency and length format.</p>
          {message && <p className={`text-sm mt-2 ${upload.isError ? "text-red-700" : "text-slate-600"}`}>{message}</p>}
        </div>
      </Card>
      <Card>
        <h2 className="font-semibold mb-3">Available datasets</h2>
        <div className="divide-y divide-slate-100">
          {(datasets.data ?? []).map((dataset) => (
            <div key={dataset.id} className="py-3 flex justify-between text-sm">
              <div>
                <div className="font-medium">{dataset.name}</div>
                <div className="text-slate-500">{dataset.total_queries} queries - {dataset.original_filename}</div>
              </div>
              <div className="flex gap-2">
                <Button
                  className="bg-slate-700"
                  onClick={async () => {
                    setMessage("");
                    setPreview(await api.datasetPreview(dataset.id));
                  }}
                >
                  Preview
                </Button>
                <Button
                  className="bg-red-700"
                  onClick={() => setDatasetToDelete(dataset)}
                >
                  Delete
                </Button>
              </div>
            </div>
          ))}
        </div>
      </Card>
      {preview && (
        <Card>
          <h2 className="font-semibold mb-3">Preview: {preview.dataset.name}</h2>
          <div className="grid grid-cols-2 gap-6 mb-4">
            <Distribution title="Frequency" values={preview.distribution.frequency} />
            <Distribution title="Length" values={preview.distribution.length} />
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left border-b">
                <th className="py-2">Frequency</th>
                <th>Length</th>
                <th>Query</th>
              </tr>
            </thead>
            <tbody>
              {preview.preview.map((query, index) => (
                <tr key={`${query.query}-${index}`} className="border-b border-slate-100">
                  <td className="py-2">{query.frequency}</td>
                  <td>{query.length}</td>
                  <td className="max-w-[720px] truncate">{query.query}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      <ConfirmDialog
        open={datasetToDelete !== null}
        title="Delete dataset"
        description={`Delete "${datasetToDelete?.name ?? ""}"? This action cannot be undone.`}
        onClose={() => setDatasetToDelete(null)}
        onConfirm={async () => {
          if (!datasetToDelete) return;
          try {
            await api.deleteDataset(datasetToDelete.id);
            if (preview?.dataset.id === datasetToDelete.id) setPreview(null);
            await qc.invalidateQueries({ queryKey: ["datasets"] });
          } catch (err) {
            setMessage(err instanceof Error ? err.message : "Could not delete dataset");
            throw err;
          }
        }}
      />
    </div>
  );
}
