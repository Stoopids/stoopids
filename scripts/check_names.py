#!/usr/bin/env python3
"""Fail if any team_name in config.json is longer than the shared team limit (shared/ui.js LIMITS.team, default 15)."""
import json,re,sys,os
root=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lim=15
try:
  m=re.search(r'team:(\d+)',open(os.path.join(root,'shared/ui.js')).read()); lim=int(m.group(1)) if m else lim
except OSError: pass
bad=[(o.get('name'),o.get('team_name')) for o in json.load(open(os.path.join(root,'config.json'))).get('owners',[]) if len(o.get('team_name') or '')>lim]
for n,t in bad: print(f'check_names: {n}: "{t}" is {len(t)} chars (max {lim})')
print('check_names:', 'FAIL' if bad else 'OK'); sys.exit(1 if bad else 0)
