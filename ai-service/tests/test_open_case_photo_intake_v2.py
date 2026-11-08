from pathlib import Path
import importlib.util,unittest
F=Path(__file__).resolve().parents[1]/'reports/teacher_open_case_photo_intake_20261106/intake_v2.py'
s=importlib.util.spec_from_file_location('intake304v2',F);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class IntakeCompatibilityTests(unittest.TestCase):
 def test_native_webp_is_bound_without_reencoding(self):
  url='s3://pmc-oa-opendata/PMC1.1/figure1.webp?md5=abcd'
  self.assertEqual(m.media_for_graphic('figure1.webp',[url]),[url])
 def test_only_case_titles_not_reviews(self):
  self.assertEqual(m.title_label('Discoid lupus erythematosus: a case report'),'Lupus')
  self.assertIsNone(m.title_label('Modern therapies for discoid lupus: a narrative review'))
  self.assertIsNone(m.title_label('Concurrent tinea corporis and plaque psoriasis: a case report'))
 def test_queries_do_not_use_unsupported_publication_type(self):
  self.assertTrue(all('[Publication Type]' not in q and '"case report"[Title]' in q for q in m.QUERIES.values()))
 def test_no_network_plot_as_photo(self):
  self.assertTrue(m.figure_reasons('Network evidence plots of plaque psoriasis outcomes','clinical','Psoriasis'))
 def test_rights_and_diagnosis_rules_unchanged(self):
  self.assertNotIn('CC BY-NC-ND',m.ALLOWED_LICENSES)
  self.assertTrue(m.figure_reasons('Clinical photographs of DLE','<fig><permissions>NC</permissions></fig>','Lupus'))
  self.assertTrue(m.figure_reasons('Clinical photographs of DLE after treatment','','Lupus'))
 def test_no_untrusted_object_urls(self):
  with self.assertRaises(ValueError):m.https_object('https://example.com/img.webp')
 def test_clinical_caption_can_pass(self):
  self.assertEqual(m.figure_reasons('Clinical presentation of DLE. The scalp shows erythematous plaques.','Original figure','Lupus'),[])
if __name__=='__main__':unittest.main()
