"""
ONTOLOGY-GROUNDED RAG - Legal Knowledge Graph Integration
Uses legal domain ontology to ground retrieval and generation
"""

from typing import Dict, List, Any, Set
import re

class LegalOntology:
    """Legal domain ontology for structured knowledge representation"""
    
    def __init__(self):
        # Legal domain hierarchy
        self.legal_domains = {
            'Criminal Law': {
                'subcategories': ['IPC', 'CrPC', 'Evidence Act', 'Juvenile Justice'],
                'related_acts': ['Indian Penal Code 1860', 'Code of Criminal Procedure 1973'],
                'key_concepts': ['mens rea', 'actus reus', 'cognizable', 'non-cognizable', 'bailable']
            },
            'Civil Law': {
                'subcategories': ['Contract', 'Property', 'Torts', 'Family Law'],
                'related_acts': ['Indian Contract Act 1872', 'Transfer of Property Act 1882'],
                'key_concepts': ['consideration', 'breach', 'damages', 'specific performance']
            },
            'Corporate Law': {
                'subcategories': ['Companies Act', 'SEBI', 'Competition Law'],
                'related_acts': ['Companies Act 2013', 'SEBI Act 1992'],
                'key_concepts': ['director', 'shareholder', 'corporate governance', 'merger']
            },
            'Tax Law': {
                'subcategories': ['GST', 'Income Tax', 'Customs'],
                'related_acts': ['GST Act 2017', 'Income Tax Act 1961'],
                'key_concepts': ['input tax credit', 'assessment', 'exemption', 'deduction']
            },
            'Data Protection': {
                'subcategories': ['DPDP Act', 'IT Act'],
                'related_acts': ['DPDP Act 2023', 'IT Act 2000'],
                'key_concepts': ['personal data', 'consent', 'data principal', 'processing']
            }
        }
        
        # Entity relationships
        self.entity_relations = {
            'governed_by': {},  # Law → Governing Act
            'applies_to': {},   # Act → Applicable entities
            'requires': {},     # Procedure → Requirements
            'leads_to': {}      # Action → Consequence
        }
        
        # Concept hierarchy
        self.concept_hierarchy = self._build_concept_hierarchy()
    
    def _build_concept_hierarchy(self) -> Dict:
        """Build hierarchical concept structure"""
        return {
            'offense': {
                'cognizable': ['murder', 'rape', 'theft', 'robbery'],
                'non-cognizable': ['defamation', 'assault', 'cheating']
            },
            'remedy': {
                'civil': ['damages', 'injunction', 'specific performance'],
                'criminal': ['imprisonment', 'fine', 'death penalty']
            },
            'procedure': {
                'filing': ['complaint', 'petition', 'appeal'],
                'trial': ['examination', 'cross-examination', 'judgment']
            }
        }
    
    def identify_domain(self, query: str) -> List[str]:
        """Identify relevant legal domains from query"""
        query_lower = query.lower()
        identified_domains = []
        
        for domain, info in self.legal_domains.items():
            # Check domain keywords
            domain_keywords = [domain.lower()] + [cat.lower() for cat in info['subcategories']]
            domain_keywords += [act.lower() for act in info['related_acts']]
            domain_keywords += info['key_concepts']
            
            if any(keyword in query_lower for keyword in domain_keywords):
                identified_domains.append(domain)
        
        return identified_domains if identified_domains else ['General Legal']
    
    def extract_entities(self, query: str) -> Dict[str, List[str]]:
        """Extract legal entities from query"""
        entities = {
            'acts': [],
            'sections': [],
            'concepts': [],
            'parties': []
        }
        
        # Extract section numbers
        section_pattern = r'\b(?:section|sec|§)\s*(\d+[A-Z]?)\b'
        sections = re.findall(section_pattern, query, re.IGNORECASE)
        entities['sections'] = sections
        
        # Extract act names
        act_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+Act\s+\d{4})'
        acts = re.findall(act_pattern, query)
        entities['acts'] = acts
        
        # Extract concepts
        for domain_info in self.legal_domains.values():
            for concept in domain_info['key_concepts']:
                if concept.lower() in query.lower():
                    entities['concepts'].append(concept)
        
        return entities
    
    def get_related_concepts(self, concept: str) -> List[str]:
        """Get related concepts from ontology"""
        related = set()
        concept_lower = concept.lower()
        
        # Search in concept hierarchy
        for category, subcategories in self.concept_hierarchy.items():
            if isinstance(subcategories, dict):
                for subcat, items in subcategories.items():
                    if concept_lower in [item.lower() for item in items]:
                        # Add sibling concepts
                        related.update(items)
                        # Add parent concepts
                        related.add(category)
                        related.add(subcat)
        
        return list(related)


class OntologyGroundedRAG:
    """RAG system grounded in legal ontology"""
    
    def __init__(self):
        self.ontology = LegalOntology()
    
    def ground_query(self, query: str) -> Dict[str, Any]:
        """Ground query in legal ontology"""
        
        # Identify domains
        domains = self.ontology.identify_domain(query)
        
        # Extract entities
        entities = self.ontology.extract_entities(query)
        
        # Get related concepts
        all_concepts = []
        for concept in entities['concepts']:
            all_concepts.extend(self.ontology.get_related_concepts(concept))
        
        # Build grounded query with ontology context
        grounding = {
            'original_query': query,
            'identified_domains': domains,
            'entities': entities,
            'related_concepts': list(set(all_concepts)),
            'ontology_context': self._build_ontology_context(domains, entities)
        }
        
        return grounding
    
    def _build_ontology_context(self, domains: List[str], entities: Dict) -> str:
        """Build context string from ontology"""
        context_parts = []
        
        context_parts.append(f"Legal Domain(s): {', '.join(domains)}")
        
        if entities['acts']:
            context_parts.append(f"Relevant Acts: {', '.join(entities['acts'])}")
        
        if entities['sections']:
            context_parts.append(f"Sections Referenced: {', '.join(entities['sections'])}")
        
        if entities['concepts']:
            context_parts.append(f"Legal Concepts: {', '.join(entities['concepts'])}")
        
        return " | ".join(context_parts)
    
    def enhance_retrieval_query(self, query: str, grounding: Dict) -> str:
        """Enhance retrieval query with ontology information"""
        
        enhanced_parts = [query]
        
        # Add domain context
        if grounding['identified_domains']:
            enhanced_parts.append(' '.join(grounding['identified_domains']))
        
        # Add related concepts
        if grounding['related_concepts']:
            enhanced_parts.append(' '.join(grounding['related_concepts'][:5]))  # Top 5
        
        # Add entity context
        entities = grounding['entities']
        if entities['acts']:
            enhanced_parts.append(' '.join(entities['acts']))
        if entities['sections']:
            enhanced_parts.append(' '.join([f"Section {s}" for s in entities['sections']]))
        
        return ' '.join(enhanced_parts)
