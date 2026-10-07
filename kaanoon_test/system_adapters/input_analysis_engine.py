"""
Advanced Input Analysis Engine for Legal Chatbot
Implements sophisticated NLP techniques for better user understanding
"""

import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class InputAnalysisEngine:
    """
    Advanced input analysis with:
    - Intent & Entity Extraction
    - Sentiment Analysis
    - AI-Powered Safety & Ethics Filtering
    - Active Clarification Strategy
    - Context Understanding
    """
    
    def __init__(self, llm_client=None):
        # Legal entity patterns
        self.section_patterns = [
            r'Section\s+(\d+[A-Z]?)',
            r'Sec\.?\s+(\d+[A-Z]?)',
            r'§\s*(\d+[A-Z]?)',
        ]
        
        self.act_patterns = [
            r'(Indian\s+Contract\s+Act,?\s*\d{4})',
            r'(Consumer\s+Protection\s+Act,?\s*\d{4})',
            r'(IPC|Indian\s+Penal\s+Code,?\s*\d{4})',
            r'(Hindu\s+Succession\s+Act,?\s*\d{4})',
            r'(Specific\s+Relief\s+Act,?\s*\d{4})',
            r'(Code\s+of\s+Civil\s+Procedure|CPC,?\s*\d{4})',
            r'(Evidence\s+Act,?\s*\d{4})',
            r'(GST\s+Act|CGST\s+Act|SGST\s+Act|IGST\s+Act)',
            r'(SC/?ST\s+Act)',
            r'(Transfer\s+of\s+Property\s+Act)',
        ]
        
        # Intent keywords
        self.intent_keywords = {
            'question': ['what', 'how', 'when', 'where', 'why', 'explain', 'define', 'tell me'],
            'complaint': ['denied', 'refused', 'rejected', 'not paid', 'breach', 'violated', 'fraud'],
            'drafting': ['draft', 'write', 'prepare', 'format', 'template', 'create'],
            'interpretation': ['meaning', 'interpret', 'clarify', 'understand', 'scope'],
            'action': ['file', 'sue', 'claim', 'recover', 'demand', 'evict', 'notice'],
            'defense': ['defend', 'reply', 'respond to', 'counter', 'protect'],
        }
        
        # Domain keywords
        self.domain_keywords = {
            'contract': ['contract', 'agreement', 'breach', 'performance', 'vendor', 'supplier', 'delivery'],
            'consumer': ['consumer', 'defective', 'warranty', 'refund', 'product', 'service', 'complaint'],
            'property': ['property', 'land', 'inheritance', 'partition', 'mutation', 'deed', 'title'],
            'insurance': ['insurance', 'claim', 'policy', 'premium', 'coverage', 'exclusion', 'cashless'],
            'employment': ['employee', 'employer', 'termination', 'salary', 'notice period', 'resignation'],
            'cyber': ['cyber', 'data', 'privacy', 'hacking', 'online', 'digital', 'IT Act'],
            'family': ['divorce', 'maintenance', 'custody', 'marriage', 'dowry', 'domestic'],
            'tenant': ['tenant', 'landlord', 'rent', 'eviction', 'lease', 'deposit'],
        }
        
        # Sentiment indicators
        self.negative_sentiment = ['stressed', 'worried', 'scared', 'urgent', 'help', 'desperate', 'frustrated']
        self.positive_sentiment = ['thank', 'grateful', 'appreciate', 'good', 'excellent']
        
        # Store LLM client for AI-powered safety analysis
        self.llm_client = llm_client
        self.llm_model = None  # Will be set when client is provided
        
    def analyze(self, user_input: str, conversation_history: List[Dict] = None) -> Dict:
        """
        Comprehensive input analysis
        
        Returns:
        {
            'intent': str,
            'entities': {...},
            'domain': str,
            'sentiment': str,
            'tone': str,
            'ambiguities': [...],
            'clarification_needed': bool,
            'clarifying_questions': [...],
            'safety_flag': bool,
            'safety_reason': str,
            'metadata': {...}
        }
        """
        
        analysis = {
            'original_input': user_input,
            'timestamp': datetime.now().isoformat(),
            'intent': None,
            'entities': {},
            'domain': None,
            'sentiment': 'neutral',
            'tone': 'normal',
            'ambiguities': [],
            'clarification_needed': False,
            'clarifying_questions': [],
            'safety_flag': False,
            'safety_reason': None,
            'metadata': {}
        }
        
        # 1. Safety Check FIRST
        safety_result = self._check_safety(user_input)
        if safety_result['is_unsafe']:
            analysis['safety_flag'] = True
            analysis['safety_reason'] = safety_result['reason']
            return analysis
        
        # 2. Extract Entities
        analysis['entities'] = self._extract_entities(user_input)
        
        # 3. Detect Intent
        analysis['intent'] = self._detect_intent(user_input)
        
        # 4. Classify Domain
        analysis['domain'] = self._classify_domain(user_input)
        
        # 5. Analyze Sentiment
        analysis['sentiment'], analysis['tone'] = self._analyze_sentiment(user_input)
        
        # 6. Check for Ambiguities
        ambiguities = self._detect_ambiguities(user_input, analysis['entities'])
        analysis['ambiguities'] = ambiguities
        
        # 7. Generate Clarifying Questions if needed
        if ambiguities:
            analysis['clarification_needed'] = True
            analysis['clarifying_questions'] = self._generate_clarifying_questions(
                user_input, ambiguities, analysis['domain']
            )
        
        # 8. Add metadata
        analysis['metadata'] = {
            'word_count': len(user_input.split()),
            'has_legal_entities': bool(analysis['entities']['sections'] or analysis['entities']['acts']),
            'complexity': self._assess_complexity(user_input, analysis),
            'urgency': self._assess_urgency(user_input, analysis['sentiment']),
        }
        
        return analysis
    
    def _extract_entities(self, text: str) -> Dict:
        """Extract legal entities: sections, acts, dates, amounts, parties"""
        entities = {
            'sections': [],
            'acts': [],
            'dates': [],
            'amounts': [],
            'parties': [],
            'jurisdiction': None
        }
        
        # Extract sections
        for pattern in self.section_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entities['sections'].append(match.group(0))
        
        # Extract acts
        for pattern in self.act_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entities['acts'].append(match.group(1))
        
        # Extract amounts (₹, rupees, Rs)
        amount_patterns = [r'₹\s*[\d,]+', r'Rs\.?\s*[\d,]+', r'rupees\s+[\d,]+']
        for pattern in amount_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entities['amounts'].append(match.group(0))
        
        # Extract dates (simple patterns)
        date_pattern = r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}'
        matches = re.finditer(date_pattern, text)
        for match in matches:
            entities['dates'].append(match.group(0))
        
        # Extract jurisdiction
        if re.search(r'Supreme\s+Court', text, re.IGNORECASE):
            entities['jurisdiction'] = 'Supreme Court'
        elif re.search(r'High\s+Court', text, re.IGNORECASE):
            entities['jurisdiction'] = 'High Court'
        elif re.search(r'District\s+Court', text, re.IGNORECASE):
            entities['jurisdiction'] = 'District Court'
        
        return entities
    
    def _detect_intent(self, text: str) -> str:
        """Detect primary user intent"""
        text_lower = text.lower()
        
        intent_scores = {}
        for intent, keywords in self.intent_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                intent_scores[intent] = score
        
        if not intent_scores:
            return 'question'  # Default
        
        return max(intent_scores, key=intent_scores.get)
    
    def _classify_domain(self, text: str) -> str:
        """Classify legal domain"""
        text_lower = text.lower()
        
        domain_scores = {}
        for domain, keywords in self.domain_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                domain_scores[domain] = score
        
        if not domain_scores:
            return 'general'
        
        return max(domain_scores, key=domain_scores.get)
    
    def _analyze_sentiment(self, text: str) -> Tuple[str, str]:
        """Analyze sentiment and tone"""
        text_lower = text.lower()
        
        # Count sentiment indicators
        negative_count = sum(1 for word in self.negative_sentiment if word in text_lower)
        positive_count = sum(1 for word in self.positive_sentiment if word in text_lower)
        
        # Check for urgency/stress markers
        urgency_markers = ['urgent', 'asap', 'immediately', 'quickly', 'help', '!!!']
        has_urgency = any(marker in text_lower for marker in urgency_markers)
        
        # Determine sentiment
        if negative_count > positive_count:
            sentiment = 'negative'
            tone = 'stressed' if has_urgency else 'concerned'
        elif positive_count > negative_count:
            sentiment = 'positive'
            tone = 'satisfied'
        else:
            sentiment = 'neutral'
            tone = 'calm'
        
        return sentiment, tone
    
    def _check_safety(self, text: str) -> Dict:
        """
        AI-Powered Safety Check using LLM
        Detects ANY unethical, illegal, or harmful request
        """
        
        # If LLM client not available, skip AI safety check
        if not self.llm_client or not self.llm_model:
            return {'is_unsafe': False, 'reason': None}
        
        try:
            # Use LLM to analyze ethical safety
            safety_prompt = f"""You are an AI Ethics and Safety Analyzer for a legal chatbot.

USER REQUEST: "{text}"

Analyze if this request is:
1. Asking for help with illegal activity (tax evasion, fraud, forgery, bribery, money laundering, hacking, theft, etc.)
2. Requesting creation of fake documents (certificates, IDs, medical reports, police FIRs, court records, etc.)
3. Seeking advice to deceive, harm, or exploit others
4. Attempting to circumvent legal obligations or hide illegal activity
5. Asking for malicious technical exploits (malware, deepfakes, data theft, CCTV tampering, etc.)
6. Trying to manipulate legal/financial systems unethically

**IMPORTANT DISTINCTIONS:**
- "How to legally minimize tax" → SAFE (legal tax planning)
- "How to evade tax" → UNSAFE (illegal)
- "Legal defenses against fraud accusation" → SAFE (defending oneself)
- "How to commit fraud without getting caught" → UNSAFE (illegal intent)
- "My rights if accused of bribery" → SAFE (knowing rights)
- "How to bribe without getting caught" → UNSAFE (illegal intent)

Respond in EXACTLY this format:
SAFE or UNSAFE
[If UNSAFE, provide brief reason in 1 sentence]

Examples:
- "What is GST?" → SAFE
- "Help me evade GST tax" → UNSAFE | Requesting illegal tax evasion advice
- "How to legally reduce income tax?" → SAFE
- "Show me ways to hide cash from government" → UNSAFE | Asking for illegal concealment of assets
- "Create a fake driver's license" → UNSAFE | Requesting creation of fraudulent government document
- "Rights if falsely accused" → SAFE
- "How to launder money through shell companies" → UNSAFE | Seeking illegal money laundering methods

Analyze now:"""

            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": safety_prompt}],
                temperature=0.1,  # Low temperature for consistent safety decisions
                max_tokens=150
            )
            
            safety_result = response.choices[0].message.content.strip()
            
            # Parse response
            if safety_result.startswith('UNSAFE'):
                reason = safety_result.split('|')[1].strip() if '|' in safety_result else 'Detected unethical or illegal request'
                return {
                    'is_unsafe': True,
                    'reason': reason
                }
            else:
                return {'is_unsafe': False, 'reason': None}
                
        except Exception as e:
            print(f"[WARNING] AI safety check failed: {e}")
            # Fail safe - allow request if AI check fails
            return {'is_unsafe': False, 'reason': None}
    
    def _detect_ambiguities(self, text: str, entities: Dict) -> List[str]:
        """
        Detect missing or ambiguous information (SMART DETECTION)
        Only flag truly incomplete queries, not detailed questions
        """
        ambiguities = []
        
        # Get word count and check if it's a detailed question
        word_count = len(text.split())
        is_detailed = word_count > 30  # Detailed questions have context
        
        # Check for vague references ONLY in short queries
        if word_count < 15 and re.search(r'\b(they|them|he|she|it)\b', text, re.IGNORECASE) and not entities['parties']:
            # But not if the question describes the situation clearly
            if not any(word in text.lower() for word in ['employee', 'employer', 'husband', 'wife', 'tenant', 'landlord', 'company', 'insurer', 'vendor', 'buyer']):
                ambiguities.append('vague_party_reference')
        
        # Check for missing jurisdiction ONLY if explicitly asking to file
        text_lower = text.lower()
        explicitly_filing = any(phrase in text_lower for phrase in ['where to file', 'which court to file', 'should i file', 'how to file'])
        if explicitly_filing and not entities['jurisdiction']:
            ambiguities.append('missing_jurisdiction')
        
        # NO longer flag missing amounts - user can describe situation without exact amounts
        
        # NO longer flag missing timeframe - context clues are enough
        
        # Check for incomplete context ONLY for very short questions
        if word_count < 8 and not any([
            '?' in text,  # Has question mark
            'what' in text_lower,
            'how' in text_lower,
            'when' in text_lower,
            'where' in text_lower,
            'why' in text_lower,
            'explain' in text_lower,
            'define' in text_lower
        ]):
            ambiguities.append('incomplete_context')
        
        return ambiguities
    
    def _generate_clarifying_questions(self, text: str, ambiguities: List[str], domain: str) -> List[str]:
        """Generate specific clarifying questions based on ambiguities"""
        questions = []
        
        if 'vague_party_reference' in ambiguities:
            questions.append("Could you please specify who you are referring to (names of parties involved)?")
        
        if 'missing_jurisdiction' in ambiguities:
            questions.append("Which court/jurisdiction would you like to file in (District/High/Supreme Court)?")
        
        if 'missing_amount' in ambiguities:
            questions.append("What is the exact amount involved in this matter?")
        
        if 'missing_timeframe' in ambiguities:
            questions.append("When did this incident occur (please provide specific dates)?")
        
        if 'incomplete_context' in ambiguities:
            if domain == 'contract':
                questions.append("Could you provide more details about the contract (what was agreed, what went wrong)?")
            elif domain == 'consumer':
                questions.append("Please provide more details about the product/service and the defect/issue.")
            elif domain == 'insurance':
                questions.append("Could you share more details about your policy, claim amount, and reason for denial?")
            else:
                questions.append("Could you provide more details about your situation for better guidance?")
        
        return questions[:3]  # Limit to top 3 questions
    
    def _assess_complexity(self, text: str, analysis: Dict) -> str:
        """Assess query complexity"""
        factors = 0
        
        # Has legal entities
        if analysis['entities']['sections'] or analysis['entities']['acts']:
            factors += 1
        
        # Multiple amounts or dates
        if len(analysis['entities']['amounts']) > 1 or len(analysis['entities']['dates']) > 1:
            factors += 1
        
        # Long text
        if len(text.split()) > 50:
            factors += 1
        
        # Action intent (complex)
        if analysis['intent'] in ['action', 'defense', 'drafting']:
            factors += 1
        
        if factors >= 3:
            return 'high'
        elif factors >= 1:
            return 'medium'
        else:
            return 'low'
    
    def _assess_urgency(self, text: str, sentiment: str) -> str:
        """Assess urgency level"""
        urgency_markers = ['urgent', 'asap', 'immediately', 'quickly', 'today', '!!!']
        text_lower = text.lower()
        
        urgency_count = sum(1 for marker in urgency_markers if marker in text_lower)
        
        if urgency_count >= 2 or sentiment == 'negative':
            return 'high'
        elif urgency_count == 1:
            return 'medium'
        else:
            return 'low'
