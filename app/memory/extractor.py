from __future__ import annotations

import re


def extract_long_term_memories(query: str) -> list[dict[str, str]]:
    """Extract explicit, high-signal preferences and phrase meanings.

    This conservative first version only persists statements with explicit markers;
    implicit personal data should not become long-term memory automatically.
    """
    memories: list[dict[str, str]] = []
    preference = re.search(r"(?:我喜欢|我偏好|我习惯|以后都用)(.+)", query)
    if preference:
        memories.append({"memory_type": "preference", "content": preference.group(0)})
    phrase = re.search(r"(.{1,40})(?:是指|的意思是|代表)(.{1,100})", query)
    if phrase:
        memories.append({"memory_type": "phrase_meaning", "content": phrase.group(0)})
    instruction = re.search(r"(?:请记住|记住|约定)(.{1,100})", query)
    if instruction:
        memories.append({"memory_type": "instruction", "content": instruction.group(0)})
    return memories
