//! Pure timing, easing and geometry helpers for the ses film.
//!
//! Every function is a plain function of time so a shot renders identically on any thread.

/// Seconds the outgoing shot spends fading toward its own background.
pub const TAIL: f32 = 0.25;

pub fn clamp01(x: f32) -> f32 {
    if x.is_nan() { 0.0 } else { x.clamp(0.0, 1.0) }
}

/// Linear 0..1 progress of `t` through `[start, start + dur]`.
pub fn ramp(t: f32, start: f32, dur: f32) -> f32 {
    clamp01((t - start) / dur.max(0.001))
}

pub fn lerp(a: f32, b: f32, p: f32) -> f32 {
    a + (b - a) * p
}

pub fn out_cubic(x: f32) -> f32 {
    let x = clamp01(x);
    1.0 - (1.0 - x).powi(3)
}

pub fn in_cubic(x: f32) -> f32 {
    clamp01(x).powi(3)
}

pub fn out_expo(x: f32) -> f32 {
    let x = clamp01(x);
    if x >= 1.0 {
        1.0
    } else {
        1.0 - 2f32.powf(-10.0 * x)
    }
}

pub fn in_out(x: f32) -> f32 {
    let x = clamp01(x);
    if x < 0.5 {
        4.0 * x * x * x
    } else {
        1.0 - (-2.0 * x + 2.0).powi(3) / 2.0
    }
}

/// Damped spring from 0 to 1, `dt` seconds after release; overshoots slightly.
pub fn spring(dt: f32) -> f32 {
    if dt <= 0.0 {
        return 0.0;
    }
    let v = 1.0 - (-7.5 * dt).exp() * (11.0 * dt).cos();
    if dt > 1.4 { 1.0 } else { v }
}

/// Entrance at `start`: (opacity, vertical offset in px).
pub fn enter(t: f32, start: f32, distance: f32) -> (f32, f32) {
    let o = out_cubic(ramp(t, start, 0.35));
    let y = (1.0 - spring(t - start)) * distance;
    (o, y)
}

/// Opacity multiplier for the last `TAIL` seconds of a shot of length `dur`.
pub fn tail(t: f32, dur: f32) -> f32 {
    1.0 - in_cubic(ramp(t, dur - TAIL, TAIL))
}

/// Deterministic pseudo-random number in 0..1.
pub fn hash(i: u32) -> f32 {
    let x = ((i as f32) * 12.9898 + 78.233).sin() * 43758.545;
    x - x.floor()
}

pub fn tr(x: f32, y: f32) -> String {
    format!("translate({x:.2} {y:.2})")
}

/// Ornamental waveform: rounded vertical bars as one path.
///
/// `reveal` (0..1) draws bars left to right; `gain` scales the amplitude. Returns `None` when
/// nothing is visible yet so callers can skip the element instead of emitting an empty path.
pub fn wave_bars(
    x: f32,
    y: f32,
    width: f32,
    amp: f32,
    step: f32,
    seed: u32,
    reveal: f32,
    gain: f32,
) -> Option<String> {
    let count = (width / step).floor().max(1.0) as u32;
    let shown = (count as f32 * clamp01(reveal)).round() as u32;
    if shown == 0 || gain <= 0.0 {
        return None;
    }
    let mut d = String::with_capacity(shown as usize * 24);
    for i in 0..shown {
        let p = i as f32 / count as f32;
        // phrase-shaped envelope: syllable lumps with a quiet start and end
        let env = (p * std::f32::consts::PI).sin().powf(0.6)
            * (0.55 + 0.45 * (p * 23.0 + seed as f32).sin().abs());
        let h = (amp * gain * env * (0.35 + 0.65 * hash(seed * 977 + i))).max(2.0);
        let bx = x + i as f32 * step;
        d.push_str(&format!("M{bx:.1} {:.1}V{:.1}", y - h, y + h));
    }
    Some(d)
}

/// `stroke-dashoffset` that shows `p` (0..1) of a stroke of length `len`.
pub fn dash_offset(len: f32, p: f32) -> f32 {
    len * (1.0 - clamp01(p))
}

/// Check mark path centred on (cx, cy), `s` px wide.
pub fn check_path(cx: f32, cy: f32, s: f32) -> String {
    format!(
        "M{:.1} {:.1}L{:.1} {:.1}L{:.1} {:.1}",
        cx - s * 0.5,
        cy,
        cx - s * 0.15,
        cy + s * 0.35,
        cx + s * 0.5,
        cy - s * 0.4
    )
}

/// Shot-relative time to film-global time.
pub fn global_time(durations: &[f32], shot: usize, t: f32) -> f32 {
    durations.iter().take(shot).sum::<f32>() + t
}
