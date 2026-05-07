import json
import os

path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prd_evolution.json')
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f'JSON valid. Project: {data["project"]}')
print(f'Phases: {list(data["evolution_phases"].keys())}')
print(f'User Stories count: {len(data["userStories"])}')
print()

for s in data['userStories']:
    print(f'  {s["id"]}: {s["title"][:70]}')
    print(f'    ACs: {len(s["acceptanceCriteria"])} | Deps: {s.get("dependencies",[])}')
    for i, ac in enumerate(s['acceptanceCriteria']):
        print(f'      [{i+1}] {ac[:100]}...' if len(ac) > 100 else f'      [{i+1}] {ac}')
    print()

# check all deps reference valid stories
all_ids = {s['id'] for s in data['userStories']}
for s in data['userStories']:
    for dep in s.get('dependencies', []):
        if dep not in all_ids:
            print(f'WARNING: {s["id"]} depends on unknown {dep}')

# verify phase stories match
for phase_name, phase_info in data['evolution_phases'].items():
    for sid in phase_info['stories']:
        if sid not in all_ids:
            print(f'WARNING: Phase {phase_name} references unknown story {sid}')

print('Validation complete.')
