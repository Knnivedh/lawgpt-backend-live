# COMPLEQA Live Test Report

- Total scenarios: 15
- Successful: 14
- Failed: 1
- Avg latency: 20.04s
- Avg subquestion coverage: 1.000
- Avg answer contract score: 0.833
- Language mismatch rate: 0.000

## Query Types

- academic_direct: 14

## Per Scenario

### Q1 - CRIMINAL LAW + EVIDENCE + CONSTITUTIONAL LAW

- status: None
- latency_s: 185.44
- query_type: error
- subquestion_coverage: 0/5 (0.00)
- contract_score: 0.00
- language_mismatch: False
- answer_len: 0
- error: HTTPSConnectionPool(host='lawgpt-backend2024.azurewebsites.net', port=443): Read timed out. (read timeout=180)
- missing_subquestions:
  - Does narco-analysis violate the right against self-incrimination under Article 20(3)?
  - What procedural safeguards govern a Section 164 statement and when is it rendered inadmissible?
  - Is evidence obtained from a warrantless phone seizure and mirroring admissible under current Indian law?
  - What is the legal standard for a valid Test Identification Parade and how does delay affect its probative value?
  - Can a conviction be sustained if multiple pieces of key evidence are found inadmissible?

### Q2 - FAMILY LAW + CONSTITUTIONAL LAW + SUCCESSION

- status: 200
- latency_s: 5.85
- query_type: academic_direct
- subquestion_coverage: 5/5 (1.00)
- contract_score: 0.83
- language_mismatch: False
- answer_len: 2211

### Q3 - ENVIRONMENTAL LAW + CONSTITUTIONAL LAW + TORT

- status: 200
- latency_s: 14.40
- query_type: academic_direct
- subquestion_coverage: 5/5 (1.00)
- contract_score: 0.83
- language_mismatch: False
- answer_len: 1959

### Q4 - COMPANY LAW + INSOLVENCY + FRAUD

- status: 200
- latency_s: 10.54
- query_type: academic_direct
- subquestion_coverage: 5/5 (1.00)
- contract_score: 0.83
- language_mismatch: False
- answer_len: 1843

### Q5 - INTELLECTUAL PROPERTY + COMPETITION LAW + CONTRACTS

- status: 200
- latency_s: 19.05
- query_type: academic_direct
- subquestion_coverage: 5/5 (1.00)
- contract_score: 0.83
- language_mismatch: False
- answer_len: 2209

### Q6 - LABOUR LAW + CONSTITUTIONAL LAW + GIGS

- status: 200
- latency_s: 18.89
- query_type: academic_direct
- subquestion_coverage: 5/5 (1.00)
- contract_score: 0.83
- language_mismatch: False
- answer_len: 2097

### Q7 - BANKING LAW + FRAUD + CONSTITUTIONAL LAW

- status: 200
- latency_s: 23.95
- query_type: academic_direct
- subquestion_coverage: 5/5 (1.00)
- contract_score: 0.83
- language_mismatch: False
- answer_len: 2164

### Q8 - CRIMINAL LAW + MEDIA LAW + CONSTITUTIONAL LAW

- status: 200
- latency_s: 19.28
- query_type: academic_direct
- subquestion_coverage: 5/5 (1.00)
- contract_score: 0.83
- language_mismatch: False
- answer_len: 2413

### Q9 - PROPERTY LAW + LAND ACQUISITION + CONSTITUTIONAL LAW

- status: 200
- latency_s: 14.27
- query_type: academic_direct
- subquestion_coverage: 5/5 (1.00)
- contract_score: 0.83
- language_mismatch: False
- answer_len: 2076

### Q10 - TAX LAW + CONSTITUTIONAL LAW + INTERNATIONAL LAW

- status: 200
- latency_s: 19.70
- query_type: academic_direct
- subquestion_coverage: 5/5 (1.00)
- contract_score: 0.83
- language_mismatch: False
- answer_len: 2162

### Q11 - ELECTION LAW + CONSTITUTIONAL LAW + CONTEMPT

- status: 200
- latency_s: 32.92
- query_type: academic_direct
- subquestion_coverage: 5/5 (1.00)
- contract_score: 0.83
- language_mismatch: False
- answer_len: 2367

### Q12 - MEDICAL LAW + CONSUMER LAW + CRIMINAL LAW

- status: 200
- latency_s: 48.96
- query_type: academic_direct
- subquestion_coverage: 5/5 (1.00)
- contract_score: 0.83
- language_mismatch: False
- answer_len: 2451

### Q13 - ADMINISTRATIVE LAW + SERVICE LAW + CONSTITUTIONAL LAW

- status: 200
- latency_s: 20.74
- query_type: academic_direct
- subquestion_coverage: 5/5 (1.00)
- contract_score: 0.83
- language_mismatch: False
- answer_len: 2229

### Q14 - INTERNET LAW + DEFAMATION + FREE SPEECH

- status: 200
- latency_s: 20.05
- query_type: academic_direct
- subquestion_coverage: 5/5 (1.00)
- contract_score: 0.83
- language_mismatch: False
- answer_len: 2265

### Q15 - INTERNATIONAL LAW + EXTRADITION + FUNDAMENTAL RIGHTS

- status: 200
- latency_s: 11.91
- query_type: academic_direct
- subquestion_coverage: 5/5 (1.00)
- contract_score: 0.83
- language_mismatch: False
- answer_len: 2249
