"""
LEGAL REASONING AGENT - Step-by-Step Legal Analysis
Performs structured legal reasoning: issue identification, statutory analysis, 
precedent research, application, exception analysis, and conclusion
"""

import re
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class LegalReasoningAgent:
    """
    Specialized agent for step-by-step legal reasoning
    
    Reasoning Steps:
    1. Issue Identification: Extract precise legal questions
    2. Statutory Analysis: Identify applicable laws, sections, rules
    3. Precedent Research: Find relevant case law from retrieved documents
    4. Application: Apply law to facts
    5. Exception Analysis: Consider exceptions, limitations, defenses
    6. Conclusion: Synthesize comprehensive answer
    """
    
    def __init__(self):
        """Initialize legal reasoning agent"""
        # Legal domain keywords
        self.legal_domains = {
            'criminal': ['ipc', 'crpc', 'criminal', 'murder', 'theft', 'fraud', 'bail', 'arrest'],
            'civil': ['cpc', 'civil', 'property', 'contract', 'tort', 'damages'],
            'constitutional': ['constitution', 'article', 'fundamental right', 'writ'],
            'property': ['property', 'transfer', 'sale', 'lease', 'possession', 'ownership'],
            'family': ['divorce', 'marriage', 'custody', 'maintenance', 'succession'],
            'commercial': ['company', 'contract', 'negotiable', 'arbitration'],
            'tax': ['tax', 'gst', 'income tax', 'assessment'],
            'labour': ['labour', 'employment', 'wages', 'industrial'],
        }
        
        # IPC section patterns
        self.ipc_pattern = r'(?:IPC|Indian Penal Code).*?Section\s*(\d+[a-z]?)'
        self.section_pattern = r'Section\s*(\d+[a-z]?)'
        
        # Case citation patterns
        self.case_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+v\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\((\d{4})\)'
    
    def analyze_legal_issue(
        self,
        query: str,
        context: List[Dict],
        query_analysis: Optional[Dict] = None
    ) -> Dict:
        """
        Perform comprehensive legal reasoning analysis
        
        Args:
            query: User's legal question
            context: Retrieved legal documents
            query_analysis: Query analysis metadata
            
        Returns:
            Dictionary with reasoning steps
        """
        reasoning = {
            'issues': self._extract_legal_issues(query, query_analysis),
            'statutes': self._identify_statutes(query, context),
            'precedents': self._find_precedents(context),
            'application': self._apply_law_to_facts(query, context),
            'exceptions': self._identify_exceptions(context),
            'conclusion': None  # Will be synthesized after all steps
        }
        
        # Synthesize conclusion
        reasoning['conclusion'] = self._synthesize_conclusion(reasoning)
        
        return reasoning
    
    def _extract_legal_issues(self, query: str, query_analysis: Optional[Dict] = None) -> List[str]:
        """Extract precise legal issues from query"""
        issues = []
        
        # Check if query analysis provides sub-questions
        if query_analysis and query_analysis.get('sub_questions'):
            issues.extend(query_analysis['sub_questions'])
        
        # Extract main issue
        query_lower = query.lower()
        
        # Detect question type
        if '?' in query:
            # Extract question part
            question_part = query.split('?')[0]
            issues.append(question_part.strip())
        
        # Detect multiple questions
        question_markers = ['?', 'what', 'how', 'when', 'where', 'why', 'can', 'should']
        question_count = sum(1 for marker in question_markers if marker in query_lower)
        
        if question_count > 1:
            # Try to split into sub-issues
            parts = re.split(r'[?\.]', query)
            issues.extend([p.strip() for p in parts if len(p.strip()) > 10])
        
        # If no issues found, use the whole query
        if not issues:
            issues.append(query)
        
        return issues[:5]  # Limit to top 5 issues
    
    def _identify_statutes(self, query: str, context: List[Dict]) -> Dict[str, List[str]]:
        """Identify applicable statutes, sections, and rules"""
        statutes = {
            'ipc_sections': [],
            'cpc_sections': [],
            'crpc_sections': [],
            'articles': [],
            'acts': [],
            'orders': [],
            'rules': []
        }
        
        # Extract from query
        combined_text = query + " " + " ".join([str(d.get('text', '')) for d in context[:5]])
        
        # IPC sections
        ipc_matches = re.findall(self.ipc_pattern, combined_text, re.IGNORECASE)
        statutes['ipc_sections'] = list(set(ipc_matches))
        
        # General sections (could be IPC, CPC, CrPC)
        section_matches = re.findall(self.section_pattern, combined_text, re.IGNORECASE)
        
        # CPC sections/orders/rules
        cpc_pattern = r'(?:CPC|Civil Procedure Code).*?(?:Section|Order|Rule)\s*(\d+[a-z]?)'
        cpc_matches = re.findall(cpc_pattern, combined_text, re.IGNORECASE)
        statutes['cpc_sections'] = list(set(cpc_matches))
        
        # CrPC sections
        crpc_pattern = r'(?:CrPC|Criminal Procedure Code).*?Section\s*(\d+[a-z]?)'
        crpc_matches = re.findall(crpc_pattern, combined_text, re.IGNORECASE)
        statutes['crpc_sections'] = list(set(crpc_matches))
        
        # Constitutional Articles
        article_pattern = r'Article\s*(\d+[a-z]?)'
        article_matches = re.findall(article_pattern, combined_text, re.IGNORECASE)
        statutes['articles'] = list(set(article_matches))
        
        # Acts
        act_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Act(?:\s+\d{4})?'
        act_matches = re.findall(act_pattern, combined_text)
        statutes['acts'] = list(set(act_matches))
        
        # Orders
        order_pattern = r'Order\s*(\d+[a-z]?)'
        order_matches = re.findall(order_pattern, combined_text, re.IGNORECASE)
        statutes['orders'] = list(set(order_matches))
        
        # Rules
        rule_pattern = r'Rule\s*(\d+[a-z]?)'
        rule_matches = re.findall(rule_pattern, combined_text, re.IGNORECASE)
        statutes['rules'] = list(set(rule_matches))
        
        return statutes
    
    def _find_precedents(self, context: List[Dict]) -> List[Dict]:
        """Find relevant case law and precedents from context"""
        precedents = []
        
        for doc in context:
            text = str(doc.get('text', doc.get('document', '')))
            metadata = doc.get('metadata', {})
            
            # Extract case citations
            case_matches = re.findall(self.case_pattern, text)
            
            for match in case_matches:
                petitioner, respondent, year = match
                case_name = f"{petitioner} v. {respondent}"
                
                # Check if already added
                if not any(p['case_name'] == case_name and p['year'] == year for p in precedents):
                    precedents.append({
                        'case_name': case_name,
                        'petitioner': petitioner,
                        'respondent': respondent,
                        'year': year,
                        'source': metadata.get('source', 'Unknown'),
                        'relevance_score': doc.get('score', 0)
                    })
            
            # Check metadata for case information
            if 'case_name' in metadata or 'court' in metadata:
                precedents.append({
                    'case_name': metadata.get('case_name', 'Unknown'),
                    'court': metadata.get('court', 'Unknown'),
                    'year': metadata.get('year', 'Unknown'),
                    'source': metadata.get('source', 'Unknown'),
                    'relevance_score': doc.get('score', 0)
                })
        
        # Sort by relevance score
        precedents.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return precedents[:10]  # Top 10 precedents
    
    def _apply_law_to_facts(self, query: str, context: List[Dict]) -> Dict:
        """Apply legal principles to the facts of the query"""
        application = {
            'legal_principles': [],
            'factual_elements': [],
            'application_steps': []
        }
        
        # Extract factual elements from query
        factual_keywords = ['when', 'where', 'who', 'what happened', 'if', 'after', 'before']
        for keyword in factual_keywords:
            if keyword in query.lower():
                # Extract sentence containing keyword
                sentences = re.split(r'[.!?]', query)
                for sentence in sentences:
                    if keyword in sentence.lower():
                        application['factual_elements'].append(sentence.strip())
        
        # Extract legal principles from context
        for doc in context[:5]:
            text = str(doc.get('text', ''))
            
            # Look for legal principles (statements about law)
            principle_indicators = [
                'according to', 'as per', 'under section', 'the law states',
                'it is established', 'the court held', 'the principle is'
            ]
            
            for indicator in principle_indicators:
                if indicator in text.lower():
                    # Extract sentence
                    sentences = re.split(r'[.!?]', text)
                    for sentence in sentences:
                        if indicator in sentence.lower() and len(sentence) > 30:
                            application['legal_principles'].append(sentence.strip()[:200])
                            break
        
        # Create application steps
        if application['factual_elements'] and application['legal_principles']:
            application['application_steps'] = [
                f"Step 1: Identify the legal issue: {application['factual_elements'][0] if application['factual_elements'] else 'Issue to be determined'}",
                f"Step 2: Apply relevant legal principle: {application['legal_principles'][0] if application['legal_principles'] else 'Principle to be applied'}",
                "Step 3: Analyze how the law applies to these facts",
                "Step 4: Consider any exceptions or defenses",
                "Step 5: Reach a conclusion"
            ]
        
        return application
    
    def _identify_exceptions(self, context: List[Dict]) -> List[str]:
        """Identify exceptions, limitations, and defenses"""
        exceptions = []
        
        exception_keywords = [
            'exception', 'except', 'however', 'but', 'unless', 'provided that',
            'limitation', 'defense', 'defence', 'exemption', 'excluded'
        ]
        
        for doc in context[:5]:
            text = str(doc.get('text', ''))
            
            for keyword in exception_keywords:
                if keyword in text.lower():
                    # Extract sentences containing exceptions
                    sentences = re.split(r'[.!?]', text)
                    for sentence in sentences:
                        if keyword in sentence.lower() and len(sentence) > 20:
                            exceptions.append(sentence.strip()[:300])
                            break
        
        return list(set(exceptions))[:5]  # Top 5 unique exceptions
    
    def _synthesize_conclusion(self, reasoning: Dict) -> str:
        """Synthesize comprehensive conclusion from all reasoning steps"""
        conclusion_parts = []
        
        # Summary of issues
        if reasoning['issues']:
            conclusion_parts.append(f"Issues Identified: {len(reasoning['issues'])} legal issue(s)")
        
        # Key statutes
        total_statutes = sum(len(v) for v in reasoning['statutes'].values() if isinstance(v, list))
        if total_statutes > 0:
            conclusion_parts.append(f"Applicable Laws: {total_statutes} statutory provision(s) identified")
        
        # Precedents
        if reasoning['precedents']:
            conclusion_parts.append(f"Relevant Precedents: {len(reasoning['precedents'])} case(s) found")
        
        # Exceptions
        if reasoning['exceptions']:
            conclusion_parts.append(f"Exceptions/Limitations: {len(reasoning['exceptions'])} identified")
        
        conclusion = "Legal Reasoning Summary: " + "; ".join(conclusion_parts)
        
        return conclusion
    
    def format_reasoning_for_prompt(self, reasoning: Dict) -> str:
        """Format reasoning analysis for inclusion in LLM prompt"""
        formatted = "LEGAL REASONING ANALYSIS:\n\n"
        
        # Issues
        if reasoning['issues']:
            formatted += "ISSUES IDENTIFIED:\n"
            for i, issue in enumerate(reasoning['issues'], 1):
                formatted += f"{i}. {issue}\n"
            formatted += "\n"
        
        # Statutes
        formatted += "APPLICABLE STATUTES:\n"
        for category, items in reasoning['statutes'].items():
            if items:
                formatted += f"- {category.replace('_', ' ').title()}: {', '.join(items[:5])}\n"
        formatted += "\n"
        
        # Precedents
        if reasoning['precedents']:
            formatted += "RELEVANT PRECEDENTS:\n"
            for i, precedent in enumerate(reasoning['precedents'][:5], 1):
                case_name = precedent.get('case_name', 'Unknown')
                year = precedent.get('year', 'Unknown')
                formatted += f"{i}. {case_name} ({year})\n"
            formatted += "\n"
        
        # Application
        if reasoning['application'].get('application_steps'):
            formatted += "APPLICATION STEPS:\n"
            for step in reasoning['application']['application_steps']:
                formatted += f"- {step}\n"
            formatted += "\n"
        
        # Exceptions
        if reasoning['exceptions']:
            formatted += "EXCEPTIONS/LIMITATIONS:\n"
            for i, exception in enumerate(reasoning['exceptions'], 1):
                formatted += f"{i}. {exception[:150]}...\n"
        
        return formatted

