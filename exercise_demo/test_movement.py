"""Behaviour checks independent of pose ML weights; real-video tests are separate."""
import unittest
from dataclasses import replace
from movement import Features, MovementRecognizer, Cycle, angle


def feature(t,knee=175,hip=.4,**kw):
    args=dict(time=t,upright=True,horizontal=False,knee=knee,elbow=175,arm=10,
        hip=hip,ankle_x=.5,ankle_y=.9,scale=.25,bilateral=True,arms_out=False)
    args.update(kw);return Features(**args)

class MovementTests(unittest.TestCase):
    def test_static_standing_and_crouch_are_unknown(self):
        for knee in [175,90]:
            rec=MovementRecognizer()
            self.assertTrue(all(rec.update(feature(i*.25,knee))['exercise']=='unknown' for i in range(40)))
    def test_squat_requires_return_then_expires(self):
        rec=MovementRecognizer()
        knees=[175,175,170,150,115,95,110,145,175,175]
        out=[rec.update(feature(i*.25,k,hip=.4+(175-k)/600)) for i,k in enumerate(knees)]
        self.assertTrue(all(r['exercise']=='unknown' for r in out[:8]))
        self.assertEqual(out[-1]['exercise'],'squat')
        for i in range(10,24):result=rec.update(feature(i*.25))
        self.assertEqual(result['exercise'],'unknown')
    def test_missing_pose_and_gap_break_cycles(self):
        rec=MovementRecognizer()
        for i,k in enumerate([175,175,160,110]):rec.update(feature(i*.5,k))
        rec.update(None)
        self.assertEqual(rec.update(feature(4,175))['exercise'],'unknown')
        rec=MovementRecognizer()
        for i,k in enumerate([175,175,160,110]):rec.update(feature(i*.5,k))
        self.assertEqual(rec.update(feature(5,175))['exercise'],'unknown')
    def test_camera_translation_does_not_complete_squat(self):
        rec=MovementRecognizer()
        for i,k in enumerate([175,175,150,100]):rec.update(feature(i*.25,k))
        for i in range(4,12):result=rec.update(feature(i*.25,175,ankle_x=.85))
        self.assertEqual(result['exercise'],'unknown')
    def test_press_is_not_lateral_raise(self):
        rec=MovementRecognizer()
        for i,a in enumerate([10,10,40,75,85,60,30,10,10]):
            result=rec.update(feature(i*.25,arm=a,elbow=90))
            self.assertEqual(result['exercise'],'unknown')
    def test_fast_glitch_does_not_complete_cycle(self):
        cycle=Cycle(158,125)
        for t,value in [(0,175),(.2,175),(.21,100),(.22,175)]:
            self.assertFalse(cycle.update(t,value))
    def test_label_persists_through_next_rep_but_expires_during_hold(self):
        rec=MovementRecognizer()
        knees=[175,175,150,110,95,130,175,175,150,110,95,125,175]
        results=[rec.update(feature(i*.5,k,hip=.4+(175-k)/600)) for i,k in enumerate(knees)]
        self.assertTrue(all(r['exercise']=='squat' for r in results[6:]))
        self.assertEqual(results[-1]['reps'],2)
        for i in range(13,22):result=rec.update(feature(i*.5,100,hip=.55))
        self.assertEqual(result['exercise'],'unknown')
    def test_standing_reanchors_initial_partial_pose(self):
        rec=MovementRecognizer()
        rec.update(feature(0,95,hip=.55,ankle_y=.75))
        for i,k in enumerate([175,175,150,110,95,130,175,175],start=1):
            y=.86 if k>=158 else .93
            result=rec.update(feature(i*.5,k,hip=.4+(175-k)/600,ankle_y=y))
        self.assertEqual(result['exercise'],'squat')
    def test_joint_geometry(self):
        self.assertAlmostEqual(angle([0,1],[0,0],[1,0]),90)
        self.assertIsNone(angle([0,0],[0,0],[1,0]))

if __name__=='__main__':unittest.main()
