import Link from "next/link";

/** The UW Analyzer mark: a crosshair (ring, vertical and horizontal lines) with a blue point at its centre. */
export function BrandMark({ className = "brand-mark" }: Readonly<{ className?: string }>) {
  return (
    <svg aria-hidden="true" className={className} viewBox="-160 -160 320 320">
      <line className="brand-mark-h" x1="-152" x2="152" y1="0" y2="0" />
      <circle className="brand-mark-ring" cx="0" cy="0" r="100" />
      <line className="brand-mark-v" x1="0" x2="0" y1="-155" y2="155" />
      <circle className="brand-mark-dot" cx="0" cy="0" r="30" />
    </svg>
  );
}

export function Brand() {
  return (
    <Link className="brand" href="/" aria-label="UW Analyzer home">
      <BrandMark />
      <span className="brand-text">
        <strong>UW Analyzer</strong>
        <small>Evidence-led underwriting</small>
      </span>
    </Link>
  );
}
