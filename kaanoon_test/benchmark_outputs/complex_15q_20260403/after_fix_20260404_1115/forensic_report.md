# Post-Deploy Forensic Report

- Total scenarios: 15
- Pass count: 12
- Fail count: 3
- Pass rate: 80.00%
- Avg latency: 8.92s
- High hallucination-risk responses: 1
- Missing BNS/BNSS framing (targeted criminal set): 1
- Missing sedition current-position marker: 0
- Missing electoral-bond current-position marker: 1
- Weak explicit sub-question structure (<4 headings): 0

## Per Scenario

### Q1 - CRIMINAL LAW + EVIDENCE + CONSTITUTIONAL LAW
- status: 200
- query_type: academic_direct
- latency_s: 22.72
- unsupported_case_citations: 1
- high_hallucination_risk: True
- answer_downgraded: True
- subq_heading_count: 5
- has_bns_or_bnss: True
- has_vombatkere_or_stay: True
- has_electoral_bond_struck_down_marker: False
- hard_fail_reasons: unsupported_case_citation_risk

### Q2 - FAMILY LAW + CONSTITUTIONAL LAW + SUCCESSION
- status: 200
- query_type: academic_direct
- latency_s: 9.68
- unsupported_case_citations: 0
- high_hallucination_risk: False
- answer_downgraded: False
- subq_heading_count: 5
- has_bns_or_bnss: True
- has_vombatkere_or_stay: False
- has_electoral_bond_struck_down_marker: True
- hard_fail_reasons: none

### Q3 - ENVIRONMENTAL LAW + CONSTITUTIONAL LAW + TORT
- status: 200
- query_type: academic_direct
- latency_s: 12.76
- unsupported_case_citations: 0
- high_hallucination_risk: False
- answer_downgraded: False
- subq_heading_count: 5
- has_bns_or_bnss: False
- has_vombatkere_or_stay: False
- has_electoral_bond_struck_down_marker: False
- hard_fail_reasons: none

### Q4 - COMPANY LAW + INSOLVENCY + FRAUD
- status: 200
- query_type: academic_direct
- latency_s: 11.15
- unsupported_case_citations: 0
- high_hallucination_risk: False
- answer_downgraded: False
- subq_heading_count: 5
- has_bns_or_bnss: False
- has_vombatkere_or_stay: False
- has_electoral_bond_struck_down_marker: False
- hard_fail_reasons: none

### Q5 - INTELLECTUAL PROPERTY + COMPETITION LAW + CONTRACTS
- status: 200
- query_type: academic_direct
- latency_s: 9.51
- unsupported_case_citations: 0
- high_hallucination_risk: False
- answer_downgraded: False
- subq_heading_count: 5
- has_bns_or_bnss: False
- has_vombatkere_or_stay: False
- has_electoral_bond_struck_down_marker: False
- hard_fail_reasons: none

### Q6 - LABOUR LAW + CONSTITUTIONAL LAW + GIGS
- status: 200
- query_type: academic_direct
- latency_s: 9.53
- unsupported_case_citations: 0
- high_hallucination_risk: False
- answer_downgraded: False
- subq_heading_count: 5
- has_bns_or_bnss: False
- has_vombatkere_or_stay: False
- has_electoral_bond_struck_down_marker: False
- hard_fail_reasons: none

### Q7 - BANKING LAW + FRAUD + CONSTITUTIONAL LAW
- status: 200
- query_type: academic_direct
- latency_s: 12.29
- unsupported_case_citations: 0
- high_hallucination_risk: False
- answer_downgraded: False
- subq_heading_count: 5
- has_bns_or_bnss: False
- has_vombatkere_or_stay: False
- has_electoral_bond_struck_down_marker: True
- hard_fail_reasons: none

### Q8 - CRIMINAL LAW + MEDIA LAW + CONSTITUTIONAL LAW
- status: 200
- query_type: academic_direct
- latency_s: 10.85
- unsupported_case_citations: 0
- high_hallucination_risk: False
- answer_downgraded: False
- subq_heading_count: 5
- has_bns_or_bnss: True
- has_vombatkere_or_stay: True
- has_electoral_bond_struck_down_marker: True
- hard_fail_reasons: none

### Q9 - PROPERTY LAW + LAND ACQUISITION + CONSTITUTIONAL LAW
- status: 200
- query_type: academic_direct
- latency_s: 10.85
- unsupported_case_citations: 0
- high_hallucination_risk: False
- answer_downgraded: False
- subq_heading_count: 5
- has_bns_or_bnss: False
- has_vombatkere_or_stay: False
- has_electoral_bond_struck_down_marker: False
- hard_fail_reasons: none

### Q10 - TAX LAW + CONSTITUTIONAL LAW + INTERNATIONAL LAW
- status: 200
- query_type: academic_direct
- latency_s: 11.87
- unsupported_case_citations: 0
- high_hallucination_risk: False
- answer_downgraded: False
- subq_heading_count: 5
- has_bns_or_bnss: False
- has_vombatkere_or_stay: False
- has_electoral_bond_struck_down_marker: False
- hard_fail_reasons: none

### Q11 - ELECTION LAW + CONSTITUTIONAL LAW + CONTEMPT
- status: 200
- query_type: academic_direct
- latency_s: 2.57
- unsupported_case_citations: 0
- high_hallucination_risk: False
- answer_downgraded: False
- subq_heading_count: 5
- has_bns_or_bnss: False
- has_vombatkere_or_stay: False
- has_electoral_bond_struck_down_marker: False
- hard_fail_reasons: missing_electoral_bond_current_position

### Q12 - MEDICAL LAW + CONSUMER LAW + CRIMINAL LAW
- status: 200
- query_type: academic_direct
- latency_s: 2.04
- unsupported_case_citations: 0
- high_hallucination_risk: False
- answer_downgraded: False
- subq_heading_count: 5
- has_bns_or_bnss: False
- has_vombatkere_or_stay: False
- has_electoral_bond_struck_down_marker: False
- hard_fail_reasons: missing_bns_bnss_framing

### Q13 - ADMINISTRATIVE LAW + SERVICE LAW + CONSTITUTIONAL LAW
- status: 200
- query_type: academic_direct
- latency_s: 2.24
- unsupported_case_citations: 0
- high_hallucination_risk: False
- answer_downgraded: False
- subq_heading_count: 5
- has_bns_or_bnss: False
- has_vombatkere_or_stay: True
- has_electoral_bond_struck_down_marker: False
- hard_fail_reasons: none

### Q14 - INTERNET LAW + DEFAMATION + FREE SPEECH
- status: 200
- query_type: academic_direct
- latency_s: 2.15
- unsupported_case_citations: 0
- high_hallucination_risk: False
- answer_downgraded: False
- subq_heading_count: 5
- has_bns_or_bnss: False
- has_vombatkere_or_stay: False
- has_electoral_bond_struck_down_marker: False
- hard_fail_reasons: none

### Q15 - INTERNATIONAL LAW + EXTRADITION + FUNDAMENTAL RIGHTS
- status: 200
- query_type: academic_direct
- latency_s: 3.58
- unsupported_case_citations: 0
- high_hallucination_risk: False
- answer_downgraded: False
- subq_heading_count: 5
- has_bns_or_bnss: False
- has_vombatkere_or_stay: False
- has_electoral_bond_struck_down_marker: False
- hard_fail_reasons: none
