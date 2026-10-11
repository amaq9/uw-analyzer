import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StatementReview } from "@/components/case/statement-review";
import { SessionProvider } from "@/components/session-provider";
import type { components } from "@/lib/api/schema";

const originalBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

const extraction: components["schemas"]["ExtractionOut"] = {
  document_id: "d1",
  filename: "accounts.pdf",
  periods: ["2025", "2024"],
  period_end_guesses: ["2025-12-31", "2024-12-31"],
  unit_guess: "thousands",
  currency_guess: "CAD",
  rows: [
    { metric: "total_assets", label: "Total assets", values: [38400, 36500] },
    { metric: "revenue", label: "Revenues", values: [46398, 46309] },
    { metric: "ocf", label: "Net cash provided by operating activities", values: [2868, 3698] },
  ],
  notes: ["Not found: total current liabilities. Type it in if the document has it."],
  metrics: [
    { metric: "total_assets", label: "Total assets" },
    { metric: "current_liabilities", label: "Total current liabilities" },
    { metric: "revenue", label: "Revenue (net sales)" },
    { metric: "ocf", label: "Net cash from operating activities" },
  ],
  notice: "These are suggestions read from the file. Check every figure against the document.",
};

beforeEach(() => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
});

afterEach(() => {
  vi.unstubAllGlobals();
  if (originalBaseUrl === undefined) delete process.env.NEXT_PUBLIC_API_BASE_URL;
  else process.env.NEXT_PUBLIC_API_BASE_URL = originalBaseUrl;
});

function renderReview(onConfirmed = () => undefined) {
  return render(
    <SessionProvider>
      <StatementReview base="/api/v1/cases/c1" documentId="d1" extraction={extraction} onConfirmed={onConfirmed} token="t" />
    </SessionProvider>,
  );
}

describe("statement review", () => {
  it("shows each suggestion next to the label found and says what was not found", () => {
    renderReview();
    expect(screen.getByText("Revenues")).toBeInTheDocument();
    expect(screen.getByText(/not found: total current liabilities/i, { selector: "p" })).toBeInTheDocument();
    expect(screen.getByLabelText("Total assets, period 1")).toHaveValue("38400");
    expect(screen.getByLabelText("Total current liabilities, period 1")).toHaveValue("");
    expect(screen.getByLabelText("Period 1 end date")).toHaveValue("2025-12-31");
  });

  it("will not confirm until the person states whether the statements are audited", async () => {
    const calls: { body?: string }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init?: RequestInit) => {
        calls.push({ body: init?.body as string });
        return Promise.resolve(new Response("[]", { status: 201 }));
      }),
    );
    const confirmed = vi.fn();
    renderReview(confirmed);
    const button = screen.getByRole("button", { name: /confirm these figures/i });
    expect(button).toBeDisabled();
    expect(screen.getByText(/whether the statements are audited/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/the statements are/i), { target: { value: "UNAUDITED" } });
    expect(button).toBeEnabled();
    fireEvent.change(screen.getByLabelText("Total current liabilities, period 1"), { target: { value: "12,547" } });
    fireEvent.click(button);

    await waitFor(() => expect(calls).toHaveLength(1));
    const body = JSON.parse(calls[0].body ?? "{}");
    expect(body).toMatchObject({ document_id: "d1", currency: "CAD", unit: "thousands", audit_status: "UNAUDITED" });
    expect(body.periods[0]).toMatchObject({ period_end: "2025-12-31" });
    expect(body.periods[0].figures).toMatchObject({ total_assets: 38400, current_liabilities: 12547, revenue: 46398 });
    expect(body.periods[1].figures.current_liabilities).toBeNull();
    await waitFor(() => expect(confirmed).toHaveBeenCalled());
    expect(await screen.findByRole("status")).toHaveTextContent(/confirmed under your name/i);
  });

  it("refuses a figure that is not a number and a period without a date", () => {
    renderReview();
    fireEvent.change(screen.getByLabelText(/the statements are/i), { target: { value: "AUDITED" } });
    const button = screen.getByRole("button", { name: /confirm these figures/i });
    expect(button).toBeEnabled();
    fireEvent.change(screen.getByLabelText("Revenue (net sales), period 1"), { target: { value: "lots" } });
    expect(button).toBeDisabled();
    expect(screen.getByText(/not a number/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Revenue (net sales), period 1"), { target: { value: "46398" } });
    fireEvent.change(screen.getByLabelText("Period 1 end date"), { target: { value: "" } });
    expect(button).toBeDisabled();
    expect(screen.getByText(/period end date/i)).toBeInTheDocument();
  });
});
