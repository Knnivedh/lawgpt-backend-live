"""
court_generators.py - Court-Grade Output Generators: Set-Off Calculator & BSA Section 63 Certificate.

Implements Gemini Architectural Blueprint Module 4:
1. Parallel Proceedings Set-Off & Disclosure Calculator (Rajnesh v. Neha Part B Overlapping Jurisdiction).
2. Automated BSA Section 63(4) Electronic Evidence Certificate Generator (SHA-256 cryptographic hash & Part A Schedule).
"""

import re
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional


def calculate_parallel_maintenance_set_off(
    awards: List[Dict[str, Any]],
    claimant_name: str = "Claimant / Wife",
    respondent_name: str = "Respondent / Husband",
) -> Dict[str, Any]:
    """
    Calculates net payable maintenance across parallel proceedings under Rajnesh v. Neha (2020 SC)
    Part B - Issue I (Overlapping Jurisdiction & Set-Off).
    
    Formula: Net Monthly Payable = Max(Award_1, Award_2, Award_3)
    unless a subsequent court has explicitly recorded reasons why an award is granted in addition.
    """
    if not awards:
        return {
            "total_proceedings": 0,
            "net_monthly_payable": 0.0,
            "set_off_summary": "No active maintenance orders submitted.",
            "disclosure_pleading_paragraph": "",
        }

    parsed_awards = []
    max_amount = 0.0
    additive_total = 0.0
    highest_forum = ""
    order_details_list = []

    additive_regex = re.compile(r"\b(?:in\s+addition\s+to|over\s+and\s+above|besides\s+the\s+amount\s+awarded|further\s+sum)\b", re.IGNORECASE)

    for a in awards:
        amount = float(a.get("amount", 0.0))
        forum = a.get("forum", "Court Order")
        order_date = a.get("order_date", "Pending")
        case_no = a.get("case_no", "")
        notes = a.get("notes", "") or ""
        is_additive = a.get("is_explicitly_additive", False) or bool(additive_regex.search(notes))

        parsed_awards.append({
            "forum": forum,
            "case_no": case_no,
            "amount": amount,
            "order_date": order_date,
            "is_additive": is_additive,
        })

        if is_additive:
            additive_total += amount
            order_details_list.append(f"{forum} (Order dated {order_date}): Rs. {amount:,.2f}/month [EXPLICITLY ADDITIVE]")
        else:
            if amount > max_amount:
                max_amount = amount
                highest_forum = forum
            order_details_list.append(f"{forum} (Order dated {order_date}): Rs. {amount:,.2f}/month")

    net_payable = max_amount + additive_total

    # Mandatory Disclosure Paragraph for court pleadings per Rajnesh v. Neha
    orders_joined = "; ".join(order_details_list)
    pleading_draft = (
        f"IN COMPLIANCE WITH THE MANDATORY DIRECTIONS OF THE HON'BLE SUPREME COURT IN "
        f"RAJNESH V. NEHA, (2021) 2 SCC 324 (PART B - ISSUE I), THE APPLICANT/PETITIONER HEREBY FULLY DISCLOSES "
        f"THAT THE FOLLOWING MAINTENANCE ORDERS HAVE BEEN PASSED IN PARALLEL PROCEEDINGS: [{orders_joined}]. "
        f"THE PRESENT CLAIM IS FILED SUBJECT TO MANDATORY ADJUSTMENT AND SET-OFF TO ENSURE THE RESPONDENT IS NOT "
        f"SUBJECTED TO DUPLICATIVE OR COMPOUNDED LIABILITY BEYOND THE HIGHEST CONCURRENT STATUTORY ASSESSMENT "
        f"OF RS. {net_payable:,.2f} PER MONTH."
    )

    return {
        "total_parallel_proceedings": len(parsed_awards),
        "proceedings_breakdown": parsed_awards,
        "highest_forum_awarded": highest_forum,
        "highest_single_award": max_amount,
        "explicitly_additive_awards_total": additive_total,
        "net_monthly_payable_by_respondent": net_payable,
        "statutory_doctrine": "Rajnesh v. Neha (2020 SC) - Overlapping Jurisdiction & Mandatory Set-Off",
        "disclosure_pleading_paragraph": pleading_draft,
    }


def generate_bsa_section_63_certificate_metadata(
    file_bytes: bytes,
    filename: str,
    device_model: str = "Client Personal Mobile Device / Computer",
    os_version: str = "Android / iOS / Windows / macOS",
    owner_name: str = "Deponent",
) -> Dict[str, Any]:
    """
    Computes the mandatory cryptographic hash required under 'The Schedule'
    to Section 63(4)(c) of the Bharatiya Sakshya Adhiniyam (BSA), 2023
    (formerly Section 65B of the Indian Evidence Act, 1872).
    """
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()
    timestamp_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    schedule_part_a = (
        f"AFFIDAVIT UNDER PART A OF THE SCHEDULE\n"
        f"READ WITH SECTION 63(4) OF THE BHARATIYA SAKSHYA ADHINIYAM, 2023\n\n"
        f"I, {owner_name}, do hereby solemnly affirm and declare on oath as under:\n\n"
        f"1. That I am the owner and lawful custodian of the electronic computing device, namely '{device_model}' "
        f"operating on '{os_version}'.\n"
        f"2. That the electronic record produced herewith, titled '{filename}' (File Size: {len(file_bytes)} bytes), "
        f"was generated and retrieved from the said device during the period over which the computer device was "
        f"regularly used and was operating properly.\n"
        f"3. That during the relevant period, the said device was in my lawful and continuous control, and there was "
        f"no mechanical or software tampering, interception, or alteration that could impair the accuracy or integrity "
        f"of the electronic contents.\n"
        f"4. That in accordance with Part A of the Schedule to Section 63(4)(c) of the Bharatiya Sakshya Adhiniyam, 2023, "
        f"the cryptographic SHA-256 hash value of the said electronic record has been verified as:\n"
        f"   SHA-256: {sha256_hash}\n"
        f"5. That the contents of the said electronic file represent an exact, untampered digital reproduction of the "
        f"original electronic communication.\n\n"
        f"DEPONENT\n\n"
        f"VERIFICATION:\n"
        f"Verified at ________ on this ____ day of ________, 2026, that the contents of the above affidavit are true "
        f"and correct to my personal knowledge, no part of it is false, and nothing material has been concealed therefrom."
    )

    schedule_part_b = (
        f"CERTIFICATE UNDER PART B OF THE SCHEDULE\n"
        f"READ WITH SECTION 63(4) OF THE BHARATIYA SAKSHYA ADHINIYAM, 2023\n\n"
        f"I, Technical Officer / Person in charge of the computer system, hereby certify:\n\n"
        f"1. That I have examined the electronic record titled '{filename}' with cryptographic hash value:\n"
        f"   SHA-256: {sha256_hash}\n"
        f"2. That the hash generation was executed using an uncorrupted, standard cryptographic algorithm (FIPS 180-4 compliant).\n"
        f"3. That the output is a true digital extract matching the electronic storage medium without bitwise deviation.\n\n"
        f"TECHNICAL EXPERT / AUTHORIZED SIGNATORY\n"
        f"Date: {timestamp_utc}"
    )

    return {
        "statutory_provision": "Section 63(4) read with The Schedule, Bharatiya Sakshya Adhiniyam, 2023",
        "former_provision": "Section 65B(4) Indian Evidence Act, 1872",
        "binding_precedent": "Arjun Panditrao Khotkar v. Kailash Kushanrao Gorantyal (2020) 7 SCC 1",
        "deponent_name": owner_name,
        "file_name": filename,
        "file_size_bytes": len(file_bytes),
        "device_specification": f"{device_model} running {os_version}",
        "hash_algorithm": "SHA-256",
        "cryptographic_hash_value": sha256_hash,
        "verification_timestamp": timestamp_utc,
        "part_a_schedule_affidavit": schedule_part_a,
        "part_b_schedule_certificate": schedule_part_b,
    }
