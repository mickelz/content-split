"""
Multi-Dimensional Quality Scorer for Structured Outputs
"""

import json
import re
import time
from typing import Any


def detect_format(text: str) -> str:
    """Auto-detect format: json, markdown, code, text"""
    text = text.strip()
    
    # JSON detection
    if text.startswith(('{', '[')):
        try:
            json.loads(text)
            return "json"
        except:
            pass
    
    # Markdown detection
    if re.match(r'^#{1,6}\s+\w+', text, re.MULTILINE):
        return "markdown"
    
    # Code detection (common patterns)
    code_patterns = [
        r'^def\s+\w+\s*\(',
        r'^class\s+\w+',
        r'^import\s+\w+',
        r'^function\s+\w+\s*\(',
        r'^\s*(if|for|while|return)\s+',
        r'\{\s*$',
    ]
    for pattern in code_patterns:
        if re.search(pattern, text, re.MULTILINE):
            return "code"
    
    return "text"


def score_completeness(text: str, format_type: str) -> float:
    """Score completeness (weight: 0.30)"""
    if not text or len(text.strip()) < 10:
        return 0.0
    
    score = 0.5  # Base score
    
    if format_type == "json":
        try:
            data = json.loads(text)
            # Check for expected fields
            if isinstance(data, dict):
                score += 0.3 * min(len(data) / 5, 1.0)
            elif isinstance(data, list):
                score += 0.3 * min(len(data) / 3, 1.0)
        except:
            return 0.0
    
    elif format_type == "markdown":
        # Check for headers, lists, paragraphs
        has_headers = bool(re.search(r'^#{1,6}\s+', text, re.MULTILINE))
        has_lists = bool(re.search(r'^[\s]*[-*+]\s+', text, re.MULTILINE))
        has_paragraphs = len(text.split('\n\n')) > 1
        
        if has_headers:
            score += 0.15
        if has_lists:
            score += 0.15
        if has_paragraphs:
            score += 0.2
    
    elif format_type == "code":
        # Check for functions/classes, imports, meaningful length
        has_funcs = bool(re.search(r'(def|function|class)\s+\w+', text))
        lines = text.split('\n')
        meaningful_lines = sum(1 for l in lines if l.strip() and not l.strip().startswith('#'))
        
        if has_funcs:
            score += 0.2
        score += 0.3 * min(meaningful_lines / 20, 1.0)
    
    else:  # text
        # Check for sentences and paragraphs
        sentences = len(re.findall(r'[.!?]+', text))
        paragraphs = len(text.split('\n\n'))
        
        score += 0.2 * min(sentences / 5, 1.0)
        score += 0.3 * min(paragraphs / 3, 1.0)
    
    return min(score, 1.0)


def score_format_compliance(text: str, format_type: str) -> float:
    """Score format compliance (weight: 0.20)"""
    if not text:
        return 0.0
    
    score = 0.6  # Base score
    
    if format_type == "json":
        try:
            json.loads(text)
            # Valid JSON is well-formed
            score += 0.4
        except json.JSONDecodeError as e:
            # Partial credit for near-JSON
            if text.strip().startswith(('{', '[')):
                score += 0.1
    
    elif format_type == "markdown":
        # Check proper markdown syntax
        has_valid_headers = bool(re.search(r'^#{1,6}\s+\w+', text, re.MULTILINE))
        balanced_brackets = text.count('[') == text.count(']')
        balanced_parens = text.count('(') == text.count(')')
        
        if has_valid_headers:
            score += 0.2
        if balanced_brackets:
            score += 0.1
        if balanced_parens:
            score += 0.1
    
    elif format_type == "code":
        # Basic syntax checks
        has_indentation = '\n    ' in text or '\n\t' in text
        balanced_braces = text.count('{') == text.count('}')
        balanced_parens = text.count('(') == text.count(')')
        
        if has_indentation:
            score += 0.15
        if balanced_braces:
            score += 0.15
        if balanced_parens:
            score += 0.1
    
    else:  # text
        # Check for proper punctuation and spacing
        proper_sentences = bool(re.search(r'[.!?]\s+[A-Z]', text))
        no_excessive_newlines = text.count('\n') < len(text) / 10
        
        if proper_sentences:
            score += 0.2
        if no_excessive_newlines:
            score += 0.2
    
    return min(score, 1.0)


def score_coverage(text: str, format_type: str) -> float:
    """Score coverage (weight: 0.25)"""
    if not text or len(text.strip()) < 10:
        return 0.0
    
    score = 0.4
    
    length = len(text)
    
    if format_type == "json":
        try:
            data = json.loads(text)
            # More fields = more coverage
            if isinstance(data, dict):
                depth = count_json_depth(data)
                score += 0.3 * min(depth / 4, 1.0)
                score += 0.3 * min(len(data) / 10, 1.0)
            elif isinstance(data, list):
                score += 0.3 * min(len(data) / 10, 1.0)
                if data and isinstance(data[0], dict):
                    score += 0.3 * min(len(data[0]) / 5, 1.0)
        except:
            pass
    
    elif format_type == "markdown":
        # More sections = more coverage
        sections = len(re.findall(r'^#{1,6}\s+', text, re.MULTILINE))
        word_count = len(text.split())
        
        score += 0.3 * min(sections / 5, 1.0)
        score += 0.3 * min(word_count / 500, 1.0)
    
    elif format_type == "code":
        # More functions/classes = more coverage
        functions = len(re.findall(r'(def|function|class)\s+\w+', text))
        lines = len([l for l in text.split('\n') if l.strip()])
        
        score += 0.3 * min(functions / 5, 1.0)
        score += 0.3 * min(lines / 50, 1.0)
    
    else:  # text
        word_count = len(text.split())
        unique_words = len(set(text.lower().split()))
        
        score += 0.3 * min(word_count / 200, 1.0)
        score += 0.3 * min(unique_words / 50, 1.0)
    
    return min(score, 1.0)


def count_json_depth(obj, current_depth=1):
    """Count maximum depth of JSON structure"""
    if isinstance(obj, dict):
        if not obj:
            return current_depth
        return max(count_json_depth(v, current_depth + 1) for v in obj.values())
    elif isinstance(obj, list):
        if not obj:
            return current_depth
        return max(count_json_depth(item, current_depth + 1) for item in obj)
    return current_depth


def score_clarity(text: str, format_type: str) -> float:
    """Score clarity (weight: 0.15)"""
    if not text:
        return 0.0
    
    score = 0.5
    
    # Check average line length (shorter = clearer)
    lines = text.split('\n')
    if lines:
        avg_line_length = sum(len(l) for l in lines) / len(lines)
        if avg_line_length < 80:
            score += 0.2
        elif avg_line_length < 120:
            score += 0.1
    
    # Check for excessive formatting mess
    excessive_caps = sum(1 for w in text.split() if w.isupper() and len(w) > 2)
    if excessive_caps < len(text.split()) * 0.1:
        score += 0.15
    
    # Check for readability (sentence structure)
    if format_type in ("text", "markdown"):
        sentences = re.split(r'[.!?]+', text)
        sentences = [s for s in sentences if s.strip()]
        if sentences:
            avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)
            if avg_sentence_length < 25:
                score += 0.15
    
    # Code: check for comments
    if format_type == "code":
        comments = len(re.findall(r'#.*$|//.*$', text, re.MULTILINE))
        code_lines = len([l for l in lines if l.strip() and not l.strip().startswith('#')])
        if code_lines > 0 and comments / code_lines > 0.1:
            score += 0.15
    
    return min(score, 1.0)


def score_validity(text: str, format_type: str) -> float:
    """Score validity (weight: 0.10)"""
    if not text:
        return 0.0
    
    score = 0.6
    
    if format_type == "json":
        try:
            json.loads(text)
            score += 0.4
        except:
            # Check if it's at least parseable as partial JSON
            if text.strip().startswith(('{', '[')):
                score += 0.1
    
    elif format_type == "code":
        # Basic validity checks
        has_syntax = bool(re.search(r'(def|function|class|import|var|let|const)\s+', text))
        balanced = text.count('{') == text.count('}') and text.count('(') == text.count(')')
        
        if has_syntax:
            score += 0.2
        if balanced:
            score += 0.2
    
    else:  # text/markdown
        # Check for gibberish (repeated chars, random strings)
        has_letters = bool(re.search(r'[a-zA-Z]', text))
        has_words = len(text.split()) > 3
        
        if has_letters:
            score += 0.2
        if has_words:
            score += 0.2
    
    return min(score, 1.0)


def generate_feedback(text: str, format_type: str, scores: dict) -> list:
    """Generate NLP feedback (bonus feature)"""
    feedback = []
    
    if scores.get("completeness", 0) < 0.7:
        if format_type == "json":
            feedback.append("Consider adding more fields to improve completeness")
        elif format_type == "markdown":
            feedback.append("Add more sections or subsections for better coverage")
        else:
            feedback.append("Expand the content for better completeness")
    
    if scores.get("format_compliance", 0) < 0.7:
        if format_type == "json":
            feedback.append("Fix JSON syntax errors for better format compliance")
        elif format_type == "markdown":
            feedback.append("Ensure consistent markdown formatting")
        else:
            feedback.append("Improve text formatting")
    
    if scores.get("coverage", 0) < 0.7:
        feedback.append("Add more detail or content for better coverage")
    
    if scores.get("clarity", 0) < 0.7:
        feedback.append("Break up long sentences or lines for better clarity")
    
    if scores.get("validity", 0) < 0.7:
        feedback.append("Fix structural issues to improve validity")
    
    if not feedback:
        feedback.append("Great work! Content meets quality standards")
    
    return feedback


def score_submission(text: str) -> dict:
    """
    Main scoring function.
    
    Args:
        text: Input text (JSON, markdown, code, or plain text)
    
    Returns:
        dict with keys: weighted_score, quality_rating, scores, feedback, pass_threshold
    """
    # Weights
    WEIGHTS = {
        "completeness": 0.30,
        "format_compliance": 0.20,
        "coverage": 0.25,
        "clarity": 0.15,
        "validity": 0.10
    }
    
    # Auto-detect format
    format_type = detect_format(text)
    
    # Score each dimension
    scores = {
        "completeness": score_completeness(text, format_type),
        "format_compliance": score_format_compliance(text, format_type),
        "coverage": score_coverage(text, format_type),
        "clarity": score_clarity(text, format_type),
        "validity": score_validity(text, format_type)
    }
    
    # Calculate weighted score
    weighted_score = sum(scores[dim] * WEIGHTS[dim] for dim in WEIGHTS)
    
    # Determine quality rating
    if weighted_score >= 0.9:
        quality_rating = "Excellent"
    elif weighted_score >= 0.75:
        quality_rating = "Good"
    elif weighted_score >= 0.6:
        quality_rating = "Fair"
    elif weighted_score >= 0.4:
        quality_rating = "Poor"
    else:
        quality_rating = "Very Poor"
    
    # Pass threshold (configurable, default 0.6)
    pass_threshold = weighted_score >= 0.6
    
    # Generate feedback
    feedback = generate_feedback(text, format_type, scores)
    
    return {
        "weighted_score": round(weighted_score, 3),
        "quality_rating": quality_rating,
        "scores": {k: round(v, 3) for k, v in scores.items()},
        "feedback": feedback,
        "pass_threshold": pass_threshold,
        "format_detected": format_type
    }


def score_batch(submissions: list) -> list:
    """Score multiple submissions efficiently."""
    return [score_submission(sub) for sub in submissions]


# Example usage
if __name__ == "__main__":
    # Test cases
    test_json = '{"name": "Test", "description": "A test item", "value": 100}'
    test_markdown = """# Title

## Section 1

Some content here.

## Section 2

More content.
"""
    test_code = """def hello():
    print("Hello, world!")
    return True
"""
    test_text = "This is a simple test. It has a few sentences. Not much else."
    
    for name, text in [("JSON", test_json), ("Markdown", test_markdown), 
                       ("Code", test_code), ("Text", test_text)]:
        print(f"\n=== {name} ===")
        result = score_submission(text)
        print(f"Score: {result['weighted_score']} ({result['quality_rating']})")
        print(f"Format: {result['format_detected']}")
        print(f"Pass: {result['pass_threshold']}")
        print(f"Feedback: {result['feedback']}")
