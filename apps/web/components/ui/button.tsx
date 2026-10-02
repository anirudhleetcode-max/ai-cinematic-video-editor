import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

const button = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember/60 disabled:pointer-events-none disabled:opacity-40",
  {
    variants: {
      variant: {
        primary: "bg-ember text-ink hover:bg-ember-400 shadow-glow",
        secondary: "bg-white/[0.06] text-fog hover:bg-white/[0.1] border border-white/[0.08]",
        ghost: "text-fog-300 hover:text-fog hover:bg-white/[0.05]",
        danger: "bg-bad/15 text-bad hover:bg-bad/25 border border-bad/30",
        outline: "border border-white/[0.12] text-fog hover:border-ember/60 hover:text-ember",
      },
      size: { sm: "h-8 px-3 text-xs", md: "h-10 px-4", lg: "h-12 px-6 text-[15px]", icon: "h-9 w-9" },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof button> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, ...props }, ref) => (
  <button ref={ref} className={cn(button({ variant, size }), className)} {...props} />
));
Button.displayName = "Button";
