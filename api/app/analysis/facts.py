"""Reads annual figures out of the SEC's XBRL "company facts" (what the SEC connector stores).

Only 10-K annual values in US dollars are used. A flow item (revenue, cash flow) must cover about a
year; a balance item must be dated at the fiscal year end. Where a tag is missing the figure stays
missing (None) and the analysis says so: nothing is estimated. Amounts are returned in millions."""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

# metric -> candidate us-gaap tags, first one present wins. kind: "instant" (balance) or "flow".
METRICS: dict[str, tuple[str, tuple[str, ...]]] = {
    "total_assets": ("instant", ("Assets",)),
    "total_equity": (
        "instant",
        (
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        ),
    ),
    "current_assets": ("instant", ("AssetsCurrent",)),
    "current_liabilities": ("instant", ("LiabilitiesCurrent",)),
    "cash": (
        "instant",
        (
            "CashAndCashEquivalentsAtCarryingValue",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        ),
    ),
    "short_term_investments": (
        "instant",
        (
            "ShortTermInvestments",
            "MarketableSecuritiesCurrent",
            "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
            "DebtSecuritiesAvailableForSaleExcludingAccruedInterestCurrent",
        ),
    ),
    "receivables": ("instant", ("AccountsReceivableNetCurrent", "ReceivablesNetCurrent")),
    "allowance_for_credit_losses": (
        "instant",
        (
            "AllowanceForDoubtfulAccountsReceivableCurrent",
            "AccountsReceivableAllowanceForCreditLossCurrent",
        ),
    ),
    "inventory": ("instant", ("InventoryNet", "InventoryFinishedGoodsNetOfReserves")),
    "goodwill": ("instant", ("Goodwill",)),
    "intangibles": (
        "instant",
        ("IntangibleAssetsNetExcludingGoodwill", "FiniteLivedIntangibleAssetsNet"),
    ),
    "debt_noncurrent": (
        "instant",
        ("LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations"),
    ),
    "debt_current": ("instant", ("LongTermDebtCurrent", "DebtCurrent")),
    "short_term_borrowings": ("instant", ("ShortTermBorrowings", "CommercialPaper")),
    "lease_noncurrent": ("instant", ("OperatingLeaseLiabilityNoncurrent",)),
    "lease_current": ("instant", ("OperatingLeaseLiabilityCurrent",)),
    "revenue": (
        "flow",
        ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"),
    ),
    "gross_profit": ("flow", ("GrossProfit",)),
    "net_income": ("flow", ("NetIncomeLoss", "ProfitLoss")),
    "operating_income": ("flow", ("OperatingIncomeLoss",)),
    "pretax_income": (
        "flow",
        (
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        ),
    ),
    "net_interest": ("flow", ("InterestIncomeExpenseNonoperatingNet", "InterestIncomeExpenseNet")),
    "interest_expense": (
        "flow",
        ("InterestExpense", "InterestExpenseNonoperating", "InterestPaidNet", "InterestPaid"),
    ),
    "depreciation_amortisation": (
        "flow",
        (
            "DepreciationDepletionAndAmortization",
            "DepreciationAndAmortization",
            "DepreciationAmortizationAndAccretionNet",
        ),
    ),
    "ocf": ("flow", ("NetCashProvidedByUsedInOperatingActivities",)),
    "capex": (
        "flow",
        ("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"),
    ),
    "dividends": ("flow", ("PaymentsOfDividendsCommonStock", "PaymentsOfDividends")),
    "buybacks": ("flow", ("PaymentsForRepurchaseOfCommonStock",)),
    "net_change_in_cash": (
        "flow",
        (
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect",
            "CashAndCashEquivalentsPeriodIncreaseDecrease",
        ),
    ),
}


@dataclass
class YearFigures:
    period_end: date
    values: dict[str, float | None] = field(default_factory=dict)  # millions
    tags: dict[str, str] = field(default_factory=dict)  # metric -> tag actually used
    filed: date | None = None
    accession: str | None = None
    derived: dict[str, str] = field(default_factory=dict)  # figure -> how it was derived


def _usd_rows(facts: dict[str, Any], tag: str) -> list[dict[str, Any]]:
    node = facts.get(tag)
    if not node:
        return []
    return [
        r
        for r in node.get("units", {}).get("USD", [])
        if r.get("form") == "10-K" and r.get("fp") == "FY"
    ]


def _value(rows: list[dict[str, Any]], end: str, kind: str) -> dict[str, Any] | None:
    good = []
    for r in rows:
        if r.get("end") != end:
            continue
        if kind == "flow":
            start = r.get("start")
            if not start:
                continue
            days = (date.fromisoformat(end) - date.fromisoformat(start)).days
            if not 350 <= days <= 380:
                continue
        good.append(r)
    return max(good, key=lambda r: r.get("filed", "")) if good else None


def fiscal_year_ends(facts: dict[str, Any], count: int = 3) -> list[str]:
    """The latest fiscal year ends that have a total-assets figure in a 10-K, newest first."""
    ends = {r["end"] for r in _usd_rows(facts, "Assets")}
    return sorted(ends, reverse=True)[:count]


def extract(company_facts: dict[str, Any], count: int = 3) -> list[YearFigures]:
    facts = company_facts.get("facts", {}).get("us-gaap", {})
    years: list[YearFigures] = []
    for end in fiscal_year_ends(facts, count):
        year = YearFigures(period_end=date.fromisoformat(end))
        for metric, (kind, tags) in METRICS.items():
            found = None
            for tag in tags:
                row = _value(_usd_rows(facts, tag), end, kind)
                if row is not None:
                    found = (tag, row)
                    break
            if found is None:
                year.values[metric] = None
                continue
            tag, row = found
            year.values[metric] = float(row["val"]) / 1_000_000
            year.tags[metric] = tag
            if metric == "total_assets":
                year.filed = date.fromisoformat(row["filed"]) if row.get("filed") else None
                year.accession = row.get("accn")
        years.append(year)
    return years


def to_figures(year: YearFigures, prior: YearFigures | None) -> dict[str, float | None]:
    """The names the ratio method expects, with derived figures noted on `year.derived`."""
    v = year.values

    def add(*parts: float | None) -> float | None:
        present = [p for p in parts if p is not None]
        return sum(present) if present else None

    cash = add(v.get("cash"), v.get("short_term_investments"))
    if v.get("short_term_investments") is not None:
        year.derived["cash"] = "cash and equivalents plus short-term investments"
    debt = add(v.get("debt_noncurrent"), v.get("debt_current"), v.get("short_term_borrowings"))
    leases = add(v.get("lease_noncurrent"), v.get("lease_current"))
    ebit = v.get("operating_income")
    pretax = v.get("pretax_income")
    if ebit is None and pretax is not None:
        ebit = pretax - (v.get("net_interest") or 0.0)
        year.derived["ebit"] = (
            "pre-tax income less net interest income (operating income not tagged)"
        )
    dep = v.get("depreciation_amortisation")
    ebitda = None if ebit is None or dep is None else ebit + dep
    if ebitda is not None:
        year.derived["ebitda"] = "EBIT plus depreciation and amortisation"
    if (
        v.get("inventory") is not None
        and year.tags.get("inventory") == "InventoryFinishedGoodsNetOfReserves"
    ):
        year.derived["inventory"] = "finished goods only (total inventory not tagged)"
    if v.get("interest_expense") is not None and year.tags.get("interest_expense", "").startswith(
        "InterestPaid"
    ):
        year.derived["interest_expense"] = "cash interest paid (interest expense not tagged)"
    return {
        "total_assets": v.get("total_assets"),
        "total_equity": v.get("total_equity"),
        "goodwill": v.get("goodwill"),
        "intangibles": v.get("intangibles"),
        "current_assets": v.get("current_assets"),
        "current_liabilities": v.get("current_liabilities"),
        "cash": cash,
        "inventory": v.get("inventory"),
        "financial_debt": debt,
        "lease_liabilities": leases,
        "debt_due_12m": add(v.get("debt_current"), v.get("short_term_borrowings")),
        "ebit": ebit,
        "ebitda": ebitda,
        "interest_expense": v.get("interest_expense"),
        "revenue": v.get("revenue"),
        "receivables": v.get("receivables"),
        "prior_receivables": prior.values.get("receivables") if prior else None,
        "allowance_for_credit_losses": v.get("allowance_for_credit_losses"),
        "days_in_period": 365.0,
        "ocf": v.get("ocf"),
        "capex": v.get("capex"),
        "dividends": v.get("dividends"),
        "buybacks": v.get("buybacks"),
        "net_change_in_cash": v.get("net_change_in_cash"),
        "net_income": v.get("net_income"),
    }
