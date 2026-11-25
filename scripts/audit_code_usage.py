"""Conservative AST reference inventory; no imports/execution of the analysed code.

Usage: python scripts/audit_code_usage.py --out out/code-usage.json
No static references means a deletion candidate, not proof of runtime unreachability.
"""
from __future__ import annotations
import argparse
import ast
from collections import defaultdict
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def inventory(root: Path):
    files = sorted(p for folder in ('aitx', 'scripts', 'tests') for p in (root/folder).rglob('*.py') if '__pycache__' not in p.parts)
    modules = {'.'.join(p.relative_to(root).with_suffix('').parts).removesuffix('.__init__'): p for p in files if p.relative_to(root).parts[0] == 'aitx'}
    refs, incoming, definitions = defaultdict(list), defaultdict(list), []
    for path in files:
        rel = str(path.relative_to(root))
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            name = node.id if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) else node.attr if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load) else None
            if name: refs[name].append({'file': rel, 'line': node.lineno, 'kind': 'name_or_attribute'})
            if isinstance(node, ast.ImportFrom):
                base = node.module or ''
                for alias in node.names:
                    refs[alias.name].append({'file': rel, 'line': node.lineno, 'kind': 'import'})
                    target = base+'.'+alias.name
                    for mod in (base, target):
                        if mod in modules: incoming[mod].append({'file': rel, 'line': node.lineno})
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in modules: incoming[alias.name].append({'file': rel, 'line': node.lineno})
        if not rel.startswith('aitx/'): continue
        def walk(node, scope=()):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    definitions.append({'file': rel, 'line': child.lineno, 'name': child.name, 'qualified_name': '.'.join(scope+(child.name,)), 'decorators': [ast.unparse(d) for d in child.decorator_list]})
                    walk(child, scope+(child.name,))
                elif isinstance(child, ast.ClassDef): walk(child, scope+(child.name,))
                else: walk(child, scope)
        walk(tree)
    for fn in definitions:
        fn['references'] = refs[fn['name']]
        fn['classification'] = ('protocol_method' if fn['name'].startswith('__') else 'no_static_reference' if not fn['references'] else 'production_reference' if any(s['file'].startswith('aitx/') for s in fn['references']) else 'external_reference_only')
    mods = [{'module': name, 'file': str(path.relative_to(root)), 'imports': incoming[name], 'classification': 'package_marker' if path.name == '__init__.py' else 'no_static_import' if not incoming[name] else 'imported'} for name, path in sorted(modules.items())]
    return {'method': 'AST identifier/attribute loads plus imports, matched conservatively by symbol name. Same-name symbols can hide dead code; references are not necessarily calls. Dynamic import/getattr/reflection are not resolved. Do not equate this with never executed.', 'scope': [str(p.relative_to(root)) for p in files], 'functions': definitions, 'modules': mods}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    result = inventory(ROOT)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'functions': len(result['functions']), 'no_static_reference': [f"{f['file']}:{f['line']} {f['qualified_name']}" for f in result['functions'] if f['classification'] == 'no_static_reference'], 'no_static_import': [m['module'] for m in result['modules'] if m['classification'] == 'no_static_import']}, ensure_ascii=False))

if __name__ == '__main__': main()
