import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

type ChipProps = {
  active?: boolean;
  children: ReactNode;
  onClick?: () => void;
  className?: string;
};

export function Chip({ active, children, onClick, className }: ChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-full px-3 py-1.5 text-sm transition",
        active
          ? "bg-zinc-100 text-[#111315] shadow-lg shadow-black/20"
          : "border border-white/15 text-white/80 hover:border-white/40 hover:text-white",
        className,
      )}
    >
      {children}
    </button>
  );
}
