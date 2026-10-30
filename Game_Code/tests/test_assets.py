import json
import tempfile
import unittest
from pathlib import Path

from src import config, sound_synth
from src.beyblade_art import design_layers, design_signature
from src.beyblade_data import all_specs, load_specs
from src.camera import Camera
from src.particles import PRIORITY_COMBAT, PRIORITY_DECOR, Particle, ParticleSystem
from src.utilities import Vec2, sanitize_name

BASELINE = {
    "inferno_fang": (100, 100, 115, 85, 105, 1.00),
    "tidal_surge": (110, 110, 95, 105, 95, 1.05),
    "verdant_reaper": (105, 105, 100, 95, 100, 1.00),
    "titan_breaker": (125, 100, 105, 125, 75, 1.35),
    "thunder_blitz": (95, 95, 110, 80, 120, 0.90),
    "gale_phantom": (100, 100, 90, 90, 125, 0.85),
    "frostbite_requiem": (100, 105, 100, 100, 95, 1.00),
    "venom_viper": (95, 100, 105, 85, 105, 0.95),
}


class DataTests(unittest.TestCase):
    def test_config_files_and_paths_resolve(self):
        self.assertTrue(config.BEYBLADE_DATA_FILE.exists())
        self.assertTrue(config.PROJECT_ROOT.joinpath("main.py").exists())

    def test_baseline_statistics_match_design(self):
        specs = all_specs()
        self.assertEqual(set(specs), set(BASELINE))
        for spec_id, (hp, sta, atk, dfn, spd, mass) in BASELINE.items():
            s = specs[spec_id]
            self.assertEqual((s.max_hp, s.max_stamina, s.attack, s.defence, s.speed, s.mass), (hp, sta, atk, dfn, spd, mass))

    def test_every_beyblade_has_ability_and_launch_data(self):
        for s in all_specs().values():
            self.assertTrue(s.ability_name)
            self.assertTrue(12.0 <= s.ability_cooldown <= 18.0 or s.id == "gale_phantom")
            self.assertIn("charge_rate", s.launch)
            for key in ("primary", "secondary", "accent", "dark"):
                self.assertIn(key, s.colors)

    def test_missing_data_file_is_reported_clearly(self):
        with self.assertRaises(FileNotFoundError):
            load_specs(Path("does_not_exist.json"))

    def test_missing_stat_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            with open(config.BEYBLADE_DATA_FILE, encoding="utf-8") as handle:
                raw = json.load(handle)
            del raw["beyblades"][0]["stats"]["mass"]
            path = Path(folder) / "bad.json"
            path.write_text(json.dumps(raw))
            with self.assertRaises(ValueError):
                load_specs(path)


class ArtAndSoundTests(unittest.TestCase):
    def test_designs_are_unique_and_layered(self):
        signatures = {sid: design_signature(sid) for sid in all_specs()}
        self.assertEqual(len(set(signatures.values())), 8)
        for sid in all_specs():
            self.assertGreater(len(design_layers(sid)), 5)

    def test_every_sound_builds_valid_pcm_and_files_exist(self):
        for name, builder in sound_synth.SOUND_BUILDERS.items():
            pcm = builder() if name != "spin_loop" else sound_synth.spin_loop()
            self.assertGreater(len(pcm), 1000, name)
            self.assertEqual(len(pcm) % 2, 0)
            self.assertTrue((config.SOUNDS_DIR / f"{name}.wav").exists(), name)

    def test_each_beyblade_has_distinct_ability_sound(self):
        sounds = [sound_synth.SOUND_BUILDERS[f"ability_{sid}"]() for sid in all_specs()]
        self.assertEqual(len(set(sounds)), 8)

    def test_generate_all_writes_files(self):
        with tempfile.TemporaryDirectory() as folder:
            written = sound_synth.generate_all(Path(folder))
            self.assertEqual(len(written), len(sound_synth.SOUND_BUILDERS))
            self.assertEqual(len(list(Path(folder).glob("*.wav"))), len(written))

    def test_sound_manager_degrades_without_audio(self):
        from src.sound_manager import SoundManager

        manager = SoundManager()
        manager.play("hit_light")
        manager.update_spin_loop(0.5)
        manager.set_enabled(False)
        manager.shutdown()


class UtilityTests(unittest.TestCase):
    def test_sanitize_name(self):
        self.assertEqual(sanitize_name("  Alex  "), "Alex")
        self.assertEqual(sanitize_name("   "), "Player")
        self.assertEqual(sanitize_name(""), "Player")
        self.assertEqual(sanitize_name("A" * 40), "A" * 16)
        self.assertEqual(sanitize_name("Al<>ex\n\t!"), "Alex")
        self.assertEqual(sanitize_name("Zoë  Ng"), "Zoë Ng")

    def test_camera_scale_is_uniform_and_invertible(self):
        for size in ((1280, 720), (960, 600), (1920, 1080)):
            for radius in config.STADIUM_RADII.values():
                cam = Camera(size, radius)
                outer_px = (radius + config.STADIUM_RIM_WIDTH) * cam.scale
                self.assertLessEqual(outer_px * 2, min(size) + 1)
                p = Vec2(37.0, -81.0)
                sx, sy = cam.to_screen(p)
                back = cam.to_world(sx, sy)
                self.assertAlmostEqual(back.x, p.x, delta=1.0 / cam.scale)
                self.assertAlmostEqual(back.y, p.y, delta=1.0 / cam.scale)

    def test_camera_shake_decays_and_restores_exact_center(self):
        cam = Camera((1280, 720), 320)
        center = cam.to_screen(Vec2())
        cam.add_shake(10.0)
        cam.update(0.016)
        for _ in range(120):
            cam.update(0.016)
        self.assertEqual(cam.to_screen(Vec2()), center)

    def test_particles_expire_and_cap(self):
        system = ParticleSystem(max_particles=10)
        for _ in range(50):
            system.emit(Particle(0, 0, 1, 1, 0.1, 2, (255, 255, 255), priority=PRIORITY_DECOR))
        self.assertEqual(len(system), 10)
        self.assertTrue(system.emit(Particle(0, 0, 0, 0, 0.5, 2, (255, 0, 0), priority=PRIORITY_COMBAT)))
        self.assertEqual(len(system), 10)
        system.update(0.2)
        self.assertEqual(len(system), 1)
        system.update(0.5)
        self.assertEqual(len(system), 0)


if __name__ == "__main__":
    unittest.main()
