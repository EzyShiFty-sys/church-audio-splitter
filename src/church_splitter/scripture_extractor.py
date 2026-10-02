import re
from typing import List, Dict, Any, Optional

BIBLE_BOOKS = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
    "Joshua", "Judges", "Ruth", "1 Samuel", "2 Samuel", "1 Kings", "2 Kings",
    "1 Chronicles", "2 Chronicles", "Ezra", "Nehemiah", "Esther", "Job",
    "Psalms?", "Proverbs", "Ecclesiastes", "Song of Solomon", "Isaiah",
    "Jeremiah", "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel",
    "Amos", "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah",
    "Haggai", "Zechariah", "Malachi",
    "Matthew", "Mark", "Luke", "John", "Acts", "Romans",
    "1 Corinthians", "2 Corinthians", "Galatians", "Ephesians", "Philippians",
    "Colossians", "1 Thessalonians", "2 Thessalonians", "1 Timothy", "2 Timothy",
    "Titus", "Philemon", "Hebrews", "James", "1 Peter", "2 Peter",
    "1 John", "2 John", "3 John", "Jude", "Revelation"
]

BOOK_PATTERN = r"\b(" + "|".join(BIBLE_BOOKS) + r")\b"

NUMBER_WORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14", "fifteen": "15",
    "sixteen": "16", "seventeen": "17", "eighteen": "18", "nineteen": "19", "twenty": "20",
    "twenty-two": "22", "twenty two": "22"
}

def extract_scriptures(transcript: str) -> List[str]:
    """Extracts spoken Scripture references from the sermon transcript."""
    results = []
    
    # Format: Book chapter (number) X verse (number) Y
    p1 = re.compile(
        BOOK_PATTERN + r"(?:\s+chapter(?:\s+number)?)?\s+(\d+|[a-zA-Z\-]+)(?:\s*(?:and)?\s*verse(?:\s+number)?\s+(\d+|[a-zA-Z\-]+))?",
        re.IGNORECASE
    )
    for m in p1.finditer(transcript):
        raw = m.group(0).strip()
        # Clean up into readable citation if possible
        book = m.group(1).title()
        ch_raw = m.group(2)
        v_raw = m.group(3)
        ch_num = NUMBER_WORDS.get(ch_raw.lower(), ch_raw) if ch_raw else None
        v_num = NUMBER_WORDS.get(v_raw.lower(), v_raw) if v_raw else None
        if ch_num and ch_num.isdigit():
            if v_num and v_num.isdigit():
                formatted = f"{book} {ch_num}:{v_num}"
            else:
                formatted = f"{book} {ch_num}"
            if formatted not in results:
                results.append(formatted)
        elif raw not in results:
            results.append(raw)

    # Standard format: Book X:Y
    p2 = re.compile(BOOK_PATTERN + r"\s+\d+:\d+(?:-\d+)?", re.IGNORECASE)
    for m in p2.finditer(transcript):
        cit = m.group(0).strip()
        if cit not in results:
            results.append(cit)

    return results

def extract_sermon_title(transcript: str) -> Optional[str]:
    """Detects spoken title declarations from the preacher."""
    patterns = [
        r"(?:preach\s+(?:on|from|about)\s+)([\"']?[A-Za-z0-9\s,\-!]+[\"']?)(?:\.|\n|\sand\b)",
        r"(?:title\s+(?:of\s+the\s+message\s+is|is)\s+)([\"']?[A-Za-z0-9\s,\-!]+[\"']?)(?:\.|\n)",
        r"(?:subject\s+(?:is|tonight\s+is|today\s+is)\s+)([\"']?[A-Za-z0-9\s,\-!]+[\"']?)(?:\.|\n)",
        r"(?:thought\s+(?:is|tonight\s+is|today\s+is)\s+)([\"']?[A-Za-z0-9\s,\-!]+[\"']?)(?:\.|\n)",
    ]
    for p in patterns:
        m = re.search(p, transcript, re.IGNORECASE)
        if m:
            title = m.group(1).strip().strip("\"'.,")
            words = title.split()
            if 2 <= len(words) <= 10:
                return " ".join(words).title()
    return None

def generate_social_summary(
    transcript: str,
    title: Optional[str] = None,
    preacher: Optional[str] = None,
    series: Optional[str] = None
) -> Dict[str, Any]:
    """Generates sermon title, scripture list, and ready-to-share social media post."""
    detected_title = title or extract_sermon_title(transcript) or "Sunday Service Message"
    scriptures = extract_scriptures(transcript)
    primary_scripture = scriptures[0] if scriptures else "Scripture Reference"

    # Extract 2 key sentences from transcript for description
    sentences = [s.strip() for s in re.split(r"[.!?]\s+", transcript) if len(s.strip().split()) >= 8]
    summary_sentence = ""
    for s in sentences:
        if any(word in s.lower() for word in ["god", "jesus", "lord", "faith", "spirit", "bible"]):
            summary_sentence = s + "."
            break
    if not summary_sentence and sentences:
        summary_sentence = sentences[0] + "."

    preacher_tag = f"Speaker: {preacher}\n" if preacher else ""
    series_tag = f"Series: {series}\n" if series else ""
    scripture_list_str = ", ".join(scriptures[:3]) if scriptures else "Holy Bible"

    post_template = (
        f"📖 \"{detected_title}\"\n"
        f"📍 Scripture: {scripture_list_str}\n"
        f"{preacher_tag}"
        f"{series_tag}\n"
        f"\" {summary_sentence} \"\n\n"
        f"Listen to the full sermon audio recording on our podcast & audio archives!\n"
        f"#Sermon #ChurchAudio #Worship #Gospel"
    )

    return {
        "title": detected_title,
        "scriptures": scriptures,
        "primary_scripture": primary_scripture,
        "summary_quote": summary_sentence,
        "social_post": post_template
    }
