"""
Retrieval labels for the legal scenarios (used by build_datasets.py).

For each scenario id:
  law   known-relevant documents in the statute pool (category family_law_2),
        chosen by reading the titles of all 81 documents in that pool
  case  known-relevant forum posts (category family_law). Judged by reading the
        title and opening text of every candidate pooled from two search
        methods (BM25 over whole documents, vector search over chunks; see
        pool_candidates.py and candidates.json), plus a few posts already
        known from earlier work
  seed  the corpus post the scenario was modelled on, where there is one. It is
        kept out of `case` so that finding the scenario's own source does not
        count as a hit; report it separately as known-item retrieval
  in_corpus  whether the statute a good answer needs is in the statute pool:
        yes / partly / no

Judgements were made by an AI assistant from titles and the first lines of
each post, not the full text. A person should spot-check them.
"""

LABELS = {
    # ── parallel scenarios ──────────────────────────────────────────────────
    "P01": dict(law=[2930], case=[2185, 478, 58, 754, 2048, 1333, 1374, 2845], seed=None, in_corpus="yes"),
    "P02": dict(law=[2950, 2983], case=[1468, 2703, 1566, 2671, 69, 123], seed=None, in_corpus="yes"),
    "P03": dict(law=[2934, 2955, 2931], case=[612, 1019, 993], seed=None, in_corpus="partly"),
    "P04": dict(law=[2930, 2950, 2953, 2968], case=[1186, 974, 400, 827, 648], seed=None, in_corpus="partly"),
    "P05": dict(law=[2950, 2956], case=[1320, 405, 2595, 2619], seed=None, in_corpus="partly"),
    "P06": dict(law=[2934, 2955], case=[2880, 396, 1281, 1310], seed=964, in_corpus="partly"),
    "P07": dict(law=[2957], case=[1259, 1867, 2358, 2075, 1270], seed=946, in_corpus="no"),
    "P08": dict(law=[2953, 2950, 2968, 2933], case=[1103, 2163], seed=86, in_corpus="yes"),
    "P09": dict(law=[2933, 2950, 2953, 2968], case=[2180, 162, 1209, 6, 1515, 2857], seed=240, in_corpus="partly"),
    "P10": dict(law=[2968, 2973], case=[1084, 128, 830], seed=1235, in_corpus="partly"),
    "P11": dict(law=[2950], case=[2725, 1573, 2204, 603], seed=2136, in_corpus="partly"),
    "P12": dict(law=[2950, 2963, 2993], case=[944, 2145, 1933, 163], seed=2533, in_corpus="yes"),
    "P13": dict(law=[], case=[1104, 1222, 1674, 178, 2605, 1734, 1289, 1691], seed=32, in_corpus="no"),
    "P14": dict(law=[2930, 2950], case=[1698, 1168, 534], seed=1133, in_corpus="partly"),
    "P15": dict(law=[2934, 2931, 2955], case=[131, 2423, 2833, 523, 612, 165], seed=491, in_corpus="yes"),
    "P16": dict(law=[2934, 2955, 2931], case=[180, 1295, 523, 1774, 154, 663], seed=531, in_corpus="partly"),
    "P17": dict(law=[2957, 2930], case=[2324, 890, 2470, 908, 2305, 2563], seed=2831, in_corpus="partly"),
    "P18": dict(law=[2957, 2958, 2930], case=[219, 712, 1552, 2083], seed=1251, in_corpus="yes"),
    "P19": dict(law=[2940, 2939, 2950], case=[713, 2511, 1834, 2261, 274, 261], seed=225, in_corpus="yes"),
    "P20": dict(law=[2941, 2950], case=[1931, 2162, 509, 1933, 510], seed=580, in_corpus="partly"),
    "P21": dict(law=[2950, 2943], case=[2506, 1431, 2847, 1260, 1302], seed=1088, in_corpus="yes"),
    "P22": dict(law=[2943, 2942, 2950], case=[1192, 124, 832, 2612, 117], seed=446, in_corpus="yes"),
    "P23": dict(law=[2950, 2930, 2957], case=[488, 219, 1321, 2064, 2083], seed=2614, in_corpus="yes"),
    "P24": dict(law=[2937, 2962, 2959], case=[146, 1270, 41, 445], seed=413, in_corpus="yes"),
    "P25": dict(law=[2959, 2938], case=[1391, 41, 186, 633], seed=887, in_corpus="partly"),
    "P26": dict(law=[2951, 2966, 3008], case=[1378, 554, 2220, 381, 916], seed=1861, in_corpus="yes"),
    "P27": dict(law=[2932, 2969], case=[1410, 1393], seed=1553, in_corpus="yes"),
    "P28": dict(law=[], case=[888, 114, 777, 2413, 822, 1136, 617], seed=2079, in_corpus="no"),
    "P29": dict(law=[2950], case=[687, 1339, 1516, 330, 2251], seed=790, in_corpus="partly"),
    "P30": dict(law=[2953, 2975, 2931], case=[583, 2911, 2309, 1985, 2457], seed=234, in_corpus="yes"),
    # ── English ─────────────────────────────────────────────────────────────
    "L-en-01": dict(law=[2933, 2950, 2983], case=[1252, 2873, 235, 324], seed=1285, in_corpus="yes"),
    "L-en-02": dict(law=[], case=[954, 355, 2366, 2359, 2000, 2794], seed=2260, in_corpus="no"),
    "L-en-03": dict(law=[2950, 2983], case=[388, 1479, 36, 2043, 1395], seed=2550, in_corpus="yes"),
    "L-en-04": dict(law=[2933, 2950], case=[480, 1830, 2576], seed=2306, in_corpus="partly"),
    "L-en-05": dict(law=[2953, 2975, 2931], case=[2457, 1868, 2229, 1094, 2623, 150], seed=2124, in_corpus="partly"),
    "L-en-06": dict(law=[], case=[984, 134], seed=2431, in_corpus="no"),
    "L-en-07": dict(law=[2955, 2931, 2934], case=[240, 1960, 19, 1878], seed=2252, in_corpus="yes"),
    "L-en-08": dict(law=[2943, 2942, 2950], case=[1196, 1862, 2091, 458], seed=519, in_corpus="yes"),
    "L-en-09": dict(law=[2950, 2941], case=[410, 2358, 407, 1770], seed=348, in_corpus="partly"),
    "L-en-10": dict(law=[2943, 2950], case=[1192, 446, 1363, 117], seed=2643, in_corpus="yes"),
    # ── Hindi ───────────────────────────────────────────────────────────────
    "L-hi-01": dict(law=[2930, 2953, 2968], case=[1902, 1264, 885, 1316], seed=None, in_corpus="yes"),
    "L-hi-02": dict(law=[2957, 2930], case=[2803, 2563, 2470, 214, 1013], seed=2831, in_corpus="yes"),
    "L-hi-03": dict(law=[2941, 2950], case=[1309, 1132, 229, 1775, 1931], seed=None, in_corpus="yes"),
    "L-hi-04": dict(law=[2932, 2969], case=[1410, 1393], seed=1553, in_corpus="yes"),
    "L-hi-05": dict(law=[2939, 2962, 2959], case=[905, 1283], seed=495, in_corpus="yes"),
    "L-hi-06": dict(law=[2932, 2930], case=[929, 2148, 1501, 52], seed=None, in_corpus="yes"),
    "L-hi-07": dict(law=[2951, 3008], case=[940, 913, 703, 981, 71], seed=2694, in_corpus="partly"),
    "L-hi-08": dict(law=[2953, 2950, 2968, 2934], case=[2176, 1103, 2163, 798], seed=420, in_corpus="yes"),
    "L-hi-09": dict(law=[2950, 2934, 2931], case=[1683, 1113, 2251, 2428, 47, 1815], seed=1106, in_corpus="yes"),
    "L-hi-10": dict(law=[2930, 2953, 2950, 2968], case=[30, 2599, 534, 1168], seed=None, in_corpus="partly"),
    # ── Hinglish ────────────────────────────────────────────────────────────
    "L-hien-01": dict(law=[], case=[2771, 1981, 939, 2807, 2380, 1281], seed=1789, in_corpus="no"),
    "L-hien-02": dict(law=[2943, 2950], case=[1192, 446, 832, 124], seed=117, in_corpus="yes"),
    "L-hien-03": dict(law=[2953, 2968, 2950, 2933], case=[2599, 1696, 30], seed=534, in_corpus="yes"),
    "L-hien-04": dict(law=[2934, 2955, 2956], case=[180, 420, 154, 531], seed=663, in_corpus="partly"),
    "L-hien-05": dict(law=[2932], case=[112, 751, 1393, 1410], seed=262, in_corpus="yes"),
    "L-hien-06": dict(law=[], case=[2651, 1345, 202, 855, 369], seed=250, in_corpus="no"),
    "L-hien-07": dict(law=[2950, 2983], case=[1242, 2853, 1561, 1526], seed=490, in_corpus="yes"),
    "L-hien-08": dict(law=[2932, 2942, 2940], case=[1651, 2074, 2658, 1388], seed=1111, in_corpus="yes"),
    "L-hien-09": dict(law=[2950], case=[1962, 1976], seed=1584, in_corpus="partly"),
    "L-hien-10": dict(law=[2942, 2940, 2950], case=[864, 1350, 1397, 164, 363], seed=458, in_corpus="yes"),
    # ── Tamil ───────────────────────────────────────────────────────────────
    "L-ta-01": dict(law=[2930], case=[1902, 2064, 2569, 906, 1316], seed=380, in_corpus="yes"),
    "L-ta-02": dict(law=[2934, 2955, 2931], case=[1040, 2456, 1996, 131, 1534], seed=154, in_corpus="yes"),
    "L-ta-03": dict(law=[2957, 2930], case=[1321, 219, 1552, 2916], seed=2083, in_corpus="yes"),
    "L-ta-04": dict(law=[2958], case=[2809], seed=None, in_corpus="yes"),
    "L-ta-05": dict(law=[2950, 2942], case=[273], seed=None, in_corpus="partly"),
    "L-ta-06": dict(law=[2930, 2953, 2950, 2968], case=[1696, 2599, 534, 1825], seed=553, in_corpus="yes"),
    "L-ta-07": dict(law=[2953, 2930, 2950], case=[1027, 1313, 66, 58], seed=359, in_corpus="yes"),
    "L-ta-08": dict(law=[2941, 2950], case=[1309, 1132, 229, 1931, 2178], seed=None, in_corpus="yes"),
    "L-ta-09": dict(law=[2940, 2950, 2994], case=[2520, 1951, 944, 2261, 261, 1802], seed=95, in_corpus="yes"),
    "L-ta-10": dict(law=[2950], case=[607, 785, 2426, 2281], seed=675, in_corpus="partly"),
    # ── Kannada ─────────────────────────────────────────────────────────────
    "L-kn-01": dict(law=[2933, 2950], case=[2873, 2184, 1997, 1356, 162], seed=539, in_corpus="yes"),
    "L-kn-02": dict(law=[2950], case=[2268, 2806, 513, 1042, 407, 1107], seed=None, in_corpus="partly"),
    "L-kn-03": dict(law=[2957, 2930], case=[1530, 141, 1027, 2356, 2192], seed=2485, in_corpus="partly"),
    "L-kn-04": dict(law=[2934, 2931, 2955], case=[2423, 491, 263, 295], seed=857, in_corpus="yes"),
    "L-kn-05": dict(law=[2942, 2940], case=[870, 1866, 2785, 2074, 1651], seed=1834, in_corpus="yes"),
    "L-kn-06": dict(law=[2950, 2951, 2966], case=[1505, 675, 679, 652], seed=973, in_corpus="partly"),
    "L-kn-07": dict(law=[2950, 2930, 2933], case=[790, 306, 2841, 687, 159], seed=None, in_corpus="partly"),
    "L-kn-08": dict(law=[2938, 2962, 2959], case=[1720, 1084, 41], seed=186, in_corpus="yes"),
    "L-kn-09": dict(law=[2933, 2968, 2973], case=[1653, 2205, 844, 1960], seed=240, in_corpus="partly"),
    "L-kn-10": dict(law=[2953, 2975], case=[1664, 1565, 1759, 1847, 10], seed=150, in_corpus="yes"),
}

# Scenarios whose pooled candidates contained few relevant posts; the corpus may
# simply have little on the topic. Treat low recall on these with caution.
THIN_POOLS = {"P27", "L-hi-04", "L-hi-05", "L-ta-04", "L-ta-05", "L-hien-09", "L-en-06"}
