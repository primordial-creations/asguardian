"""
Heimdall Duplication Detector - block extraction and clone-finding helpers.

Standalone functions for extracting code blocks and grouping them into
clone families. Accepts config as explicit parameters.
"""

import ast
import difflib
import hashlib
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple, cast

from Asgard.Heimdall.Quality.models.duplication_models import (
    CloneFamily,
    CodeBlock,
    DuplicationConfig,
    DuplicationType,
)


# Normalization patterns for token comparison
NORMALIZATION_PATTERNS = [
    (r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', 'IDENT'),  # Variable/function names
    (r'\b\d+\.?\d*\b', 'NUM'),  # Numbers
    (r'"[^"]*"', 'STR'),  # Double-quoted strings
    (r"'[^']*'", 'STR'),  # Single-quoted strings
    (r'#.*$', '', re.MULTILINE),  # Python comments
    (r'//.*$', '', re.MULTILINE),  # C-style comments
]


def tokenize(content: str) -> List[str]:
    """Tokenize code content."""
    tokens = re.findall(r'\w+|[^\w\s]', content)
    return [t.strip() for t in tokens if t.strip()]


def normalize_tokens(tokens: List[str]) -> List[str]:
    """Normalize tokens for structural comparison."""
    token_string = " ".join(tokens)

    for pattern, replacement, *flags in NORMALIZATION_PATTERNS:
        flag = flags[0] if flags else 0
        token_string = re.sub(cast(str, pattern), cast(str, replacement), token_string, flags=cast(int, flag))

    return [t.strip() for t in token_string.split() if t.strip()]


def hash_tokens(tokens: List[str]) -> str:
    """Calculate hash of token sequence."""
    token_string = "".join(tokens)
    return hashlib.md5(token_string.encode()).hexdigest()


def is_meaningful_block(lines: List[str], min_block_size: int) -> bool:
    """Check if block contains meaningful code."""
    meaningful = 0
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and len(stripped) > 3:
            meaningful += 1
    return cast(bool, meaningful >= min_block_size // 2)


def extract_python_blocks(
    content: str,
    lines: List[str],
    file_path: str,
    relative_path: str,
    config: DuplicationConfig,
) -> List[CodeBlock]:
    """Extract code blocks based on Python function/class boundaries."""
    blocks: List[CodeBlock] = []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return extract_sliding_window_blocks(lines, file_path, relative_path, config)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start_line = node.lineno
            end_line = node.end_lineno or start_line

            if end_line - start_line + 1 >= config.min_block_size:
                block_lines = lines[start_line - 1:end_line]
                block_content = "\n".join(block_lines)

                tokens = tokenize(block_content)
                normalized = normalize_tokens(tokens)
                hash_value = hash_tokens(normalized)

                blocks.append(CodeBlock(
                    file_path=file_path,
                    relative_path=relative_path,
                    start_line=start_line,
                    end_line=end_line,
                    content=block_content,
                    tokens=tokens,
                    normalized_tokens=normalized,
                    hash_value=hash_value,
                    line_count=end_line - start_line + 1,
                ))

    return blocks


def extract_sliding_window_blocks(
    lines: List[str],
    file_path: str,
    relative_path: str,
    config: DuplicationConfig,
) -> List[CodeBlock]:
    """Extract code blocks using sliding window approach."""
    blocks: List[CodeBlock] = []
    min_size = config.min_block_size
    step = max(1, min_size // 2)

    for start in range(0, len(lines) - min_size + 1, step):
        end = start + min_size
        block_lines = lines[start:end]
        block_content = "\n".join(block_lines)

        if not is_meaningful_block(block_lines, min_size):
            continue

        tokens = tokenize(block_content)
        normalized = normalize_tokens(tokens)
        hash_value = hash_tokens(normalized)

        blocks.append(CodeBlock(
            file_path=file_path,
            relative_path=relative_path,
            start_line=start + 1,
            end_line=end,
            content=block_content,
            tokens=tokens,
            normalized_tokens=normalized,
            hash_value=hash_value,
            line_count=min_size,
        ))

    return blocks


def extract_blocks_from_file(
    file_path: Path, root_path: Path, config: DuplicationConfig
) -> Tuple[List[CodeBlock], int]:
    """
    Extract code blocks from a single file.

    Returns:
        Tuple of (list of code blocks, total lines in file)
    """
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return [], 0

    lines = content.splitlines()
    total_lines = len(lines)

    if total_lines < config.min_block_size:
        return [], total_lines

    relative_path = str(file_path.relative_to(root_path))

    if file_path.suffix == ".py":
        blocks = extract_python_blocks(
            content, lines, str(file_path), relative_path, config
        )
    else:
        blocks = extract_sliding_window_blocks(
            lines, str(file_path), relative_path, config
        )

    return blocks, total_lines


def calculate_similarity(block1: CodeBlock, block2: CodeBlock) -> float:
    """Calculate similarity between two code blocks."""
    matcher = difflib.SequenceMatcher(
        None, block1.normalized_tokens, block2.normalized_tokens
    )
    return matcher.ratio()


def find_clone_families(
    blocks: List[CodeBlock], config: DuplicationConfig
) -> List[CloneFamily]:
    """
    Find clone families among code blocks.

    Groups blocks by similarity into clone families.
    """
    families: List[CloneFamily] = []
    used_blocks: Set[int] = set()

    hash_groups: Dict[str, List[int]] = defaultdict(list)
    for i, block in enumerate(blocks):
        hash_groups[block.hash_value].append(i)

    for hash_value, indices in hash_groups.items():
        if len(indices) >= 2:
            family = CloneFamily(
                match_type=DuplicationType.EXACT,
                average_similarity=1.0,
                severity=CloneFamily.calculate_severity(len(indices)),
            )
            for idx in indices:
                family.add_block(blocks[idx])
                used_blocks.add(idx)
            families.append(family)

    remaining = [i for i in range(len(blocks)) if i not in used_blocks]

    for i in range(len(remaining)):
        if remaining[i] in used_blocks:
            continue

        idx_i = remaining[i]
        similar_indices = [idx_i]

        for j in range(i + 1, len(remaining)):
            if remaining[j] in used_blocks:
                continue

            idx_j = remaining[j]
            similarity = calculate_similarity(blocks[idx_i], blocks[idx_j])

            if similarity >= config.similarity_threshold:
                similar_indices.append(idx_j)
                used_blocks.add(idx_j)

        if len(similar_indices) >= 2:
            used_blocks.add(idx_i)
            avg_similarity = sum(
                calculate_similarity(blocks[idx_i], blocks[k])
                for k in similar_indices[1:]
            ) / (len(similar_indices) - 1) if len(similar_indices) > 1 else 1.0

            match_type = (
                DuplicationType.STRUCTURAL if avg_similarity > 0.9
                else DuplicationType.SIMILAR
            )

            family = CloneFamily(
                match_type=match_type,
                average_similarity=avg_similarity,
                severity=CloneFamily.calculate_severity(len(similar_indices)),
            )
            for idx in similar_indices:
                family.add_block(blocks[idx])
            families.append(family)

    return families
