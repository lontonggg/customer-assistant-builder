import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export function FieldShell({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-zinc-200 bg-white px-4 py-3 transition hover:border-zinc-300 focus-within:border-zinc-400",
        className,
      )}
    >
      {children}
    </div>
  );
}
