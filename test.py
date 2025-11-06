import re
from typing import Dict, List, Optional, Tuple

SIDE_KEYWORDS: Dict[str, List[str]] = {
    "좌": ["좌측", "왼쪽", "좌", "왼"],
    "우": ["우측", "오른쪽", "우", "오른"],
    "양": ["양측", "양쪽"],
}

BODY_KEYWORDS: Dict[str, List[str]] = {
    "어깨": ["어깨", "견관절", "견"],
    "목": ["목", "경추"],
    "허리": ["허리", "요추", "요"],
    "등": ["등", "흉추"],
    "상지": ["팔", "상지", "팔꿈치", "주관절"],
    "하지": ["다리", "하지", "무릎", "슬관절", "고관절"],
    "복부": ["복부", "배"],
}

TREATMENT_PLANS: Dict[str, Dict[str, List[str] or str]] = {
    "어깨": {
        "label": "어깨",
        "atx": ["견정", "천주", "견우", "견료", "견외수"],
        "cupping": ["견정", "천주"],
        "device": ["대추"],
        "pharm": ["견우", "견료"],
        "diagnosis": [
            "회전근개 근긴장 및 경미한 염좌 의심",
            "견관절 과사용으로 인한 근육성 통증 가능성 있음.",
        ],
        "prescription": "작약감초탕",
    },
    "default": {
        "label": "증상 부위",
        "atx": ["국소부위", "해당 경혈"],
        "cupping": ["국소부위"],
        "device": ["해당 부위"],
        "pharm": ["국소 경혈"],
        "diagnosis": ["근육성 통증 의심", "추가 평가 필요."],
        "prescription": "증상에 따라 추후 결정",
    },
}

NEGATIVE_SIGNS = "발적, 부종 없음"

SYMPTOM_KEYWORDS = [
    "통증",
    "아프",
    "저림",
    "뻐근",
    "불편",
    "압박",
    "힘듦",
    "어려움",
    "괜찮",
]

TEST_PATTERN = re.compile(r"([A-Za-z ]+?)\s*((?:\+{1,2}|-)/(?:\+{1,2}|-))")
DURATION_PATTERN = re.compile(r"(\d+\s*(?:일|주|개월|달|년)\s*전부터)")


def detect_side(text: str) -> Optional[str]:
    for side, keywords in SIDE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return side
    return None


def detect_body_part(text: str) -> str:
    for part, keywords in BODY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return part
    return "default"


def side_label(side: Optional[str]) -> str:
    return {"좌": "좌측", "우": "우측", "양": "양측"}.get(side or "", "").strip()


def extract_duration(text: str) -> str:
    match = DURATION_PATTERN.search(text)
    if match:
        return f"{match.group(1)} 발생"
    return "발병 시점 불명"


def extract_mode(text: str) -> str:
    mode_match = re.search(r"([가-힣\s]{0,30}(?:하다가|중|이후)[^\n\.]*)", text)
    if mode_match:
        phrase = mode_match.group(1).strip()
        if phrase and not phrase.endswith("."):
            phrase += "."
        return phrase if phrase else "특이사항 없음"
    return "특이사항 없음"


def attach_object_particle(word: str) -> str:
    if not word:
        return word
    last_char = word[-1]
    code = ord(last_char)
    if 0xAC00 <= code <= 0xD7A3:
        has_final = (code - 0xAC00) % 28 != 0
        particle = "을" if has_final else "를"
    else:
        particle = "을"
    return word + particle


def split_sentences(text: str) -> List[str]:
    raw_sentences = re.split(r"[\n\.]+", text)
    return [sentence.strip() for sentence in raw_sentences if sentence.strip()]


def build_pi(sentences: List[str]) -> str:
    details: List[str] = []
    for sentence in sentences:
        clean_sentence = sentence.strip()
        if not clean_sentence:
            continue
        if "전부터" in clean_sentence:
            continue
        if any(keyword in clean_sentence for keyword in SYMPTOM_KEYWORDS):
            if "괜찮" in clean_sentence and "통증" not in clean_sentence:
                clean_sentence = clean_sentence.replace("돌리는건", "회전시")
                clean_sentence = clean_sentence.replace("돌릴 때", "회전시")
                clean_sentence = clean_sentence.replace("괜찮다", "통증 없음")
                clean_sentence = clean_sentence.replace("괜찮음", "통증 없음")
            if "돌리면 아프다" in clean_sentence:
                clean_sentence = clean_sentence.replace("돌리면 아프다", "돌릴 때 통증")
            if "통증이 있다" in clean_sentence:
                clean_sentence = clean_sentence.replace("통증이 있다", "통증")
            details.append(clean_sentence)
    if not details:
        return "증상 관련 추가 기술 없음."
    cleaned = [detail.rstrip(".") for detail in details]
    return ". ".join(cleaned) + "."


def extract_tests(text: str) -> Tuple[List[str], str]:
    tests: List[str] = []

    def _record(match: re.Match) -> str:
        name = match.group(1).strip()
        result = match.group(2).strip()
        if name:
            tests.append(f"{name} {result}")
        return ""

    cleaned_text = TEST_PATTERN.sub(_record, text)
    return tests, cleaned_text


def extract_tenderness(sentences: List[str]) -> List[str]:
    findings: List[str] = []
    for sentence in sentences:
        if "압통" in sentence:
            findings.append(sentence.rstrip("."))
    return findings


def determine_plan(body_part: str) -> Dict[str, List[str] or str]:
    return TREATMENT_PLANS.get(body_part, TREATMENT_PLANS["default"])


def format_plan(plan: Dict[str, List[str] or str], side: Optional[str]) -> List[str]:
    label = plan["label"]
    side_text = {"좌": "좌", "우": "우", "양": "양측"}.get(side or "", "").strip()
    side_section = f"{side_text} {label}".strip()
    if not side_section:
        side_section = label
    lines = [f"Hot pack / ICT / IR ({side_section})"]
    lines.append(
        "ATx (" + " ".join(plan["atx"]) + ") / 침전기자극술 / 자락관법 (" + " ".join(plan["cupping"]) + ") / 기기구술 (" + " ".join(plan["device"]) + ")"
    )
    lines.append("약침 (" + " ".join(plan["pharm"]) + ")")
    lines.append(f"처방 : {plan['prescription']}")
    return lines


def build_assessment(plan: Dict[str, List[str] or str]) -> List[str]:
    return plan["diagnosis"]  # type: ignore[return-value]


def generate_chart(text: str) -> str:
    tests, cleaned_text = extract_tests(text)
    sentences = split_sentences(cleaned_text)
    side = detect_side(text)
    body_part = detect_body_part(text)
    plan = determine_plan(body_part)

    chief_side = side_label(side)
    chief_label = plan["label"]
    chief = f"{chief_side} {chief_label} 통증".strip()

    duration = extract_duration(text)
    mode = extract_mode(text)
    if mode != "특이사항 없음":
        base_mode = mode.rstrip(".")
        if "하다가" in base_mode:
            base_mode = base_mode.replace("하다가", " 운동 중")
        body_phrase = chief_label
        if "삐끗" in base_mode:
            particle_phrase = attach_object_particle(body_phrase or "해당 부위")
            if "삐끗한" in base_mode and particle_phrase not in base_mode:
                base_mode = base_mode.replace("삐끗한", f"{particle_phrase} 삐끗한")
            elif "삐끗" in base_mode and particle_phrase not in base_mode:
                base_mode = base_mode.replace("삐끗", f"{particle_phrase} 삐끗")
        base_mode = base_mode.replace("것 같다", "").strip()
        base_mode = " ".join(base_mode.split())
        if "통증" not in base_mode:
            base_mode = base_mode + " 이후 통증 발생함"
        mode = base_mode + "."
    pi = build_pi(sentences)

    tenderness = extract_tenderness(sentences)

    s_lines = [
        f"C/C : {chief}",
        f"O/S : {duration}",
        f"mode 및 특이사항 : {mode}",
        "P/H : 특이사항 없음",
        "S/H : 특이사항 없음",
        f"P/I : {pi}",
    ]

    o_lines = []
    if tests:
        o_lines.extend(tests)
    if tenderness:
        o_lines.extend(tenderness)
    o_lines.append(NEGATIVE_SIGNS)

    a_lines = build_assessment(plan)
    p_lines = format_plan(plan, side)

    sections = [
        "S)\n" + "\n".join(s_lines),
        "O)\n" + "\n".join(o_lines),
        "A)\n" + "\n".join(a_lines),
        "P)\n" + "\n".join(p_lines),
    ]

    return "\n\n".join(sections)


if __name__ == "__main__":
    import sys

    input_text = sys.stdin.read().strip()
    if not input_text:
        print("입력된 텍스트가 없습니다.")
    else:
        print(generate_chart(input_text))
