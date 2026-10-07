import Link from "next/link";

export function Brand() {
  return (
    <Link className="brand" href="/" aria-label="UW Analyzer home">
      <span className="brand-mark" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      <span>
        <strong>UW Analyzer</strong>
        <small>Verified external research</small>
      </span>
    </Link>
  );
}
