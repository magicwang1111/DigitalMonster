import unittest
from pathlib import Path
from PIL import Image, ImageSequence


class AnimationAssetTests(unittest.TestCase):
    def test_generated_interaction_scale_matches_idle(self):
        root=Path(__file__).resolve().parents[1]/'digitalmon/static/pet'
        for form in ('guilmon','growlmon','wargrowlmon','gallantmon','gallantmon-cm','gallantmon-x'):
            with Image.open(root/f'{form}-idle.gif') as idle:
                reference=idle.convert('RGBA').getbbox()
            actions=('feed','pet') if form in ('gallantmon-cm','gallantmon-x') else ('feed',)
            for action in actions:
                with self.subTest(form=form,action=action), Image.open(root/f'{form}-{action}.gif') as gif:
                    boxes=[f.convert('RGBA').getbbox() for f in ImageSequence.Iterator(gif)]
                    self.assertLessEqual(max(b[3]-b[1] for b in boxes),reference[3]-reference[1]+1)
                    self.assertTrue(all(abs(b[3]-reference[3])<=1 for b in boxes))

    def test_walk_scale_and_feet_match_idle(self):
        root=Path(__file__).resolve().parents[1]/'digitalmon/static/pet'
        for form in ('guilmon','growlmon','wargrowlmon','gallantmon','gallantmon-cm','gallantmon-x'):
            with Image.open(root/f'{form}-idle.gif') as idle:
                reference=idle.convert('RGBA').getbbox()
            with Image.open(root/f'{form}-walk.gif') as gif:
                frames=[f.convert('RGBA') for f in ImageSequence.Iterator(gif)]
                self.assertEqual(len(frames),8,form)
                self.assertEqual(len({f.tobytes() for f in frames}),8,form)
                boxes=[f.getbbox() for f in frames]
            self.assertLessEqual(max(b[3]-b[1] for b in boxes),reference[3]-reference[1]+1)
            self.assertTrue(all(abs(b[3]-reference[3])<=1 for b in boxes))
    def test_articulated_feeding_assets_are_distinct_transparent_frames(self):
        root = Path(__file__).resolve().parents[1]/'digitalmon/static/pet'
        for name in ('guilmon', 'growlmon', 'wargrowlmon', 'gallantmon', 'gallantmon-cm', 'gallantmon-x'):
            with self.subTest(form=name), Image.open(root/f'{name}-feed.gif') as gif:
                frames = [f.convert('RGBA') for f in ImageSequence.Iterator(gif)]
                self.assertEqual(len(frames), 12)
                self.assertEqual(len({f.tobytes() for f in frames}), 12)
                self.assertTrue(all(f.size == (256,256) for f in frames))
                self.assertTrue(all(f.getpixel((0,0))[3] == 0 for f in frames))

    def test_hidden_bread_has_four_distinct_poses(self):
        path = Path(__file__).resolve().parents[1]/'digitalmon/static/pet/guilmon-bread.gif'
        with Image.open(path) as gif:
            self.assertEqual(gif.n_frames, 4)

    def test_cm_and_x_have_articulated_idle_and_pet_actions(self):
        root = Path(__file__).resolve().parents[1]/'digitalmon/static/pet'
        for form in ('gallantmon-cm','gallantmon-x'):
            for action in ('idle','pet'):
                with self.subTest(form=form,action=action), Image.open(root/f'{form}-{action}.gif') as gif:
                    frames=[f.convert('RGBA') for f in ImageSequence.Iterator(gif)]
                    self.assertEqual(len(frames),4)
                    self.assertEqual(len({f.tobytes() for f in frames}),4)
                    self.assertTrue(all(f.getpixel((0,0))[3]==0 for f in frames))
