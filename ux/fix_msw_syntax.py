#!/usr/bin/env python3
"""Fix MSW 2.x syntax to MSW 1.x"""

import re
import sys
from pathlib import Path

def fix_msw_syntax(content):
    """Convert MSW 2.x syntax to MSW 1.x"""

    # Fix imports
    content = re.sub(
        r'import\s*{\s*http\s*,\s*res\s*,\s*json\s*}\s*from\s*["\']msw["\']',
        'import { rest } from "msw"',
        content
    )

    # Fix handler signatures - () => to (req, res, ctx) =>
    # Pattern: rest.METHOD("url", () =>
    content = re.sub(
        r'(rest\.\w+\([^)]*,\s*)\(\)\s*=>',
        r'\1(req, res, ctx) =>',
        content
    )

    # Fix single-line res(json(...)) -> res(ctx.json(...))
    # Pattern: res(json(...)) where ... doesn't contain commas or closing paren at top level
    content = re.sub(
        r'res\(json\(([^)]+)\)\)',
        r'res(ctx.json(\1))',
        content
    )

    # Fix multiline res( json(...), { status: X } ) patterns
    # This is more complex - need to handle multiline
    # First, handle the pattern: res( json({...}), { status: X } )
    pattern = r'res\(\s*json\((\{[^}]*\})\),\s*\{\s*status:\s*(\d+)\s*\}\s*\)'
    replacement = r'res(\n        ctx.status(\2),\n        ctx.json(\1)\n      )'
    content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)

    return content

if __name__ == '__main__':
    test_dir = Path('/workspace/ux/src/api/services/__tests__')

    for test_file in test_dir.glob('*.test.ts'):
        if test_file.name == 'simple.test.ts':
            continue  # Already correct

        print(f"Fixing {test_file.name}...")
        content = test_file.read_text()
        fixed = fix_msw_syntax(content)
        test_file.write_text(fixed)
        print(f"  ✓ Fixed {test_file.name}")

    print("Done!")
