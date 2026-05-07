import json, os

path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prd_quant_evolution.json')
d = json.load(open(path, 'r', encoding='utf-8'))

print(f'JSON valid. Project: {d["project"]}')
print(f'Phases: {list(d["evolution_phases"].keys())}')
print(f'User Stories: {len(d["userStories"])}')
print()

ids = {s['id'] for s in d['userStories']}
for s in d['userStories']:
    acs = len(s['acceptanceCriteria'])
    deps = s.get('dependencies', [])
    print(f'  {s["id"]}: {s["title"][:60]}')
    print(f'    ACs={acs}, Deps={deps}')

# Check deps
external_deps = {'US-001', 'US-002', 'US-003', 'US-026', 'US-E02'}
bad_deps = []
for s in d['userStories']:
    for dep in s.get('dependencies', []):
        if dep not in ids and dep not in external_deps:
            bad_deps.append((s['id'], dep))

if bad_deps:
    print(f'\nWARNING: {len(bad_deps)} unresolvable dependencies:')
    for bd in bad_deps:
        print(f'  {bd[0]} -> {bd[1]}')
else:
    print('\nAll dependencies resolvable.')

# Check phase story references
for pname, pinfo in d['evolution_phases'].items():
    for sid in pinfo['stories']:
        if sid not in ids:
            print(f'WARNING: Phase {pname} refs unknown {sid}')

print('\nValidation complete.')
