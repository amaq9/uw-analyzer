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

export function SkillsIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="m12 3 1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5z" />
      <path d="m18.5 14 .8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8zM5 15l.8 2.2L8 18l-2.2.8L5 21l-.8-2.2L2 18l2.2-.8z" />
    </Icon>
  );
}

export function AlertIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M12 3 2.8 20h18.4zM12 9v5M12 17.5v.1" />
    </Icon>
  );
}

export function GearIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2.8v2.4M12 18.8v2.4M2.8 12h2.4M18.8 12h2.4M5.5 5.5l1.7 1.7M16.8 16.8l1.7 1.7M5.5 18.5l1.7-1.7M16.8 7.2l1.7-1.7" />
      <circle cx="12" cy="12" r="6.3" />
    </Icon>
  );
}

export function FolderIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M3.5 6.5h6l2 2h9v10h-17zM3.5 10.5h17" />
    </Icon>
  );
}

export function TrendIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="m3.5 17 6-6 4 4 7-7.5M15 7.5h5.5V13" />
    </Icon>
  );
}

export function DocumentSearchIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M13 20.5H5.5v-17h9l3 3V10M14.5 3.5v3h3M8.5 9h5M8.5 12.5h3" />
      <circle cx="15.5" cy="16" r="3" />
      <path d="m17.7 18.2 2.3 2.3" />
    </Icon>
  );
}

export function DocumentCheckIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M6 3.5h9l3 3v14H6zM15 3.5v3h3" />
      <path d="m9 13.5 2.2 2.2 4-4.4" />
    </Icon>
  );
}

export function HistoryIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M4.5 12a7.5 7.5 0 1 0 2.2-5.3" />
      <path d="M4 4.5v3.7h3.7M12 8v4.3l3 1.8" />
    </Icon>
  );
}

export function DocumentChartIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M6 3.5h9l3 3v14H6zM15 3.5v4h4" />
      <path d="M9 16v-3m3 3V9m3 7v-5" />
    </Icon>
  );
}
