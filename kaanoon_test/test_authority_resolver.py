import sys
from pathlib import Path


project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from kaanoon_test.authority_resolver import AuthorityResolver, normalize_authority_display_name


HIJAB_INTERFAITH_QUERY = """
Government college bans religious identifiers including hijab. Muslim students challenge under
Articles 14, 19, 21 and 25. Hindu students wear saffron scarves. Public order tensions arise.
An adult Muslim woman marries a Hindu man under the Special Marriage Act. Family files habeas
corpus and FIR alleging love jihad, forced conversion, cheating and conspiracy. State monitors
interfaith marriages.
"""


def test_authority_pack_loads_with_required_fields():
    resolver = AuthorityResolver()

    assert len(resolver.records) >= 10
    for record in resolver.records:
        assert record.authority_id
        assert record.canonical_name
        assert record.aliases
        assert record.issues
        assert record.holding_summary
        assert record.limits_or_cautions
        assert record.source_locator


def test_hijab_interfaith_query_resolves_core_authorities():
    resolver = AuthorityResolver()
    issues = [
        {
            "id": "constitutional_privacy",
            "bucket": "constitutional",
            "label": "Privacy, religion, equality and public order",
            "question": "Whether hijab restriction, surveillance, FIR and habeas corpus violate rights.",
        }
    ]

    bundle = resolver.build_bundle(HIJAB_INTERFAITH_QUERY, issues)
    ids = {row["id"] for row in bundle["verified_authorities"]}

    assert "privacy_puttaswamy" in ids
    assert "adult_marriage_shafin_jahan" in ids
    assert "adult_choice_lata_singh" in ids
    assert "religion_bijoe_emmanuel" in ids
    assert "religion_shirur_mutt" in ids
    assert "religion_sabarimala" in ids
    assert "hijab_aishat_shifa_resham" in ids
    assert "criminal_process_lalita_kumari" in ids
    assert "criminal_quashing_bhajan_lal" in ids


def test_retrieved_doc_upgrades_canonical_status():
    resolver = AuthorityResolver()
    docs = [
        {
            "text": "Justice K.S. Puttaswamy right to privacy Article 21 holding",
            "metadata": {
                "title": "Justice K.S. Puttaswamy (Retd.) v. Union of India",
                "case_id": "puttaswamy_2017",
                "court": "Supreme Court of India",
                "year": "2017",
                "source_store": "azure_sc_local",
                "source_tier": "authoritative",
            },
        }
    ]

    bundle = resolver.build_bundle("privacy surveillance Article 21 Puttaswamy", [], docs)
    puttaswamy = next(row for row in bundle["verified_authorities"] if row["id"] == "privacy_puttaswamy")

    assert puttaswamy["status"] == "retrieved"
    assert puttaswamy["case_id"] == "puttaswamy_2017"
    assert puttaswamy["source_store"] == "azure_sc_local"


def test_batch_display_name_is_replaced_when_fallback_exists():
    assert normalize_authority_display_name("batch_20_43", fallback="Privacy issue") == "Privacy issue"
    assert normalize_authority_display_name("batch-20-43", case_name="Puttaswamy") == "Puttaswamy"
