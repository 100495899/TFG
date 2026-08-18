import { FormEvent, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { Button, Card, Input } from "../../components/ui";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const user = await api.login(email, password);
      queryClient.setQueryData(["current-user"], user);
      navigate("/audits");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    }
  }

  return (
    <div className="min-h-screen grid place-items-center bg-slate-100">
      <Card className="w-[380px]">
        <h1 className="text-xl font-semibold mb-1">RAG Timing Audit</h1>
        <p className="text-sm text-slate-500 mb-4">Admin access required</p>
        <div className="text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded-md p-3 mb-4">
          Authorized security testing only. Use this tool against systems you own or have explicit permission to audit.
        </div>
        <form onSubmit={submit} className="space-y-3">
          <Input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
          <Input value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" type="password" />
          {error && <div className="text-sm text-red-600">{error}</div>}
          <Button className="w-full">Login</Button>
        </form>
      </Card>
    </div>
  );
}
