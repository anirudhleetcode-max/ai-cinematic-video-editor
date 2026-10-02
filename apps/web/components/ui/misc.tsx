import type { HTMLAttributes, InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";
import { forwardRef } from "react";
import { cn } from "@/lib/cn";

export const Card = ({ className, ...p }: HTMLAttributes<HTMLDivElement>) => <div className={cn("panel", className)} {...p} />;

export const CardHeader = ({ title, subtitle, action, className }: { title: ReactNode; subtitle?: ReactNode; action?: ReactNode; className?: string }) => (
  <div className={cn("flex items-start justify-between gap-3 border-b border-white/[0.05] px-4 py-3", className)}>
    <div>
      <div className="text-sm font-semibold tracking-tight text-fog">{title}</div>
      {subtitle ? <div className="mt-0.5 text-xs text-fog-500">{subtitle}</div> : null}
    </div>
    {action}
  </div>
);

const tones = {
  neutral: "bg-white/[0.06] text-fog-300 border-white/[0.08]",
  ember: "bg-ember/12 text-ember border-ember/25",
  ok: "bg-ok/10 text-ok border-ok/25",
  warn: "bg-warn/10 text-warn border-warn/25",
  bad: "bg-bad/10 text-bad border-bad/25",
  cyan: "bg-cyan/10 text-cyan border-cyan/25",
};

export const Badge = ({ tone = "neutral", className, children }: { tone?: keyof typeof tones; className?: string; children: ReactNode }) => (
  <span className={cn("inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium leading-none", tones[tone], className)}>{children}</span>
);

export const Progress = ({ value, className, indeterminate }: { value: number; className?: string; indeterminate?: boolean }) => (
  <div className={cn("relative h-1.5 overflow-hidden rounded-full bg-white/[0.06]", className)}>
    <div
      className={cn("h-full rounded-full bg-gradient-to-r from-ember-600 to-ember transition-[width] duration-500", indeterminate && "animate-shimmer bg-[length:200%_100%]")}
      style={{ width: `${Math.max(0, Math.min(100, value * 100))}%` }}
    />
  </div>
);

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(({ className, ...p }, ref) => (
  <input
    ref={ref}
    className={cn(
      "h-10 w-full rounded-lg border border-white/[0.08] bg-ink-900 px-3 text-sm text-fog placeholder:text-fog-500 focus:border-ember/50 focus:outline-none focus:ring-2 focus:ring-ember/20",
      className,
    )}
    {...p}
  />
));
Input.displayName = "Input";

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...p }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "w-full resize-none rounded-xl border border-white/[0.08] bg-ink-900 p-3.5 text-[14px] leading-relaxed text-fog placeholder:text-fog-500 focus:border-ember/50 focus:outline-none focus:ring-2 focus:ring-ember/20",
      className,
    )}
    {...p}
  />
));
Textarea.displayName = "Textarea";

export function Segmented<T extends string>({ value, options, onChange }: { value: T; options: { value: T; label: string; hint?: string }[]; onChange: (v: T) => void }) {
  return (
    <div className="inline-flex rounded-lg border border-white/[0.08] bg-ink-900 p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          title={o.hint}
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
            value === o.value ? "bg-white/[0.09] text-fog shadow-sm" : "text-fog-500 hover:text-fog-300",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export const Empty = ({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) => (
  <div className="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center">
    {icon ? <div className="text-fog-500">{icon}</div> : null}
    <div className="text-sm font-medium text-fog-300">{title}</div>
    {children ? <div className="max-w-sm text-xs text-fog-500">{children}</div> : null}
  </div>
);
