from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path
from typing import Callable, Dict, List, Optional

SAMPLE_RATE = 22050
Samples = List[float]


def _count(duration: float) -> int:
    return max(1, int(duration * SAMPLE_RATE))


def sine(duration: float, f0: float, f1: Optional[float] = None, volume: float = 1.0) -> Samples:
    n = _count(duration)
    f1 = f0 if f1 is None else f1
    phase = 0.0
    out = []
    for i in range(n):
        freq = f0 + (f1 - f0) * i / n
        phase += 2.0 * math.pi * freq / SAMPLE_RATE
        out.append(math.sin(phase) * volume)
    return out


def saw(duration: float, f0: float, f1: Optional[float] = None, volume: float = 1.0) -> Samples:
    n = _count(duration)
    f1 = f0 if f1 is None else f1
    phase = 0.0
    out = []
    for i in range(n):
        freq = f0 + (f1 - f0) * i / n
        phase = (phase + freq / SAMPLE_RATE) % 1.0
        out.append((phase * 2.0 - 1.0) * volume)
    return out


def noise(duration: float, seed: int = 1, volume: float = 1.0) -> Samples:
    rng = random.Random(seed)
    return [(rng.random() * 2.0 - 1.0) * volume for _ in range(_count(duration))]


def fm(duration: float, carrier: float, modulator: float, index: float, volume: float = 1.0) -> Samples:
    n = _count(duration)
    return [
        math.sin(2 * math.pi * carrier * i / SAMPLE_RATE + index * math.sin(2 * math.pi * modulator * i / SAMPLE_RATE)) * volume
        for i in range(n)
    ]


def lowpass(samples: Samples, alpha: float) -> Samples:
    out, last = [], 0.0
    for s in samples:
        last += alpha * (s - last)
        out.append(last)
    return out


def highpass(samples: Samples, alpha: float) -> Samples:
    low = lowpass(samples, alpha)
    return [s - l for s, l in zip(samples, low)]


def sweep_lowpass(samples: Samples, a0: float, a1: float) -> Samples:
    out, last, n = [], 0.0, len(samples)
    for i, s in enumerate(samples):
        alpha = a0 + (a1 - a0) * i / n
        last += alpha * (s - last)
        out.append(last)
    return out


def envelope(samples: Samples, attack: float = 0.005, decay: float = 6.0) -> Samples:
    n = len(samples)
    attack_n = max(1, int(attack * SAMPLE_RATE))
    out = []
    for i, s in enumerate(samples):
        gain = min(1.0, i / attack_n) * math.exp(-decay * i / n)
        out.append(s * gain)
    return out


def swell(samples: Samples, peak: float = 0.5) -> Samples:
    n = len(samples)
    out = []
    for i, s in enumerate(samples):
        t = i / n
        gain = t / peak if t < peak else max(0.0, (1.0 - t) / (1.0 - peak))
        out.append(s * gain)
    return out


def amplitude_mod(samples: Samples, rate: float, depth: float = 0.5) -> Samples:
    return [s * (1.0 - depth + depth * (0.5 + 0.5 * math.sin(2 * math.pi * rate * i / SAMPLE_RATE))) for i, s in enumerate(samples)]


def delay(samples: Samples, seconds: float) -> Samples:
    return [0.0] * int(seconds * SAMPLE_RATE) + samples


def mix(*layers: Samples) -> Samples:
    length = max(len(layer) for layer in layers)
    out = [0.0] * length
    for layer in layers:
        for i, s in enumerate(layer):
            out[i] += s
    return out


def scale(samples: Samples, gain: float) -> Samples:
    return [s * gain for s in samples]


def normalize(samples: Samples, peak: float = 0.8) -> Samples:
    top = max((abs(s) for s in samples), default=0.0)
    if top < 1e-9:
        return samples
    k = peak / top
    return [s * k for s in samples]


def fade_edges(samples: Samples, ms: float = 4.0) -> Samples:
    n = min(len(samples) // 2, int(ms * SAMPLE_RATE / 1000.0))
    out = list(samples)
    for i in range(n):
        k = i / n
        out[i] *= k
        out[-1 - i] *= k
    return out


def to_pcm(samples: Samples) -> bytes:
    clipped = [max(-1.0, min(1.0, s)) for s in samples]
    return struct.pack("<%dh" % len(clipped), *[int(s * 32000) for s in clipped])


def crackle(duration: float, seed: int, density: float = 40.0) -> Samples:
    rng = random.Random(seed)
    n = _count(duration)
    out = [0.0] * n
    for _ in range(int(duration * density)):
        start = rng.randrange(0, n)
        length = rng.randrange(40, 160)
        amp = rng.uniform(0.3, 1.0)
        for k in range(length):
            if start + k < n:
                out[start + k] += (rng.random() * 2.0 - 1.0) * amp * math.exp(-5.0 * k / length)
    return out


def _finish(samples: Samples, peak: float = 0.8) -> bytes:
    return to_pcm(fade_edges(normalize(samples, peak)))


def ui_click() -> bytes:
    return _finish(envelope(sine(0.07, 900, 600), 0.002, 7), 0.5)


def ui_select() -> bytes:
    return _finish(mix(envelope(sine(0.12, 600, 900), 0.003, 5), delay(envelope(sine(0.12, 900, 1200), 0.003, 5), 0.07)), 0.55)


def countdown_tick() -> bytes:
    return _finish(envelope(mix(sine(0.18, 660), sine(0.18, 1320, volume=0.3)), 0.004, 6), 0.7)


def let_it_rip() -> bytes:
    rise = envelope(saw(0.5, 300, 900, 0.5), 0.01, 2.5)
    blast = envelope(lowpass(noise(0.5, 9), 0.25), 0.01, 3.0)
    return _finish(mix(envelope(sine(0.6, 880, 1320), 0.005, 3.5), rise, blast), 0.85)


def attach() -> bytes:
    click = envelope(highpass(noise(0.05, 3), 0.3), 0.001, 9)
    clack = delay(envelope(mix(sine(0.12, 300, 180), lowpass(noise(0.12, 4), 0.3, ), ), 0.002, 8), 0.04)
    return _finish(mix(click, clack), 0.8)


def charge() -> bytes:
    return _finish(amplitude_mod(envelope(saw(1.2, 120, 700, 0.6), 0.1, 0.3), 18, 0.35), 0.5)


def launch() -> bytes:
    whoosh = swell(sweep_lowpass(noise(0.55, 21), 0.05, 0.5), 0.25)
    zip_ = envelope(sine(0.4, 500, 1800, 0.5), 0.01, 3.0)
    snap = envelope(highpass(noise(0.08, 22), 0.2), 0.001, 9)
    return _finish(mix(whoosh, zip_, snap), 0.85)


def dash() -> bytes:
    return _finish(swell(sweep_lowpass(noise(0.28, 31), 0.05, 0.5), 0.3), 0.7)


def attack() -> bytes:
    return _finish(mix(envelope(sine(0.18, 700, 260), 0.002, 7), envelope(highpass(noise(0.18, 32), 0.15), 0.002, 8)), 0.8)


def hit(heavy: bool) -> bytes:
    duration = 0.45 if heavy else 0.25
    base = 1.0 if heavy else 1.6
    ring = mix(
        envelope(sine(duration, 1800 * base, 1700 * base, 0.5), 0.001, 8),
        envelope(sine(duration, 2650 * base, 2600 * base, 0.35), 0.001, 10),
        envelope(sine(duration, 960 * base, 900 * base, 0.5), 0.001, 7),
    )
    clang = envelope(highpass(noise(duration, 33), 0.2), 0.001, 10)
    thud = envelope(sine(duration, 140 * base, 70 * base, 0.8), 0.001, 9) if heavy else [0.0]
    return _finish(mix(ring, clang, thud), 0.85)


def wall() -> bytes:
    return _finish(mix(envelope(sine(0.22, 220, 110), 0.001, 8), envelope(lowpass(noise(0.22, 34), 0.3), 0.001, 9)), 0.7)


def restore() -> bytes:
    notes = [sine(0.16, 523), sine(0.16, 659), sine(0.3, 784)]
    out = mix(*[delay(envelope(note, 0.005, 4.0), 0.11 * i) for i, note in enumerate(notes)])
    return _finish(out, 0.6)


def recover() -> bytes:
    return _finish(mix(envelope(sine(0.5, 330, 495), 0.04, 2.5), envelope(sine(0.5, 495, 660, 0.5), 0.1, 2.5)), 0.55)


def eliminated() -> bytes:
    return _finish(mix(envelope(sine(0.7, 400, 80), 0.005, 3.5), envelope(lowpass(noise(0.7, 35), 0.15), 0.005, 4.0)), 0.8)


def victory() -> bytes:
    notes = [(523, 0.18), (659, 0.18), (784, 0.18), (1047, 0.5)]
    out, t = [], 0.0
    for freq, dur in notes:
        out.append(delay(envelope(mix(sine(dur + 0.2, freq), sine(dur + 0.2, freq * 2, volume=0.3)), 0.005, 3.0), t))
        t += dur
    return _finish(mix(*out), 0.75)


def defeat() -> bytes:
    notes = [(392, 0.25), (330, 0.25), (262, 0.25), (196, 0.7)]
    out, t = [], 0.0
    for freq, dur in notes:
        out.append(delay(envelope(mix(sine(dur + 0.25, freq), saw(dur + 0.25, freq, volume=0.15)), 0.01, 3.0), t))
        t += dur
    return _finish(mix(*out), 0.7)


def spin_loop() -> bytes:
    rng = random.Random(5)
    n = SAMPLE_RATE
    out = [0.0] * n
    for freq in range(2800, 5200, 130):
        phase = rng.uniform(0, 2 * math.pi)
        amp = rng.uniform(0.2, 1.0)
        for i in range(n):
            out[i] += math.sin(2 * math.pi * freq * i / SAMPLE_RATE + phase) * amp
    for freq, amp in ((190, 0.5), (380, 0.25)):
        for i in range(n):
            out[i] += math.sin(2 * math.pi * freq * i / SAMPLE_RATE) * amp * 4
    return to_pcm(normalize(out, 0.5))


def ability_inferno_fang() -> bytes:
    burst = envelope(lowpass(noise(0.9, 41), 0.35), 0.01, 3.5)
    boom = envelope(sine(0.9, 110, 45, 1.0), 0.004, 4.0)
    roar = swell(sweep_lowpass(noise(0.9, 42), 0.08, 0.6), 0.3)
    return _finish(mix(burst, boom, roar, scale(crackle(0.9, 43), 0.6)), 0.9)


def ability_tidal_surge() -> bytes:
    flow = amplitude_mod(swell(sweep_lowpass(noise(1.1, 44), 0.04, 0.25), 0.55), 5, 0.5)
    bubbles = mix(*[delay(envelope(sine(0.12, 400 + 140 * k, 900 + 100 * k, 0.5), 0.005, 6), 0.1 * k) for k in range(6)])
    surge = envelope(sine(1.1, 150, 260, 0.6), 0.2, 2.0)
    return _finish(mix(flow, bubbles, surge), 0.85)


def ability_verdant_reaper() -> bytes:
    swish = envelope(highpass(noise(0.7, 45), 0.15), 0.01, 4.0)
    chirps = mix(*[delay(envelope(sine(0.1, 900, 2400, 0.5), 0.003, 7), 0.07 * k) for k in range(5)])
    pulse = envelope(fm(0.7, 220, 330, 3.0, 0.5), 0.01, 4.0)
    return _finish(mix(swish, chirps, pulse), 0.85)


def ability_titan_breaker() -> bytes:
    rumble = swell(sine(1.2, 55, 38, 1.0), 0.2)
    impact = envelope(lowpass(noise(1.0, 46), 0.12), 0.002, 4.0)
    crack = delay(envelope(highpass(noise(0.3, 47), 0.1), 0.001, 8), 0.05)
    debris = scale(crackle(1.0, 48, 25), 0.5)
    return _finish(mix(rumble, impact, crack, debris), 0.95)


def ability_thunder_blitz() -> bytes:
    zap = envelope(sine(0.35, 3200, 180, 0.7), 0.001, 5.0)
    crack = envelope(highpass(noise(0.25, 49), 0.25), 0.001, 8.0)
    rumble = delay(swell(lowpass(noise(1.0, 50), 0.06), 0.15), 0.12)
    sizzle = scale(crackle(0.5, 51, 80), 0.7)
    return _finish(mix(zap, crack, rumble, sizzle), 0.95)


def ability_gale_phantom() -> bytes:
    gust = swell(sweep_lowpass(noise(0.9, 52), 0.03, 0.55), 0.4)
    whistle = envelope(sine(0.9, 700, 1500, 0.2), 0.2, 2.0)
    return _finish(mix(gust, whistle), 0.85)


def ability_frostbite_requiem() -> bytes:
    tinkles = mix(*[delay(envelope(sine(0.4, f, f * 1.01, 0.5), 0.002, 7), 0.06 * k) for k, f in enumerate((2093, 2637, 3136, 2349, 3520, 4186))])
    shimmer = envelope(highpass(noise(0.9, 53), 0.1), 0.05, 3.0)
    low = envelope(sine(0.9, 220, 110, 0.5), 0.01, 3.0)
    return _finish(mix(tinkles, scale(shimmer, 0.5), low), 0.85)


def ability_venom_viper() -> bytes:
    wobble = envelope(fm(1.0, 90, 7, 4.0, 0.9), 0.05, 2.5)
    bubbles = mix(*[delay(envelope(sine(0.15, 180, 420, 0.4), 0.004, 6), 0.13 * k) for k in range(6)])
    hiss = envelope(sweep_lowpass(noise(1.0, 54), 0.3, 0.05), 0.02, 3.0)
    return _finish(mix(wobble, bubbles, scale(hiss, 0.6)), 0.85)


SOUND_BUILDERS: Dict[str, Callable[[], bytes]] = {
    "ui_click": ui_click,
    "ui_select": ui_select,
    "countdown_tick": countdown_tick,
    "let_it_rip": let_it_rip,
    "attach": attach,
    "charge": charge,
    "launch": launch,
    "dash": dash,
    "attack": attack,
    "hit_light": lambda: hit(False),
    "hit_heavy": lambda: hit(True),
    "wall": wall,
    "restore": restore,
    "recover": recover,
    "eliminated": eliminated,
    "victory": victory,
    "defeat": defeat,
    "spin_loop": spin_loop,
    "ability_inferno_fang": ability_inferno_fang,
    "ability_tidal_surge": ability_tidal_surge,
    "ability_verdant_reaper": ability_verdant_reaper,
    "ability_titan_breaker": ability_titan_breaker,
    "ability_thunder_blitz": ability_thunder_blitz,
    "ability_gale_phantom": ability_gale_phantom,
    "ability_frostbite_requiem": ability_frostbite_requiem,
    "ability_venom_viper": ability_venom_viper,
}


def write_wav(path: Path, pcm: bytes) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(pcm)


def generate_all(directory: Path) -> List[str]:
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name, builder in SOUND_BUILDERS.items():
        write_wav(directory / f"{name}.wav", builder())
        written.append(name)
    return written


if __name__ == "__main__":
    from src.config import SOUNDS_DIR

    print(f"Generated {len(generate_all(SOUNDS_DIR))} sounds in {SOUNDS_DIR}")
