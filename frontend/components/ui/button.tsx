import Link from "next/link";
import { cn } from "@/lib/utils";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "outline" | "ghost";
type Size = "md" | "sm";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
  asChild?: boolean;
  href?: string;
};

export function Button({
  className,
  variant = "primary",
  size = "md",
  leftIcon,
  rightIcon,
  children,
  asChild = false,
  href,
  ...props
}: ButtonProps) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition active:scale-[0.99] cursor-pointer disabled:cursor-not-allowed disabled:active:scale-100 disabled:opacity-55";

  const sizes: Record<Size, string> = {
    md: "px-5 py-2.5 text-sm",
    sm: "px-3 py-1.5 text-xs",
  };

  const variants: Record<Variant, string> = {
    primary:
      "bg-zinc-900 text-white shadow-md shadow-zinc-300/60 hover:bg-zinc-800 disabled:bg-zinc-300 disabled:text-zinc-600 disabled:shadow-none",
    outline:
      "border border-zinc-300 text-zinc-800 hover:border-zinc-400 hover:bg-zinc-100 disabled:border-zinc-200 disabled:bg-zinc-100 disabled:text-zinc-500",
    ghost: "text-zinc-700 hover:text-zinc-900 hover:bg-zinc-100 disabled:text-zinc-400 disabled:hover:bg-transparent",
  };

  if (asChild && href) {
    return (
      <Link
        href={href}
        className={cn(base, sizes[size], variants[variant], className)}
      >
        {leftIcon}
        {children}
        {rightIcon}
      </Link>
    );
  }

  return (
    <button
      className={cn(base, sizes[size], variants[variant], className)}
      {...props}
    >
      {leftIcon}
      {children}
      {rightIcon}
    </button>
  );
}
