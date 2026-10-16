"""The authoritative commercial baseline (PCM-001 … PCM-004).

A commercial record starts from the customer's commitment, which in this repository is an **accepted** quotation
version: frozen at ISSUE (document and HTML sealed by their digests) and, at ACCEPTED, its accepted total (the frozen
total plus the optional items the customer chose) and its effective accepted baseline (sealed by a digest) through
``mtq_commercial.quotations.record_decision``, the one decision path for staff and for the customer's secure link.
Nothing mutable (estimates, rate cards, pricing) is read.

The baseline is a lineage, never a copy of a quotation:

    accepted base quotation → accepted variation 1 → accepted variation 2 → current commercial value

Each ``commercial_baseline`` row references one ACCEPTED version with the digests that make it reproducible, its
accepted total and GST, the cumulative value and GST, and ``baseline_sha256`` over that reference and the previous
row's digest. Rows are immutable (database triggers). A variation accepted on a chain with a commercial record is
appended in the acceptance transaction (``on_quotation_accepted``, an ``ACCEPTANCE_HOOKS`` listener; its failure refuses
the acceptance). ``sync`` appends, under the account lock, any accepted version a concurrent opening could not see.

The GST of an accepted version is what the quotation froze: its ``tax_minor`` plus the GST of the optional lines the
customer chose. If the version has no recorded GST, the baseline's GST is unknown (null), never computed from a rate.

This module does not use the Project Lifecycle: a commercial record exists whether or not a project was booked.
"""

from __future__ import annotations

import hashlib
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock
from veda.kernel.errors import ApiError, field_error
from veda.kernel.jcs import canonical_bytes
from veda.modules.crm.leads.models import Lead
from veda.modules.mtq.models import Property
from veda.modules.mtq_commercial import quotations, rendering
from veda.modules.mtq_commercial.models import Quotation, QuotationLine

from . import events
from .models import CommercialAccount, CommercialBaseline


# --- the accepted facts of a quotation version ------------------------------------------------------------------------
def accepted_chain(s: Session, number: str) -> list[Quotation]:
    """Every ACCEPTED version of the chain: the base, then each accepted variation in order."""
    return list(s.execute(sa.select(Quotation).where(Quotation.quotation_number == number,
                                                     Quotation.status == "ACCEPTED", Quotation.is_deleted == sa.false())
                          .order_by(Quotation.variation_no, Quotation.version_no)).scalars())  # fmt: skip


def accepted_baseline_verifies(q: Quotation) -> bool:
    return (
        q.accepted_baseline is not None
        and q.accepted_baseline_sha256 is not None
        and hashlib.sha256(canonical_bytes(q.accepted_baseline)).hexdigest() == q.accepted_baseline_sha256
    )


def accepted_tax(s: Session, q: Quotation) -> int | None:
    """The GST frozen in ``q`` for what the customer accepted: the version's GST plus that of the chosen optional lines."""
    if q.tax_minor is None or q.tax_status != "APPLIED":
        return None
    chosen = list(q.selected_optional_line_ids or [])
    extra = 0
    if chosen:
        for (tax,) in s.execute(sa.select(QuotationLine.tax_minor).where(QuotationLine.id.in_(chosen))):
            if tax is None:
                return None
            extra += int(tax)
    return int(q.tax_minor) + extra


def reference(row: CommercialBaseline, previous_sha256: str | None) -> dict[str, Any]:
    """The canonical reference a baseline row's digest is computed over."""
    return {
        "account_id": row.account_id, "sequence_no": row.sequence_no, "kind": row.kind,
        "previous_baseline_sha256": previous_sha256, "quotation_id": row.quotation_id,
        "quotation_number": row.quotation_number, "variation_no": row.variation_no, "version_no": row.version_no,
        "snapshot_sha256": row.snapshot_sha256, "accepted_baseline_sha256": row.accepted_baseline_sha256,
        "accepted_total_minor": row.accepted_total_minor, "accepted_tax_minor": row.accepted_tax_minor,
        "value_minor": row.value_minor, "tax_minor": row.tax_minor, "decided_on": clock.to_rfc3339(row.decided_on),
    }  # fmt: skip


def digest(row: CommercialBaseline, previous_sha256: str | None) -> str:
    return hashlib.sha256(canonical_bytes(reference(row, previous_sha256))).hexdigest()


def rows(s: Session, account_id: str) -> list[CommercialBaseline]:
    return list(s.execute(sa.select(CommercialBaseline).where(CommercialBaseline.account_id == account_id)
                          .order_by(CommercialBaseline.sequence_no)).scalars())  # fmt: skip


def current(s: Session, account: CommercialAccount) -> CommercialBaseline:
    found = s.execute(sa.select(CommercialBaseline).where(CommercialBaseline.account_id == account.id,
                                                          CommercialBaseline.sequence_no == account.baseline_seq)
                      ).scalar_one_or_none()  # fmt: skip
    assert found is not None  # the account is opened with its original baseline
    return found


def _verifiable(q: Quotation) -> bool:
    return (q.status == "ACCEPTED" and q.accepted_total_minor is not None and q.decided_on is not None
            and q.snapshot_sha256 is not None and accepted_baseline_verifies(q) and rendering.integrity(q))  # fmt: skip


def append(
    s: Session, account: CommercialAccount, q: Quotation, previous: CommercialBaseline | None
) -> CommercialBaseline:
    """Record ``q`` (ACCEPTED, verified) as the account's next baseline. The caller holds the account lock."""
    if not _verifiable(q):
        raise ApiError(409, "QUOTATION_INTEGRITY_FAILED", f"{quotations.number_label(q)} does not verify against its "
                       "sealed digests; it cannot become a commercial baseline.", extra={"quotation_id": q.id})  # fmt: skip
    tax = accepted_tax(s, q)
    value = (previous.value_minor if previous else 0) + int(q.accepted_total_minor or 0)
    if value < 0:
        raise ApiError(409, "INVALID_STATE", "An accepted variation would make the project value negative.")
    before_tax: int | None = 0 if previous is None else previous.tax_minor
    total_tax = None if tax is None or before_tax is None else before_tax + tax
    row = CommercialBaseline(
        account_id=account.id, lead_id=account.lead_id, sequence_no=(previous.sequence_no + 1) if previous else 1,
        kind="ORIGINAL" if previous is None else "VARIATION", previous_baseline_id=previous.id if previous else None,
        quotation_id=q.id, quotation_number=q.quotation_number, variation_no=q.variation_no, version_no=q.version_no,
        snapshot_sha256=q.snapshot_sha256, accepted_baseline_sha256=q.accepted_baseline_sha256,
        accepted_total_minor=int(q.accepted_total_minor or 0), accepted_tax_minor=tax, value_minor=value,
        tax_minor=total_tax, decided_on=q.decided_on,
    )  # fmt: skip
    row.baseline_sha256 = digest(row, previous.baseline_sha256 if previous else None)
    s.add(row)
    s.flush()
    account.baseline_seq = row.sequence_no
    events.record(s, account, "BASELINE_RECORDED", row.id, quotation_id=q.id, variation_no=q.variation_no,
                  version_no=q.version_no, sequence_no=row.sequence_no, accepted_total_minor=row.accepted_total_minor,
                  value_minor=row.value_minor, baseline_sha256=row.baseline_sha256)  # fmt: skip
    return row


def sync(s: Session, account: CommercialAccount) -> int:
    """Append, in order, every accepted version of the chain not yet recorded after the latest row (the caller holds
    the account lock). A version accepted out of order is left for ``problems`` to report (fail closed)."""
    recorded = rows(s, account.id)
    known = {r.quotation_id for r in recorded}
    last = recorded[-1] if recorded else None
    n = 0
    for q in accepted_chain(s, account.quotation_number):
        if q.id in known or q.variation_no == 0 or (last is not None and q.variation_no <= last.variation_no):
            continue
        last = append(s, account, q, last)
        n += 1
    return n


def problems(s: Session, account: CommercialAccount) -> list[dict[str, Any]]:
    """Why the baseline does not verify (empty when it does). Fail closed: any mismatch is a problem."""
    lead = s.get(Lead, account.lead_id)
    if lead is not None and lead.anonymized_on is not None:  # erasure re-seals the frozen documents (by design)
        return [{"code": "BASELINE_ERASED", "message": "The customer record was erased; the quotation documents were "
                 "redacted and re-sealed, and the commercial record is closed."}]  # fmt: skip
    out: list[dict[str, Any]] = []
    chain = rows(s, account.id)
    previous: str | None = None
    for n, row in enumerate(chain, start=1):
        label = f"baseline {row.sequence_no}"
        if row.sequence_no != n or digest(row, previous) != row.baseline_sha256:
            out.append({"code": "BASELINE_TAMPERED", "message": f"The reference of {label} does not match its digest.",
                        "baseline_id": row.id})  # fmt: skip
        q = s.get(Quotation, row.quotation_id)
        if (q is None or not _verifiable(q) or q.snapshot_sha256 != row.snapshot_sha256
                or q.accepted_baseline_sha256 != row.accepted_baseline_sha256
                or int(q.accepted_total_minor or 0) != row.accepted_total_minor):  # fmt: skip
            out.append({"code": "QUOTATION_INTEGRITY_FAILED", "message": f"The accepted quotation of {label} no longer "
                        "matches its sealed digests.", "baseline_id": row.id, "quotation_id": row.quotation_id})  # fmt: skip
        previous = row.baseline_sha256
    if not chain or chain[-1].sequence_no != account.baseline_seq:
        out.append(
            {"code": "BASELINE_POINTER_INVALID", "message": "The current baseline is not the latest recorded one."}
        )
    recorded = {r.quotation_id for r in chain}
    for q in accepted_chain(s, account.quotation_number):
        if q.id not in recorded:
            out.append({"code": "VARIATION_NOT_RECORDED", "message": f"Accepted {quotations.number_label(q)} is not in "
                        "the commercial baseline yet.", "quotation_id": q.id})  # fmt: skip
    return out


# --- opening ----------------------------------------------------------------------------------------------------------
def candidates(s: Session, lead_condition) -> list[Quotation]:
    """Accepted base quotations (within scope) that have no commercial record yet."""
    opened = sa.select(CommercialAccount.quotation_number).where(CommercialAccount.is_deleted == sa.false())
    return list(s.execute(sa.select(Quotation).join(Lead, Lead.id == Quotation.lead_id).where(
        Quotation.status == "ACCEPTED", Quotation.variation_no == 0, Quotation.is_deleted == sa.false(),
        Quotation.quotation_number.not_in(opened), Lead.is_deleted == sa.false(), Lead.anonymized_on.is_(None),
        lead_condition,
    ).order_by(Quotation.decided_on.desc())).scalars())  # fmt: skip


def open_account(s: Session, q: Quotation) -> CommercialAccount:
    """Open the commercial record of ``q`` (an ACCEPTED base version of a live lead) with its whole accepted chain."""
    if q.quotation_kind != "BASE" or q.variation_no != 0:
        raise ApiError(422, "VALIDATION_FAILED", "A commercial record starts from the accepted base quotation, not a "
                       "variation.", errors=[field_error("quotation_id", "NOT_A_BASE_QUOTATION", "Not a base "
                                                         "quotation.")])  # fmt: skip
    if q.status != "ACCEPTED":
        raise ApiError(409, "QUOTATION_NOT_ACCEPTED", f"{quotations.number_label(q)} is {q.status.lower()}; only an "
                       "accepted quotation becomes a commercial record.", extra={"status": q.status})  # fmt: skip
    lead = s.get(Lead, q.lead_id)
    prop = s.get(Property, q.property_id)
    if lead is None or lead.is_deleted or lead.anonymized_on is not None or prop is None or prop.is_deleted:
        raise ApiError(409, "INVALID_STATE", "This customer record is closed; no commercial record can be opened.")
    existing = s.execute(sa.select(CommercialAccount).where(CommercialAccount.quotation_number == q.quotation_number,
                                                            CommercialAccount.is_deleted == sa.false())
                         ).scalar_one_or_none()  # fmt: skip
    if existing is not None:
        raise ApiError(409, "ALREADY_OPEN", f"{q.quotation_number} already has a commercial record.",
                       extra={"account_id": existing.id})  # fmt: skip
    account = CommercialAccount(lead_id=q.lead_id, property_id=q.property_id, quotation_number=q.quotation_number,
                                base_quotation_id=q.id, currency=q.currency, baseline_seq=1)  # fmt: skip
    s.add(account)
    s.flush()
    events.record(s, account, "ACCOUNT_OPENED", account.id, quotation_id=q.id, quotation_number=q.quotation_number)
    append(s, account, q, None)
    sync(s, account)
    return account


def on_quotation_accepted(s: Session, q: Quotation) -> None:
    """Called by the B4 decision service when a quotation is accepted (same transaction). A variation accepted on a
    chain with a commercial record becomes its next baseline, under the account lock. The base acceptance creates
    nothing: the commercial record is opened explicitly by staff."""
    from . import access

    if q.quotation_kind != "VARIATION":
        return
    account = s.execute(sa.select(CommercialAccount).where(CommercialAccount.quotation_number == q.quotation_number,
                                                           CommercialAccount.is_deleted == sa.false())
                        ).scalar_one_or_none()  # fmt: skip
    if account is None:
        return
    access.lock(s, account)
    if s.execute(sa.select(CommercialBaseline.id).where(CommercialBaseline.quotation_id == q.id)).first() is not None:
        return  # already recorded (idempotent)
    sync(s, account)
    access.touch(s, account)
