import { useEffect, useState } from "react";
import { X } from "lucide-react";

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`bg-white border border-slate-200 rounded-md p-4 ${className}`}>{children}</div>;
}

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger";
};

const buttonVariants = {
  primary: "bg-slate-900 text-white",
  secondary: "border border-slate-300 bg-white text-slate-700",
  danger: "bg-red-700 text-white"
};

export function Button({ children, className = "", variant = "primary", ...props }: ButtonProps) {
  return (
    <button className={`px-3 py-2 rounded-md text-sm disabled:opacity-50 ${buttonVariants[variant]} ${className}`} {...props}>
      {children}
    </button>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm" {...props} />;
}

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm font-mono" {...props} />;
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm bg-white" {...props} />;
}

type ModalProps = {
  open: boolean;
  title: string;
  children: React.ReactNode;
  onClose: () => void;
  className?: string;
};

export function Modal({ open, title, children, onClose, className = "" }: ModalProps) {
  useEffect(() => {
    if (!open) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        className={`w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-md bg-white shadow-xl ${className}`}
      >
        <div className="sticky top-0 flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
          <h2 id="modal-title" className="font-semibold">{title}</h2>
          <button type="button" onClick={onClose} className="p-1 text-slate-500 hover:text-slate-900" aria-label="Close dialog">
            <X size={18} />
          </button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  onConfirm: () => Promise<void>;
  onClose: () => void;
};

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Delete",
  onConfirm,
  onClose
}: ConfirmDialogProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) setError("");
  }, [open]);

  async function confirm() {
    setIsSubmitting(true);
    setError("");
    try {
      await onConfirm();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The action could not be completed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Modal open={open} title={title} onClose={isSubmitting ? () => undefined : onClose} className="max-w-md">
      <p className="text-sm text-slate-600">{description}</p>
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      <div className="mt-5 flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onClose} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button type="button" onClick={confirm} disabled={isSubmitting}>
          {isSubmitting ? "Deleting..." : confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}
