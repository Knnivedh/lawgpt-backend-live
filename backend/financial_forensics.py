"""
financial_forensics.py - Rajnesh v. Neha Financial Forensics & Discrepancy Engine.

Implements Gemini Architectural Blueprint Module 3:
1. True Net Disposable Income Normalizer (Rajnesh v. Neha, Kalyan Dey Chowdhury, Bhushan Kumar Meen).
   - Permits ONLY mandatory statutory deductions (TDS, mandatory 12% EPF, Professional Tax, ESI).
   - Disallows and adds back voluntary loan EMIs (Car, Home, Personal), VPF top-ups, LIC premiums.
   - Computes standard judicial maintenance band (20-25% without child, 30-40% with child).
2. Automated Concealment & Perjury Detection Matrix (FIN-01 to FIN-05).
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


ALLOWED_STATUTORY_CATEGORIES = {
    "INCOME_TAX_TDS",
    "MANDATORY_EPF_12_PCT",
    "PROFESSIONAL_TAX",
    "MANDATORY_ESI",
    "MANDATORY_NPS_TIER1_GOVT",
}

DISALLOWED_VOLUNTARY_PATTERNS = [
    (re.compile(r"\b(?:car\s+emi|auto\s+loan|vehicle\s+loan)\b", re.IGNORECASE), "Car Loan EMI", "VOLUNTARY_LOAN"),
    (re.compile(r"\b(?:personal\s+loan|pl\s+emi|consumer\s+loan)\b", re.IGNORECASE), "Personal Loan EMI", "VOLUNTARY_LOAN"),
    (re.compile(r"\b(?:home\s+loan|housing\s+loan|hl\s+emi)\b", re.IGNORECASE), "Home Loan EMI", "VOLUNTARY_LOAN"),
    (re.compile(r"\b(?:vpf|voluntary\s+provident\s+fund)\b", re.IGNORECASE), "Voluntary PF Top-Up", "VOLUNTARY_SAVINGS"),
    (re.compile(r"\b(?:lic|insurance\s+premium|policy\s+premium)\b", re.IGNORECASE), "LIC / Insurance Premium", "VOLUNTARY_SAVINGS"),
    (re.compile(r"\b(?:festival\s+advance|salary\s+advance)\b", re.IGNORECASE), "Salary Advance Recovery", "VOLUNTARY_ADVANCE"),
]

STATUTORY_DEDUCTION_PATTERNS = [
    (re.compile(r"\b(?:tds|tax\s+deducted|income\s+tax)\b", re.IGNORECASE), "INCOME_TAX_TDS"),
    (re.compile(r"\b(?:provident\s+fund|epf|pf\s+deduction)\b", re.IGNORECASE), "MANDATORY_EPF_12_PCT"),
    (re.compile(r"\b(?:prof(?:essional)?\s+tax|ptax)\b", re.IGNORECASE), "PROFESSIONAL_TAX"),
    (re.compile(r"\b(?:esi|esic)\b", re.IGNORECASE), "MANDATORY_ESI"),
]


@dataclass
class PayslipLineItem:
    label: str
    amount: float
    category: str


def compute_assessable_maintenance_income(
    gross_monthly_income: float,
    deductions: List[PayslipLineItem],
    has_minor_child: bool = False,
    basic_salary: Optional[float] = None,
    is_claimant_residing_in_mortgaged_home: bool = False,
) -> Dict[str, Any]:
    """
    Computes true Net Disposable Income per Rajnesh v. Neha (2020 SC)
    and Bhushan Kumar Meen v. Mansi Meen (2010 SC).
    Only statutory mandatory deductions are permitted.
    Caps EPF at 12% of basic salary (flagging excess as voluntary VPF).
    Permits Home Loan EMI credit if claimant is residing in the mortgaged home.
    """
    statutory_total = 0.0
    disallowed_voluntary_total = 0.0
    disallowed_items = []
    allowed_items = []

    # Maximum statutory EPF is 12% of basic
    max_epf = (0.12 * basic_salary) if basic_salary else None

    for item in deductions:
        # Check if item is home loan EMI and claimant resides there
        if is_claimant_residing_in_mortgaged_home and "home" in item.label.lower() and "emi" in item.label.lower():
            statutory_total += item.amount
            allowed_items.append({
                "label": item.label,
                "amount": item.amount,
                "category": "SHARED_HOUSEHOLD_SHELTER_CREDIT",
                "note": "Permitted as credit because claimant and child reside in mortgaged property."
            })
            continue

        if item.category in ALLOWED_STATUTORY_CATEGORIES:
            # Check EPF cap
            if item.category == "MANDATORY_EPF_12_PCT" and max_epf is not None and item.amount > max_epf:
                allowed_amount = max_epf
                excess_vpf = item.amount - max_epf
                statutory_total += allowed_amount
                allowed_items.append({"label": f"{item.label} (Mandatory 12% EPF)", "amount": allowed_amount, "category": item.category})
                disallowed_voluntary_total += excess_vpf
                disallowed_items.append({
                    "label": f"{item.label} (Excess Voluntary VPF)",
                    "amount": excess_vpf,
                    "note": "Added back: Voluntary Provident Fund exceeding statutory 12% limit disallowed per Rajnesh v. Neha"
                })
            else:
                statutory_total += item.amount
                allowed_items.append({"label": item.label, "amount": item.amount, "category": item.category})
        else:
            disallowed_voluntary_total += item.amount
            disallowed_items.append({
                "label": item.label,
                "amount": item.amount,
                "note": "Added back to net disposable income per Rajnesh v. Neha (voluntary expense)"
            })

    net_assessable_income = max(0.0, gross_monthly_income - statutory_total)

    # Standard Judicial Benchmark: ~20-25% for spouse alone, ~30-40% with minor child
    min_pct = 0.30 if has_minor_child else 0.20
    max_pct = 0.40 if has_minor_child else 0.25

    estimated_min = net_assessable_income * min_pct
    estimated_max = net_assessable_income * max_pct

    return {
        "gross_monthly_income": round(gross_monthly_income, 2),
        "allowed_statutory_deductions_total": round(statutory_total, 2),
        "allowed_items": allowed_items,
        "added_back_voluntary_deductions_total": round(disallowed_voluntary_total, 2),
        "disallowed_items_flagged": disallowed_items,
        "true_net_assessable_income": round(net_assessable_income, 2),
        "benchmark_guideline": "Kalyan Dey Chowdhury v. Rita Dey Chowdhury Nee Nandy (2017 SC) & Rajnesh v. Neha (2020 SC)",
        "maintenance_band_monthly": {
            "min_award": round(estimated_min, 2),
            "max_award": round(estimated_max, 2),
            "percentage_range": f"{int(min_pct*100)}% - {int(max_pct*100)}%",
        },
    }


def execute_concealment_matrix(financial_profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Executes the 5 automated concealment cross-checks (FIN-01 to FIN-05).
    """
    findings = []

    # Rule FIN-01: Credit Card spend > 85% of declared annual net income
    annual_net = financial_profile.get("declared_annual_net_income", 0.0)
    annual_cc_spend = financial_profile.get("annual_credit_card_spend", 0.0)
    if annual_net > 0 and annual_cc_spend > (annual_net * 0.85):
        findings.append({
            "rule_id": "FIN-01",
            "rule_title": "Unexplained High Lifestyle vs Declared Income Discrepancy",
            "severity": "CRITICAL",
            "pattern_detected": f"Annual Credit Card expenditure (Rs. {annual_cc_spend:,.2f}) exceeds 85% of declared net annual income (Rs. {annual_net:,.2f}).",
            "legal_consequence": "Under Rajnesh v. Neha, courts hold that spending habits determine standard of living. The court draws an adverse inference of concealed income and imputes income commensurate with actual expenditure.",
            "court_action": "File application to summon complete Credit Card statements and CIBIL CIR report under Section 91 CrPC / Section 94 BNSS.",
        })

    # Rule FIN-02: Recurring transfers > 20k to family within 6 months prior to separation
    recent_siphoning = financial_profile.get("pre_separation_family_transfers_monthly", 0.0)
    if recent_siphoning >= 20000.0:
        findings.append({
            "rule_id": "FIN-02",
            "rule_title": "Artificial Asset Stripping / Siphoning to Relatives",
            "severity": "HIGH",
            "pattern_detected": f"Recurring monthly transfers averaging Rs. {recent_siphoning:,.2f} initiated to parents/siblings within 6 months prior to separation.",
            "legal_consequence": "Disallowed under Rajnesh v. Neha Part B. Transfers initiated proximate to matrimonial breakdown are treated as deliberate siphoning to artificially depress visible income.",
            "court_action": "Summon bank accounts of transferee relatives and request add-back into husband's assessable income.",
        })

    # Rule FIN-03: AIS / Form 26AS TDS entries != declared salary
    unreported_ais = financial_profile.get("has_unreported_26as_ais_income", False)
    if unreported_ais:
        findings.append({
            "rule_id": "FIN-03",
            "rule_title": "Undisclosed Form 26AS / AIS Revenue Streams",
            "severity": "CRITICAL",
            "pattern_detected": "TDS entries present under Sec 194A (Interest), 194J (Professional fees), or 194S (VDA/Crypto) not declared in Affidavit.",
            "legal_consequence": "Concealment of taxable revenue streams. Constitutes statutory non-disclosure violating mandatory Supreme Court asset guidelines.",
            "court_action": "File certified copy of AIS/26AS with application for adverse inference and immediate interim award based on undisclosed receipts.",
        })

    # Rule FIN-04: ITR Gross Total Income drops > 35% following separation
    itr_drop_pct = financial_profile.get("post_separation_itr_drop_percentage", 0.0)
    if itr_drop_pct >= 35.0:
        findings.append({
            "rule_id": "FIN-04",
            "rule_title": "Deliberate Post-Separation Income Depression",
            "severity": "HIGH",
            "pattern_detected": f"ITR Gross Total Income dropped by {itr_drop_pct:.1f}% immediately after separation or filing of maintenance petition.",
            "legal_consequence": "Under Jasbir Kaur Sehgal v. District Judge, Dehradun, sudden post-dispute drops in taxable income are viewed as intentional suppression. The court will assess maintenance on past earning capacity and professional qualifications.",
            "court_action": "Request assessment based on 3-year pre-dispute average income.",
        })

    # Rule FIN-05: Active GSTIN / MCA Director DIN not listed in Section II assets
    hidden_entity = financial_profile.get("hidden_corporate_entity_or_gstin", False)
    if hidden_entity:
        findings.append({
            "rule_id": "FIN-05",
            "rule_title": "Undisclosed Corporate Entity / Active Business Ownership",
            "severity": "CRITICAL",
            "pattern_detected": "Active Director DIN or GSTIN registration detected in public registers not disclosed in Part II of Asset Affidavit.",
            "legal_consequence": "Perjury under Section 340 CrPC / Section 379 BNSS read with Section 227 BNS (giving false statement on oath). Court can initiate criminal prosecution.",
            "court_action": "File Section 340 CrPC / 379 BNSS application for perjury and criminal prosecution for submitting a false affidavit under oath.",
        })

    return findings


def analyze_financial_document_text(document_text: str) -> Dict[str, Any]:
    """
    Parses salary slip or financial affidavit text to compute true net income
    and detect financial concealment patterns.
    """
    text = document_text or ""
    low = text.lower()

    # Extract Gross Income
    gross = 0.0
    gross_match = re.search(r"\b(?:gross\s+(?:salary|earnings?|income)|ctc|total\s+earnings?)\b[^\d]*([0-9,]+(?:\.[0-9]{2})?)", low)
    if gross_match:
        try:
            gross = float(gross_match.group(1).replace(",", ""))
        except Exception:
            gross = 0.0

    # If gross not found, look for salary / income numbers
    if gross == 0.0:
        alt_match = re.search(r"\b(?:salary|income|in-hand|earnings?)\s*(?:of|is|:|=|rs\.?|inr)?\s*([0-9,]+(?:\.[0-9]{2})?)", low)
        if alt_match:
            try:
                gross = float(alt_match.group(1).replace(",", ""))
            except Exception:
                gross = 0.0

    # Extract Deductions
    deductions = []
    has_child = any(k in low for k in ["child", "minor", "son", "daughter", "school fee", "daycare"])

    # Statutory Deductions
    tds_match = re.search(r"\b(?:tds|tax\s+deducted|income\s+tax)\b[^\d]*([0-9,]+(?:\.[0-9]{2})?)", low)
    if tds_match:
        try:
            deductions.append(PayslipLineItem("Income Tax (TDS)", float(tds_match.group(1).replace(",", "")), "INCOME_TAX_TDS"))
        except Exception:
            pass

    pf_match = re.search(r"\b(?:pf|epf|provident\s+fund)\b[^\d]*([0-9,]+(?:\.[0-9]{2})?)", low)
    if pf_match:
        try:
            deductions.append(PayslipLineItem("Mandatory EPF (12%)", float(pf_match.group(1).replace(",", "")), "MANDATORY_EPF_12_PCT"))
        except Exception:
            pass

    pt_match = re.search(r"\b(?:professional\s+tax|ptax)\b[^\d]*([0-9,]+(?:\.[0-9]{2})?)", low)
    if pt_match:
        try:
            deductions.append(PayslipLineItem("Professional Tax", float(pt_match.group(1).replace(",", "")), "PROFESSIONAL_TAX"))
        except Exception:
            pass

    # Voluntary Deductions
    car_match = re.search(r"\b(?:car\s+loan|car\s+emi|auto\s+loan)\b[^\d]*([0-9,]+(?:\.[0-9]{2})?)", low)
    if car_match:
        try:
            deductions.append(PayslipLineItem("Car Loan EMI", float(car_match.group(1).replace(",", "")), "VOLUNTARY_LOAN"))
        except Exception:
            pass

    home_match = re.search(r"\b(?:home\s+loan|housing\s+loan|hl\s+emi)\b[^\d]*([0-9,]+(?:\.[0-9]{2})?)", low)
    if home_match:
        try:
            deductions.append(PayslipLineItem("Home Loan EMI", float(home_match.group(1).replace(",", "")), "VOLUNTARY_LOAN"))
        except Exception:
            pass

    pl_match = re.search(r"\b(?:personal\s+loan|pl\s+emi)\b[^\d]*([0-9,]+(?:\.[0-9]{2})?)", low)
    if pl_match:
        try:
            deductions.append(PayslipLineItem("Personal Loan EMI", float(pl_match.group(1).replace(",", "")), "VOLUNTARY_LOAN"))
        except Exception:
            pass

    vpf_match = re.search(r"\b(?:vpf|voluntary\s+pf)\b[^\d]*([0-9,]+(?:\.[0-9]{2})?)", low)
    if vpf_match:
        try:
            deductions.append(PayslipLineItem("Voluntary PF Top-Up", float(vpf_match.group(1).replace(",", "")), "VOLUNTARY_SAVINGS"))
        except Exception:
            pass

    forensics_calc = None
    if gross > 0:
        forensics_calc = compute_assessable_maintenance_income(gross, deductions, has_minor_child=has_child)

    # Cross-check rules detection
    profile = {
        "declared_annual_net_income": (forensics_calc["true_net_assessable_income"] * 12) if forensics_calc else 0.0,
        "annual_credit_card_spend": 0.0,
        "pre_separation_family_transfers_monthly": 0.0,
        "has_unreported_26as_ais_income": any(k in low for k in ["ais mismatch", "26as mismatch", "unreported interest", "crypto transfer", "consultancy fee"]),
        "post_separation_itr_drop_percentage": 0.0,
        "hidden_corporate_entity_or_gstin": any(k in low for k in ["active directorship", "mca din", "gstin not disclosed", "undisclosed company"]),
    }

    # CC spend check
    cc_match = re.search(r"\bcredit\s+card\s+(?:payments?|spend|bill)[^\d]*([0-9,]+(?:\.[0-9]{2})?)", low)
    if cc_match:
        try:
            profile["annual_credit_card_spend"] = float(cc_match.group(1).replace(",", "")) * 12
        except Exception:
            pass

    # Siphoning check
    siphon_match = re.search(r"\b(?:transfer(?:red)?|sent|paid)\s+(?:to\s+(?:father|mother|brother|sister|parents|family))[^\d]*([0-9,]+(?:\.[0-9]{2})?)", low)
    if siphon_match:
        try:
            profile["pre_separation_family_transfers_monthly"] = float(siphon_match.group(1).replace(",", ""))
        except Exception:
            pass

    # ITR drop check
    itr_drop_match = re.search(r"\b(?:income\s+dropped|drop(?:ped)?\s+by|reduced\s+by)\s+([0-9]{1,2})%", low)
    if itr_drop_match:
        try:
            profile["post_separation_itr_drop_percentage"] = float(itr_drop_match.group(1))
        except Exception:
            pass

    concealment_findings = execute_concealment_matrix(profile)

    return {
        "financial_forensics_enabled": True,
        "income_forensics": forensics_calc,
        "concealment_matrix_findings": concealment_findings,
        "num_discrepancies_flagged": len(concealment_findings),
        "rajnesh_compliance_status": "NON_COMPLIANT_CONCEALMENT_DETECTED" if concealment_findings else "COMPLIANT",
    }
