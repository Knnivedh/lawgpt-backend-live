"""
ANSWER VALIDATOR - Fact-checking and Hallucination Detection
Fixes: No validation, hallucinations, incorrect citations
"""

import re
from typing import Dict, List, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AnswerValidator:
    """
    Validates AI-generated answers for:
    1. Citation grounding (claims backed by sources)
    2. Legal accuracy (IPC sections, Acts exist)
    3. Hallucination detection
    4. Completeness checking
    """
    
    def __init__(self):
        """Initialize validator with known legal references"""
        
        # Known IPC sections (most common ones)
        self.valid_ipc_sections = set([
            '120B', '121', '124A', '153A', '153B', '161', '166', '167', '171', '172',
            '193', '201', '211', '279', '299', '300', '302', '304', '304A', '304B',
            '307', '308', '312', '313', '323', '324', '325', '326', '329', '331',
            '332', '333', '334', '341', '342', '354', '354A', '354B', '354C', '354D',
            '363', '364', '365', '366', '367', '370', '375', '376', '376A', '376AB',
            '376B', '376C', '376D', '376E', '377', '378', '379', '380', '381', '382',
            '383', '384', '385', '386', '387', '388', '389', '392', '393', '394',
            '395', '396', '397', '398', '399', '400', '401', '402', '403', '404',
            '405', '406', '407', '408', '409', '411', '412', '413', '414', '415',
            '416', '417', '418', '419', '420', '421', '422', '423', '424', '425',
            '426', '427', '428', '429', '430', '431', '432', '433', '435', '436',
            '437', '438', '441', '447', '448', '449', '450', '451', '452', '453',
            '454', '457', '458', '459', '460', '461', '462', '463', '464', '465',
            '466', '467', '468', '469', '470', '471', '472', '473', '474', '475',
            '476', '477', '477A', '489A', '489B', '489C', '489D', '489E', '493',
            '494', '495', '496', '497', '498', '498A', '499', '500', '501', '502',
            '503', '504', '505', '506', '507', '508', '509', '511'
        ])
        
        # Known Acts (major Indian laws)
        self.valid_acts = [
            'Indian Penal Code', 'IPC',
            'Code of Criminal Procedure', 'Criminal Procedure Code', 'CrPC',
            'Code of Civil Procedure', 'Civil Procedure Code', 'CPC',
            'Indian Evidence Act', 'IEA',
            'Constitution of India',
            'Hindu Marriage Act', 'Special Marriage Act',
            'Muslim Personal Law',
            'Indian Succession Act',
            'Transfer of Property Act',
            'Limitation Act',
            'Prevention of Corruption Act',
            'Domestic Violence Act',
            'Dowry Prohibition Act',
            'Information Technology Act', 'IT Act',
            'Right to Information Act', 'RTI Act',
            'Consumer Protection Act',
            'Companies Act',
            'Income Tax Act',
            'GST Act', 'Goods and Services Tax Act',
            'Labour Laws',
            'Factories Act',
            'Workmen Compensation Act',
            'Employees Provident Fund Act',
            'Trade Unions Act',
            'Industrial Disputes Act',
            'Maternity Benefit Act',
            'Payment of Wages Act',
            'Minimum Wages Act',
            'Contract Labour Act',
            'Sexual Harassment of Women Act', 'POSH Act',
            'POCSO Act', 'Protection of Children from Sexual Offences Act',
            'SC ST Prevention of Atrocities Act',
            'Juvenile Justice Act',
            'Motor Vehicles Act',
            'Arms Act',
            'NDPS Act', 'Narcotic Drugs and Psychotropic Substances Act',
            'Wildlife Protection Act',
            'Forest Conservation Act',
            'Environment Protection Act',
            'Water Act', 'Air Act',
            'Food Safety and Standards Act',
            'National Food Security Act',
            'Land Acquisition Act',
            'Urban Land Ceiling Act',
            'RERA', 'Real Estate Regulatory Act'
        ]
        
        # Constitutional Articles (1-395 range)
        self.valid_article_ranges = range(1, 396)
    
    def validate_ipc_sections(self, answer: str) -> Tuple[bool, List[str]]:
        """
        Validate all IPC sections mentioned in answer
        
        Args:
            answer: AI-generated answer
            
        Returns:
            Tuple of (all_valid, list_of_issues)
        """
        issues = []
        
        # Find all IPC section references
        ipc_pattern = r'IPC\s+(?:Section\s+)?(\d+[A-Z]{0,2})'
        matches = re.findall(ipc_pattern, answer, re.IGNORECASE)
        
        if not matches:
            return True, []  # No IPC sections to validate
        
        for section in matches:
            # Check if truncated (ends with ...)
            if '...' in section or len(section) < 2:
                issues.append(f"⚠️ Truncated IPC section: '{section}' - appears incomplete")
                continue
            
            # Check if in valid range
            section_num = re.sub(r'[A-Z]+', '', section)
            
            # IPC sections range from 1 to 511 + special sections
            try:
                num = int(section_num)
                if num > 511:
                    issues.append(f"⚠️ Invalid IPC section: {section} (out of range)")
            except ValueError:
                issues.append(f"⚠️ Malformed IPC section: {section}")
        
        all_valid = len(issues) == 0
        
        return all_valid, issues
    
    def validate_constitutional_articles(self, answer: str) -> Tuple[bool, List[str]]:
        """
        Validate Constitutional Articles
        
        Args:
            answer: AI-generated answer
            
        Returns:
            Tuple of (all_valid, list_of_issues)
        """
        issues = []
        
        # Find Article references
        article_pattern = r'Article\s+(\d+[A-Z]?)'
        matches = re.findall(article_pattern, answer, re.IGNORECASE)
        
        if not matches:
            return True, []
        
        for article in matches:
            article_num = int(re.sub(r'[A-Z]', '', article))
            
            if article_num not in self.valid_article_ranges:
                issues.append(f"⚠️ Invalid Article: {article} (Constitution has Articles 1-395)")
        
        all_valid = len(issues) == 0
        
        return all_valid, issues
    
    def validate_act_references(self, answer: str) -> Tuple[bool, List[str]]:
        """
        Validate Act references
        
        Args:
            answer: AI-generated answer
            
        Returns:
            Tuple of (all_valid, list_of_issues)
        """
        issues = []
        
        # Find Act references (Name + Act + Year)
        act_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+Act(?:,?\s+\d{4})?)'
        matches = re.findall(act_pattern, answer)
        
        if not matches:
            return True, []
        
        for act_mention in matches:
            # Check if it's a known Act (fuzzy match)
            is_valid = any(
                known_act.lower() in act_mention.lower() or
                act_mention.lower() in known_act.lower()
                for known_act in self.valid_acts
            )
            
            if not is_valid:
                # Could be a valid but lesser-known Act
                logger.warning(f"Unknown Act mentioned: {act_mention}")
        
        return True, issues  # Don't fail on unknown Acts (too many to enumerate)
    
    def check_citation_grounding(
        self,
        answer: str,
        retrieved_docs: List[Dict]
    ) -> Tuple[float, List[str]]:
        """
        Check if answer claims are grounded in retrieved documents
        
        Args:
            answer: AI-generated answer
            retrieved_docs: Documents used for generation
            
        Returns:
            Tuple of (grounding_score, list_of_issues)
        """
        issues = []
        
        # Extract claims that should be cited
        claim_patterns = [
            r'According to (?:Section|Article|Act|the law)',
            r'Under (?:Section|Article|IPC|CrPC|the)',
            r'The (?:Supreme Court|High Court) held',
            r'In (?:the case of|landmark case)',
        ]
        
        claims = []
        for pattern in claim_patterns:
            claims.extend(re.findall(f'{pattern}[^.]+\\.', answer, re.IGNORECASE))
        
        if not claims:
            # No explicit claims to check
            return 1.0, []
        
        # Check if each claim is grounded in sources
        grounded_count = 0
        
        for claim in claims:
            # Extract key terms from claim
            key_terms = re.findall(r'\b(?:Section|Article|IPC|CrPC)\s+\d+[A-Z]?', claim)
            key_terms += re.findall(r'([A-Z][a-z]+\s+Act(?:,?\s+\d{4})?)', claim)
            
            # Check if any retrieved doc contains these terms
            is_grounded = False
            
            for doc in retrieved_docs:
                doc_text = doc.get('text', '')
                
                # Check if claim terms appear in document
                if any(term.lower() in doc_text.lower() for term in key_terms):
                    is_grounded = True
                    break
            
            if is_grounded:
                grounded_count += 1
            else:
                issues.append(f"⚠️ Ungrounded claim: {claim[:100]}...")
        
        grounding_score = grounded_count / len(claims) if claims else 1.0
        
        return grounding_score, issues
    
    def detect_hallucinations(
        self,
        answer: str,
        retrieved_docs: List[Dict]
    ) -> Tuple[bool, List[str]]:
        """
        Detect potential hallucinations
        
        Args:
            answer: AI-generated answer
            retrieved_docs: Source documents
            
        Returns:
            Tuple of (has_hallucinations, list_of_hallucinations)
        """
        hallucinations = []
        
        # Check 1: IPC sections mentioned but not in sources
        ipc_in_answer = set(re.findall(r'IPC\s+(?:Section\s+)?(\d+[A-Z]{0,2})', answer, re.IGNORECASE))
        
        ipc_in_sources = set()
        for doc in retrieved_docs:
            ipc_in_sources.update(
                re.findall(r'IPC\s+(?:Section\s+)?(\d+[A-Z]{0,2})', doc.get('text', ''), re.IGNORECASE)
            )
        
        # Find IPC sections in answer but not in sources
        unsourced_ipc = ipc_in_answer - ipc_in_sources
        
        if unsourced_ipc:
            hallucinations.append(
                f"⚠️ IPC sections not found in sources: {', '.join(unsourced_ipc)}"
            )
        
        # Check 2: Case names mentioned but not in sources
        case_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+v\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        cases_in_answer = set(re.findall(case_pattern, answer))
        
        cases_in_sources = set()
        for doc in retrieved_docs:
            cases_in_sources.update(
                re.findall(case_pattern, doc.get('text', ''))
            )
        
        unsourced_cases = cases_in_answer - cases_in_sources
        
        if unsourced_cases:
            hallucinations.append(
                f"⚠️ Case names not found in sources: {len(unsourced_cases)} cases"
            )
        
        # Check 3: Specific numbers/dates not in sources (potential fabrication)
        # This is a heuristic - numbers in legal contexts should be verifiable
        
        has_hallucinations = len(hallucinations) > 0
        
        return has_hallucinations, hallucinations
    
    def check_answer_completeness(self, answer: str) -> Tuple[float, List[str]]:
        """
        Check if answer has all required components
        
        Args:
            answer: AI-generated answer
            
        Returns:
            Tuple of (completeness_score, list_of_missing_components)
        """
        missing = []
        score_components = []
        
        # Check for legal basis
        has_legal_basis = bool(
            re.search(r'(?:Section|Article|Act|IPC|CrPC|Constitution)', answer, re.IGNORECASE)
        )
        score_components.append(1.0 if has_legal_basis else 0.0)
        if not has_legal_basis:
            missing.append("Missing legal basis (no sections/articles cited)")
        
        # Check for explanation/reasoning
        has_explanation = len(answer) > 300  # Threshold for detailed explanation
        score_components.append(1.0 if has_explanation else 0.5)
        if not has_explanation:
            missing.append("Answer may be too brief (< 300 chars)")
        
        # Check for structure (headings, bullets, etc.)
        has_structure = bool(
            re.search(r'(?:\n\n|##|\*\*|• |a\)|b\)|c\))', answer)
        )
        score_components.append(1.0 if has_structure else 0.5)
        if not has_structure:
            missing.append("Lacks clear structure (no headings/bullets)")
        
        completeness_score = sum(score_components) / len(score_components)
        
        return completeness_score, missing
    
    def validate_answer(
        self,
        answer: str,
        retrieved_docs: List[Dict]
    ) -> Dict:
        """
        Complete validation of AI-generated answer
        
        Args:
            answer: AI-generated answer
            retrieved_docs: Source documents used
            
        Returns:
            Validation report with scores and issues
        """
        logger.info("Validating answer...")
        
        # Run all validation checks
        ipc_valid, ipc_issues = self.validate_ipc_sections(answer)
        article_valid, article_issues = self.validate_constitutional_articles(answer)
        act_valid, act_issues = self.validate_act_references(answer)
        
        grounding_score, grounding_issues = self.check_citation_grounding(answer, retrieved_docs)
        has_hallucinations, hallucination_issues = self.detect_hallucinations(answer, retrieved_docs)
        completeness_score, completeness_issues = self.check_answer_completeness(answer)
        
        # Compile all issues
        all_issues = (
            ipc_issues + 
            article_issues + 
            act_issues + 
            grounding_issues + 
            hallucination_issues + 
            completeness_issues
        )
        
        # Calculate overall validity score
        validity_components = [
            1.0 if ipc_valid else 0.5,
            1.0 if article_valid else 0.5,
            grounding_score,
            1.0 if not has_hallucinations else 0.3,
            completeness_score
        ]
        
        overall_score = sum(validity_components) / len(validity_components)
        
        # Determine if answer is acceptable
        is_valid = overall_score >= 0.7 and not has_hallucinations
        
        validation_report = {
            'is_valid': is_valid,
            'overall_score': overall_score,
            'scores': {
                'ipc_validation': 1.0 if ipc_valid else 0.5,
                'article_validation': 1.0 if article_valid else 0.5,
                'grounding_score': grounding_score,
                'hallucination_free': 1.0 if not has_hallucinations else 0.0,
                'completeness': completeness_score
            },
            'issues': all_issues,
            'has_hallucinations': has_hallucinations,
            'num_issues': len(all_issues)
        }
        
        if not is_valid:
            logger.warning(f"Answer validation failed! Score: {overall_score:.2f}, Issues: {len(all_issues)}")
        else:
            logger.info(f"✓ Answer validated successfully! Score: {overall_score:.2f}")
        
        return validation_report
    
    def get_validation_summary(self, validation_report: Dict) -> str:
        """
        Generate human-readable validation summary
        
        Args:
            validation_report: Report from validate_answer()
            
        Returns:
            Formatted summary string
        """
        summary = f"""
ANSWER VALIDATION REPORT:
{"="*60}
Overall Score: {validation_report['overall_score']:.2%}
Status: {'✓ VALID' if validation_report['is_valid'] else '✗ INVALID'}

Detailed Scores:
  - IPC Validation: {validation_report['scores']['ipc_validation']:.2%}
  - Article Validation: {validation_report['scores']['article_validation']:.2%}
  - Citation Grounding: {validation_report['scores']['grounding_score']:.2%}
  - Hallucination Check: {validation_report['scores']['hallucination_free']:.2%}
  - Completeness: {validation_report['scores']['completeness']:.2%}

Issues Found: {validation_report['num_issues']}
"""
        
        if validation_report['issues']:
            summary += "\nDetailed Issues:\n"
            for i, issue in enumerate(validation_report['issues'], 1):
                summary += f"{i}. {issue}\n"
        
        return summary


# Example usage
if __name__ == "__main__":
    validator = AnswerValidator()
    
    print("Answer Validator - Ready for integration")
    print("\nKey Features:")
    print("✓ IPC section validation")
    print("✓ Constitutional Article validation")
    print("✓ Citation grounding check")
    print("✓ Hallucination detection")
    print("✓ Completeness verification")

