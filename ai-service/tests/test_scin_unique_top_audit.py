import importlib.util
from pathlib import Path
import unittest
F=Path(__file__).resolve().parents[1]/'reports/teacher_scin_unique_top_audit_20261106/run_audit.py'
s=importlib.util.spec_from_file_location('scin302',F);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class SourceDecisionTests(unittest.TestCase):
 def test_tie_is_not_resolved_by_dictionary_order(self):
  a=m.decision("{'Eczema':.5,'Psoriasis':.5}");b=m.decision("{'Psoriasis':.5,'Eczema':.5}")
  self.assertEqual(a['strict_target'],None);self.assertEqual(b['strict_target'],None)
  self.assertEqual(a['top_labels'],b['top_labels']);self.assertNotEqual(a['legacy_first_target'],b['legacy_first_target'])
 def test_outside_tie_is_ambiguous_without_alias_expansion(self):
  d=m.decision("{'Eczema':.5,'Allergic Contact Dermatitis':.5}")
  self.assertIsNone(d['strict_target']);self.assertIn('OUTSIDE_EIGHT',d['possible_legacy_targets'])
 def test_unique_top_does_not_mean_clinically_confirmed(self):
  d=m.decision("{'Cutaneous lupus':.5,'Eczema':.25,'Psoriasis':.25}")
  self.assertEqual(d['strict_target'],'Lupus');self.assertFalse(d['clinical_confirmation'])
 def test_invalid_or_duplicate_weights_fail(self):
  for raw in ["{'Eczema':-1}","{'Eczema':1.1}","{'Eczema':True}","{}","{'Eczema':.5,'Eczema':.5}"]:
   with self.assertRaises(ValueError):m.decision(raw)
 def test_missing_narrow_alias_does_not_invent_label(self):
  self.assertIsNone(m.decision("{'Allergic Contact Dermatitis':1}")['strict_target'])
 def test_case_size_matched_control_and_class_weight_sums(self):
  rows=[dict(path=f'base/{c}',label=c,source='original_train') for c in m.CLASSES]
  units=[]
  for case,tied in [('tie',True),('clean',False)]:
   paths=[case+'/1',case+'/2'];rows.extend(dict(path=p,label='Eczema',source='SCIN') for p in paths)
   units.append(dict(case_id=case,label='Eczema',images=2,paths=paths,decision=dict(unique_top=not tied)))
  d=m.masks(rows,units)
  self.assertEqual(d['arms']['unique_top']['retained_by_class'],d['arms']['matched_control']['retained_by_class'])
  self.assertEqual(set(d['arms']['unique_top']['excluded_paths']),{'tie/1','tie/2'})
  self.assertFalse(set(d['arms']['unique_top']['excluded_paths'])&set(d['arms']['matched_control']['excluded_paths']))
 def test_no_approximate_control_when_matching_impossible(self):
  rows=[dict(path=f'base/{c}',label=c,source='original_train') for c in m.CLASSES]
  u=dict(case_id='a',label='Lupus',images=1,paths=['a'],decision=dict(unique_top=False))
  rows.append(dict(path='a',label='Lupus',source='SCIN'))
  with self.assertRaises(ValueError):m.masks(rows,[u])
if __name__=='__main__':unittest.main()
