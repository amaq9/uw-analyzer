/** Small display helpers shared by the case workspace screens. */

export function readable(value: string | null | undefined) {
  if (!value) return "Not provided";
  const text = value.toLowerCase().replaceAll("_", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function dateTime(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : "Not recorded";
}

export function dateOnly(value: string | null | undefined) {
  if (!value) return "Not recorded";
  return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** Money with its currency. Large amounts are shown in millions or billions. */
export function money(value: string | number | null | undefined, currency?: string | null) {
  if (value === null || value === undefined || value === "") return "Not provided";
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "Not provided";
  const code = currency || "USD";
  const abs = Math.abs(amount);
  const sign = amount < 0 ? "-" : "";
  if (abs >= 1_000_000_000) return `${sign}${code} ${(Math.round(abs / 10_000_000) / 100).toFixed(2)}bn`;
  if (abs >= 1_000_000) return `${sign}${code} ${(Math.round(abs / 10_000) / 100).toFixed(2)}m`;
  return `${sign}${code} ${abs.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

/** Rewrite "24,603m" or "CAD 24,603m" in analyst text as "CAD 24.60bn". A currency already in the text is kept, never doubled. */
export function shorten(text: string, currency?: string | null) {
  const fallback = currency || "USD";
  return text.replace(/(?:\b([A-Z]{3}) ?)?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)m(?![A-Za-z])/g, (_match, own: string | undefined, digits: string) => {
    const code = own ?? fallback;
    const millions = Number(digits.replaceAll(",", ""));
    if (!Number.isFinite(millions)) return _match;
    return millions >= 1000 ? `${code} ${(Math.round(millions / 10) / 100).toFixed(2)}bn` : `${code} ${millions.toLocaleString()}m`;
  });
}

export function bytes(size: number) {
  if (size >= 1_048_576) return `${(size / 1_048_576).toFixed(1)} MB`;
  if (size >= 1024) return `${Math.round(size / 1024)} KB`;
  return `${size} B`;
}
