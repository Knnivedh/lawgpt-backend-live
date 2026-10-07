"""
Statute-Aware Section Chunker for Indian Legal Acts
=====================================================

Replaces naive chunk-based ingestion with structure-aware parsing that:
1. Detects real section boundaries in statute text
2. Creates one chunk per legal section with proper metadata
3. Preserves section numbers, titles, act names, chapter context
4. Handles multiple data formats found in our statute JSONs
5. Splits oversized sections while preserving context headers

Supported formats (auto-detected):
- chunk-based: BNS 2023 style (--- Section X --- markers)
- number-based: Indian Contract Act style (pre-chunked with real section nums)
- marker-based: Consumer Protection Act style (full text + subsection entries)
- monolithic: Companies Act 2013 style (single massive entry)

Author: LAW-GPT Team
"""

import hashlib
import json
import re
import logging
from pathlib import Path
from typing import Any, List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Maximum chunk size in characters. Sections exceeding this will be sub-chunked.
MAX_CHUNK_CHARS = 3000
# Minimum chunk size - sections smaller than this may be merged with adjacent
MIN_CHUNK_CHARS = 100
# Overlap characters when sub-chunking long sections
OVERLAP_CHARS = 200


class StatuteSectionChunker:
    """
    Structure-aware chunker for Indian legal statutes.
    
    Parses raw statute text and creates properly bounded chunks with rich metadata:
    - act_name: Name of the statute/act
    - chapter: Current chapter heading
    - section_number: Real section number (e.g., "302", "2(47)")
    - section_title: Section title/heading
    - part: Part or Schedule heading if applicable
    """
    
    # Regex patterns for detecting section boundaries in raw text
    # Pattern for "--- Section X ---" markers (BNS style)
    MARKER_PATTERN = re.compile(
        r'^---\s*(?:Section\s+)?(\d+[A-Z]{0,3})\s*---',
        re.MULTILINE
    )

    # GAP-5 FIX: the unanchored twin of MARKER_PATTERN. In the stored corpus a
    # chunk begins
    #     Act: <name>
    #     Section: <n> (Chunk <n>)
    #     Content: --- Section <n> ---
    # so the "--- Section N ---" marker sits AFTER "Content: " on its line and
    # a "^"-anchored pattern can never match it. This pattern finds it wherever
    # it occurs, which is what marker-based chunk parsing needs.
    MARKER_INLINE_PATTERN = re.compile(
        r'---\s*(?:Section\s+)?(\d+[A-Z]{0,3})\s*---'
    )
    
    # Pattern for inline section numbering: "123. Title text"
    # Handles sections like "1.", "2.", "302.", "44A.", "10B."
    SECTION_NUM_PATTERN = re.compile(
        r'^\s*(\d+[A-Z]?)\.\s*\n',
        re.MULTILINE
    )
    
    # Section with title on same line: "302. Punishment for murder"
    SECTION_WITH_TITLE_PATTERN = re.compile(
        r'^\s*(\d+[A-Z]?)\.\s+([A-Z][^.\n]{5,80}(?:\.|-|—))',
        re.MULTILINE
    )
    
    # Chapter heading pattern
    CHAPTER_PATTERN = re.compile(
        r'^(?:Chapter|CHAPTER)\s+([IVXLCDM]+(?:\s*[A-Z])?)\b[^\n]*',
        re.MULTILINE
    )
    
    # Part heading pattern
    PART_PATTERN = re.compile(
        r'^(?:Part|PART)\s+([IVXLCDMA-Z]+)\b[^\n]*',
        re.MULTILINE
    )
    
    # Schedule heading pattern
    SCHEDULE_PATTERN = re.compile(
        r'^(?:Schedule|SCHEDULE|FIRST SCHEDULE|SECOND SCHEDULE|THIRD SCHEDULE)',
        re.MULTILINE
    )
    
    # Subsection entries from Kanoon-style data: "[Section 1] [Entire Act]"
    KANOON_HEADER_PATTERN = re.compile(
        r'^\[\s*\n*(?:Section\s+\d+|Entire\s+Act)\s*\n*\]',
        re.MULTILINE
    )

    # ------------------------------------------------------------------
    # GAP-1: entry classification for marker-based files.
    # ------------------------------------------------------------------
    # A Kanoon "entire act" entry is the one that opens with the
    # "Union of India - Act" nav header. Measured on the corpus:
    #   Consumer_Protection_Act_2019  entries=631  5 act-header entries
    #     idx 0    126,915  "No. 35 of 2019"  -> Consumer Protection Act, 2019
    #     idx 66   143,294  "34 of 2006"      -> Food Safety & Standards Act, 2006
    #     idx 248  824,097  "2 of 1974"       -> Code of Criminal Procedure, 1973
    #     idx 400  276,009  "7 of 2017"
    #     idx 401   71,161  "68 of 1986"
    #   The_Companies_Act_1956  entries=2043  2 act-header entries
    #     idx 0     50,548  "1."              -> NOT an act: it is "Union of
    #                       India - Section", i.e. Section 1 (Statement of
    #                       Objects and Reasons) with footnotes
    #     idx 96    68,052  "38 of 1949"      -> Chartered Accountants Act, 1949
    #     idx 411 1,404,197  "1 of 1956"      -> the ACT ITSELF
    # The old code read sections[0] only, so for both acts it parsed either a
    # small preamble or a single mislabelled section and dropped the bulk.
    KANOON_ACT_HEADER_PATTERN = re.compile(
        r'\A\s*Union\s+of\s+India\s*-\s*Act\b', re.IGNORECASE)

    # The act's real title is the first non-empty line after the header, e.g.
    #   "Union of India - Act\n\nThe Code of Criminal Procedure, 1973\n\n..."
    # The stored `section_number` label is NOT reliable: idx 248 of CPA 2019
    # is labelled "2 of 1974" but contains the Code of Criminal Procedure,
    # 1973. So the header wins over the label.
    KANOON_ACT_TITLE_PATTERN = re.compile(
        r'\A\s*Union\s+of\s+India\s*-\s*Act\s*[\r\n]+(?:\s*[\r\n]+)*\s*'
        r'([^\r\n]{3,140})')

    # A subsection / sub-clause label: "(1)", "(a)", "(ii)", "(7)", "(Commencement)"
    SUBSECTION_LABEL_PATTERN = re.compile(r'^\(([^()]{1,32})\)$')

    # ------------------------------------------------------------------
    # GAP-2: thread the parent section number out of a chunk header.
    # ------------------------------------------------------------------
    # Tried in order; the first hit wins. Every form below is header
    # scaffolding that _clean_kanoon_artifacts then strips, so the parent MUST
    # be resolved from the RAW content before cleaning.
    PARENT_PATTERNS = (
        # BNS style: "--- Section 302 ---"
        re.compile(r'---\s*(?:Section\s+)?(\d+[A-Z]{0,3})\s*---'),
        # Kanoon bracketed nav token: "[\nSection 111A\n]", "[\nSection 10FZA(2)\n]"
        re.compile(r'\[\s*Section\s+(\d+[A-Z]{0,3})\s*(?:\([^)\n]{1,32}\))*\s*\]'),
        # Kanoon breadcrumb: "Section 111A(7) in The Companies Act, 1956"
        re.compile(r'\bSection\s+(\d+[A-Z]{0,3})\s*(?:\([^)\n]{1,32}\))*\s+in\s+'),
        # Kanoon breadcrumb: "Section 137 in The Transfer Of Property Act, 1882"
        re.compile(r'^[ \t]*Section\s+(\d+[A-Z]{0,3})\s+in\s+\S', re.MULTILINE),
        # "Section: 302" in the stored "Act:/Section:/Content:" preamble
        re.compile(r'^[ \t]*Section\s*:\s*(\d+[A-Z]{0,3})\s*$', re.MULTILINE),
    )

    # Entry size above which an entry with no usable section label is treated
# as act body text rather than dropped.
    FULLTEXT_MIN_CHARS = 50000

    # Floor for EMITTING an already-nav-cleaned entry. This is deliberately
    # far below `min_chunk_chars` (100): that value sizes chunks, it should not
    # gate emission. A Kanoon subsection such as
    #   "(Commencement)\nIt shall come into force on the first day of July, 1882."
    # is 54 chars of real statutory text and must be indexed, while a body of
    # "***" (3 chars) is not worth a chunk. Using min_chunk_chars as a drop
    # gate silently lost 0.7-1.9% of the words in NI Act 1881, Transfer of
    # Property and the Central Boards of Revenue Act.
    MIN_EMIT_CHARS = 20

    def __init__(self, max_chunk_chars: int = MAX_CHUNK_CHARS, 
                 min_chunk_chars: int = MIN_CHUNK_CHARS):
        self.max_chunk_chars = max_chunk_chars
        self.min_chunk_chars = min_chunk_chars
        # GAP-4: per-file allocators. `_chunk_seq` makes the
        # (source_file, section_number, chunk_index) triple unique by
        # construction - it was measured colliding across 524 records in 150
        # groups - and `_id_seq` is the last-resort guard on the id itself.
        self._file_key = ''
        self._chunk_seq: dict = {}
        self._id_seq: dict = {}

    def process_statute_file(self, file_path: Path) -> List[Dict]:
        """
        Process a single statute JSON file and return properly chunked records.
        
        Args:
            file_path: Path to the statute JSON file
            
        Returns:
            List of dicts with 'id', 'text', 'metadata' keys
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return []
        
        act_name = data.get('act_name', file_path.stem.replace("_", " "))
        sections = data.get('sections', [])
        fmt = data.get('format_detected', '')
        
        if not sections:
            logger.warning(f"No sections found in {file_path.name}")
            return []
        
        # GAP-4: reset the per-file uniqueness allocators.
        self._file_key = hashlib.md5(file_path.stem.encode()).hexdigest()[:8]
        self._chunk_seq = {}
        self._id_seq = {}
        
        # Auto-detect format and route to appropriate handler.
        # Detection runs on the RAW sections: _normalize_sections changes entry
        # lengths, which would make the size thresholds order-dependent.
        fmt_type = self._detect_format(sections, fmt)

        # GAP-9 / GAP-2: clean nav scaffolding and re-key subsection entries
        # ONCE, for every file, BEFORE dispatch. Previously
        # _clean_kanoon_artifacts was reachable from only two handlers, so the
        # 883 chunks (22.5%) that still carried scaffolding were exactly the
        # files routed elsewhere - NI Act 1881 (252/252) and Transfer of
        # Property (344/357) both take the generic path.
        sections = self._normalize_sections(sections)

        logger.info(f"Processing {file_path.name}: {len(sections)} raw entries, "
                    f"format={fmt_type}")
        
        if fmt_type == 'number-based':
            records = self._process_number_based(sections, act_name, file_path)
        elif fmt_type == 'number-with-title':
            records = self._process_number_with_title(sections, act_name, file_path)
        elif fmt_type == 'chunk-based':
            records = self._process_chunk_based(sections, act_name, file_path)
        elif fmt_type == 'marker-based':
            records = self._process_marker_based(sections, act_name, file_path)
        elif fmt_type == 'monolithic':
            records = self._process_monolithic(sections, act_name, file_path)
        else:
            # Fallback: treat as generic
            records = self._process_generic(sections, act_name, file_path)
        
        logger.info(f"  -> Produced {len(records)} chunks for {act_name}")
        return records

    def _detect_format(self, sections: List[Dict], format_hint: str) -> str:
        """
        Auto-detect the format of statute data.

        Robustness: this runs BEFORE _normalize_sections, and the corpus
        contains entries that are plain strings rather than dicts (the same
        shape that used to raise "'str' object has no attribute 'get'" in
        production). Every field read here therefore goes through _field().
        """
        def _field(s, key, default=''):
            if isinstance(s, dict):
                v = s.get(key, default)
            else:
                v = default
            return '' if v is None else str(v)

        def _size(s):
            return len(_field(s, 'content'))

        # Check for monolithic (single massive entry)
        if len(sections) == 1 and _size(sections[0]) > 50000:
            return 'monolithic'
        
        # Check if sections have real section numbers (not "Chunk N")
        sample = sections[:10]
        chunk_titled = sum(1 for s in sample
                         if re.match(r'^Chunk\s+\d+$', _field(s, 'section_title').strip()))
        if sample and chunk_titled > len(sample) * 0.5:
            return 'chunk-based'
        
        # Check for a massive entry ANYWHERE (marker-based: full act text plus
        # per-section / per-subsection entries).
        #
        # GAP-1 FIX: this used to look only at sections[0]. For
        # Consumer_Protection_Act_2019 and The_Companies_Act_1956 the bulk act
        # text is at idx 0 and idx 411 respectively - but idx 0 is a 50,548-char
        # Section-1 blob in the Companies Act file, i.e. it cleared the old
        # 50,000 threshold by luck, not by design. Taking the max over ALL
        # entries is what the handler now actually parses, so detect on the max.
        if len(sections) > 1 and max((_size(s) for s in sections), default=0) > 50000:
            return 'marker-based'
        
        # Check if section_numbers look like real numbers (plain "123" or "123.")
        real_nums = sum(1 for s in sample
                       if re.match(r'^\d+[A-Z]{0,3}\.?$', _field(s, 'section_number').strip()))
        if sample and real_nums > len(sample) * 0.5:
            return 'number-based'
        
        # Check for "number-with-title" format where section_number contains "N. Title"
        # e.g., "1. Short title, extent and commencement."
        num_with_title = sum(1 for s in sample
                            if re.match(r'^\d+[A-Z]{0,3}\.\s+\S',
                                        _field(s, 'section_number').strip()))
        if sample and num_with_title > len(sample) * 0.5:
            return 'number-with-title'
        
        # Use format hint if provided (but NOT marker-based for small section counts)
        if format_hint in ('chunk-based', 'number-based'):
            return format_hint
        
        return 'generic'

    # ==================== NORMALISATION / EMISSION ====================

    @staticmethod
    def _normalize_act_name(name: str) -> str:
        """Collapse a scraped act title to a stable comparison form."""
        return re.sub(r'\s+', ' ', str(name)).strip().strip(',. ')

    @classmethod
    def _same_act(cls, a: str, b: str) -> bool:
        """True when two act titles denote the same statute."""
        def norm(x):
            return re.sub(r'[^a-z0-9]', '', str(x).lower())
        return bool(norm(a)) and norm(a) == norm(b)

    def _resolve_parent_section(self, content: str) -> str:
        """
        GAP-2: pull the enclosing statutory section number out of a chunk
        header. Must be called on RAW content - every one of these forms is
        navigation scaffolding that _clean_kanoon_artifacts strips.

        Returns '' when no parent can be read.
        """
        if not content:
            return ''
        for pattern in self.PARENT_PATTERNS:
            m = pattern.search(content)
            if m:
                return m.group(1)
        return ''

    def _normalize_sections(self, sections: List[Dict]) -> List[Dict]:
        """
        GAP-1 + GAP-2 + GAP-9, applied uniformly to EVERY file before the
        format handler runs.

        Per entry this:
          1. resolves the parent section number from the raw header and threads
             it forward (GAP-2 - subsection entries are re-keyed "345(a)"
             instead of being dropped or left as a bare "(a)");
          2. classifies the entry as full_text / section / subsection / other,
             using the "Union of India - Act" header rather than index 0
             (GAP-1 - the act body is not always the first entry);
          3. cleans Kanoon navigation scaffolding (GAP-9 - this used to run in
             only two handlers, which is why 883 chunks kept the scaffolding);
          4. resolves the real act title for embedded acts, because the stored
             label lies (CPA 2019 idx 248 is labelled "2 of 1974" but holds the
             Code of Criminal Procedure, 1973).

        Handlers then read the normalised keys and never see the scaffolding.
        """
        normalized: List[Dict] = []
        current_parent = ''

        for i, raw in enumerate(sections):
            if not isinstance(raw, dict):
                normalized.append({
                    'content': str(raw or ''),
                    'section_number': str(i + 1),
                    'section_title': '',
                    'entry_kind': 'other',
                    'parent_section': current_parent,
                    'raw_section_number': '',
                    'embedded_act': '',
                    'sub_label': '',
                })
                continue

            content = str(raw.get('content', '') or '')
            raw_num = str(raw.get('section_number', '') or '').strip()
            raw_title = str(raw.get('section_title', '') or '').strip()

            # --- GAP-2: parent from the raw header, before cleaning --------
            parent = self._resolve_parent_section(content) or current_parent

            # --- GAP-1: classify -------------------------------------------
            is_act_body = bool(self.KANOON_ACT_HEADER_PATTERN.match(content))
            embedded_act = ''
            if is_act_body:
                title_m = self.KANOON_ACT_TITLE_PATTERN.match(content)
                if title_m:
                    embedded_act = self._normalize_act_name(title_m.group(1))

            sub_m = self.SUBSECTION_LABEL_PATTERN.match(raw_num)
            label = raw_num.rstrip('.')
            is_plain_section = bool(re.match(r'^\d+[A-Z]{0,3}$', label))

            if is_act_body:
                kind = 'full_text'
            elif sub_m:
                kind = 'subsection'
            elif is_plain_section:
                kind = 'section'
            elif len(content) > self.FULLTEXT_MIN_CHARS:
                # Unlabelled bulk text: keep it rather than discard it.
                kind = 'full_text'
            else:
                kind = 'other'

            # --- GAP-2: compound section key -------------------------------
            if kind == 'subsection' and sub_m:
                sub_label = sub_m.group(1).strip()
                if parent:
                    key = f"{parent}({sub_label})"
                else:
                    # No parent resolvable anywhere: keep the label but mark it
                    # as unkeyed rather than inventing a section number.
                    key = f"({sub_label})"
            elif is_plain_section:
                key = label
            elif kind == 'full_text':
                key = embedded_act or raw_num or f"entry_{i + 1}"
            else:
                key = raw_num or f"entry_{i + 1}"

            # A plain section entry becomes the parent for following entries
            # that carry no header of their own.
            if kind == 'section':
                current_parent = label

            title = raw_title
            if kind == 'subsection' or title == raw_num:
                # "(1)" / "(a)" as a title is the label, not a title.
                title = ''

            entry = dict(raw)
            entry.update({
                # --- GAP-9: clean on every path -----------------------------
                'content': self._clean_kanoon_artifacts(content),
                'section_number': key,
                'section_title': title,
                'entry_kind': kind,
                'parent_section': parent,
                'raw_section_number': raw_num,
                'embedded_act': embedded_act,
                'sub_label': sub_m.group(1).strip() if sub_m else '',
            })
            normalized.append(entry)

        return normalized

    def _emit_record(self, bucket: List[Dict], *, act_name: str,
                     file_path: Path, section_number: str,
                     section_title: str, content: str,
                     chapter: str = '', source_type: str = '',
                     id_tag: str = 'c',
                     extra_meta: Optional[Dict] = None) -> None:
        """
        GAP-4: the single place a chunk record is created.

        Centralising it guarantees the invariant that was violated:
          * every (source_file, section_number, chunk_index) triple is unique -
            chunk_index is allocated from a running counter per (file, section)
            instead of restarting at 0 in each handler. Measured before the
            fix: 150 colliding groups across 524 records, because
            `full_text_parse` and `kanoon_section` both emitted section 1 of
            Consumer Protection Act with chunk_index 0.
          * chunk ids are unique by construction, with a deterministic `_r<n>`
            fallback if anything still clashes.
        """
        section_number = str(section_number).strip() or 'unknown'
        section_title = str(section_title or '').strip()
        if section_title == section_number:
            section_title = ''

        chunks = self._build_section_chunks(
            act_name=act_name,
            section_number=section_number,
            section_title=section_title,
            content=content,
            chapter=chapter
        )
        if not chunks:
            return

        seq_key = (self._file_key, section_number)
        base_index = self._chunk_seq.get(seq_key, 0)
        emitted = []

        for sub_index, chunk_text in enumerate(chunks):
            chunk_index = self._chunk_seq.get(seq_key, 0)
            self._chunk_seq[seq_key] = chunk_index + 1

            chunk_id = f"D8_{self._file_key}_{id_tag}{section_number}_{chunk_index}"
            self._id_seq[chunk_id] = self._id_seq.get(chunk_id, 0) + 1
            if self._id_seq[chunk_id] > 1:
                chunk_id = f"{chunk_id}_r{self._id_seq[chunk_id]}"

            metadata = {
                'domain': 'statutes',
                'act': act_name,
                'section_number': section_number,
                'section_title': section_title,
                'chapter': chapter,
                'source_file': file_path.name,
                'source_type': source_type,
                'chunk_index': chunk_index,
                'sub_index': sub_index,
                'section_chunk_offset': base_index,
                'total_chunks': len(chunks),
            }
            if extra_meta:
                metadata.update({k: v for k, v in extra_meta.items()
                                 if v not in (None, '')})

            record = {
                'id': self._sanitize_id(chunk_id),
                'text': chunk_text,
                'metadata': metadata,
            }
            bucket.append(record)
            emitted.append(record)

    def _process_number_based(self, sections: List[Dict], act_name: str, 
                               file_path: Path) -> List[Dict]:
        """
        Process well-structured statutes (Indian Contract Act style).
        Each section already has correct section_number and section_title.
        Just need to add context headers and handle oversized sections.
        """
        records = []
        current_chapter = ""
        
        for i, section in enumerate(sections):
            sec_num = str(section.get('section_number', str(i + 1))).strip()
            sec_title = str(section.get('section_title', '')).strip()
            content = section.get('content', '').strip()
            
            if not content:
                continue
            
            # Detect chapter changes from content
            chapter_match = self.CHAPTER_PATTERN.search(content)
            if chapter_match:
                current_chapter = chapter_match.group(0).strip()
            
            # Build structured text
            self._emit_record(
                records,
                act_name=act_name,
                file_path=file_path,
                section_number=sec_num,
                section_title=sec_title,
                content=content,
                chapter=current_chapter,
                source_type='number_based',
                id_tag='s',
            )
        
        return records

    def _process_number_with_title(self, sections: List[Dict], act_name: str,
                                    file_path: Path) -> List[Dict]:
        """
        Process statutes where section_number contains "N. Title text"
        (Competition Act, Partnership Act, Sale of Goods Act style).
        Parse the real section number and title from the compound field.
        """
        records = []
        
        for i, section in enumerate(sections):
            raw_num = str(section.get('section_number', '')).strip()
            content = section.get('content', '').strip()
            
            if not content:
                continue
            
            # Parse "N. Title text" from section_number
            num_title_match = re.match(r'^(\d+[A-Z]?)\.\s*(.*)', raw_num)
            if num_title_match:
                sec_num = num_title_match.group(1)
                sec_title = num_title_match.group(2).rstrip('.')
            else:
                sec_num = raw_num
                sec_title = str(section.get('section_title', '')).strip()
            
            self._emit_record(
                records,
                act_name=act_name,
                file_path=file_path,
                section_number=sec_num,
                section_title=sec_title,
                content=content,
                chapter='',
                source_type='number_with_title',
                id_tag='s',
            )
        
        return records

    def _process_chunk_based(self, sections: List[Dict], act_name: str,
                              file_path: Path) -> List[Dict]:
        """
        Process BNS-style data where each entry has "--- Section X ---" markers
        and section_title is just "Chunk N" (useless).
        Parse the real section info from the content.
        """
        records = []
        current_chapter = ""
        
        for i, section in enumerate(sections):
            content = section.get('content', '').strip()
            if not content:
                continue
            
            # Parse the structured content: --- Section X ---\nACT\nChapter Y\nS.\nN\nTitle\nDescription\nContent
            parsed = self._parse_chunk_marker_content(content)
            
            if parsed:
                sec_num = parsed['section_number']
                sec_title = parsed['section_title']
                body = parsed['body']
                if parsed.get('chapter'):
                    current_chapter = parsed['chapter']
            else:
                # Fallback: use what we have.
                # GAP: `section` is only a dict for dict-shaped input. The
                # corpus also yields plain strings here, and the unguarded
                # .get() below raised
                #   "Query failed: 'str' object has no attribute 'get'"
                # in production. Handle both shapes safely.
                if isinstance(section, dict):
                    sec_num = str(section.get('section_number', str(i + 1))).strip()
                    sec_title = str(section.get('section_title', '')).strip()
                else:
                    sec_num = str(section).strip() or str(i + 1)
                    sec_title = ''
                body = content
            
            if not body.strip():
                continue
            
            self._emit_record(
                records,
                act_name=act_name,
                file_path=file_path,
                section_number=sec_num,
                section_title=sec_title,
                content=body,
                chapter=current_chapter,
                source_type='chunk_based',
                id_tag='s',
            )
        
        return records

    def _process_marker_based(self, sections: List[Dict], act_name: str,
                               file_path: Path) -> List[Dict]:
        """
        Process Consumer Protection Act / Companies Act 1956 style:
        - one or MORE entries hold entire act bodies (100K - 1.4M chars)
        - the remaining entries are individual sections/subsections from Kanoon

        GAP-1 FIX. The old version did `full_text = sections[0]` and iterated
        `sections[1:]`, i.e. it assumed the act body is entry 0. That is false:
          Consumer_Protection_Act_2019  631 entries, 1,826,930 chars
              idx 0     126,915  the act body
              idx 66    143,294  Food Safety & Standards Act, 2006
              idx 248   824,097  Code of Criminal Procedure, 1973
              idx 400   276,009  Act 7 of 2017
              idx 401    71,161  Act 68 of 1986
          The_Companies_Act_1956       2,043 entries, 2,825,202 chars
              idx 0      50,548  Section 1 (Objects and Reasons), NOT the act
              idx 96     68,052  Chartered Accountants Act, 1949
              idx 411  1,404,197  the act body
        Entry 0 alone covered 8.4% / 28.8% of the two acts and the rest of the
        statute was silently dropped - ~233,303 unique shingles.

        This version walks EVERY entry:
          * act-body entries are split into sections, under the act's real
            title read from the "Union of India - Act" header (the stored label
            is unreliable - CPA 2019 idx 248 is labelled "2 of 1974" but holds
            the Code of Criminal Procedure, 1973);
          * section entries are emitted;
          * subsection entries are EMITTED with a compound "345(a)" key built by
            threading the parent section, instead of being `continue`d away
            (GAP-2 - that `continue` deleted 458 entries for CPA 2019 and 1,614
            for Companies Act 1956).
        """
        records = []

        for section in sections:
            content = str(section.get('content', '') or '').strip()
            if not content:
                continue

            kind = section.get('entry_kind', 'other')
            sec_num = str(section.get('section_number', '')).strip()
            sec_title = str(section.get('section_title', '')).strip()
            embedded_act = str(section.get('embedded_act', '') or '').strip()

            # ---- act body entries, at ANY index ------------------------
            if kind == 'full_text':
                if len(content) < 10000:
                    continue
                body_act = embedded_act or act_name
                extra = {}
                if embedded_act and not self._same_act(embedded_act, act_name):
                    # Real, cited legislation that happens to be bundled inside
                    # this file. Index it under its own act and record where it
                    # came from rather than mislabel it as the parent act.
                    extra = {
                        'embedded_in_act': act_name,
                        'embedded_label': str(section.get('raw_section_number', '')),
                    }
                else:
                    body_act = act_name
                records.extend(self._split_full_act_text(
                    content, body_act, file_path, source_type='full_text_parse',
                    extra_meta=extra))
                continue

            # ---- everything else is a scoped entry --------------------
            if not sec_num:
                continue

            # GAP-2: subsection entries are re-keyed by _normalize_sections
            # into "345(a)". They are emitted, not skipped.
            if kind == 'subsection':
                extra = {'parent_section': section.get('parent_section', '')}
                if section.get('sub_label'):
                    extra['subsection_label'] = section['sub_label']
                self._emit_record(
                    records,
                    act_name=act_name,
                    file_path=file_path,
                    section_number=sec_num,
                    section_title=sec_title,
                    content=content,
                    chapter='',
                    source_type='kanoon_subsection',
                    id_tag='u',
                    extra_meta=extra,
                )
                continue

            if len(content) < self.MIN_EMIT_CHARS:
                continue

            self._emit_record(
                records,
                act_name=act_name,
                file_path=file_path,
                section_number=sec_num,
                section_title=sec_title,
                content=content,
                chapter='',
                source_type='kanoon_section',
                id_tag='k',
                extra_meta={'parent_section': section.get('parent_section', '')},
            )

        return records

    def _process_monolithic(self, sections: List[Dict], act_name: str,
                             file_path: Path) -> List[Dict]:
        """
        Process single-entry statutes (Companies Act 2013 style).
        The entire act is in one massive content field.
        """
        full_text = str(sections[0].get('content', '') or '')
        # GAP-1: the single entry may be an act other than the file's nominal
        # act (Companies Act 2013 files carry one embedded act body).
        body_act = str(sections[0].get('embedded_act', '') or '').strip() or act_name
        if not self._same_act(body_act, act_name):
            return self._split_full_act_text(
                full_text, body_act, file_path, source_type='full_text_parse',
                extra_meta={'embedded_in_act': act_name})
        return self._split_full_act_text(full_text, act_name, file_path)

    def _process_generic(self, sections: List[Dict], act_name: str,
                          file_path: Path) -> List[Dict]:
        """
        Fallback processor for unrecognized formats.

        GAP-2/GAP-9: this handler used to pass `section_number` through
        untouched and never clean, which is exactly why NI Act 1881
        (252/252) and Transfer of Property (344/357) were the GAP-9 outliers.
        Normalisation has already run by this point, so subsection keys arrive
        as "4(a)" and the content is already free of nav scaffolding.
        """
        records = []
        for i, section in enumerate(sections):
            content = str(section.get('content', '') or '').strip()
            if not content:
                continue

            sec_num = str(section.get('section_number', str(i + 1))).strip()
            sec_title = str(section.get('section_title', '') or '').strip()
            kind = str(section.get('entry_kind', '') or 'other')

            if kind == 'full_text':
                # Unlabelled bulk text: keep it rather than drop it.
                body_act = str(section.get('embedded_act', '') or '').strip() or act_name
                records.extend(self._split_full_act_text(
                    content, body_act, file_path, source_type='full_text_parse'))
                continue

            if len(content) < self.MIN_EMIT_CHARS:
                continue

            self._emit_record(
                records,
                act_name=act_name,
                file_path=file_path,
                section_number=sec_num,
                section_title=sec_title,
                content=content,
                chapter='',
                source_type=('kanoon_subsection' if kind == 'subsection'
                             else 'generic'),
                id_tag=('u' if kind == 'subsection' else 'g'),
                extra_meta={'parent_section': section.get('parent_section', '')},
            )

        return records

    # ==================== CORE PARSING METHODS ====================

    def _strip_chunk_preamble(self, content: str) -> str:
        """Remove the leading "Act:/Section:/Content:" preamble that the
        ingestion writer prepends, so marker parsing sees the raw chunk body.

        The stored corpus carries this preamble, which is why an anchored
        .match() never fired and every BNS section_number came out off by one.
        Tolerates the preamble after leading whitespace/blank lines.
        """
        if not content:
            return content
        text = content.lstrip()
        # The stored form is "Act: ...\nSection: ...\nContent: ..." - THREE
        # labelled lines. A two-iteration stripper left "Content: " in front of
        # the marker and the match still failed, so loop until no labelled
        # preamble line remains, with a hard bound for safety.
        for _ in range(8):
            m = re.match(r'(?is)\A(?:Act|Section|Content|Title|Chapter)\s*:[^\n]*\n?',
                         text)
            if not m:
                break
            text = text[m.end():].lstrip()
        return text

    def _parse_chunk_marker_content(self, content: str) -> Optional[Dict]:
        """
        Parse BNS-style chunk content:
        --- Section 302 ---
        BNS
        Chapter XVI
        S.
        302
        Punishment for murder.
        Description
        <actual content>
        """
        # GAP-5 FIX: this used MARKER_PATTERN.match(content), which anchors at
        # position 0. Stored chunks begin with an "Act: ...\nSection: ...
        #\nContent: ..." preamble, so .match() always returned None and every
        # BNS chunk's metadata section_number came out off by one relative to
        # the "--- Section N ---" marker actually present in its body
        # (measured 357/357 wrong, delta +1 for 354 chunks).
        #
        # ROOT CAUSE, confirmed against the real corpus: the marker is NOT at
        # the start of a line. A stored chunk reads
        #     Act: Bharatiya Nyaya Sanhita 2023
        #     Section: 3 (Chunk 3)
        #     Content: --- Section 1 ---
        # so the line-anchored MARKER_PATTERN ("^---") can never fire: the
        # marker is preceded by "Content: " on the same line. Note also that the
        # "Section:" metadata line holds a synthetic "Chunk N" value, NOT the
        # statutory number - only the body marker is authoritative.
        #
        # Use the unanchored marker pattern so the real section number is read
        # from the body.
        marker_match = self.MARKER_INLINE_PATTERN.search(content)
        if not marker_match:
            return None

        sec_num = marker_match.group(1)
        rest = content[marker_match.end():].strip()
        
        lines = rest.split('\n')
        chapter = ''
        section_title = ''
        body_start = 0
        
        # Parse header fields
        for idx, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Skip act name abbreviation (e.g., "BNS")
            if idx == 0 and len(line_stripped) < 10 and not line_stripped.startswith('Chapter'):
                continue
            
            # Chapter line
            if line_stripped.startswith('Chapter') or line_stripped.startswith('CHAPTER'):
                chapter = line_stripped
                continue
            
            # "S." marker (section prefix)
            if line_stripped == 'S.':
                continue
            
            # Section number line (matches our section number)
            if line_stripped == sec_num:
                continue
            
            # "Description" marker
            if line_stripped == 'Description':
                body_start = idx + 1
                break
            
            # This is likely the section title
            if not section_title and len(line_stripped) > 3:
                section_title = line_stripped.rstrip('.')
                continue
            
            # If we haven't found "Description" but we're past the header
            if idx > 6:
                body_start = idx
                break
        
        body = '\n'.join(lines[body_start:]).strip() if body_start < len(lines) else rest
        
        return {
            'section_number': sec_num,
            'section_title': section_title,
            'chapter': chapter,
            'body': body
        }

    def _split_full_act_text(self, full_text: str, act_name: str,
                              file_path: Path,
                              source_type: str = 'full_text_parse',
                              extra_meta: Optional[Dict] = None) -> List[Dict]:
        """
        Split a full act text into individual section chunks.
        Handles the main act parsing by finding section boundaries.

        GAP-1: `act_name` may be an EMBEDDED act's own title, because the same
        method now parses every act-body entry in a file, not just entry 0.
        """
        records = []
        
        # Clean the text first (idempotent - normally already done by
        # _normalize_sections, kept so direct callers are still safe)
        text = self._clean_kanoon_artifacts(full_text)
        
        # Find all section starts: "N. Title text" or standalone "N.\n"
        # We look for section markers at the start of a line
        section_pattern = re.compile(
            r'^(\d+[A-Z]?)\.\s*\n(.+?)(?=\n\d+[A-Z]?\.\s*\n|\Z)',
            re.MULTILINE | re.DOTALL
        )
        
        # Also try the pattern with title on same line
        section_pattern_titled = re.compile(
            r'^(\d+[A-Z]?)\.\s+([A-Z][^\n]+?)(?:\.—|—|-)\s*\n(.+?)(?=\n\d+[A-Z]?\.\s|\Z)',
            re.MULTILINE | re.DOTALL
        )
        
        # Try to find chapter-aware sections
        # First, detect all chapter boundaries
        chapters = list(self.CHAPTER_PATTERN.finditer(text))
        
        # Find sections using the simpler pattern first
        matches = list(section_pattern.finditer(text))
        
        if not matches:
            # Try the titled pattern
            matches_titled = list(section_pattern_titled.finditer(text))
            if matches_titled:
                self._emit_leading_matter(
                    records, text, matches_titled[0].start(), act_name, file_path,
                    source_type, extra_meta)
                for m in matches_titled:
                    sec_num = m.group(1)
                    sec_title = m.group(2).strip()
                    body = m.group(3).strip()
                    chapter = self._find_chapter_for_position(chapters, m.start(), text)
                    
                    self._emit_record(
                        records,
                        act_name=act_name,
                        file_path=file_path,
                        section_number=sec_num,
                        section_title=sec_title,
                        content=body,
                        chapter=chapter,
                        source_type=source_type,
                        id_tag='f',
                        extra_meta=extra_meta,
                    )
            else:
                # Last resort: split by paragraphs with size limits
                records.extend(self._fallback_paragraph_split(text, act_name, file_path))
        else:
            current_chapter = ''
            self._emit_leading_matter(
                records, text, matches[0].start(), act_name, file_path,
                source_type, extra_meta)
            for m_idx, m in enumerate(matches):
                sec_num = m.group(1)
                body = m.group(2).strip()
                
                # Extract title from first line of body
                first_line = body.split('\n')[0].strip() if body else ''
                sec_title = ''
                
                # Check if first line looks like a title
                if first_line and len(first_line) < 120 and not first_line.startswith('('):
                    sec_title = first_line.rstrip('.').rstrip('—').rstrip('-').strip()
                    body = '\n'.join(body.split('\n')[1:]).strip()
                
                # Find chapter context
                chapter = self._find_chapter_for_position(chapters, m.start(), text)
                if chapter:
                    current_chapter = chapter
                
                self._emit_record(
                    records,
                    act_name=act_name,
                    file_path=file_path,
                    section_number=sec_num,
                    section_title=sec_title,
                    content=body,
                    chapter=current_chapter,
                    source_type=source_type,
                    id_tag='f',
                    extra_meta=extra_meta,
                )
        
        if not any(r['metadata'].get('source_type') != 'act_preamble' for r in records):
            # Absolute fallback: no section boundary was recognised at all, so
            # the body still has to be emitted by paragraph. (The check must
            # ignore the leading-matter chunk, otherwise a preamble-only match
            # would suppress the fallback and drop the whole act body.)
            records.clear()
            records.extend(self._fallback_paragraph_split(text, act_name, file_path))
        
        return records

    def _emit_leading_matter(self, bucket: List[Dict], text: str,
                             first_section_start: int,
                             act_name: str, file_path: Path,
                             source_type: str = 'full_text_parse',
                             extra_meta: Optional[Dict] = None) -> None:
        """
        Emit the text that precedes the first recognised section boundary.

        GAP-1 follow-on: `section_pattern` only matches from the first
        "N.\\n" line onwards, so everything before it - the act title, the
        gazette/commencement block, the "[Amended by ...]" history and, for
        several acts, the whole "Statement of Objects and Reasons" - was
        silently discarded.

        Measured cost of that gap before this method existed: routing
        The_Industrial_Disputes_Act_1947.json through this parser dropped
        ~31,000 of 188,000 characters (98.31% -> 78.54% shingle retention,
        because the generic handler had previously kept the preamble inside a
        paragraph-split chunk). The same applies to Companies Amendment 2001,
        Depositories 1996 and SEBI 1992.
        """
        if first_section_start <= 0:
            return
        head = text[:first_section_start].strip()
        if len(head) < self.min_chunk_chars:
            return
        self._emit_record(
            bucket,
            act_name=act_name,
            file_path=file_path,
            section_number='preamble',
            section_title='Act header, commencement and pre-section material',
            content=head,
            chapter='',
            source_type='act_preamble',
            id_tag='a',
            extra_meta=extra_meta,
        )

    def _fallback_paragraph_split(self, text: str, act_name: str, 
                                   file_path: Path) -> List[Dict]:
        """
        Last resort: split by paragraphs with context-preserving headers.
        Used when no section boundaries can be detected.
        """
        records = []
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        current_chunk = ""
        chunk_idx = 0
        
        for para in paragraphs:
            if len(current_chunk) + len(para) < self.max_chunk_chars:
                current_chunk += '\n\n' + para if current_chunk else para
            else:
                if current_chunk:
                    self._emit_record(
                        records,
                        act_name=act_name,
                        file_path=file_path,
                        section_number=f'para_{chunk_idx}',
                        section_title='',
                        content=current_chunk,
                        chapter='',
                        source_type='paragraph_split',
                        id_tag='p',
                    )
                    chunk_idx += 1
                current_chunk = para
        
        # Flush remaining
        if current_chunk:
            self._emit_record(
                records,
                act_name=act_name,
                file_path=file_path,
                section_number=f'para_{chunk_idx}',
                section_title='',
                content=current_chunk,
                chapter='',
                source_type='paragraph_split',
                id_tag='p',
            )
        
        return records

    # ==================== TEXT BUILDING METHODS ====================

    def _build_section_chunks(self, act_name: str, section_number: str,
                               section_title: str, content: str,
                               chapter: str = '') -> List[str]:
        """
        Build one or more text chunks for a section.
        Adds structural header and splits if content exceeds max size.
        
        Returns list of chunk strings (usually just one).
        """
        # Build the context header that appears at the top of every chunk
        header_parts = [f"Act: {act_name}"]
        if chapter:
            header_parts.append(f"Chapter: {chapter}")
        
        sec_label = f"Section {section_number}"
        if section_title and section_title != section_number:
            sec_label += f" - {section_title}"
        header_parts.append(sec_label)
        
        header = '\n'.join(header_parts)
        
        # Clean the content
        content = content.strip()
        if not content:
            return [header]
        
        full_text = f"{header}\n\n{content}"
        
        # If within size limit, return as single chunk
        if len(full_text) <= self.max_chunk_chars:
            return [full_text]
        
        # Need to sub-chunk: split at paragraph/subsection boundaries
        return self._sub_chunk_section(header, content)

    def _sub_chunk_section(self, header: str, content: str) -> List[str]:
        """
        Split an oversized section into sub-chunks while preserving:
        - The header context on each chunk
        - Paragraph/subsection boundaries
        - Proviso/Explanation/Illustration groupings
        """
        chunks = []
        
        # Split into logical segments (subsections, explanations, provisos)
        segments = self._split_into_segments(content)
        
        current_chunk_parts = []
        current_size = len(header) + 2  # +2 for \n\n
        
        for segment in segments:
            segment_size = len(segment)
            
            if current_size + segment_size + 1 <= self.max_chunk_chars:
                current_chunk_parts.append(segment)
                current_size += segment_size + 1
            else:
                # Flush current chunk
                if current_chunk_parts:
                    chunk_text = header + '\n\n' + '\n'.join(current_chunk_parts)
                    chunks.append(chunk_text)
                
                # Start new chunk with this segment
                if segment_size + len(header) + 2 <= self.max_chunk_chars:
                    current_chunk_parts = [segment]
                    current_size = len(header) + 2 + segment_size
                else:
                    # Segment itself is too big, force-split it
                    for sub in self._force_split(segment, self.max_chunk_chars - len(header) - 2):
                        chunks.append(header + '\n\n' + sub)
                    current_chunk_parts = []
                    current_size = len(header) + 2
        
        # Flush remaining
        if current_chunk_parts:
            chunk_text = header + '\n\n' + '\n'.join(current_chunk_parts)
            chunks.append(chunk_text)
        
        return chunks if chunks else [header + '\n\n' + content[:self.max_chunk_chars]]

    def _split_into_segments(self, content: str) -> List[str]:
        """
        Split content into logical segments at subsection/paragraph boundaries.
        Preserves Provisos, Explanations, and Illustrations with their parent.
        """
        # Split at subsection markers: (1), (2), (a), (b), etc.
        # Also split at Explanation, Proviso, Illustration markers
        segment_pattern = re.compile(
            r'\n(?=\(\d+\)\s|\([a-z]\)\s|Explanation\b|Proviso\b|Illustration\b|PROVIDED\b|Schedule\b)',
            re.MULTILINE
        )
        
        parts = segment_pattern.split(content)
        
        # If we get good segments, return them
        if len(parts) > 1:
            return [p.strip() for p in parts if p.strip()]
        
        # Fallback: split by double newlines (paragraphs)
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        
        if len(paragraphs) > 1:
            return paragraphs
        
        # Last resort: return as-is (will be force-split later if needed)
        return [content]

    def _force_split(self, text: str, max_size: int) -> List[str]:
        """Force-split text at sentence boundaries when it exceeds max_size."""
        if len(text) <= max_size:
            return [text]
        
        chunks = []
        current = ""
        
        # Split at sentence boundaries (period followed by space/newline)
        sentences = re.split(r'(?<=[.;])\s+', text)
        
        for sent in sentences:
            if len(current) + len(sent) + 1 <= max_size:
                current += ' ' + sent if current else sent
            else:
                if current:
                    chunks.append(current.strip())
                if len(sent) > max_size:
                    # Even a single sentence is too big, hard split
                    for start in range(0, len(sent), max_size - OVERLAP_CHARS):
                        chunks.append(sent[start:start + max_size])
                else:
                    current = sent
                    continue
                current = ""
        
        if current:
            chunks.append(current.strip())
        
        return chunks

    # ==================== UTILITY METHODS ====================

    def _find_chapter_for_position(self, chapters: list, pos: int, text: str) -> str:
        """Find the chapter heading that applies to a given text position."""
        current_chapter = ''
        for ch_match in chapters:
            if ch_match.start() <= pos:
                current_chapter = ch_match.group(0).strip()
            else:
                break
        return current_chapter

    def _clean_kanoon_artifacts(self, text: str) -> str:
        """Remove Kanoon.org navigation artifacts from text.

        GAP-9 FIX: the previous patterns required the bracket contents on a
        single line, e.g.
            [\\s*\\n*(?:Section\\s+\\d+|Entire\\s+Act)\\s*\\n*]
        but the scraped corpus splits them across three lines:
            [\\n\\nSection 1\\n\\n]
        so the cleaner was effectively a NO-OP: 3,355 of 3,972 statute chunks
        (84.5%) still carried navigation scaffolding. These patterns are
        newline-tolerant (\\s matches \\n) and bounded so they cannot swallow
        real statutory text.
        """
        if not text:
            return text

        # Kanoon breadcrumb lines, e.g.
        #   "Section 137 in The Transfer Of Property Act, 1882"
        #   "Section 111A(7) in The Companies Act, 1956"
        #   "Section 1(1) in Consumer Protection Act, 2019"
        #   "Section 2(6)(a) in Consumer Protection Act, 2019"  <- nested
        # These were the single largest surviving GAP-9 source: 504 chunks.
        # Line-anchored so a mid-sentence "... as in Section 9 ..." is safe.
        # The qualifier group repeats, so nested "(6)(a)" is consumed whole -
        # a single optional group left the breadcrumb behind.
        text = re.sub(
            r'^[ \t]*Section\s+\d+[A-Z]{0,3}\s*(?:\([^)\n]{1,32}\))*[ \t]+in[ \t]+'
            r'[A-Z][^\n]{0,90}[ \t]*\n?',
            '', text, flags=re.MULTILINE)

        # Bracketed nav tokens, including multi-line forms. GAP-9: this
        # required "Section" + digits, but the corpus also carries bare
        # "[\nSubsection\n]" and "[Section 111A in ...]" forms.
        text = re.sub(
            r'\[\s*(?:Section|Subsection|Entire\s+Act)[^\]\[]{0,140}\]',
            '', text, flags=re.DOTALL)

        # "Union of India - Section/Subsection/Act" nav headers (line-continued
        # forms included).
        text = re.sub(
            r'Union of India\s*-\s*(?:Section|Subsection|Act)[^\n]{0,120}\n?',
            '', text, flags=re.DOTALL)

        # Bare "Union of India - " prefixes left behind.
        text = re.sub(r'^\s*Union of India\s*-\s*', '', text, flags=re.MULTILINE)

        # Whitespace-only lines left where bracketed tokens were removed
        # (the corpus writes "[\nEntire Act\n]\n \n [\n..."). Clearing them
        # keeps the anchors above reliable and stops " " padding lines
        # surviving into chunk bodies.
        text = re.sub(r'^[ \t]+$', '', text, flags=re.MULTILINE)

        # Collapse >2 consecutive newlines.
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    @staticmethod
    def _sanitize_id(chunk_id: str) -> str:
        """Sanitize chunk ID to be safe for vector store keys."""
        # Replace spaces, dots, special chars with underscores
        return re.sub(r'[^a-zA-Z0-9_-]', '_', chunk_id)


# ==================== VERIFICATION: DECLARED vs BODY ====================
#
# Task 6 acceptance requires a reusable off-by-one audit. A section's
# authoritative number is the "--- Section N ---" marker inside its own body;
# the `section_number` field stored beside it is only a label, and a corrupt
# scrape can carry it one out of step with the text it wraps. In
# Bharatiya_Nyaya_Sanhita_2023.json that label is body+1 on 357 of 358 entries,
# which is how the corpus ended up holding Section 318's text under the label
# 319. Counting the disagreements mechanically is the only way to prove an
# ingestion run is clean.
#
# The marker shape is deliberately the same as MARKER_INLINE_PATTERN: a stored
# chunk can carry the marker after a "Content: " prefix, so it is searched for
# anywhere rather than only at the start of a line.

BODY_SECTION_MARKER = re.compile(r'---\s*(?:Section\s+)?(\d+[A-Z]{0,3})\s*---')


def _normalise_section_label(value: Any) -> str:
    """Reduce a section label to a comparable form: '  Section 319. ' -> '319'."""
    text = re.sub(r'\s+', '', str(value if value is not None else ''))
    text = re.sub(r'^section', '', text, flags=re.IGNORECASE)
    return text.rstrip('.')


def _declared_and_body(item: Any) -> Tuple[str, str]:
    """Pull (declared label, body text) out of either supported input shape.

    Accepts raw statute-JSON sections ({'section_number', 'content'}) and
    emitted chunk records ({'metadata': {'section_number'}, 'text'}), so one
    audit works against the sources and against the ingestion output alike.
    """
    if not isinstance(item, dict):
        return '', ''
    metadata = item.get('metadata')
    if isinstance(metadata, dict) and 'text' in item:
        return (str(metadata.get('section_number', '') or ''),
                str(item.get('text') or ''))
    body = item.get('content')
    if body is None:
        body = item.get('text', '')
    return (str(item.get('section_number', '') or ''), str(body or ''))


def audit_declared_vs_body_sections(sections: Any) -> Dict[str, int]:
    """Compare every section's declared number against its body marker.

    Returns {'checked': n, 'mismatches': m}. `checked` counts only entries
    that actually carry a body marker: an entry without one is unverifiable,
    not wrong, so it is never scored as a mismatch.
    """
    checked = 0
    mismatches = 0
    for item in sections or []:
        declared, body = _declared_and_body(item)
        if not body:
            continue
        marker = BODY_SECTION_MARKER.search(body)
        if not marker:
            continue
        checked += 1
        if _normalise_section_label(declared) != _normalise_section_label(marker.group(1)):
            mismatches += 1
    return {'checked': checked, 'mismatches': mismatches}


def count_declared_vs_body_mismatches(sections: Any) -> int:
    """Reusable off-by-one counter: declared `section_number` vs body marker."""
    return audit_declared_vs_body_sections(sections)['mismatches']


# ==================== SOURCE SELECTION (Task 6) ====================
#
# The scraped statute directory holds MORE THAN ONE VARIANT of the same act:
#
#   Bharatiya_Nyaya_Sanhita_2023.json                          <- corrupt: the
#                                                                 declared
#                                                                 `section_number`
#                                                                 is body+1 on
#                                                                 357 of 358 entries
#   Bharatiya_Nyaya_Sanhita_2023_repaired.json                 <- clean
#   Bharatiya_Nyaya_Sanhita_2023.REPAIRED.json                 <- clean
#   Bharatiya_Nyaya_Sanhita_2023.backup_20261003_195801.json   <- junk
#   Bharatiya_Nyaya_Sanhita_2023.backup_20261003_200256.json   <- junk
#
# `statutes_dir.glob("*.json")` ingested all five, which measured as 1,975 BNS
# chunks out of 11,121 records - five near-identical copies of the same 395
# chunks - with the corrupt copy's labels contradicting the clean ones. That is
# the contradiction the deployed bot served when it answered that BNS S.319's
# punishment lives in S.318. Selection is therefore now explicit: junk is
# dropped, and exactly ONE source per act is ingested.

# Never ingested: rolled backups, .bak copies, and the run summary.
# `\.backup_.*$` (not `[^.]*$`) because the timestamped variant still carries
# the ".json" suffix: "Act_2023.backup_20261003_195801.json".
JUNK_STATUTE_FILE_PATTERN = re.compile(r'\.backup_.*$|\.bak$|^summary\.json$',
                                       re.IGNORECASE)

# Trailing repair decoration stripped when deriving an act key from a filename.
_ACT_KEY_DECORATION = re.compile(r'[._-]?repaired$', re.IGNORECASE)

# Leading article tokens that never distinguish one act from another. Stripped
# AFTER punctuation normalisation so "The_Negotiable_Instruments_Act_1881",
# "The Negotiable Instruments Act, 1881" and "the-negotiable-instruments-act-1881"
# all reduce to the same token sequence.
_LEADING_ACT_ARTICLES = frozenset({'the', 'a', 'an'})

# Preference tiers for choosing between variants of one act. LOWEST WINS.
_PREFERENCE_REPAIRED_WITH_PROVENANCE = 0
_PREFERENCE_REPAIRED = 1
_PREFERENCE_CANONICAL = 2
_PREFERENCE_OTHER = 3


def is_junk_statute_file(file_path: Path) -> bool:
    """True for rolled backups (*.backup_*), *.bak copies and summary.json."""
    return bool(JUNK_STATUTE_FILE_PATTERN.search(Path(file_path).name))


def act_key_for_file(file_path: Path) -> str:
    """Normalised act identity derived from a filename.

    'Bharatiya_Nyaya_Sanhita_2023.json', '..._2023_repaired.json' and
    '..._2023.REPAIRED.json' all map to 'bharatiya_nyaya_sanhita_2023', which is
    what groups the variants of one act.

    Leading articles ('The', 'A', 'An') and all punctuation are normalised away,
    so 'Negotiable_Instruments_Act_1881.json' and
    'The_Negotiable_Instruments_Act_1881.json' - one statute scraped twice under
    both its short and its formal title - map to the SAME key
    'negotiable_instruments_act_1881'.

    Why this is not unsafe: an article and punctuation carry no statutory
    identity, so stripping them cannot merge two different enactments. Every
    other discriminating token is kept verbatim, and in particular the YEAR is
    never touched, so 'The_Companies_Act_1956' and 'The_Companies_Act_2013'
    stay distinct ('companies_act_1956' vs 'companies_act_2013') and so do
    'Consumer_Protection_Act_2019' and 'The_Consumer_Protection_Act_1986'.

    The previous docstring claimed NOT stripping articles was "the safer error"
    because merging would drop a statute while failing to merge merely
    reintroduces duplication. That reasoning was wrong about the size of the
    terms: the un-merged case did not merely admit an extra variant, it let
    both copies of the Negotiable Instruments Act 1881 be ingested and compete
    with each other in RRF fusion (measured 251 + 154 = 405 records, 4.2% of
    the index, 148/255 sections duplicated). The error being guarded against
    was not reachable by stripping a leading article, so the guard only bought
    the defect.

    Genuinely decorated variants are still kept apart: 'Act_repaired-v2.json'
    normalises to 'act_repaired_v2', which is NOT 'act', so such a file keeps
    its own key and is still ingested alongside 'Act.json'.
    """
    stem = _ACT_KEY_DECORATION.sub('', Path(file_path).stem)
    key = re.sub(r'[^a-z0-9]+', '_', stem.lower()).strip('_')

    # Drop leading article tokens so the short and formal titles of one act
    # collide. Never strip the last token: a file called 'The.json' keeps the
    # key 'the' rather than collapsing to the empty string.
    tokens = key.split('_')
    while len(tokens) > 1 and tokens[0] in _LEADING_ACT_ARTICLES:
        tokens.pop(0)
    return '_'.join(tokens)


def _source_preference(file_path: Path) -> int:
    """Rank a candidate source within its act group. Lower is better.

    Preference order, documented and deterministic:
      1. ``*_repaired.json`` - the pf_repair_sections.py output. It carries the
         ``_repair`` provenance block and repaired section titles that the
         ``.REPAIRED`` copy lacks, so it wins when both are present.
      2. any other filename containing "repaired" (case-insensitive).
      3. the plain canonical name ("<Act>.json") - the normal single-source case.
      4. any other decorated variant (e.g. "Act (Copy)", "Act_v2").
    """
    name = Path(file_path).name
    stem = Path(file_path).stem
    if 'repaired' in name.lower():
        if re.search(r'_repaired$', stem, re.IGNORECASE):
            return _PREFERENCE_REPAIRED_WITH_PROVENANCE
        return _PREFERENCE_REPAIRED
    if re.sub(r'[^a-zA-Z0-9]+', '_', stem).strip('_') == stem:
        return _PREFERENCE_CANONICAL
    return _PREFERENCE_OTHER


def select_statute_source_files(statutes_dir: str | Path) -> List[Path]:
    """Choose exactly one ingestion source per act.

    Junk (backup/`.bak`/`summary.json`) is dropped outright. The rest are
    grouped by :func:`act_key_for_file` and the best-ranked file in each group
    wins, ties broken by filename so the choice is reproducible. Every choice
    and every skip is logged at INFO.

    When each act has a single source - the normal corpus - the returned list
    is exactly the old ``sorted(glob("*.json"))`` list minus the junk, so
    single-source acts behave identically to before.

    Args:
        statutes_dir: Directory holding the statute JSON files.

    Returns:
        Source files to ingest, in filename order.
    """
    statutes_dir = Path(statutes_dir)
    if not statutes_dir.exists():
        return []

    groups: Dict[str, List[Path]] = {}
    junk: List[str] = []
    for file_path in sorted(statutes_dir.glob("*.json")):
        if is_junk_statute_file(file_path):
            junk.append(file_path.name)
            continue
        groups.setdefault(act_key_for_file(file_path), []).append(file_path)

    selected: List[Path] = []
    duplicates_dropped = 0
    for act_key in sorted(groups):
        candidates = groups[act_key]
        chosen = sorted(candidates, key=lambda p: (_source_preference(p), p.name))[0]
        if len(candidates) > 1:
            duplicates_dropped += len(candidates) - 1
            skipped = ", ".join(c.name for c in candidates if c != chosen)
            logger.info(f"Act '{act_key}': {len(candidates)} source variants "
                        f"-> chose {chosen.name} (skipped: {skipped})")
        selected.append(chosen)

    # Keep the pre-fix ordering (filename order) so record ids and the
    # duplicate-id suffixing downstream behave identically for single-source acts.
    selected.sort(key=lambda p: p.name)

    for name in junk:
        logger.info(f"Skipping non-source statute file: {name}")
    logger.info(f"Statute source selection: {len(selected)} acts from "
                f"{sum(len(v) for v in groups.values())} candidate files "
                f"({len(junk)} junk skipped, "
                f"{duplicates_dropped} duplicate variant(s) dropped)")

    return selected


# ==================== CONVENIENCE FUNCTIONS ====================

def process_all_statutes(statutes_dir: str | Path, 
                          max_chunk_chars: int = MAX_CHUNK_CHARS) -> List[Dict]:
    """
    Process all statute JSON files in a directory.

    Ingestion reads ONE source per act (see
    :func:`select_statute_source_files`): backup/`.bak`/`summary.json` files
    are ignored and duplicate variants of an act are resolved by the documented
    preference order, so a corrupt scrape can no longer sit in the corpus
    beside its own repaired copy.

    Args:
        statutes_dir: Path to directory containing statute JSON files
        max_chunk_chars: Maximum characters per chunk

    Returns:
        List of properly chunked records ready for vector store ingestion
    """
    statutes_dir = Path(statutes_dir)
    if not statutes_dir.exists():
        logger.error(f"Statutes directory not found: {statutes_dir}")
        return []
    
    chunker = StatuteSectionChunker(max_chunk_chars=max_chunk_chars)
    all_records = []
    
    for file_path in select_statute_source_files(statutes_dir):
        records = chunker.process_statute_file(file_path)
        all_records.extend(records)
    
    logger.info(f"Total statute chunks produced: {len(all_records)}")

    # Deduplicate IDs: if the same ID appears more than once, suffix with _b2, _b3, ...
    seen_ids: dict = {}
    for record in all_records:
        rid = record['id']
        if rid in seen_ids:
            seen_ids[rid] += 1
            record['id'] = f"{rid}_b{seen_ids[rid]}"
        else:
            seen_ids[rid] = 1

    duplicates_fixed = sum(1 for v in seen_ids.values() if v > 1)
    if duplicates_fixed:
        logger.warning(f"Fixed {duplicates_fixed} duplicate chunk IDs by appending _b<n> suffix")

    return all_records


# ==================== CLI TEST ====================

if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    # Default to BACKUP_DATA path
    default_dir = Path(__file__).parent.parent.parent / "DATA" / "Statutes" / "json"
    backup_dir = Path(r"c:\Users\LOQ\Downloads\LAW-GPT_new\BACKUP_DATA\DATA\Statutes\json")
    
    statutes_dir = default_dir if default_dir.exists() else backup_dir
    
    if len(sys.argv) > 1:
        statutes_dir = Path(sys.argv[1])
    
    print(f"Processing statutes from: {statutes_dir}")
    
    records = process_all_statutes(statutes_dir)
    
    print(f"\n{'='*60}")
    print(f"TOTAL RECORDS: {len(records)}")
    
    # Print summary by act
    from collections import Counter
    act_counts = Counter(r['metadata']['act'] for r in records)
    print(f"\nBy Act:")
    for act, count in act_counts.most_common():
        print(f"  {act}: {count} chunks")
    
    # Print sample chunks
    print(f"\n{'='*60}")
    print("SAMPLE CHUNKS:")
    for r in records[:5]:
        print(f"\n--- ID: {r['id']} ---")
        print(f"Section: {r['metadata'].get('section_number')} | Title: {r['metadata'].get('section_title', '')[:60]}")
        print(f"Chapter: {r['metadata'].get('chapter', '')[:60]}")
        print(f"Text ({len(r['text'])} chars):")
        print(r['text'][:300])
        print("...")
