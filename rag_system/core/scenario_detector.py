"""
Scenario Detector - Enhanced Query Understanding for Legal Scenarios
Detects specific legal scenarios and triggers appropriate retrieval strategies
"""

import re
from typing import Dict, List, Any, Optional


class ScenarioDetector:
    """Detects legal scenario type and triggers appropriate retrieval strategy"""
    
    SCENARIO_PATTERNS = {
        'law_transition': {
            'keywords': ['IPC replaced', 'BNS', 'new law', 'law changed', 'transition',
                         'old law', 'which law applies', 'IPC to BNS', 'law change',
                         'still under IPC', 'BNS now', 'CrPC to BNSS'],
            'trigger_retrieval': ['Section 534 BNS', 'saved proceedings', 'transition rules',
                                  'IPC BNS mapping', 'retrospective effect', 'law applicability'],
            'mandatory_statutes': ['Section 534 BNS', 'transition rules']
        },
        'domestic_violence': {
            'keywords': ['domestic violence', 'DV', 'abuse', 'PWDVA', 'left husband',
                         'violence at home', 'husband beating', 'marital abuse',
                         'physical abuse', 'mental harassment husband', 'cruelty'],
            'trigger_retrieval': ['PWDVA 2005', 'Protection order', 'Residence rights',
                                  'Monetary relief PWDVA', 'Section 125 CrPC',
                                  'BNSS 128 maintenance'],
            'mandatory_statutes': ['PWDVA', 'Section 125 CrPC', 'BNSS 128']
        },
        'adverse_possession': {
            'keywords': ['adverse possession', 'claiming land', 'occupied land',
                         'using property without permission', 'possession for years',
                         'neighbor using land', 'encroachment claims ownership'],
            'trigger_retrieval': ['Limitation Act Article 65', '12 year possession',
                                  'adverse possession requirements', 'hostile possession',
                                  'continuous possession'],
            'requires_calculation': True
        },
        'consumer_complaint': {
            'keywords': ['defective product', 'warranty issue', 'seller manufacturer',
                         'consumer complaint', 'online marketplace', 'product defect',
                         'warranty denied', 'refund refused', 'replacement denied',
                         'e-commerce not responding'],
            'trigger_retrieval': ['Consumer Protection Act 2019', 'District Consumer Forum',
                                  'jurisdiction by value', 'e-commerce liability',
                                  'compensation quantum', 'E-Daakhil'],
            'extract_amount': True
        },
        'rti_rejection': {
            'keywords': ['RTI rejected', 'information denied', 'RTI application',
                         'public information', 'transparency', 'freedom of information',
                         'government information refused'],
            'trigger_retrieval': ['RTI Act 2005', 'Section 8 exemptions', 'Section 8(2) public interest',
                                  'First Appellate Authority', 'Information Commission'],
            'mandatory_statutes': ['Section 8 RTI', 'Section 19 RTI']
        },
        'maintenance_family': {
            'keywords': ['maintenance', 'alimony', 'wife support', 'child support',
                         'Section 125', 'BNSS 128', 'unable to maintain',
                         'divorce maintenance', 'interim maintenance'],
            'trigger_retrieval': ['Section 125 CrPC', 'BNSS 128', 'maintenance quantum',
                                  'interim maintenance', 'factors for maintenance'],
            'extract_income': True
        },
        'labour_termination': {
            'keywords': ['terminated', 'termination', 'fired', 'dismissed', 'notice period',
                         'wrongful termination', 'illegal termination', 'retrenchment'],
            'trigger_retrieval': ['Industrial Disputes Act', 'wrongful termination',
                                  'notice period violation', 'Labour Court', 'back wages'],
            'requires_calculation': True  # For notice period calculations
        },
        'cyber_crime': {
            'keywords': ['fake account', 'morphed images', 'cyber crime', 'online defamation',
                         'hacking', 'identity theft', 'privacy violation', 'data breach',
                         'WhatsApp fraud'],
            'trigger_retrieval': ['IT Act 2000', 'Section 66C identity theft', 'Section 66E privacy',
                                  'Section 67 obscene content', 'cyber crime police', 'BNS defamation'],
            'mandatory_statutes': ['IT Act 2000']
        }
    }
    
    def __init__(self):
        self.detected_scenarios = []
    
    def detect_scenario(self, query: str) -> Dict[str, Any]:
        """
        Detect legal scenario and return enhanced retrieval strategy
        
        Args:
            query: User's legal query
            
        Returns:
            Dict with detected scenarios and enhanced query
        """
        query_lower = query.lower()
        detected_scenarios = []
        
        for scenario, config in self.SCENARIO_PATTERNS.items():
            # Check if any keyword matches
            matched_keywords = [kw for kw in config['keywords'] if kw.lower() in query_lower]
            
            if matched_keywords:
                scenario_info = {
                    'type': scenario,
                    'matched_keywords': matched_keywords,
                    'retrieval_strategy': config['trigger_retrieval'],
                    'requires_calculation': config.get('requires_calculation', False),
                    'mandatory_statutes': config.get('mandatory_statutes', []),
                    'extract_amount': config.get('extract_amount', False),
                    'extract_income': config.get('extract_income', False)
                }
                detected_scenarios.append(scenario_info)
        
        # Build enhanced query
        enhanced_query = self._build_enhanced_query(query, detected_scenarios)
        
        # Extract numerical data if needed
        extracted_data = self._extract_numerical_data(query, detected_scenarios)
        
        return {
            'scenarios': detected_scenarios,
            'enhanced_query': enhanced_query,
            'extracted_data': extracted_data,
            'has_scenarios': len(detected_scenarios) > 0
        }
    
    def _build_enhanced_query(self, original_query: str, scenarios: List[Dict]) -> str:
        """
        Build enhanced query with scenario-specific terms
        """
        if not scenarios:
            return original_query
        
        enhanced_terms = set()
        for scenario in scenarios:
            enhanced_terms.update(scenario['retrieval_strategy'])
        
        # Add enhanced terms to query for better retrieval
        enhanced = f"{original_query} {' '.join(list(enhanced_terms)[:10])}"
        return enhanced
    
    def _extract_numerical_data(self, query: str, scenarios: List[Dict]) -> Dict[str, Any]:
        """
        Extract numerical data like years, amounts, income from query
        """
        data = {}
        
        # Extract years for timeline calculations
        if any(s.get('requires_calculation') for s in scenarios):
            years = re.findall(r'\b(19|20)\d{2}\b', query)
            if years:
                data['years'] = [int(y) for y in years]
                if len(years) >= 2:
                    data['year_range'] = (min(map(int, years)), max(map(int, years)))
                    data['duration_years'] = max(map(int, years)) - min(map(int, years))
        
        # Extract monetary amounts (₹ or Rs.)
        if any(s.get('extract_amount') or s.get('extract_income') for s in scenarios):
            # Pattern for Indian currency amounts
            amount_patterns = [
                r'₹\s*([0-9,]+(?:\.\d{2})?)',  # ₹65,000
                r'Rs\.?\s*([0-9,]+(?:\.\d{2})?)',  # Rs. 65000
                r'(?:INR|rupees)\s*([0-9,]+(?:\.\d{2})?)'  # INR 65000
            ]
            
            amounts = []
            for pattern in amount_patterns:
                matches = re.findall(pattern, query)
                amounts.extend([float(m.replace(',', '')) for m in matches])
            
            if amounts:
                data['amounts'] = amounts
                data['primary_amount'] = max(amounts)  # Assume largest is primary
        
        # Extract time periods (months, days)
        time_patterns = {
            'months': r'(\d+)\s*months?',
            'days': r'(\d+)\s*days?',
            'years_text': r'(\d+)\s*years?'
        }
        
        for key, pattern in time_patterns.items():
            matches = re.findall(pattern, query.lower())
            if matches:
                data[key] = [int(m) for m in matches]
        
        return data
    
    def get_scenario_specific_prompt(self, scenario_type: str) -> str:
        """
        Get scenario-specific instructions for the LLM
        """
        prompt_instructions = {
            'law_transition': """
CRITICAL: This is a LAW TRANSITION query.
MANDATORY: You MUST explain which law applies (old vs new law).
Include: Section 534 BNS saved proceedings clause.
Explain: Cases filed before July 1, 2024 continue under IPC.
Provide: IPC to BNS section mapping if applicable.
""",
            'domestic_violence': """
CRITICAL: This is a DOMESTIC VIOLENCE case.
MANDATORY: You MUST mention PWDVA 2005 as PRIMARY remedy.
Include: All PWDVA remedies (Protection Order, Residence Order, Monetary Relief, Custody).
Also mention: Section 125 CrPC/BNSS 128 can be filed SIMULTANEOUSLY.
Emphasize: PWDVA is faster (60 days) and provides more comprehensive protection.
""",
            'adverse_possession': """
CRITICAL: This requires TIMELINE CALCULATION.
MANDATORY: Calculate exact duration of possession in years.
Compare: Duration vs 12-year requirement (Limitation Act Article 65).
Conclude: Based on mathematical comparison, not general statements.
If duration > 12 years: Adverse possession claim LIKELY VALID.
If duration < 12 years: Claim NOT valid, owner can still recover.
""",
            'consumer_complaint': """
CRITICAL: This is a CONSUMER COMPLAINT.
MANDATORY: Specify EXACT jurisdiction (District Forum for up to ₹1 crore).
Include: Specific compensation quantum (refund amount + ₹X to ₹Y mental agony).
Mention: E-commerce platform liability (Section 2(16) - jointly liable).
Provide: Timeline (2 years to file, E-Daakhil online option).
""",
            'rti_rejection': """
CRITICAL: This is RTI REJECTION case.
MANDATORY: Identify specific exemption cited (Section 8(1) sub-clauses).
Explain: Public interest test (Section 8(2)) overrides exemptions.
Provide: Appeal procedure (First Appellate Authority 30 days, then IC 90 days).
""",
        }
        
        return prompt_instructions.get(scenario_type, "")
    
    def validate_response_completeness(self, scenario_type: str, response: str) -> Dict[str, Any]:
        """
        Validate if the response addresses all required elements for the scenario
        """
        validation = {
            'complete': True,
            'missing_elements': [],
            'suggestions': []
        }
        
        response_lower = response.lower()
        
        # Scenario-specific checks
        if scenario_type == 'law_transition':
            if 'section 534' not in response_lower and 'saved proceedings' not in response_lower:
                validation['complete'] = False
                validation['missing_elements'].append('Section 534 BNS transition rule')
        
        if scenario_type == 'domestic_violence':
            if 'pwdva' not in response_lower and 'protection of women' not in response_lower:
                validation['complete'] = False
                validation['missing_elements'].append('PWDVA 2005 (primary DV remedy)')
        
        if scenario_type == 'adverse_possession':
            if '12' not in response and 'twelve' not in response_lower:
                validation['complete'] = False
                validation['missing_elements'].append('12-year requirement for adverse possession')
        
        if scenario_type == 'consumer_complaint':
            if 'district consumer' not in response_lower and 'district forum' not in response_lower:
                validation['complete'] = False
                validation['missing_elements'].append('Specific forum (District Consumer Forum)')
        
        return validation


# Singleton instance
_detector = None

def get_scenario_detector() -> ScenarioDetector:
    """Get singleton instance of ScenarioDetector"""
    global _detector
    if _detector is None:
        _detector = ScenarioDetector()
    return _detector
