"""A small, made-up 10-K (HTML) for tests: the notes and auditor's report, with switches for what they say.

Nothing here is a real company's text. The sentences are written the way real filings word these things,
including the hypothetical risk-factor sentences that must never raise a concern."""

FILLER = (
    "<p>The Company designs, markets and sells products to customers through wholesale and direct channels. "
    "Revenue is recognised when control of the goods passes to the customer, which is generally on shipment. "
    "Inventories are stated at the lower of cost and net realisable value. Property and equipment are "
    "depreciated on a straight-line basis over their estimated useful lives.</p>"
)


def filing_html(
    *,
    going_concern: str = "none",  # none | negated | doubt
    covenants: str = "complied",  # complied | breach | hypothetical | silent
    opinion: str = "clean",  # clean | qualified | missing
    customers: str = "none_over_10",  # none_over_10 | big | silent
    auditor_change: str = "none",  # none | changed
    material_weakness: str = "effective",  # effective | weakness
) -> bytes:
    parts = [
        "<html><body>",
        "<ix:header><ix:hidden>substantial doubt going concern covenant</ix:hidden></ix:header>",
        "<script>var covenant = 'not in compliance';</script>",
        "<p>Item 1A. Risk Factors</p>",
        "<p>A breach of the covenants in our credit agreement could result in an event of default and "
        "could raise substantial doubt about our ability to continue as a going concern.</p>",
        "<p>If we fail to remain in compliance with our covenants, our lenders may demand repayment.</p>",
    ]
    parts += [FILLER] * 60
    parts.append("<p>Item 3. Legal Proceedings</p>")
    parts.append(
        "<p>We are subject to claims in the ordinary course of business. We believe that none of the "
        "pending matters will have a material effect on our financial position. See Note 11.</p>"
    )
    if going_concern == "negated":
        parts.append(
            "<p>Management evaluated whether conditions raise substantial doubt and concluded that "
            "there is no substantial doubt about the Company's ability to continue as a going concern.</p>"
        )
    elif going_concern == "doubt":
        parts.append(
            "<p>These conditions raise substantial doubt about the Company's ability to continue as a "
            "going concern.</p>"
        )
    parts.append("<p>Note 6. Credit facilities</p>")
    parts.append(
        "<p>The Company has a $2.0 billion revolving credit facility that matures in 2029, and no "
        "borrowings were outstanding under it at year end.</p>"
    )
    if covenants == "complied":
        parts.append("<p>As of year end, the Company was in compliance with all covenants.</p>")
    elif covenants == "breach":
        parts.append(
            "<p>At year end the Company was not in compliance with the leverage covenant and obtained "
            "a waiver from its lenders.</p>"
        )
    elif covenants == "hypothetical":
        parts.append(
            "<p>The credit agreement contains customary covenants that limit additional borrowing.</p>"
        )
    if customers == "none_over_10":
        parts.append(
            "<p>No single customer accounted for 10% or more of the Company's revenues in any period "
            "presented.</p>"
        )
    elif customers == "big":
        parts.append(
            "<p>One customer accounted for 62% of the Company's revenues and 58% of accounts "
            "receivable.</p>"
        )
    parts.append(
        "<p>The allowance for credit losses was $42 million at year end, compared with $38 million a year "
        "earlier.</p>"
    )
    parts.append(
        "<p>Item 9. Changes in and Disagreements with Accountants on Accounting and Financial Disclosure</p>"
    )
    parts.append(
        "<p>None.</p>"
        if auditor_change == "none"
        else "<p>The Audit Committee dismissed its prior auditor and engaged a new independent registered "
        "public accounting firm during the year.</p>"
    )
    parts.append("<p>Subsequent Events</p>")
    parts.append("<p>No events occurred after the balance sheet date that require disclosure.</p>")
    if opinion != "missing":
        parts.append("<p>Report of Independent Registered Public Accounting Firm</p>")
        if opinion == "clean":
            parts.append(
                "<p>In our opinion, the consolidated financial statements present fairly, in all material "
                "respects, the financial position of the Company at year end.</p>"
            )
        else:
            parts.append(
                "<p>Basis for Qualified Opinion. Except for the effects of the matter described above, the "
                "consolidated financial statements present fairly, in all material respects, the financial "
                "position of the Company.</p>"
            )
        parts.append("<p>/s/ Example Audit LLP</p>")
    if material_weakness == "effective":
        parts.append(
            "<p>In our opinion, the Company maintained, in all material respects, effective internal "
            "control over financial reporting as of year end.</p>"
        )
    else:
        parts.append(
            "<p>Management identified a material weakness in internal control over the accounting for "
            "income taxes.</p>"
        )
    parts.append("</body></html>")
    return "\n".join(parts).encode()
