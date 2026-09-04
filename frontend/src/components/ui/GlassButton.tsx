import type { ButtonHTMLAttributes, ReactNode } from "react";

type GlassButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  variant?: "primary" | "secondary";
};

export default function GlassButton({
  children,
  variant = "primary",
  className = "",
  ...props
}: GlassButtonProps) {
  return (
    <button
      className={`glass-button glass-button--${variant} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}