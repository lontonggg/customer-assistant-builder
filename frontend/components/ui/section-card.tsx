import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

type SectionCardProps = {
  title: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
  titleClassName?: string;
};

export function SectionCard({
  title,
  subtitle,
  children,
  className,
  titleClassName,
}: SectionCardProps) {
  return (
    <div
      className={cn(
        "glass rounded-3xl border border-zinc-200 p-6 shadow-lg shadow-zinc-200/80 lg:p-7",
        className,
      )}
    >
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <p
            className={cn(
              "text-xl uppercase tracking-[0.2em] text-zinc-700",
              titleClassName,
            )}
          >
            {title}
          </p>
          {subtitle ? (
            <p className="mt-1 text-sm text-zinc-600">{subtitle}</p>
          ) : null}
        </div>
      </div>
      {children}
    </div>
  );
}
