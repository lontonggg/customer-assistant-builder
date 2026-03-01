import type { ReactNode } from "react";

export function Label({
  children,
  hint,
}: {
  children: ReactNode;
  hint?: string;
}) {
  return (
    <div className="flex items-center justify-between text-sm font-medium text-zinc-700">
      <span>{children}</span>
      {hint ? <span className="text-xs text-zinc-500">{hint}</span> : null}
    </div>
  );
}
