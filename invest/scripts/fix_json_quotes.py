import json
import re

path = r'e:\AI_Generated_Projects\agent_demos\invest\prd_evolution.json'
content = open(path, 'r', encoding='utf-8').read()

# Fix specific known problematic patterns by replacing " inside Chinese text with 「」
# Pattern: a CJK/punctuation character followed by " followed by more text (not JSON structural)
# Detect " that is NOT JSON structural by context:
# A structural " is preceded by: {, [, :, ,, whitespace, or start of file
# A structural " is followed by: }, ], :, ,, whitespace, or end of file
# A content " (the one we need to fix) is between text content

# Let me use a simple regex-based state approach:
# Match: (non-ASCII or CJK punctuation) " (anything that's not a JSON delimiter)
# This will match content quotes that follow Chinese text

# More targeted: the issue is in acceptanceCriteria strings where " appears as part of quoted text
# These are always preceded by a CJK char or CJK punctuation like — (U+2014)

# Let me find ALL ASCII double quotes and categorize them
lines = content.split('\n')
problematic_lines = []

for i, line in enumerate(lines):
    # Skip lines that don't look like string values
    stripped = line.strip()
    if not stripped.startswith('"'):
        continue
    
    # Check if this line (or nearby context) has an issue
    # Find " that's not at the start/end of the stripped line
    in_string = False
    quote_positions = []
    for j, ch in enumerate(stripped):
        if ch == '"':
            quote_positions.append(j)
    
    # If there are more than 2 quotes on a well-formed JSON string line,
    # or if quotes appear in the middle of the content, we have issues
    if len(quote_positions) > 2:
        problematic_lines.append((i+1, stripped))

if problematic_lines:
    print(f"Found {len(problematic_lines)} lines with >2 quotes:")
    for ln, txt in problematic_lines:
        print(f"  Line {ln}: {txt[:150]}")
else:
    print("No lines with obvious quote issues found via this method.")

# Alternative approach: rebuild the file by escaping internal quotes
# Strategy: for each line that is a string value in a JSON array/object,
# if the content part contains unescaped ", escape them

# Actually the simplest correct approach: find every " that has a CJK char
# or CJK punctuation before it (within the same string value) and replace with 「」
# But we need to NOT match the opening " of a string value.

# Let me use a more precise regex: find " preceded by a char that is NOT
# a JSON structural character (not :, {, [, ,, whitespace, newline)
# AND preceded by a char whose codepoint > 127 (non-ASCII) or is CJK punct

content_quote_pattern = re.compile(
    r'(?<=[^\x00-\x20\x22\x2c\x3a\x5b\x5d\x7b\x7d])\x22'
    # preceding char is NOT: control chars, space, ", comma, colon, brackets, braces
)

# But this might still be too aggressive. Let me be conservative:
# Only replace " that follows a character with codepoint > 127
conservative_pattern = re.compile(r'(?<=[^\x00-\x7f])\x22')

matches = list(conservative_pattern.finditer(content))
print(f"\nFound {len(matches)} quotes following non-ASCII chars:")

# Filter: don't match if this " is the closing quote of a JSON string
# A closing " would be followed by , or ] or } or : or whitespace or newline
real_fixes = []
for m in matches:
    pos = m.start()
    # Check what follows this "
    after = content[pos+1:pos+2] if pos+1 < len(content) else ''
    if after not in ('', ',', ']', '}', ':', ' ', '\n', '\r', '\t'):
        real_fixes.append(m)
        line_num = content[:pos].count('\n') + 1
        ctx_start = max(0, pos - 15)
        ctx_end = min(len(content), pos + 15)
        print(f"  Line {line_num}, pos {pos}: ...{content[ctx_start:ctx_end]}...")
    # Also check if this is preceded by a structural char - if so skip
    before = content[pos-1:pos] if pos > 0 else ''
    # Actually all matches already pass the non-ASCII lookup, so before is non-ASCII

print(f"\n{len(real_fixes)} quotes to fix (excluding structural closers)")

# Apply fixes
fixed = content
for m in reversed(real_fixes):
    fixed = fixed[:m.start()] + '「' + fixed[m.end():]

# Verify
try:
    json.loads(fixed)
    print("\nFixed JSON is valid!")
    open(path, 'w', encoding='utf-8').write(fixed)
    print("Written fixed content to file.")
except json.JSONDecodeError as e:
    print(f"\nStill invalid at line {e.lineno}, col {e.colno}: {e.msg}")
    err_pos = e.pos
    ctx_start = max(0, err_pos - 40)
    ctx_end = min(len(fixed), err_pos + 40)
    print(f"  Context: {repr(fixed[ctx_start:ctx_end])}")
