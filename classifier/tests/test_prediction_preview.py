"""Preview scores may be shown before acceptance, but cannot qualify a label."""
import unittest
from kinevoa_classifier.preview import prediction_preview

class PreviewTests(unittest.TestCase):
    def test_rejected_top_class_remains_visible_without_changing_decision(self):
        result={'exercise':'unknown','source':'unknown','raw_label':'shoulder press','score':.42}
        p=prediction_preview(result)
        self.assertEqual(p,{'preview_label':'Unknown','preview_score':None,'preview_source':'image'})
        self.assertEqual(result['exercise'],'unknown')
    def test_allowed_low_score_preview_is_still_visible(self):
        p=prediction_preview({'exercise':'unknown','source':'unknown','raw_label':'squat','score':.42})
        self.assertEqual(p['preview_label'],'Squat');self.assertEqual(p['preview_score'],.42)
    def test_movement_does_not_inherit_unrelated_image_probability(self):
        p=prediction_preview({'exercise':'squat','source':'movement','raw_label':'deadlift','score':.98})
        self.assertEqual(p['preview_label'],'Squat');self.assertIsNone(p['preview_score'])
    def test_crop_preview_uses_crop_score(self):
        p=prediction_preview({'exercise':'pushup','source':'person_crop','raw_label':'plank','score':.9,'crop_label':'push up','crop_score':.72})
        self.assertEqual(p['preview_label'],'Push-up');self.assertEqual(p['preview_score'],.72)
    def test_invalid_scores_are_not_displayed(self):
        for score in [float('nan'),float('inf'),-1,2,True,'90']:
            self.assertIsNone(prediction_preview({'exercise':'unknown','score':score})['preview_score'])
    def test_cloud_confirmation_has_no_fabricated_probability(self):
        p=prediction_preview({'exercise':'lunge','source':'openai_vision','cloud_confirmed':True,'display_name':'Lunge','score':.99})
        self.assertEqual(p['preview_label'],'Unknown');self.assertIsNone(p['preview_score'])
if __name__=='__main__':unittest.main()
