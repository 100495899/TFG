export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`bg-white border border-slate-200 rounded-md p-4 ${className}`}>{children}</div>;
}

export function Button({ children, className = "", ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button className={`px-3 py-2 rounded-md bg-slate-900 text-white text-sm disabled:opacity-50 ${className}`} {...props}>
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
