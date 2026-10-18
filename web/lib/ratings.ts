/** The agencies' own websites are the main sources for a published rating (ADR 0020). */

export type AgencyId = "MOODYS" | "SP" | "FITCH";

export const AGENCY_SITES: Record<AgencyId, { name: string; domain: string; home: string; label: string }> = {
  SP: { name: "S&P", domain: "spglobal.com", home: "https://www.spglobal.com/ratings", label: "www.spglobal.com" },
  MOODYS: { name: "Moody's", domain: "moodys.com", home: "https://ratings.moodys.com", label: "ratings.moodys.com" },
  FITCH: { name: "Fitch", domain: "fitchratings.com", home: "https://www.fitchratings.com", label: "www.fitchratings.com" },
};

/** True when the address is on that agency's own website. The whole domain is checked, so a look-alike never counts. */
export function isAgencySite(agency: AgencyId, address: string): boolean {
  let host: string;
  try {
    host = new URL(address.trim()).hostname.toLowerCase().replace(/\.$/, "");
  } catch {
    return false;
  }
  const domain = AGENCY_SITES[agency].domain;
  return host === domain || host.endsWith(`.${domain}`);
}
