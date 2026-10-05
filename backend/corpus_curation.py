"""
corpus_curation.py - retrieval-time curation of the statute/case-law pool.

Nothing is deleted from Milvus. These lists only change what the retriever
returns, so they are reversible by editing this file.

The parent_ids are specific to the collection built from data/chunked/
(MILVUS_COLLECTION_NAME=indian_family_law_cases_hrag_test). If the corpus is
re-chunked, ids change and these lists must be rebuilt; better still, remove
or merge the source documents at that point and empty the lists.
"""

from typing import Dict, FrozenSet, Optional

# Documents in the family_law_2 pool that are not about family law.
EXCLUDED_PARENT_IDS = frozenset({
    2967,  # "custody" under s.167 CrPC (police/agency detention)
    2978,  # bail order, arms possession
    2979,  # army officer promotion dispute
    2980,  # vehicle repossession, consumer law
    2981,  # public health officers' service writ (1966)
    2982,  # West Bengal Inland Fisheries Act charge-sheet
    3009,  # tax incentives for foreign direct investment
    3010,  # written grounds of arrest (Art. 22 / BNSS s.47)
})

# Several articles on the same act or the same ruling. Searching returns at
# most one document per group, so one subject cannot take every statute slot.
SAME_SUBJECT_GROUPS = [
    {2926, 2950},              # Hindu Marriage Act, 1955
    {2927, 2951},              # Special Marriage Act, 1954
    {2930, 2952},              # Protection of Women from Domestic Violence Act, 2005
    {2931, 2954},              # Hindu Minority and Guardianship Act, 1956
    {2932, 2960},              # Hindu Succession Act, 1956
    {2962, 2986, 2987, 2988},  # divorced Muslim women, maintenance under s.125 CrPC
    {2989, 2990, 2991, 2992},  # child of Muslim-Hindu marriage, father's property
    {2983, 2984, 2985},        # Article 142 and mutual-consent divorce decrees
    {2964, 2999},              # marriage equality: Rohatgi's arguments
    {2965, 3000, 3001},        # marriage equality: Justice Khanna's recusal
    {2997, 2998},              # marriage equality: directions on queer rights
    {3006, 3007},              # marriage equality: review hearing date
]

_GROUP_OF: Dict[int, FrozenSet[int]] = {
    pid: frozenset(group) for group in SAME_SUBJECT_GROUPS for pid in group
}


def subject_key(parent_id: Optional[int]):
    """Documents with the same key count as one subject. None stays None."""
    if parent_id is None:
        return None
    return _GROUP_OF.get(parent_id, parent_id)
