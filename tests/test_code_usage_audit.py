from scripts.audit_code_usage import inventory


def test_ast_inventory_counts_alias_and_attribute_references_without_importing_code(tmp_path):
    for folder in ('aitx', 'scripts', 'tests'):
        (tmp_path/folder).mkdir()
    (tmp_path/'aitx/example.py').write_text('raise RuntimeError("must not execute")\ndef dead(): pass\ndef callback(): pass\nclass Example:\n    @property\n    def flag(self): return True\n')
    (tmp_path/'scripts/entry.py').write_text('from aitx.example import callback as run\nrun()\nobj.flag\n')
    result = inventory(tmp_path)
    functions = {f['name']: f for f in result['functions']}
    assert functions['dead']['classification'] == 'no_static_reference'
    assert functions['callback']['classification'] == 'external_reference_only'
    assert functions['flag']['references'][0]['kind'] == 'name_or_attribute'
    assert result['modules'][0]['classification'] == 'imported'
