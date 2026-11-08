from pathlib import Path
import importlib.util,unittest
F=Path(__file__).resolve().parents[1]/'reports/teacher_open_case_photo_intake_20261106/intake.py'
s=importlib.util.spec_from_file_location('intake304',F);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class IntakeTests(unittest.TestCase):
 def test_anonymous_s3_url_only(self):
  self.assertEqual(m.https_object('s3://pmc-oa-opendata/PMC1.1/a.jpg?md5=abc'),'https://pmc-oa-opendata.s3.amazonaws.com/PMC1.1/a.jpg?md5=abc')
  for u in ['https://attacker.test/a','s3://different/a','https://pmc-oa-opendata.s3.amazonaws.com/../x']:
   with self.assertRaises(ValueError):m.https_object(u)
 def test_no_ND_or_TDM_as_image_license(self):
  self.assertNotIn('CC BY-NC-ND',m.ALLOWED_LICENSES);self.assertNotIn('TDM',m.ALLOWED_LICENSES);self.assertIn('CC BY-NC',m.ALLOWED_LICENSES)
 def test_narrow_single_disease_titles(self):
  self.assertEqual(m.title_label('Discoid lupus erythematosus: a case report'),'Lupus')
  self.assertIsNone(m.title_label('Concurrent tinea corporis and plaque psoriasis'))
  self.assertIsNone(m.title_label('Systemic lupus nephritis'))
  self.assertIsNone(m.title_label('Tinea versicolor'))
 def test_no_microscopy_or_mixed_timepoints(self):
  for cap in ['Clinical photographs of tinea corporis and histopathology (H&E)','Clinical photograph of plaque psoriasis after treatment']:
   self.assertTrue(m.figure_reasons(cap,cap,'Tinea' if 'tinea' in cap else 'Psoriasis'))
 def test_no_third_party_permission_by_parent_license(self):
  cap='Clinical photographs of discoid lupus erythematosus'
  self.assertTrue(m.figure_reasons(cap,'Image reproduced with permission from VisualDx.','Lupus'))
  self.assertTrue(m.figure_reasons(cap,'<fig><permissions><license>CC BY-NC-ND</license></permissions></fig>','Lupus'))
  self.assertEqual(m.figure_reasons(cap,'Original clinical image.','Lupus'),[])
 def test_graphic_media_binding(self):
  urls=['s3://pmc-oa-opendata/PMC1.1/paper-g001.jpg?md5=abc','s3://pmc-oa-opendata/PMC1.1/paper-g002.jpg']
  self.assertEqual(m.media_for_graphic('paper-g001',urls),[urls[0]])
  self.assertEqual(m.media_for_graphic('missing',urls),[])
if __name__=='__main__':unittest.main()
