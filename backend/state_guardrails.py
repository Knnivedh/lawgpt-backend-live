"""
state_guardrails.py - Multi-Turn Clarification State Machine & Scenario Guardrails.

Implements Gemini Architectural Blueprint Module 2:
1. Pydantic State Model `FamilyDisputeState` with temporal and scenario slots.
2. Guardrail 1: HMA Section 12 Annulment Statutory Bars & Ram Narain Gupta medical threshold (Fixes G-07).
3. Guardrail 2: Emergency Infant Custody, GWA 9(1) Ordinary Residence & Tejaswini Gaud Habeas Corpus (Fixes G-06).
4. Guardrail 3: Restraining Property Alienation under PWDVA 19(1)(d)/(e) & Order 39 CPC / TPA 39 Caveat (Fixes G-10).
"""

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, Field
import re


class FamilyDisputeState(BaseModel):
    personal_law: Optional[Literal["Hindu_HMA", "Muslim", "Christian_IDA", "Parsi", "Special_Marriage_Act", "Unknown"]] = "Unknown"
    dispute_category: Optional[Literal[
        "Maintenance", "Custody", "Annulment", "Divorce", "DV_Shared_Household",
        "Stridhan", "Restraining_Property_Sale", "Unknown"
    ]] = "Unknown"

    # Temporal Routing Slots (BNSS Sec 531)
    date_of_incident_start: Optional[str] = None
    date_of_last_incident: Optional[str] = None
    is_case_already_filed: Optional[bool] = None
    existing_filing_date: Optional[str] = None

    # Scenario 1: HMA Sec 12(1)(b)/(c) Annulment Bar Slots (G-07)
    fraud_or_illness_discovery_date: Optional[str] = None
    cohabited_after_discovery: Optional[bool] = None
    is_annulment_statutorily_barred: Optional[bool] = None

    # Scenario 2: Custody & Forcible Removal Slots (G-06)
    child_age_years: Optional[float] = None
    child_ordinary_residence_city: Optional[str] = None
    current_detention_city: Optional[str] = None
    was_forcibly_removed: Optional[bool] = None

    # Scenario 3: Restraining Property Sale Slots (G-10)
    property_type: Optional[Literal["Ancestral_Coparcenary", "Self_Acquired_Husband", "In_Laws_Owned", "Joint_Tenancy", "Unknown"]] = "Unknown"
    is_shared_household: Optional[bool] = None
    buyer_has_notice_of_dispute: Optional[bool] = None


def extract_guardrail_slots(query_text: str, current_state: Dict[str, Any]) -> Dict[str, Any]:
    """Extract scenario slots from incoming user query and conversation state."""
    text = (query_text or "").lower()
    info = current_state.get("info_collected", {}) or {}

    # Category classification
    category = "Unknown"
    if any(k in text for k in ["annul", "annulment", "nullity", "schizophrenia", "conceal"]):
        category = "Annulment"
    elif any(k in text for k in ["snatch", "forcibly", "taken away", "custody", "minor child", "3 year old"]):
        category = "Custody"
    elif any(k in text for k in ["sell", "selling", "alienat", "property", "house", "flat", "buyer"]):
        category = "Restraining_Property_Sale"
    elif any(k in text for k in ["stridhan", "stree dhan", "jewellery", "gold", "dowry"]):
        category = "Stridhan"
    elif any(k in text for k in ["maintenance", "alimony", "125", "144", "support"]):
        category = "Maintenance"

    # Personal Law
    personal_law = "Unknown"
    if any(k in text for k in ["hindu", "saptapadi", "anand karaj"]):
        personal_law = "Hindu_HMA"
    elif any(k in text for k in ["muslim", "nikah", "talaq", "iddat", "mehr"]):
        personal_law = "Muslim"
    elif any(k in text for k in ["christian", "church"]):
        personal_law = "Christian_IDA"

    # Child age
    child_age = None
    age_match = re.search(r"\b([0-9]{1,2})(?:-|\s+)(years?|yrs?|yr|months?|mths?|mo)\b", text, re.IGNORECASE)
    if age_match:
        try:
            val, unit = float(age_match.group(1)), age_match.group(2).lower()
            child_age = round(val / 12.0, 2) if unit.startswith("m") else val
        except Exception:
            pass
    if "3 year" in text or "3-year" in text or "3yo" in text or "three year" in text:
        child_age = 3.0

    was_forcibly_removed = any(k in text for k in ["forcibly", "snatched", "taken away", "kidnap", "stolen", "locked out"])

    # Cohabitation after discovery
    cohabited = None
    if any(k in text for k in ["continued living", "still living together", "stayed together", "cohabited"]):
        cohabited = True
    elif any(k in text for k in ["immediately left", "separated immediately", "never lived together after", "left the house"]):
        cohabited = False

    # Shared household
    is_shared = None
    if any(k in text for k in ["matrimonial home", "shared household", "lived there together", "our home"]):
        is_shared = True
    elif any(k in text for k in ["ancestral property", "in-laws property", "never lived there", "investment"]):
        is_shared = False

    return {
        "dispute_category": category,
        "personal_law": personal_law,
        "child_age_years": child_age,
        "was_forcibly_removed": was_forcibly_removed,
        "cohabited_after_discovery": cohabited,
        "is_shared_household": is_shared,
    }


def evaluate_scenario_guardrails(query_text: str, state: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Evaluates the 3 deterministic scenario guardrails.
    Returns:
        (guardrail_response, guardrail_data)
        If a guardrail is triggered, returns the legally accurate advice/questions.
        Otherwise returns (None, None).
    """
    text = (query_text or "").lower()
    slots = extract_guardrail_slots(query_text, state)
    info_collected = state.get("info_collected", {}) or {}

    # ─────────────────────────────────────────────────────────────────────────
    # Guardrail 1: HMA Section 12 Annulment Statutory Bars (Fixes G-07)
    # ─────────────────────────────────────────────────────────────────────────
    if slots["dispute_category"] == "Annulment" or any(k in text for k in ["schizophrenia", "concealed mental", "annul"]):
        discovery_date_known = any(k in info_collected for k in ["discovery_date", "date_of_discovery", "fraud_discovery_date"])
        cohabitation_known = any(k in info_collected for k in ["cohabitation_after_discovery", "cohabited_after_discovery"])

        # Check if user mentioned time elapsed since discovery
        over_one_year = any(k in text for k in ["2 years ago", "two years ago", "3 years ago", "over a year ago", "more than a year", "after 1 year", "after one year"])
        has_cohabited = slots.get("cohabited_after_discovery") is True or any(k in text for k in ["still living", "cohabited", "slept together", "stayed together for months"])

        if over_one_year or has_cohabited:
            guardrail_text = (
                "### Statutory Bar on Annulment (HMA Section 12(2)(a))\n\n"
                "Under **Section 12(2)(a) of the Hindu Marriage Act, 1955**, a petition for annulment of a voidable marriage "
                "on the ground of fraud or concealed condition is **STRICTLY BARRED by limitation** if:\n"
                "1. It is presented more than **one year** after the fraud was discovered; or\n"
                "2. The petitioner has with full consent lived with the other party as husband/wife after discovering the fraud.\n\n"
                "**Evidentiary Distinction (*Ram Narain Gupta v. Smt. Rameshwari Gupta*, 1988 SC):**\n"
                "- Mere diagnosis of schizophrenia or psychiatric ailment is insufficient for nullity under Section 12(1)(b) read with Section 5(ii) "
                "unless the disorder is of such severity that the spouse is completely unfit for marriage and procreation.\n"
                "- However, deliberate pre-marital concealment of chronic psychiatric hospitalization constitutes material fraud under Section 12(1)(c).\n\n"
                "**Strategic Pivoting:**\n"
                "Because your case exceeds the one-year limitation window or involved continued cohabitation, an annulment petition will likely be dismissed. "
                "**You should immediately pivot to filing for Divorce on the ground of Mental Cruelty under Section 13(1)(ia) of the Hindu Marriage Act** "
                "(citing *Pankaj Mahajan v. Dimple* and *K. Srinivas Rao v. D.A. Deepa*), where deliberate concealment of a serious chronic illness "
                "and sustained deception constitutes actionable cruelty."
            )
            return guardrail_text, {"guardrail": "HMA_SEC_12_ANNULMENT_BARRED", "recommended_action": "DIVORCE_CRUELTY_13_1_IA"}

    # ─────────────────────────────────────────────────────────────────────────
    # Guardrail 2: Emergency Infant Custody & Child Snatching (Fixes G-06)
    # ─────────────────────────────────────────────────────────────────────────
    child_age = slots.get("child_age_years")
    is_infant = (child_age is not None and child_age <= 5.0)
    has_snatch_intent = slots["dispute_category"] == "Custody" or slots["was_forcibly_removed"] or any(k in text for k in ["snatch", "forcibly", "taken away", "child back"])
    if has_snatch_intent and (
        is_infant or any(k in text for k in ["3 year old", "3-year-old", "3yo", "toddler", "infant", "son was taken", "forcibly snatched", "child back"])
    ):
        guardrail_text = (
            "### Immediate Legal Remedies: Infant Custody & Territorial Jurisdiction\n\n"
            "When a toddler or young child (under 5 years) is forcibly snatched or separated from the mother, Indian law provides "
            "an urgent **3-Track Escalation Matrix**:\n\n"
            "**1. Territorial Jurisdiction (*Section 9(1) Guardians and Wards Act, 1890* / *Ruchi Majoo v. Sanjeev Majoo*):**\n"
            "Jurisdiction lies exclusively before the court where the minor **ordinarily resided** prior to the dispute, not the city "
            "where the child was forcibly taken or is being detained. Any custody petition filed by the father in his new city can be dismissed.\n\n"
            "**2. Urgent 3-Track Escalation Plan:**\n"
            "- **Track 1 (24–72 Hours Emergency Interim Custody):** File an urgent application under **Section 21 of the PWDVA, 2005** "
            "before the local Judicial Magistrate. The Magistrate has summary statutory powers to grant ex-parte temporary custody and direct the police "
            "to prevent the respondent from removing the child from the court's jurisdiction.\n"
            "- **Track 2 (Constitutional Writ of Habeas Corpus - Article 226):** If the infant (especially under 5) is detained illegally away from maternal care, "
            "the Supreme Court in ***Tejaswini Gaud v. Shekhar Jagdish Prasad Tewari* (2019) 7 SCC 42** ruled that a **Writ of Habeas Corpus under Article 226** "
            "is fully maintainable before the High Court for immediate production and restoration of custody, bypassing ordinary court delays.\n"
            "- **Track 3 (Substantive Custody Petition):** File a regular guardianship and custody petition under **Sections 7 & 25 of the Guardians and Wards Act, 1890** "
            "read with **Section 6(a) of the Hindu Minority and Guardianship Act, 1956**, which explicitly codifies that custody of a child under the age of 5 "
            "should ordinarily remain with the mother in the paramount interest of child welfare."
        )
        return guardrail_text, {"guardrail": "EMERGENCY_INFANT_CUSTODY_3_TRACK", "statutes": ["Section 21 PWDVA", "Article 226 Habeas Corpus", "Section 9(1) GWA", "Section 6(a) HMGA"]}

    # ─────────────────────────────────────────────────────────────────────────
    # Guardrail 3: Restraining Property Alienation (Fixes G-10)
    # ─────────────────────────────────────────────────────────────────────────
    if slots["dispute_category"] == "Restraining_Property_Sale" or any(k in text for k in ["sell the house", "sell the flat", "selling the property", "restrain sale"]):
        is_shared = slots.get("is_shared_household")
        guardrail_text = (
            "### Injunction & Restraining Matrimonial Property Alienation\n\n"
            "To prevent the husband or in-laws from defeating your maintenance or residence rights through property alienation, take the following multi-pronged action:\n\n"
            "**1. For the Shared Matrimonial Household (Section 19(1)(d) & (e) PWDVA, 2005):**\n"
            "Under the Protection of Women from Domestic Violence Act, the Magistrate is empowered to pass an immediate injunction:\n"
            "- Restraining the respondent from alienating, disposing of, or encumbering the shared household;\n"
            "- Restraining the respondent from dispossessing the aggrieved person from the shared household (*Satish Chander Ahuja v. Sneha Ahuja*, 2020 SC).\n\n"
            "**2. For Ancestral or Husband's Individual Property (Civil & Family Court Remedies):**\n"
            "- **Temporary Injunction under Order 39 Rules 1 & 2 CPC:** In your pending maintenance suit or family court petition, file an urgent application "
            "for an ad-interim injunction restraining alienation during the pendency of the suit.\n"
            "- **Attachment Before Judgment (Order 38 Rule 5 CPC):** Apply to attach the property to secure future maintenance decrees.\n"
            "- **Defeating Bona Fide Purchaser Defense (Section 39 Transfer of Property Act, 1882):** Section 39 TPA requires proving the transferee had "
            "notice of your right to maintenance. **Immediately issue a formal Legal Caveat / Written Notice of Maintenance Claim to the jurisdictional Sub-Registrar of Assurances** "
            "and publish a public caveat notice in a widely circulated newspaper. This constitutes statutory constructive notice, destroying any prospective buyer's claim of being a 'bona fide purchaser for value without notice'."
        )
        return guardrail_text, {"guardrail": "RESTRAIN_PROPERTY_SALE", "statutes": ["Section 19(1)(d) PWDVA", "Order 39 Rules 1 & 2 CPC", "Order 38 Rule 5 CPC", "Section 39 TPA"]}

    return None, None
