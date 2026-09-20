"""Conservative section-heading recognition for extracted research papers."""

import re


UNKNOWN_SECTION = "unknown"

# These are deliberately complete, standalone heading names. PDF body lines
# that merely contain one of these words must not change the section.
_HEADING_SECTIONS = {
    "abstract": "abstract",
    "introduction": "introduction",
    "background": "background",
    "method": "methods",
    "methods": "methods",
    "methodology": "methods",
    "materials and methods": "methods",
    "results": "results",
    "discussion": "discussion",
    "conclusion": "conclusion",
    "conclusions": "conclusion",
    "references": "references",
    "bibliography": "references",
    "appendix": "appendix",
    "appendices": "appendix",
    "supplementary material": "supplementary_material",
    "supplementary materials": "supplementary_material",
    "acknowledgement": "acknowledgments",
    "acknowledgements": "acknowledgments",
    "acknowledgment": "acknowledgments",
    "acknowledgments": "acknowledgments",
    "funding": "funding",
    "funding statement": "funding",
    "data availability": "data_availability",
    "data availability statement": "data_availability",
    "author contributions": "author_contributions",
    "author contribution statement": "author_contributions",
    "credit authorship contribution statement": "author_contributions",
    "declaration of competing interest": "conflicts_of_interest",
    "declaration of competing interests": "conflicts_of_interest",
    "conflict of interest": "conflicts_of_interest",
    "conflicts of interest": "conflicts_of_interest",
    "declaration of generative ai and ai-assisted": "generative_ai_statement",
    "declaration of generative ai and ai-assisted technologies in the writing process": "generative_ai_statement",
}

_NUMBERED_HEADING = re.compile(r"^\d+(?:\.\d+)*[.)]?(?:\s*\|\s*|\s+)")


def heading_section(line: str) -> str | None:
    """Return the normalized section for a standalone heading line, if any."""
    normalized = " ".join(line.strip().casefold().split())
    normalized = _NUMBERED_HEADING.sub("", normalized)
    normalized = normalized.removesuffix(":").strip()
    return _HEADING_SECTIONS.get(normalized)


def section_ranges(
    text: str,
    initial_section: str = UNKNOWN_SECTION,
) -> tuple[list[tuple[int, int, str]], str]:
    """Split text offsets at recognized headings and return the ending state."""
    transitions: list[tuple[int, str]] = []
    section = initial_section

    for line_match in re.finditer(r"(?m)^[^\r\n]*(?:\r?\n|$)", text):
        line = line_match.group(0).rstrip("\r\n")
        recognized = heading_section(line)
        if section == "references" and recognized not in {
            "appendix", "supplementary_material",
        }:
            # A references list can contain standalone-looking article titles.
            # Only explicit post-reference material can end this section.
            continue
        if recognized is not None and recognized != section:
            transitions.append((line_match.start(), recognized))
            section = recognized

    ranges: list[tuple[int, int, str]] = []
    start = 0
    active_section = initial_section
    for transition_start, next_section in transitions:
        if transition_start > start:
            ranges.append((start, transition_start, active_section))
        start = transition_start
        active_section = next_section
    if start < len(text):
        ranges.append((start, len(text), active_section))

    return ranges, section
