#!/usr/bin/env python3
"""Validate crash report against mandatory field checklist.

Replaces the crash-report-reviewer Haiku agent with a deterministic script.
Structural checks (11/14) are definitive. Semantic checks (3/14: Root cause,
Trigger, Why now) use word-count heuristics — flagged as NEEDS_REVIEW when
content is too short or contains placeholder markers.

Usage:
    python3 validate-report.py < report.txt
    python3 validate-report.py --console-url "https://..." < report.txt

Output (stdout): YAML block with pass/score/missing/needs_review
Exit code: 0 always (validation result in stdout, script errors in stderr)
"""
import re
import sys

PLACEHOLDER_RE = re.compile(
    r'\b(TBD|TODO|N/?A|UNKNOWN|PLACEHOLDER|FILL\s+IN|TO\s+BE\s+DETERMINED)\b',
    re.IGNORECASE,
)

VALID_COMPONENTS = {'ui', 'network', 'database', 'services', 'background', 'business'}

CRITICAL_FIELDS = {'Assignee', 'Fix before', 'Fix after', 'Executed commands', 'JIRA Brief'}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def split_sections(text):
    """Split markdown text into {lowercase_header: content} by ## / ### headers."""
    sections = {}
    current = None
    lines = []
    for line in text.split('\n'):
        m = re.match(r'^(#{2,3})\s+(.+)$', line)
        if m:
            if current is not None:
                sections[current] = '\n'.join(lines)
            current = m.group(2).strip().lower()
            lines = []
        else:
            lines.append(line)
    if current is not None:
        sections[current] = '\n'.join(lines)
    return sections


def find(sections, *keywords):
    """Return content of first section whose header contains any keyword."""
    for key, content in sections.items():
        if any(kw in key for kw in keywords):
            return content
    return None


def word_count(text):
    t = re.sub(r'```[\s\S]*?```', '', text)
    t = re.sub(r'`[^`]*`', '', t)
    t = re.sub(r'[#*_\[\]()]', ' ', t)
    return len(t.split())


def sentence_count(text):
    t = re.sub(r'```[\s\S]*?```', '', text)
    t = re.sub(r'`[^`]*`', '', t)
    parts = re.split(r'[.!?]+', t)
    return sum(1 for p in parts if len(p.strip().split()) >= 3)


def is_placeholder_only(text):
    stripped = text.strip()
    return bool(PLACEHOLDER_RE.search(stripped)) and len(stripped.split()) <= 5


def extract_subfield(text, field_name):
    """Extract content after **field_name:** until next **Field or section end."""
    pattern = r'(?:\*\*)?{}(?:\*\*)?[:\s]*(.+?)(?=\n\s*\*\*[A-Z]|\n\s*#{{2,}}|\Z)'.format(
        re.escape(field_name)
    )
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else None


def get_semantic_field(sections, field_name):
    """Get text for Trigger/Why now/Prevention — from dedicated or parent section."""
    s = find(sections, field_name.lower())
    if s and s.strip():
        return s.strip()
    s = find(sections, 'context', 'prevention')
    if s:
        return extract_subfield(s, field_name)
    return None


# ---------------------------------------------------------------------------
# Field checks — each returns 'OK', 'MISSING', or 'NEEDS_REVIEW'
# ---------------------------------------------------------------------------

def chk_exception(sections):
    s = find(sections, 'basic')
    if not s:
        return 'MISSING'
    m = re.search(r'(?:exception|error|crash\s*type)[:\s]+(\S.+)', s, re.IGNORECASE)
    return 'OK' if m and not is_placeholder_only(m.group(1)) else 'MISSING'


def chk_version(sections):
    s = find(sections, 'basic')
    if not s:
        return 'MISSING'
    if re.search(r'\bversion\b', s, re.IGNORECASE) or 'DATA UNAVAILABLE' in s.upper():
        return 'OK'
    return 'MISSING'


def chk_component(sections):
    s = find(sections, 'basic')
    if not s:
        return 'MISSING'
    words = set(re.findall(r'\b\w+\b', s.lower()))
    return 'OK' if words & VALID_COMPONENTS else 'MISSING'


def chk_stack_trace(sections):
    s = find(sections, 'stack trace')
    if not s:
        return 'MISSING'
    hits = re.findall(r'[:(]\d+[):]', s)
    return 'OK' if len(hits) >= 3 else 'MISSING'


def chk_checked_files(sections):
    s = find(sections, 'checked file', 'analyzed file', 'files checked')
    if not s or not s.strip():
        return 'MISSING'
    if re.search(r'(?:author|commit|blame)', s, re.IGNORECASE):
        return 'OK'
    if re.search(r'`[^`]+\.\w+`', s):
        return 'OK'
    return 'MISSING'


def chk_executed_commands(sections):
    s = find(sections, 'executed command', 'commands executed', 'git command')
    if not s:
        return 'MISSING'
    return 'OK' if re.search(r'git\s+(?:blame|log)', s) else 'MISSING'


def chk_root_cause(sections):
    """Semantic check: >=2 sentences of technical explanation, >=15 words."""
    s = find(sections, 'root cause')
    if not s or not s.strip():
        return 'MISSING'
    if is_placeholder_only(s):
        return 'NEEDS_REVIEW'
    if word_count(s) < 15:
        return 'NEEDS_REVIEW'
    if sentence_count(s) >= 2:
        return 'OK'
    return 'NEEDS_REVIEW'


def chk_fix_before(sections):
    s = find(sections, 'proposed fix', 'solution')
    if not s:
        return 'MISSING'
    lower = s.lower()
    pos = lower.find('before')
    if pos == -1:
        pos = lower.find('до')
    if pos == -1:
        return 'MISSING'
    return 'OK' if '```' in s[pos:] else 'MISSING'


def chk_fix_after(sections):
    s = find(sections, 'proposed fix', 'solution')
    if not s:
        return 'MISSING'
    lower = s.lower()
    pos = lower.find('after')
    if pos == -1:
        pos = lower.find('после')
    if pos == -1:
        return 'MISSING'
    return 'OK' if '```' in s[pos:] else 'MISSING'


def chk_assignee(sections):
    s = find(sections, 'assignee')
    if not s or not s.strip():
        return 'MISSING'
    if is_placeholder_only(s):
        return 'MISSING'
    if re.search(r'git\s*blame', s, re.IGNORECASE):
        return 'OK'
    # TBD with justification (long text explaining why) is acceptable
    if PLACEHOLDER_RE.search(s) and word_count(s) >= 10:
        return 'OK'
    if word_count(s) >= 3:
        return 'OK'
    return 'MISSING'


def chk_trigger(sections):
    """Semantic check: specific action/event."""
    text = get_semantic_field(sections, 'Trigger')
    if not text:
        return 'MISSING'
    if is_placeholder_only(text):
        return 'NEEDS_REVIEW'
    if word_count(text) < 3:
        return 'NEEDS_REVIEW'
    return 'OK'


def chk_why_now(sections):
    """Semantic check: explanation of what changed."""
    text = get_semantic_field(sections, 'Why now')
    if not text:
        return 'MISSING'
    if is_placeholder_only(text):
        return 'NEEDS_REVIEW'
    if word_count(text) < 5:
        return 'NEEDS_REVIEW'
    return 'OK'


def chk_prevention(sections):
    text = get_semantic_field(sections, 'Prevention')
    if not text:
        return 'MISSING'
    if is_placeholder_only(text):
        return 'MISSING'
    return 'OK' if word_count(text) >= 3 else 'MISSING'


def chk_jira_brief(text, console_url=None):
    """Check JIRA Brief section. Returns (status, missing_sub_fields)."""
    m = re.search(r'#{2,3}\s*JIRA\s*Brief(.*?)(?=\n#{2,3}\s[^#]|\Z)', text, re.IGNORECASE | re.DOTALL)
    if not m:
        return 'MISSING', []
    jira = m.group(1)
    required = ['Crash', 'Component', 'Assignee', 'Problem',
                 'Stack trace', 'Fix', 'Reproduction', 'Firebase']
    missing = [
        f for f in required
        if not re.search(r'(?:\*\*)?{}(?:\*\*)?[:\s]'.format(re.escape(f)), jira, re.IGNORECASE)
    ]
    if console_url and console_url not in jira:
        missing.append('Firebase URL (expected: {})'.format(console_url))
    return ('OK', []) if not missing else ('PARTIAL', missing)


# ---------------------------------------------------------------------------
# Main validation
# ---------------------------------------------------------------------------

CHECKS = [
    ('Exception',           chk_exception,         "Specify exception type in Basic info"),
    ('App version',         chk_version,           "Specify app version or [DATA UNAVAILABLE]"),
    ('Component',           chk_component,         "Specify component: UI/Network/Database/Services/Background"),
    ('Stack trace analysis', chk_stack_trace,       "Include >=3 stack lines with line numbers"),
    ('Checked files',       chk_checked_files,     "Include >=1 file with author and commit info"),
    ('Executed commands',   chk_executed_commands,  "Include >=1 git blame/git log command"),
    ('Root cause',          chk_root_cause,        "Provide >=2 sentences of technical explanation"),
    ('Fix before',          chk_fix_before,        "Add Before code block in Proposed fix"),
    ('Fix after',           chk_fix_after,         "Add After code block in Proposed fix"),
    ('Assignee',            chk_assignee,          "Specify name + source (git blame: file:line)"),
    ('Trigger',             chk_trigger,           "Specify the action/event that triggers the crash"),
    ('Why now',             chk_why_now,           "Explain what changed to cause this now"),
    ('Prevention',          chk_prevention,        "Add recommendation on how to prevent this"),
]


def validate(text, console_url=None):
    sections = split_sections(text)

    ok = 0
    missing = []
    needs_review = []

    for name, fn, fix_hint in CHECKS:
        result = fn(sections)
        if result == 'OK':
            ok += 1
        elif result == 'MISSING':
            missing.append({'field': name, 'format': 'detailed', 'fix': fix_hint})
        elif result == 'NEEDS_REVIEW':
            needs_review.append({'field': name, 'format': 'detailed', 'fix': fix_hint})
            ok += 1  # counts toward score, but flagged for LLM review

    # JIRA Brief — 1 check (14th field)
    jira_status, jira_missing = chk_jira_brief(text, console_url)
    if jira_status == 'OK':
        ok += 1
    elif jira_status == 'MISSING':
        missing.append({'field': 'JIRA Brief', 'format': 'jira_brief',
                        'fix': 'Add complete JIRA Brief section'})
    else:  # PARTIAL
        missing.append({'field': 'JIRA Brief', 'format': 'jira_brief',
                        'fix': 'Missing fields: {}'.format(', '.join(jira_missing))})

    # Determine pass / fail / null
    has_critical = any(m['field'] in CRITICAL_FIELDS for m in missing)
    if has_critical or ok < 12:
        pass_val = False
    elif needs_review:
        pass_val = None  # LLM command decides
    else:
        pass_val = True

    return {
        'pass': pass_val,
        'score': '{}/14'.format(ok),
        'missing': missing,
        'needs_review': needs_review,
    }


# ---------------------------------------------------------------------------
# YAML output
# ---------------------------------------------------------------------------

def to_yaml(result):
    lines = ['review:']
    p = result['pass']
    lines.append('  pass: {}'.format('null' if p is None else str(p).lower()))
    lines.append('  score: "{}"'.format(result['score']))
    for key in ('missing', 'needs_review'):
        items = result[key]
        if not items:
            lines.append('  {}: []'.format(key))
        else:
            lines.append('  {}:'.format(key))
            for item in items:
                lines.append('    - field: "{}"'.format(item['field']))
                lines.append('      format: "{}"'.format(item['format']))
                lines.append('      fix: "{}"'.format(item['fix']))
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    console_url = None
    args = sys.argv[1:]
    if '--console-url' in args:
        idx = args.index('--console-url')
        if idx + 1 < len(args):
            console_url = args[idx + 1]

    text = sys.stdin.read()
    if not text.strip():
        print('ERROR: empty input', file=sys.stderr)
        sys.exit(1)

    print(to_yaml(validate(text, console_url)))


if __name__ == '__main__':
    main()
