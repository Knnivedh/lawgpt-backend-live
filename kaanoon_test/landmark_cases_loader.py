"""
Landmark Cases Database Loader
Provides quick access to landmark case information
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class LandmarkCasesDB:
    """Database for landmark cases and legal doctrines"""
    
    def __init__(self, db_path: str = "landmark_cases_database.json"):
        """Initialize landmark cases database"""
        self.db_path = Path(__file__).parent / db_path
        self.cases = []
        self.case_index = {}  # Index for fast lookup
        self.keyword_index = {}  # Keyword to cases mapping
        self.load_database()
    
    def load_database(self):
        """Load landmark cases from JSON file"""
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.cases = data.get('landmark_cases', [])
            
            # Build indices for fast lookup
            self._build_indices()
            
            logger.info(f"✅ Loaded {len(self.cases)} landmark cases")
        except FileNotFoundError:
            logger.error(f"Landmark cases database not found: {self.db_path}")
            self.cases = []
        except Exception as e:
            logger.error(f"Error loading landmark cases: {e}")
            self.cases = []
    
    def _build_indices(self):
        """Build search indices for fast lookup"""
        for case in self.cases:
            # Case name index
            case_name = case['name'].lower()
            self.case_index[case_name] = case
            
            # Keyword index
            keywords = case.get('keywords', [])
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower not in self.keyword_index:
                    self.keyword_index[keyword_lower] = []
                self.keyword_index[keyword_lower].append(case)
        
        logger.info(f"Built indices: {len(self.case_index)} cases, {len(self.keyword_index)} keywords")
    
    def search_by_name(self, case_name: str) -> Optional[Dict]:
        """Search for case by name"""
        case_name_lower = case_name.lower()
        
        # Exact match
        if case_name_lower in self.case_index:
            return self.case_index[case_name_lower]
        
        # Partial match
        for name, case in self.case_index.items():
            if case_name_lower in name or name in case_name_lower:
                return case
        
        return None
    
    def search_by_keywords(self, keywords: List[str]) -> List[Dict]:
        """Search for cases by keywords"""
        results = []
        seen_cases = set()
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in self.keyword_index:
                for case in self.keyword_index[keyword_lower]:
                    case_name = case['name']
                    if case_name not in seen_cases:
                        results.append(case)
                        seen_cases.add(case_name)
        
        return results
    
    def search_by_query(self, query: str) -> List[Dict]:
        """Search for cases relevant to query"""
        query_lower = query.lower()
        results = []
        
        # Search by case name mentions
        for case_name, case in self.case_index.items():
            if case_name in query_lower:
                results.append(case)
        
        # Search by keywords in query
        for keyword in self.keyword_index.keys():
            if keyword in query_lower:
                for case in self.keyword_index[keyword]:
                    if case not in results:
                        results.append(case)
        
        return results[:5]  # Return top 5 matches
    
    def get_case_info(self, case_name: str) -> Optional[str]:
        """Get formatted case information"""
        case = self.search_by_name(case_name)
        if not case:
            return None
        
        info = []
        info.append(f"**{case['name']}**")
        info.append(f"Case: {case['case']} ({case['year']})")
        
        if 'citation' in case:
            info.append(f"Citation: {case['citation']}")
        
        info.append(f"\n{case['description']}")
        
        if 'key_principles' in case and case['key_principles']:
            info.append("\nKey Principles:")
            for principle in case['key_principles']:
                info.append(f"• {principle}")
        
        if 'alternatives' in case and case['alternatives']:
            info.append("\nAlternatives/Options:")
            for alt in case['alternatives']:
                info.append(f"• {alt}")
        
        if 'related_sections' in case:
            info.append(f"\nRelated Sections: {', '.join(case['related_sections'])}")
        
        if 'related_articles' in case:
            info.append(f"Related Articles: {', '.join(case['related_articles'])}")
        
        if 'related_laws' in case:
            info.append(f"Related Laws: {', '.join(case['related_laws'])}")
        
        return "\n".join(info)
    
    def enhance_answer_with_cases(self, query: str, answer: str) -> str:
        """Enhance answer with relevant landmark case information"""
        relevant_cases = self.search_by_query(query)
        
        if not relevant_cases:
            return answer
        
        # Check if case info is already in answer
        answer_lower = answer.lower()
        cases_to_add = []
        
        for case in relevant_cases:
            case_name_lower = case['name'].lower()
            case_case_lower = case['case'].lower()
            
            # Only add if not already mentioned comprehensively
            if case_name_lower not in answer_lower and case_case_lower not in answer_lower:
                cases_to_add.append(case)
        
        # Add landmark case information
        if cases_to_add:
            enhancement = "\n\n**Relevant Landmark Cases:**\n"
            for case in cases_to_add[:2]:  # Add top 2 relevant cases
                enhancement += f"\n• **{case['name']}**: {case['case']} ({case['year']})"
                enhancement += f"\n  {case['description'][:200]}..."
                if 'alternatives' in case and case['alternatives']:
                    enhancement += f"\n  Alternatives: {', '.join(case['alternatives'])}"
            
            answer += enhancement
        
        return answer


# Global instance
_landmark_db = None

def get_landmark_db() -> LandmarkCasesDB:
    """Get singleton instance of landmark cases database"""
    global _landmark_db
    if _landmark_db is None:
        _landmark_db = LandmarkCasesDB()
    return _landmark_db
