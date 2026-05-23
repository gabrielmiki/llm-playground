from __future__ import annotations

from collections.abc import Generator, Iterable
from dataclasses import dataclass

import ftfy
import regex


@dataclass
class CleaningResult:
    cleaned_text: str
    original_text: str
    was_fixed: bool
    encoding_fixed: bool
    whitespace_fixed: bool
    special_chars_removed: int
    is_garbled: bool


class TextCleaner:
    def clean(self, text: str) -> CleaningResult:
        encoding_fixed = False
        whitespace_fixed = False
        special_chars_removed = 0

        fixed = ftfy.fix_text(text)
        if fixed != text:
            encoding_fixed = True
        cleaned = fixed

        whitespace_normalized = regex.sub(r"\s+", " ", cleaned).strip()
        if whitespace_normalized != cleaned:
            whitespace_fixed = True
        cleaned = whitespace_normalized

        before_special = len(cleaned)
        cleaned = regex.sub(r"\p{C}", "", cleaned)
        special_chars_removed = before_special - len(cleaned)

        non_alpha_count = len(regex.sub(r"\p{L}", "", cleaned))
        is_garbled = non_alpha_count > len(cleaned) * 0.5 if cleaned else False

        was_fixed = encoding_fixed or whitespace_fixed or special_chars_removed > 0

        return CleaningResult(
            cleaned_text=cleaned,
            original_text=text,
            was_fixed=was_fixed,
            encoding_fixed=encoding_fixed,
            whitespace_fixed=whitespace_fixed,
            special_chars_removed=special_chars_removed,
            is_garbled=is_garbled,
        )

    def clean_many(
        self, texts: Iterable[str]
    ) -> Generator[CleaningResult, None, None]:
        for text in texts:
            yield self.clean(text)
