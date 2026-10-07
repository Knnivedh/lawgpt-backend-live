"""
Timeline Builder - Extract and structure timeline information from text
"""
import re
from typing import List, Dict, Optional


class TimelineBuilder:
    """Build structured timelines from LLM-generated responses"""
    
    def build_timeline_from_text(self, response_text: str, extracted_dates: List[str] = None) -> List[Dict]:
        """
        Extract timeline events from LLM response text
        
        Args:
            response_text: The full LLM response
            extracted_dates: Optional list of dates extracted from source documents
        
        Returns:
            List of timeline events:
            [
                {
                    'date': 'Oct 2012',
                    'event': 'Initial incident',
                    'description': 'Soujanya was raped and murdered...',
                    'source': 'theweek.in'
                },
                ...
            ]
        """
        timeline = []
        
        # Pattern 1: "**Background — Event (Date):** Description... (source)"
        # Matches the format from our enhanced educational template
        pattern1 = r'\*\*([^(]+)\(([^)]+)\):\*\*\s*([^(]+?)(?:\(([^)]+)\))?(?=\n|$|\*\*)'
        matches1 = re.findall(pattern1, response_text, re.MULTILINE)
        
        for event_name, date, description, source in matches1:
            timeline.append({
                'event': event_name.strip().replace('—', '-').strip(),
                'date': date.strip(),
                'description': description.strip(),
                'source': source.strip() if source else None
            })
        
        # Pattern 2: "Date: Event description... (source)"
        # e.g., "Oct 2012: Soujanya was raped... (theweek.in)"
        pattern2 = r'([A-Z][a-z]+\s+\d{1,2},?\s+\d{4}|[A-Z][a-z]+\s+\d{4}):\s*([^(]+?)(?:\(([^)]+)\))?(?=\n|$)'
        matches2 = re.findall(pattern2, response_text)
        
        for date, description, source in matches2:
            # Avoid duplicates (if already captured by pattern1)
            if not any(t['date'] == date.strip() for t in timeline):
                timeline.append({
                    'date': date.strip(),
                    'description': description.strip(),
                    'source': source.strip() if source else None
                })
        
        # Pattern 3: Bullet points with dates
        # e.g., "- **Event (Date):** Description (source)"
        pattern3 = r'-\s*\*\*([^(]+)\(([^)]+)\):\*\*\s*([^(]+?)(?:\(([^)]+)\))?(?=\n|$)'
        matches3 = re.findall(pattern3, response_text, re.MULTILINE)
        
        for event, date, description, source in matches3:
            timeline.append({
                'event': event.strip(),
                'date': date.strip(),
                'description': description.strip(),
                'source': source.strip() if source else None
            })
        
        # Sort by date (best effort - doesn't handle all date formats perfectly)
        timeline = self._sort_timeline(timeline)
        
        # Remove duplicates based on date + description similarity
        timeline = self._deduplicate_timeline(timeline)
        
        return timeline
    
    def _sort_timeline(self, timeline: List[Dict]) -> List[Dict]:
        """Sort timeline events chronologically"""
        def parse_date_key(event):
            """Extract year for sorting"""
            date_str = event.get('date', '')
            # Extract 4-digit year
            year_match = re.search(r'\d{4}', date_str)
            if year_match:
                return int(year_match.group())
            return 0  # Unknown dates go to beginning
        
        return sorted(timeline, key=parse_date_key)
    
    def _deduplicate_timeline(self, timeline: List[Dict]) -> List[Dict]:
        """Remove duplicate timeline events"""
        seen = set()
        unique_timeline = []
        
        for event in timeline:
            # Create a signature based on date and first 50 chars of description
            desc_snippet = event.get('description', '')[:50].strip().lower()
            signature = f"{event.get('date', '')}-{desc_snippet}"
            
            if signature not in seen:
                seen.add(signature)
                unique_timeline.append(event)
        
        return unique_timeline
    
    def format_timeline_markdown(self, timeline: List[Dict]) -> str:
        """
        Format timeline as markdown
        
        Returns:
            Markdown string with formatted timeline
        """
        if not timeline:
            return ""
        
        md = "## Timeline\n\n"
        
        for event in timeline:
            # Format: **Date:** Description (source)
            md += f"**{event['date']}:** "
            
            if event.get('event'):
                md += f"*{event['event']}* — "
            
            md += event['description']
            
            if event.get('source'):
                md += f" ({event['source']})"
            
            md += "\n\n"
        
        return md
    
    def format_timeline_json(self, timeline: List[Dict]) -> Dict:
        """
        Format timeline as structured JSON
        
        Returns:
            {
                'timeline': [...],
                'event_count': N,
                'date_range': {'earliest': '...', 'latest': '...'}
            }
        """
        if not timeline:
            return {
                'timeline': [],
                'event_count': 0,
                'date_range': None
            }
        
        # Extract years for date range
        years = []
        for event in timeline:
            year_match = re.search(r'\d{4}', event.get('date', ''))
            if year_match:
                years.append(int(year_match.group()))
        
        date_range = None
        if years:
            date_range = {
                'earliest': min(years),
                'latest': max(years)
            }
        
        return {
            'timeline': timeline,
            'event_count': len(timeline),
            'date_range': date_range
        }
    
    def extract_key_dates(self, timeline: List[Dict]) -> List[str]:
        """Extract list of all dates from timeline"""
        return [event['date'] for event in timeline if event.get('date')]
