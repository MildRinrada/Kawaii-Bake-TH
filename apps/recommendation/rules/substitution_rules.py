"""The ingredient substitution rule registry.

This module  not a table  owns substitution knowledge in Phase 12
(ADR 0018 §12). Rules are curated kitchen practice keyed by the same
normalised form ``recipes`` stores in ``RecipeIngredient.normalized_name``,
so a free-text ingredient matches a rule exactly when it would match the
"recipes containing X" filter. A future ingredient catalogue replaces this
dict with a lookup behind the same ``lookup()`` seam.

Honesty rules, enforced by convention and tests:

- A ``ratio`` is present only where the conversion is well established;
  otherwise it is empty and the option is a *candidate*, not a formula.
- Allergen implications appear as cautions in ``note``. Nothing here claims
  nutritional equivalence, allergy safety, or medical suitability.
- ``confidence`` is one of three coarse buckets  the only precision that
  honestly exists.
- Options are declared best-first; declaration order is the API order.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.recommendation.constants import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
)


@dataclass(frozen=True)
class SubstitutionOption:
    """One substitution candidate for an ingredient."""

    name: str
    ratio: str
    note: str
    confidence: str


# Canonical rules. Keys MUST already be in normalised form (lowercase,
# NFC, single-spaced)  a test asserts this so a typo cannot silently
# create an unreachable rule.
RULES: dict[str, tuple[SubstitutionOption, ...]] = {
    "เนย": (
        SubstitutionOption(
            name="มาการีน",
            ratio="1:1",
            note="รสและกลิ่นต่างจากเนยแท้เล็กน้อย",
            confidence=CONFIDENCE_HIGH,
        ),
        SubstitutionOption(
            name="น้ำมันมะพร้าว",
            ratio="1:1",
            note="เนื้อสัมผัสแน่นขึ้นเมื่อเย็นตัว และมีกลิ่นมะพร้าวอ่อน ๆ",
            confidence=CONFIDENCE_MEDIUM,
        ),
        SubstitutionOption(
            name="น้ำมันพืช",
            ratio="3/4 ถ้วย ต่อเนย 1 ถ้วย",
            note="เหมาะกับเค้กเนื้อชุ่ม แต่โครงสร้างคุกกี้จะเปลี่ยน",
            confidence=CONFIDENCE_MEDIUM,
        ),
    ),
    "นมสด": (
        SubstitutionOption(
            name="นมถั่วเหลือง",
            ratio="1:1",
            note="มีถั่วเหลือง  ผู้แพ้ถั่วเหลืองควรหลีกเลี่ยง",
            confidence=CONFIDENCE_HIGH,
        ),
        SubstitutionOption(
            name="นมข้าวโอ๊ต",
            ratio="1:1",
            note="ให้รสหวานอ่อน ๆ จากข้าวโอ๊ต",
            confidence=CONFIDENCE_HIGH,
        ),
        SubstitutionOption(
            name="นมอัลมอนด์",
            ratio="1:1",
            note="มีถั่วเปลือกแข็ง  ผู้แพ้ถั่วควรหลีกเลี่ยง เนื้อบางกว่านมวัว",
            confidence=CONFIDENCE_MEDIUM,
        ),
    ),
    "แป้งอเนกประสงค์": (
        SubstitutionOption(
            name="แป้งเค้ก",
            ratio="1 ถ้วย + 2 ช้อนโต๊ะ ต่อแป้งอเนกประสงค์ 1 ถ้วย",
            note="กลูเตนต่ำกว่า เนื้อขนมเบาละเอียดขึ้น",
            confidence=CONFIDENCE_HIGH,
        ),
        SubstitutionOption(
            name="แป้งขนมปัง",
            ratio="1:1",
            note="กลูเตนสูงกว่า เนื้อขนมจะเหนียวแน่นขึ้น",
            confidence=CONFIDENCE_MEDIUM,
        ),
    ),
    "ไข่ไก่": (
        SubstitutionOption(
            name="เมล็ดแฟลกซ์บดผสมน้ำ",
            ratio="แฟลกซ์ 1 ช้อนโต๊ะ + น้ำ 3 ช้อนโต๊ะ ต่อไข่ 1 ฟอง",
            note="พักให้ข้นก่อนใช้ เหมาะกับบราวนี่และมัฟฟิน",
            confidence=CONFIDENCE_MEDIUM,
        ),
        SubstitutionOption(
            name="กล้วยสุกบด",
            ratio="ครึ่งลูก ต่อไข่ 1 ฟอง",
            note="ได้รสกล้วยชัดเจน และเนื้อขนมแน่นขึ้น",
            confidence=CONFIDENCE_LOW,
        ),
    ),
    "น้ำตาลทราย": (
        SubstitutionOption(
            name="น้ำผึ้ง",
            ratio="3/4 ถ้วย ต่อน้ำตาล 1 ถ้วย",
            note="ลดของเหลวในสูตรลงเล็กน้อย ผิวขนมจะเข้มสีเร็วขึ้น",
            confidence=CONFIDENCE_MEDIUM,
        ),
        SubstitutionOption(
            name="น้ำตาลมะพร้าว",
            ratio="1:1",
            note="สีเข้มขึ้นและมีกลิ่นคาราเมล",
            confidence=CONFIDENCE_MEDIUM,
        ),
    ),
    "บัตเตอร์มิลค์": (
        SubstitutionOption(
            name="นมสดผสมน้ำมะนาว",
            ratio="นม 1 ถ้วย + น้ำมะนาว 1 ช้อนโต๊ะ",
            note="พักไว้ 5–10 นาทีให้ตัวก่อนใช้",
            confidence=CONFIDENCE_HIGH,
        ),
        SubstitutionOption(
            name="โยเกิร์ตรสธรรมชาติผสมนม",
            ratio="โยเกิร์ต 3/4 ถ้วย + นม 1/4 ถ้วย",
            note="",
            confidence=CONFIDENCE_MEDIUM,
        ),
    ),
    "ผงฟู": (
        SubstitutionOption(
            name="เบกกิ้งโซดาผสมครีมออฟทาร์ทาร์",
            ratio="เบกกิ้งโซดา 1/4 ช้อนชา + ครีมออฟทาร์ทาร์ 1/2 ช้อนชา ต่อผงฟู 1 ช้อนชา",
            note="ผสมสดใช้ทันที อย่าเก็บไว้",
            confidence=CONFIDENCE_HIGH,
        ),
    ),
    "วิปปิ้งครีม": (
        SubstitutionOption(
            name="เนยละลายผสมนม",
            ratio="เนย 1/4 ถ้วย + นม 3/4 ถ้วย ต่อครีม 1 ถ้วย",
            note="ใช้ในเนื้อขนมและซอสได้ แต่ตีไม่ขึ้นฟู",
            confidence=CONFIDENCE_MEDIUM,
        ),
    ),
    "ดาร์กช็อกโกแลต": (
        SubstitutionOption(
            name="โกโก้ผงผสมเนย",
            ratio="โกโก้ 3 ช้อนโต๊ะ + เนย 1 ช้อนโต๊ะ ต่อช็อกโกแลต 28 กรัม",
            note="รสขมกว่าเล็กน้อย ปรับน้ำตาลตามชอบ",
            confidence=CONFIDENCE_MEDIUM,
        ),
    ),
}

# Normalised alias → canonical key. Thai and English spellings of the same
# ingredient resolve to one rule, so the registry has exactly one place per
# fact. Keys here MUST also be in normalised form.
ALIASES: dict[str, str] = {
    "butter": "เนย",
    "unsalted butter": "เนย",
    "เนยจืด": "เนย",
    "เนยสด": "เนย",
    "milk": "นมสด",
    "whole milk": "นมสด",
    "fresh milk": "นมสด",
    "นม": "นมสด",
    "all-purpose flour": "แป้งอเนกประสงค์",
    "all purpose flour": "แป้งอเนกประสงค์",
    "ap flour": "แป้งอเนกประสงค์",
    "แป้งสาลีอเนกประสงค์": "แป้งอเนกประสงค์",
    "egg": "ไข่ไก่",
    "eggs": "ไข่ไก่",
    "ไข่": "ไข่ไก่",
    "sugar": "น้ำตาลทราย",
    "granulated sugar": "น้ำตาลทราย",
    "น้ำตาล": "น้ำตาลทราย",
    "buttermilk": "บัตเตอร์มิลค์",
    "baking powder": "ผงฟู",
    "whipping cream": "วิปปิ้งครีม",
    "heavy cream": "วิปปิ้งครีม",
    "ครีมข้น": "วิปปิ้งครีม",
    "dark chocolate": "ดาร์กช็อกโกแลต",
    "ช็อกโกแลต": "ดาร์กช็อกโกแลต",
    "chocolate": "ดาร์กช็อกโกแลต",
}


def canonical_key(normalized_name: str) -> str:
    """Fold a normalised name onto its canonical rule key.

    Names the registry does not know canonicalise to themselves, so exact
    matching still works for unknown ingredients. This is also how the
    endpoint's ``?ingredient=`` filter matches across languages  asking
    for ``butter`` finds the recipe's ``เนย`` line, because both fold to
    the same key.

    Args:
        normalized_name: The output of ``normalize_ingredient_name``.

    Returns:
        The canonical key.
    """
    return ALIASES.get(normalized_name, normalized_name)


def lookup(normalized_name: str) -> tuple[SubstitutionOption, ...]:
    """Return the substitution options for a normalised ingredient name.

    Args:
        normalized_name: The output of ``normalize_ingredient_name``.

    Returns:
        The options best-first, or an empty tuple when nothing is known 
        an honest empty answer, never a guess.
    """
    return RULES.get(canonical_key(normalized_name), ())
