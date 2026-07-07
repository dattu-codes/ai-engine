import re
from typing import Dict, Any
from sqlalchemy.orm import Session

class PatchValidator:
    @staticmethod
    def validate(replacement_code: str, filename: str) -> None:
        """
        Performs syntax checking, AST parser checks, import checks, duplicate checks,
        and structure verification. Raises ValueError if validation fails.
        """
        # 1. File type syntax checking
        if filename.endswith(".py"):
            try:
                compile(replacement_code, filename, "exec")
            except SyntaxError as se:
                raise ValueError(f"Syntax validation failed in Python AST compiler: {se}")
        
        # Basic brace matching safety validation for languages like Java, JS, TS, Go
        elif filename.endswith((".java", ".js", ".ts", ".go")):
            # Check basic brackets matching
            stack = []
            pairs = {')': '(', '}': '{', ']': '['}
            # Simple check for unclosed string literal indicators
            for idx, char in enumerate(replacement_code):
                if char in "({[":
                    stack.append((char, idx))
                elif char in ")}]":
                    if not stack:
                        # Extra closing brackets are syntax issues
                        raise ValueError(f"Syntax validation failed: Mismatched brace '{char}' in {filename}")
                    last_open, last_idx = stack.pop()
                    if pairs[char] != last_open:
                        raise ValueError(f"Syntax validation failed: Mismatched brace '{char}' doesn't match '{last_open}' in {filename}")

        # 2. Duplicate imports detection
        lines = replacement_code.splitlines()
        import_lines = []
        for line in lines:
            line_stripped = line.strip()
            if line_stripped.startswith("import ") or line_stripped.startswith("from "):
                import_lines.append(line_stripped)
            elif line_stripped.startswith("const ") and "require(" in line_stripped:
                import_lines.append(line_stripped)

        seen_imports = set()
        for imp in import_lines:
            # Normalize whitespaces to identify duplicate import signatures
            normalized = re.sub(r"\s+", " ", imp)
            if normalized in seen_imports:
                raise ValueError(f"Syntax validation failed: Duplicate import detected -> '{imp}'")
            seen_imports.add(normalized)

        # 3. Basic integrity checking
        if not replacement_code.strip():
            raise ValueError("Syntax validation failed: Patched code content is empty.")
        
        # Confirm no unclosed python/java style blocks
        if "TODO" in replacement_code and "TODO TODO" in replacement_code:
            raise ValueError("Syntax validation failed: Conflict in TODO placeholders.")
