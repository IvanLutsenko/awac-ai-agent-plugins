#!/usr/bin/env python3
"""Validate crash report against mandatory field checklist.

Replaces the crash-report-reviewer Haiku agent with a deterministic script.
Structural checks (11/14) are definitive. Semantic checks (3/14: Root cause,
Trigger, Why now) use word-count heuristics — flagged as NEEDS_REVIEW when
content is too short or contains placeholder markers.

Section header policy: forensics-agents always emit English headers (Basic info,
Stack trace, Root cause, Proposed fix, Assignee, ...) — body content is in the
configured language. SECTION_ALIASES below is a safety-net for cases when the
LLM translates a header anyway. Add new languages by extending the dict — no
logic change required.

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
# Multi-language section aliases (en + ru + es + de + fr + pt + it)
#
# Section headers are normatively English (see Language Policy in
# forensics-android.md / forensics-ios.md). This dict is a safety-net for
# reports where LLM translated a header. Substring match, lowercase.
# Add a new language: append its translations to each list. No code change.
# ---------------------------------------------------------------------------

SECTION_ALIASES = {
    'basic': [
        'basic info', 'basic information', 'basic',
        'базовая информация', 'базовая',
        'información básica', 'básico',
        'grundinformationen',
        'informations de base',
        'informações básicas',
        'informazioni di base',
    ],
    'stack_trace': [
        'stack trace', 'stack-trace',
        'анализ stack trace', 'анализ стека', 'стек',
        'análisis de stack', 'pila',
        'stack-analyse', 'stapel',
        'analyse de pile',
        'rastreio de pilha',
        'analisi stack',
    ],
    'checked_files': [
        'checked file', 'analyzed file', 'files checked',
        'проверенные файлы', 'проанализированные файлы',
        'archivos revisados', 'archivos analizados',
        'überprüfte dateien', 'analysierte dateien',
        'fichiers vérifiés', 'fichiers analysés',
        'arquivos verificados',
        'file controllati',
    ],
    'executed_commands': [
        'executed command', 'commands executed', 'git command',
        'выполненные команды', 'выполненные git команды',
        'comandos ejecutados',
        'ausgeführte befehle',
        'commandes exécutées',
        'comandos executados',
        'comandi eseguiti',
    ],
    'root_cause': [
        'root cause',
        'корневая причина', 'причина',
        'causa raíz',
        'grundursache',
        'cause racine',
        'causa raiz',
        'causa principale',
    ],
    'proposed_fix': [
        'proposed fix', 'solution',
        'предлагаемый fix', 'предлагаемое решение',
        'corrección propuesta', 'solución',
        'lösungsvorschlag', 'behebung',
        'correctif proposé', 'solution proposée',
        'correção proposta',
        'correzione proposta',
    ],
    'assignee': [
        'assignee',
        'ответственный', 'исполнитель',
        'asignado', 'responsable',
        'verantwortlich', 'zuständig',
        'assigné',
        'responsável',
        'assegnatario',
    ],
    'context_prev': [
        'context', 'prevention', 'context & prevention',
        'контекст', 'контекст и предотвращение', 'предотвращение',
        'contexto', 'prevención',
        'kontext', 'prävention',
        'contexte', 'prévention',
        'prevenção',
        'contesto', 'prevenzione',
    ],
    'trigger': [
        'trigger',
        'триггер',
        'desencadenante', 'disparador',
        'auslöser',
        'déclencheur',
        'gatilho',
        'innesco',
    ],
    'why_now': [
        'why now',
        'почему сейчас',
        'por qué ahora',
        'warum jetzt',
        'pourquoi maintenant',
        'por que agora',
        'perché ora',
    ],
    'prevention': [
        'prevention',
        'предотвращение', 'профилактика',
        'prevención',
        'prävention',
        'prévention',
        'prevenção',
        'prevenzione',
    ],
}

JIRA_FIELD_ALIASES = {
    'Crash':        ['crash', 'краш', 'ошибка', 'fallo', 'absturz', 'plantage', 'queda', 'arresto'],
    'Component':    ['component', 'компонент', 'componente', 'komponente', 'composant'],
    'Assignee':     ['assignee', 'ответственный', 'исполнитель', 'asignado', 'responsable',
                     'verantwortlich', 'assigné', 'responsável', 'assegnatario'],
    'Problem':      ['problem', 'проблема', 'problema', 'problème'],
    'Stack trace':  ['stack trace', 'stack-trace', 'стек', 'pila', 'stapel', 'pile',
                     'rastreio de pilha', 'stack'],
    'Fix':          ['fix', 'исправление', 'решение', 'corrección', 'solución',
                     'behebung', 'lösung', 'correctif', 'solution',
                     'correção', 'correzione'],
    'Reproduction': ['reproduction', 'воспроизведение', 'шаги воспроизведения',
                     'reproducción', 'reproduktion', 'reprodução', 'riproduzione'],
    'Firebase':     ['firebase'],
}

BEFORE_TOKENS = ['before', 'до', 'antes', 'vorher', 'avant', 'prima']
AFTER_TOKENS  = ['after',  'после', 'después', 'nachher', 'après', 'depois', 'dopo']


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HEADER_RE = re.compile(r'^(#{2,3})\s+(.+)$')
# bold-only header: line is entirely **Text** or **Text:**  (no other content)
_BOLD_HEADER_RE = re.compile(r'^\*\*([^*]+?)\*\*\s*:?\s*$')


def split_sections(text):
    """Split markdown text into {lowercase_header: content} by ## / ### headers
    AND bold-only header lines (`**Basic info:**` / `**Базовая информация:**`).

    Forensics agents use `**Bold:**` lines as subheaders inside a `### Crash:`
    parent section — those need to be addressable too.
    """
    sections = {}
    current = None
    lines = []

    def flush(name, body_lines):
        if name is None:
            return
        # last-write-wins is fine for our checks; but skip empty bodies
        sections[name] = '\n'.join(body_lines)

    for line in text.split('\n'):
        m = _HEADER_RE.match(line)
        if m:
            flush(current, lines)
            current = m.group(2).strip().lower()
            lines = []
            continue
        bm = _BOLD_HEADER_RE.match(line.strip())
        if bm:
            flush(current, lines)
            current = bm.group(1).strip().lower()
            lines = []
            continue
        lines.append(line)
    flush(current, lines)
    return sections


def find_section(sections, key):
    """Return content of first section whose header matches any alias for `key`."""
    aliases = SECTION_ALIASES[key]
    for header, content in sections.items():
        if any(alias in header for alias in aliases):
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


def extract_subfield_any(text, aliases):
    """Find subfield labelled by any of `aliases`. Returns content until next bold-label or section break."""
    for alias in aliases:
        pattern = r'(?:\*\*)?{}(?:\*\*)?[:\s]*(.+?)(?=\n\s*\*\*[A-Za-zА-Яа-я]|\n\s*#{{2,}}|\Z)'.format(
            re.escape(alias)
        )
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1).strip()
    return None


def get_semantic_field(sections, alias_key):
    """Get text for Trigger/Why now/Prevention — from dedicated section or parent context section."""
    s = find_section(sections, alias_key)
    if s and s.strip():
        return s.strip()
    s = find_section(sections, 'context_prev')
    if s:
        return extract_subfield_any(s, SECTION_ALIASES[alias_key])
    return None


# ---------------------------------------------------------------------------
# Field checks — each returns 'OK', 'MISSING', or 'NEEDS_REVIEW'
# ---------------------------------------------------------------------------

def chk_exception(sections):
    s = find_section(sections, 'basic')
    if not s:
        return 'MISSING'
    m = re.search(r'(?:exception|error|crash\s*type|исключение|ошибка|тип\s*краша)[:\s]+(\S.+)',
                  s, re.IGNORECASE)
    return 'OK' if m and not is_placeholder_only(m.group(1)) else 'MISSING'


def chk_version(sections):
    s = find_section(sections, 'basic')
    if not s:
        return 'MISSING'
    # Match en/de/fr/it/pt 'vers...' and ru 'верс...' prefixes (handles plural/case forms)
    if re.search(r'(?i)\b(?:vers|верс)', s):
        return 'OK'
    if 'DATA UNAVAILABLE' in s.upper():
        return 'OK'
    return 'MISSING'


def chk_component(sections):
    s = find_section(sections, 'basic')
    if not s:
        return 'MISSING'
    words = set(re.findall(r'\b\w+\b', s.lower()))
    return 'OK' if words & VALID_COMPONENTS else 'MISSING'


def chk_stack_trace(sections):
    s = find_section(sections, 'stack_trace')
    if not s:
        return 'MISSING'
    line_num_hits = len(re.findall(r'[:(]\d+[):]', s))
    if line_num_hits >= 3:
        return 'OK'
    # Fallback: stack-frame "at <symbol>" lines (Java/Kotlin/iOS) — accept >=4 even
    # without explicit line numbers (system frames often omit them).
    frame_hits = len(re.findall(r'(?im)^\s*at\s+\S', s))
    if frame_hits >= 4:
        return 'OK'
    if line_num_hits >= 2 and frame_hits >= 2:
        return 'OK'
    return 'MISSING'


def chk_checked_files(sections):
    s = find_section(sections, 'checked_files')
    if not s or not s.strip():
        return 'MISSING'
    if re.search(r'(?:author|commit|blame|автор|коммит)', s, re.IGNORECASE):
        return 'OK'
    if re.search(r'`[^`]+\.\w+`', s):
        return 'OK'
    return 'MISSING'


def chk_executed_commands(sections):
    """Evidence check: the report must name a command that actually inspected code.

    `git fetch` is deliberately NOT accepted — forensics agents run it as a
    mandatory pre-flight before any blame, so it is present in every run and
    proves nothing about the agent having looked at the code.
    """
    s = find_section(sections, 'executed_commands')
    # Anchored to the start of a line (optionally a list bullet or a code fence),
    # so prose that merely mentions a command - "no inspection yet, git blame later" -
    # is not evidence that one ran.
    cmd = r'(?m)^[ \t]*(?:[-*+][ \t]+|\d+[.)][ \t]+)?`{0,3}[ \t]*git\s+(?:blame|log|ls-tree)\b'
    return 'OK' if s and re.search(cmd, s) else 'MISSING'


def chk_root_cause(sections):
    """Semantic check: >=2 sentences of technical explanation, >=15 words."""
    s = find_section(sections, 'root_cause')
    if not s or not s.strip():
        return 'MISSING'
    if is_placeholder_only(s):
        return 'NEEDS_REVIEW'
    if word_count(s) < 15:
        return 'NEEDS_REVIEW'
    if sentence_count(s) >= 2:
        return 'OK'
    return 'NEEDS_REVIEW'


def _has_token_with_codeblock(section_body, tokens):
    lower = section_body.lower()
    pos = -1
    for tok in tokens:
        idx = lower.find(tok)
        if idx != -1 and (pos == -1 or idx < pos):
            pos = idx
    if pos == -1:
        return False
    return '```' in section_body[pos:]


def _has_subsection_with_codeblock(sections, tokens):
    """Bold-only split may peel `**Before:**`/`**After:**` into their own sections.
    Check if any section header equals (or starts with) one of the tokens AND its
    body contains a code fence."""
    for header, body in sections.items():
        head = header.strip(': ').strip()
        if head in tokens and '```' in body:
            return True
    return False


def chk_fix_before(sections):
    if _has_subsection_with_codeblock(sections, BEFORE_TOKENS):
        return 'OK'
    s = find_section(sections, 'proposed_fix')
    if not s:
        return 'MISSING'
    return 'OK' if _has_token_with_codeblock(s, BEFORE_TOKENS) else 'MISSING'


def chk_fix_after(sections):
    if _has_subsection_with_codeblock(sections, AFTER_TOKENS):
        return 'OK'
    s = find_section(sections, 'proposed_fix')
    if not s:
        return 'MISSING'
    return 'OK' if _has_token_with_codeblock(s, AFTER_TOKENS) else 'MISSING'


def chk_assignee(sections):
    s = find_section(sections, 'assignee')
    if not s or not s.strip():
        return 'MISSING'
    if is_placeholder_only(s):
        return 'MISSING'
    if re.search(r'git\s*blame|git\s*log', s, re.IGNORECASE):
        return 'OK'
    # TBD with justification (long text explaining why) is acceptable
    if PLACEHOLDER_RE.search(s) and word_count(s) >= 10:
        return 'OK'
    if word_count(s) >= 3:
        return 'OK'
    return 'MISSING'


def chk_trigger(sections):
    """Semantic check: specific action/event."""
    text = get_semantic_field(sections, 'trigger')
    if not text:
        return 'MISSING'
    if is_placeholder_only(text):
        return 'NEEDS_REVIEW'
    if word_count(text) < 3:
        return 'NEEDS_REVIEW'
    return 'OK'


def chk_why_now(sections):
    """Semantic check: explanation of what changed."""
    text = get_semantic_field(sections, 'why_now')
    if not text:
        return 'MISSING'
    if is_placeholder_only(text):
        return 'NEEDS_REVIEW'
    if word_count(text) < 5:
        return 'NEEDS_REVIEW'
    return 'OK'


def chk_prevention(sections):
    text = get_semantic_field(sections, 'prevention')
    if not text:
        return 'MISSING'
    if is_placeholder_only(text):
        return 'MISSING'
    return 'OK' if word_count(text) >= 3 else 'MISSING'


def chk_jira_brief(text, console_url=None):
    """Check JIRA Brief section. Returns (status, missing_sub_fields)."""
    m = re.search(r'#{2,3}\s*JIRA\s*Brief(.*?)(?=\n#{2,3}\s[^#]|\Z)',
                  text, re.IGNORECASE | re.DOTALL)
    if not m:
        return 'MISSING', []
    jira = m.group(1)
    missing = []
    for canonical, aliases in JIRA_FIELD_ALIASES.items():
        found = False
        for alias in aliases:
            if re.search(r'(?:\*\*)?{}(?:\*\*)?[:\s]'.format(re.escape(alias)),
                         jira, re.IGNORECASE):
                found = True
                break
        if not found:
            missing.append(canonical)
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
