import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function Icon({ children, ...props }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      {children}
    </svg>
  );
}

export function OverviewIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z" />
    </Icon>
  );
}

export function CasesIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M4 7.5h16v11H4zM8 7.5v-2h8v2M4 11.5h16" />
    </Icon>
  );
}

export function ResearchIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="10.5" cy="10.5" r="5.5" />
      <path d="m15 15 5 5M8 10.5h5M10.5 8v5" />
    </Icon>
  );
}

export function EvidenceIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M6 3.5h9l3 3v14H6zM15 3.5v4h4M9 12h6M9 16h6" />
    </Icon>
  );
}

export function ReportsIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M5 20V9m5 11V4m5 16v-7m5 7V7" />
    </Icon>
  );
}

export function ShieldIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M12 3 5 6v5c0 4.6 2.9 8.1 7 10 4.1-1.9 7-5.4 7-10V6z" />
      <path d="m9 12 2 2 4-4" />
    </Icon>
  );
}

export function AuditIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M7 4h10v16H7zM10 8h4M10 12h4M10 16h4" />
    </Icon>
  );
}

export function ArrowIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M5 12h14m-5-5 5 5-5 5" />
    </Icon>
  );
}

export function CheckIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="m5 12 4 4L19 6" />
    </Icon>
  );
}

export function LockIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <rect x="5" y="10" width="14" height="10" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
    </Icon>
  );
}

export function MenuIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M4 7h16M4 12h16M4 17h16" />
    </Icon>
  );
}
