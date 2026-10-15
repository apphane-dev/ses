//! ses — "Manuscript to air". A markdown script and a voice sample become narrated WAVs.
//!
//! Warm studio dark, cream ink, one ember accent. Instrument Serif for display, IBM Plex Mono
//! for files and script lines. Script: `STORYBOARD.md`.

use crate::{Shot, identity::*, kit::*};
use fframes::Svgr;

pub const DURATIONS: [f32; 6] = [5.0, 6.0, 6.0, 5.0, 5.0, 5.0];
pub const TITLES: [&str; 6] = [
    "SesInputs",
    "SesParse",
    "SesSynth",
    "SesGates",
    "SesOutput",
    "SesOutro",
];
/// Shot-relative visual event times; the animations use these same values.
pub const HITS: [&[f32]; 6] = [
    &[0.1, 0.6, 3.6],
    &[0.8, 2.4, 2.9, 3.8],
    &[1.0, 2.0, 3.0, 4.0],
    &[0.9, 2.1, 3.3],
    &[0.6, 1.0, 1.4, 2.6],
    &[0.5],
];

/// Plex Mono advance width per px of font size.
const MONO_ADV: f32 = 0.6;

/// The example script every shot reads from.
const SCRIPT: [&str; 9] = [
    "## 0:00 — Welcome",
    "> Welcome back to the workshop.",
    "> Today we build a bookshelf.",
    "> It takes one afternoon.",
    "> TODO",
    "## 0:20 — Tools",
    "> You need a saw and a square.",
    "## 0:40 — Assembly",
    "> Measure twice. Cut once.",
];
const SENTENCES: [&str; 3] = [
    "Welcome back to the workshop.",
    "Today we build a bookshelf.",
    "It takes one afternoon.",
];
const FILES: [&str; 3] = [
    "slide-00-welcome.wav",
    "slide-01-tools.wav",
    "slide-02-assembly.wav",
];

pub fn render<'a>(shot: Shot, t: f32) -> Svgr<'a> {
    let dur = DURATIONS[shot.index()];
    let body = match shot {
        Shot::Inputs => inputs(t),
        Shot::Parse => parse(t),
        Shot::Synth => synth(t),
        Shot::Gates => gates(t),
        Shot::Output => output(t),
        Shot::Outro => outro(t),
    };
    // The closing card holds to the last frame.
    let fade = if shot == Shot::Outro {
        1.0
    } else {
        tail(t, dur)
    };
    fframes::svgr!(<g>
        <rect x="0" y="0" width="1920" height="1080" fill={BG} />
        <g opacity={fade}>{body}</g>
        {chrome(shot.index(), t)}
    </g>)
}

fn hit(shot: usize, i: usize) -> f32 {
    HITS[shot].get(i).copied().unwrap_or(0.0)
}

/// Persistent header and the film-long tape at the bottom.
fn chrome<'a>(shot: usize, t: f32) -> Svgr<'a> {
    let total: f32 = DURATIONS.iter().sum();
    let px = 160.0 + 1600.0 * clamp01(global_time(&DURATIONS, shot, t) / total);
    let ticks: Vec<Svgr> = (1..6)
        .map(|i| {
            let x = 160.0 + 1600.0 * global_time(&DURATIONS, i, 0.0) / total;
            fframes::svgr!(<path d={format!("M{x:.1} 970V990")} stroke={LINE} stroke-width="2" />)
        })
        .collect();
    fframes::svgr!(<g>
        <text x="160" y="134" font-family={SERIF} font-size="56" font-weight="400" fill={CREAM}>"ses"</text>
        <text x="244" y="128" font-family={MONO} font-size="28" font-weight="400" fill={DIM}>"voice-cloning voiceover pipeline"</text>
        <text x="1760" y="128" text-anchor="end" font-family={MONO} font-size="28" font-weight="400" fill={DIM}>{format!("{:02} / 06", shot + 1)}</text>
        <path d="M160 980H1760" stroke={LINE} stroke-width="2" />
        {ticks}
        <path d={format!("M160 980H{px:.1}")} stroke={EMBER} stroke-width="4" stroke-linecap="round" />
        <circle cx={px} cy="980" r="8" fill={EMBER} />
    </g>)
}

fn wave<'a>(
    x: f32,
    y: f32,
    w: f32,
    amp: f32,
    step: f32,
    seed: u32,
    reveal: f32,
    gain: f32,
    color: &'static str,
    stroke: f32,
) -> Svgr<'a> {
    match wave_bars(x, y, w, amp, step, seed, reveal, gain) {
        Some(d) => {
            fframes::svgr!(<path d={d} fill="none" stroke={color} stroke-width={stroke} stroke-linecap="round" />)
        }
        None => Svgr::empty(),
    }
}

/// Display line rising into place at `start`.
fn serif_line<'a>(
    text: &'static str,
    x: f32,
    y: f32,
    size: f32,
    fill: &'static str,
    t: f32,
    start: f32,
) -> Svgr<'a> {
    let (o, dy) = enter(t, start, 36.0);
    fframes::svgr!(<text x={x} y={y + dy} opacity={o} font-family={SERIF} font-size={size} font-weight="400" letter-spacing="-1" fill={fill}>{text}</text>)
}

fn mono<'a>(text: String, x: f32, y: f32, size: f32, fill: &'static str) -> Svgr<'a> {
    fframes::svgr!(<text x={x} y={y} font-family={MONO} font-size={size} font-weight="400" fill={fill}>{text}</text>)
}

// 01 — a voice sample and a markdown script, side by side.
fn inputs<'a>(t: f32) -> Svgr<'a> {
    let reveal = 0.2 + 0.8 * out_cubic(ramp(t, hit(0, 1), 1.6));
    let breathe = 1.0 + 0.06 * (t * 2.6).sin();
    let lines: Vec<Svgr> = SCRIPT[..6]
        .iter()
        .enumerate()
        .map(|(i, line)| {
            let y = [330.0, 392.0, 444.0, 496.0, 548.0, 616.0][i];
            let (o, dy) = if i < 2 { (1.0, 0.0) } else { enter(t, 0.25 + (i - 2) as f32 * 0.18, 18.0) };
            let fill = if line.starts_with("##") { HEAD } else { INK };
            fframes::svgr!(<g opacity={o} transform={tr(0.0, dy)}>{mono(line.to_string(), 1000.0, y, 30.0, fill)}</g>)
        })
        .collect();
    let link = out_expo(ramp(t, hit(0, 2), 0.7));
    let pulse = 1.0 - ramp(t, hit(0, 2) + 0.5, 0.8);
    let link_path = "M510 680C510 730 700 744 960 744C1220 744 1360 730 1360 680";
    fframes::svgr!(<g>
        <text x="160" y="232" font-family={MONO} font-size="28" font-weight="400" letter-spacing="4" fill={DIM}>"VOICE SAMPLE"</text>
        <text x="960" y="232" font-family={MONO} font-size="28" font-weight="400" letter-spacing="4" fill={DIM}>"SCRIPT.MD"</text>
        <rect x="160" y="260" width="700" height="420" rx="24" fill={PANEL} stroke={LINE} stroke-width="2" />
        <text x="200" y="320" font-family={MONO} font-size="30" font-weight="400" fill={CREAM}>"in/my_voice.wav"</text>
        {wave(204.0, 450.0, 612.0, 78.0, 12.0, 3, reveal, breathe, CREAM, 5.0)}
        <path d="M200 560H820" stroke={LINE} stroke-width="2" />
        <text x="200" y="612" font-family={MONO} font-size="30" font-weight="400" fill={CREAM}>"in/my_voice.txt"</text>
        <text x="200" y="652" font-family={MONO} font-size="28" font-weight="400" fill={DIM}>"transcript: enables ICL cloning"</text>
        <rect x="960" y="260" width="800" height="420" rx="24" fill={PAPER} />
        {lines}
        <path d={link_path} fill="none" stroke={EMBER} stroke-width="3" stroke-dasharray="1200" stroke-dashoffset={format!("{:.1}", dash_offset(1200.0, link))} />
        <circle cx="960" cy="744" r={4.0 + 10.0 * link} fill={EMBER} opacity={clamp01(link)} />
        <circle cx="960" cy="744" r={14.0 + 30.0 * (1.0 - pulse)} fill="none" stroke={EMBER} stroke-width="2" opacity={clamp01(pulse * link)} />
        {serif_line("Give it a voice and a script.", 160.0, 880.0, 104.0, CREAM, t, hit(0, 0))}
    </g>)
}

// 02 — the parser reads headings and quoted lines; TODO is skipped; headings become WAV names.
fn parse<'a>(t: f32) -> Svgr<'a> {
    let y_of = |i: usize| 372.0 + i as f32 * 54.0;
    // reading order: (line, time it is read)
    let reads: [(usize, f32); 8] = [
        (0, 0.8),
        (1, 1.15),
        (2, 1.45),
        (3, 1.75),
        (4, 2.4),
        (5, 2.9),
        (6, 3.15),
        (7, 3.4),
    ];
    let mut cursor = y_of(0);
    for (line, at) in reads {
        if t >= at {
            cursor = y_of(line);
        }
    }
    let hl_o = clamp01(ramp(t, 0.6, 0.2)) * (1.0 - ramp(t, 3.7, 0.3));
    let lines: Vec<Svgr> = SCRIPT
        .iter()
        .enumerate()
        .map(|(i, line)| {
            let read_at = reads.iter().find(|r| r.0 == i).map(|r| r.1).unwrap_or(3.6);
            let is_head = line.starts_with("##");
            let fill = if is_head && t >= read_at { HEAD } else { INK };
            let o = if i == 4 {
                1.0 - 0.6 * ramp(t, hit(1, 1) + 0.2, 0.3)
            } else {
                1.0
            };
            fframes::svgr!(<g opacity={o}>{mono(line.to_string(), 200.0, y_of(i), 32.0, fill)}</g>)
        })
        .collect();
    let strike = out_cubic(ramp(t, hit(1, 1), 0.3));
    let todo_w = 6.0 * 32.0 * MONO_ADV + 8.0;
    let (sk_o, _) = enter(t, hit(1, 1) + 0.15, 0.0);
    // slug tiles, wired from their headings
    let heads = [0usize, 5, 7];
    let tiles: Vec<Svgr> = FILES
        .iter()
        .enumerate()
        .map(|(i, file)| {
            let start = hit(1, 3) + i as f32 * 0.15;
            let ty = 420.0 + i as f32 * 130.0;
            let hy = y_of(heads[i]) - 10.0;
            let hx = 1040.0;
            let wire = out_expo(ramp(t, start - 0.15, 0.6));
            let (o, _) = enter(t, start, 0.0);
            let dx = (1.0 - spring(t - start)) * 70.0;
            let d = format!("M{hx:.1} {hy:.1}C{:.1} {hy:.1} {:.1} {:.1} 1120 {:.1}", hx + 50.0, 1070.0, ty + 48.0, ty + 48.0);
            fframes::svgr!(<g>
                <path d={d} fill="none" stroke={EMBER} stroke-width="2.5" stroke-dasharray="700" stroke-dashoffset={format!("{:.1}", dash_offset(700.0, wire))} />
                <circle cx={hx} cy={hy} r="7" fill={EMBER} opacity={clamp01(wire * 3.0)} />
                <g opacity={o} transform={tr(dx, 0.0)}>
                    <rect x="1120" y={ty} width="640" height="96" rx="14" fill={PANEL} stroke={EMBER} stroke-width="2" />
                    {mono(file.to_string(), 1156.0, ty + 59.0, 32.0, CREAM)}
                </g>
            </g>)
        })
        .collect();
    fframes::svgr!(<g>
        {serif_line("Headings become sections.", 160.0, 240.0, 92.0, CREAM, t, 0.1)}
        <rect x="160" y="300" width="880" height="560" rx="24" fill={PAPER} />
        <rect x="176" y={cursor - 40.0} width="848" height="54" rx="8" fill={EMBER} opacity={0.22 * hl_o} />
        <rect x="176" y={cursor - 40.0} width="6" height="54" fill={EMBER} opacity={hl_o} />
        {lines}
        <path d={format!("M196 {:.1}H{:.1}", y_of(4) - 11.0, 196.0 + todo_w * strike.max(0.01))} stroke={HEAD} stroke-width="4" stroke-linecap="round" opacity={clamp01(strike * 4.0)} />
        <text x="372" y={y_of(4)} opacity={sk_o} font-family={MONO} font-size="28" font-weight="400" fill={HEAD}>"skipped, not narrated"</text>
        {tiles}
        {serif_line("TODO lines stay silent.", 1120.0, 858.0, 60.0, DIM, t, hit(1, 1) + 0.2)}
    </g>)
}

// 03 — sentences pass one at a time through the voice-clone engine.
fn synth<'a>(t: f32) -> Svgr<'a> {
    let ring_x = 960.0;
    let ring_y = 540.0;
    let mut pulse = 0.0f32;
    for i in 0..3 {
        let dt = t - hit(2, i);
        if dt >= 0.0 {
            pulse = pulse.max((1.0 - dt / 0.45).max(0.0));
        }
    }
    let merge = in_out(ramp(t, hit(2, 3), 0.7));
    let chips: Vec<Svgr> = SENTENCES
        .iter()
        .enumerate()
        .map(|(i, s)| {
            let h = hit(2, i);
            let y = 420.0 + i as f32 * 120.0;
            let travel = in_out(ramp(t, h - 0.45, 0.45));
            let x = lerp(160.0, ring_x - 270.0, travel);
            let yy = lerp(y, ring_y - 40.0, travel);
            let s_scale = lerp(1.0, 0.3, travel);
            let o = 1.0 - ramp(t, h - 0.22, 0.2);
            let ghost = 0.35 * ramp(t, h, 0.3);
            fframes::svgr!(<g>
                <rect x="160" y={y} width="560" height="80" rx="40" fill="none" stroke={LINE} stroke-width="2" stroke-dasharray="6 8" opacity={ghost} />
                <g opacity={o} transform={format!("translate({:.1} {:.1}) scale({:.3})", x + 270.0 * (1.0 - s_scale), yy + 40.0 * (1.0 - s_scale), s_scale.max(0.01))}>
                    <rect x="0" y="0" width="560" height="80" rx="40" fill={PANEL} stroke={CREAM} stroke-width="2" />
                    {mono(s.to_string(), 32.0, 50.0, 28.0, CREAM)}
                </g>
            </g>)
        })
        .collect();
    let waves: Vec<Svgr> = (0..3)
        .map(|i| {
            let h = hit(2, i);
            let reveal = out_cubic(ramp(t, h, 0.6));
            let row_y = 460.0 + i as f32 * 120.0;
            // after the last hit the three takes close up into one section strip
            let sx = lerp(1.0, 0.33, merge);
            let x = lerp(1236.0, 1180.0 + i as f32 * 196.0, merge);
            let y = lerp(row_y, ring_y, merge);
            fframes::svgr!(<g>
                <text x="1180" y={row_y + 10.0} opacity={clamp01((1.0 - merge) * reveal)} font-family={MONO} font-size="28" font-weight="400" fill={DIM}>{format!("{:02}", i + 1)}</text>
                <g transform={format!("translate({x:.1} {y:.1}) scale({sx:.3} 1)")}>
                    {wave(0.0, 0.0, 520.0, 44.0, 10.0, 11 + i as u32, reveal, 1.0, CREAM, 5.0)}
                </g>
            </g>)
        })
        .collect();
    let label_o = clamp01(ramp(t, hit(2, 3) + 0.5, 0.3));
    fframes::svgr!(<g>
        {serif_line("Sentence by sentence, in your voice.", 160.0, 240.0, 92.0, CREAM, t, 0.0)}
        <text x={ring_x} y="336" text-anchor="middle" font-family={MONO} font-size="28" font-weight="400" fill={DIM}>"my_voice.wav + my_voice.txt"</text>
        <path d="M960 352V396" stroke={DIM} stroke-width="2" stroke-dasharray="4 8" />
        <circle cx={ring_x} cy={ring_y} r={140.0 + 14.0 * pulse} fill={PANEL} stroke={EMBER} stroke-width={2.0 + 6.0 * pulse} />
        <circle cx={ring_x} cy={ring_y} r={170.0 + 40.0 * (1.0 - pulse)} fill="none" stroke={EMBER} stroke-width="2" opacity={clamp01(pulse * 0.8)} />
        <text x={ring_x} y="548" text-anchor="middle" font-family={SERIF} font-size="56" font-weight="400" fill={CREAM}>"Qwen3-TTS"</text>
        <text x={ring_x} y="596" text-anchor="middle" font-family={MONO} font-size="28" font-weight="400" fill={DIM}>"voice clone"</text>
        {chips}
        {waves}
        <text x="1180" y="636" opacity={label_o} font-family={MONO} font-size="28" font-weight="400" fill={EMBER}>"slide-00-welcome.wav"</text>
        <text x="160" y="900" font-family={MONO} font-size="28" font-weight="400" fill={DIM}>"one sentence at a time, for stable prosody"</text>
    </g>)
}

// 04 — three quality gates: garble re-roll, dead-pause re-render, enhancement-noise fallback.
fn gates<'a>(t: f32) -> Svgr<'a> {
    let names = ["GARBLE", "DEAD PAUSE", "ADDED HASH"];
    let outcomes = [
        "Re-roll the chunk.",
        "Re-render the section.",
        "Keep the raw take.",
    ];
    // playhead along the rail, arriving at each cell centre on its hit
    let keys = [
        (0.0, 160.0),
        (hit(3, 0), 380.0),
        (hit(3, 1), 960.0),
        (hit(3, 2), 1540.0),
        (4.4, 1760.0),
    ];
    let mut head_x = 160.0;
    for w in keys.windows(2) {
        if t >= w[0].0 {
            head_x = lerp(w[0].1, w[1].1, in_out(ramp(t, w[0].0, w[1].0 - w[0].0)));
        }
    }
    let cells: Vec<Svgr> = (0..3)
        .map(|i| {
            let x = 160.0 + i as f32 * 580.0;
            let h = hit(3, i);
            let (o, dy) = (1.0, 0.0);
            let flip = ramp(t, h, 0.5);
            let sy = (std::f32::consts::PI * flip).cos().abs().max(0.02);
            let fixed = flip >= 0.5;
            let wx = x + 32.0;
            let cy = 530.0;
            let defect = match i {
                0 => {
                    if fixed {
                        wave(wx, 0.0, 376.0, 64.0, 9.0, 41, 1.0, 1.0, CREAM, 4.0)
                    } else {
                        fframes::svgr!(<g>
                            {wave(wx, 0.0, 376.0, 64.0, 9.0, 40, 1.0, 1.0, CREAM, 4.0)}
                            {wave(wx + 120.0, 0.0, 140.0, 150.0, 5.0, 7, 1.0, 1.0, EMBER, 3.0)}
                        </g>)
                    }
                }
                1 => {
                    if fixed {
                        wave(wx, 0.0, 376.0, 64.0, 9.0, 43, 1.0, 1.0, CREAM, 4.0)
                    } else {
                        fframes::svgr!(<g>
                            {wave(wx, 0.0, 130.0, 64.0, 9.0, 42, 1.0, 1.0, CREAM, 4.0)}
                            <path d={format!("M{:.1} 0H{:.1}", wx + 146.0, wx + 236.0)} stroke={EMBER} stroke-width="4" stroke-dasharray="3 10" stroke-linecap="round" />
                            {wave(wx + 250.0, 0.0, 126.0, 64.0, 9.0, 44, 1.0, 1.0, CREAM, 4.0)}
                        </g>)
                    }
                }
                _ => {
                    let drop = in_cubic(ramp(t, h, 0.5));
                    fframes::svgr!(<g>
                        {wave(wx, 0.0, 376.0, 64.0, 9.0, 45, 1.0, 1.0, CREAM, 4.0)}
                        <g opacity={1.0 - drop} transform={tr(0.0, 60.0 * drop)}>
                            {wave(wx, 0.0, 376.0, 26.0, 4.0, 46, 1.0, 1.0, EMBER, 1.5)}
                        </g>
                    </g>)
                }
            };
            let sy = if i == 2 { 1.0 } else { sy };
            let ok = out_cubic(ramp(t, h + 0.45, 0.25));
            let (out_o, out_dy) = enter(t, h + 0.35, 24.0);
            fframes::svgr!(<g opacity={o} transform={tr(0.0, dy)}>
                <rect x={x} y="340" width="440" height="360" rx="20" fill={PANEL} stroke={LINE} stroke-width="2" />
                <text x={x + 32.0} y="396" font-family={MONO} font-size="28" font-weight="400" letter-spacing="3" fill={EMBER}>{names[i]}</text>
                <path d={check_path(x + 396.0, 384.0, 34.0)} fill="none" stroke={EMBER} stroke-width="6" stroke-linecap="round" stroke-linejoin="round" opacity={ok} />
                <g transform={format!("translate(0 {cy:.1}) scale(1 {sy:.3})")}>{defect}</g>
                <text x={x} y={782.0 + out_dy} opacity={out_o} font-family={SERIF} font-size="52" font-weight="400" fill={CREAM}>{outcomes[i]}</text>
            </g>)
        })
        .collect();
    fframes::svgr!(<g>
        {serif_line("Bad takes get another pass.", 160.0, 240.0, 92.0, CREAM, t, 0.0)}
        <path d="M160 300H1760" stroke={LINE} stroke-width="2" />
        <path d={format!("M160 300H{head_x:.1}")} stroke={EMBER} stroke-width="3" />
        <circle cx={head_x} cy="300" r="9" fill={EMBER} />
        {cells}
        <text x="160" y="900" font-family={MONO} font-size="28" font-weight="400" fill={DIM}>"gates tuned to Qwen3-TTS and LavaSR"</text>
    </g>)
}

// 05 — one WAV per section, then all of them joined into full.wav.
fn output<'a>(t: f32) -> Svgr<'a> {
    let widths = [620.0, 380.0, 300.0];
    let merged_x = [400.0, 1060.0, 1480.0];
    let rows: Vec<Svgr> = (0..3)
        .map(|i| {
            let h = hit(4, i);
            let y = 380.0 + i as f32 * 120.0;
            let (o, _) = enter(t, h, 0.0);
            let dx = (1.0 - spring(t - h)) * -80.0;
            let reveal = out_cubic(ramp(t, h + 0.1, 0.5));
            let m = in_out(ramp(t, hit(4, 3) + i as f32 * 0.08, 0.7));
            let wx = lerp(620.0, merged_x[i], m);
            let wy = lerp(y, 800.0, m);
            let name_o = (0.3 + 0.7 * o) * (1.0 - 0.65 * m);
            let name_fill = if t >= h { CREAM } else { DIM };
            fframes::svgr!(<g>
                <g opacity={name_o}>
                    {mono(FILES[i].to_string(), 160.0, y + 12.0, 32.0, name_fill)}
                </g>
                <g opacity={o} transform={tr(dx, 0.0)}>{wave(wx, wy, widths[i], 40.0, 10.0, 60 + i as u32, reveal, 1.0, if m > 0.98 { EMBER } else { CREAM }, 5.0)}</g>
            </g>)
        })
        .collect();
    let (full_o, full_dy) = enter(t, hit(4, 3) + 0.4, 20.0);
    let gap_o = clamp01(ramp(t, hit(4, 3) + 0.7, 0.3));
    fframes::svgr!(<g>
        {serif_line("One WAV per section. One full render.", 160.0, 240.0, 92.0, CREAM, t, 0.0)}
        {rows}
        <path d="M160 700H1760" stroke={LINE} stroke-width="2" opacity={full_o} />
        <text x="160" y={812.0 + full_dy} opacity={full_o} font-family={MONO} font-size="32" font-weight="400" fill={EMBER}>"full.wav"</text>
        <g opacity={gap_o} fill={DIM}>
            <circle cx="1040" cy="800" r="4" />
            <circle cx="1460" cy="800" r="4" />
        </g>
        <text x="160" y="900" opacity={full_o} font-family={MONO} font-size="28" font-weight="400" fill={DIM}>"offline after the first model download"</text>
    </g>)
}

// 06 — closing card.
fn outro<'a>(t: f32) -> Svgr<'a> {
    let (t_o, t_dy) = enter(t, 0.15, 60.0);
    let (u_o, u_dy) = enter(t, hit(5, 0), 30.0);
    let (c_o, c_dy) = enter(t, hit(5, 0) + 0.25, 30.0);
    let (m_o, _) = enter(t, hit(5, 0) + 0.45, 0.0);
    let gain = 0.8 + 0.2 * (t * 1.9).sin();
    let cmd = "python -m ses --script script.md --sample my_voice";
    let cmd_w = cmd.len() as f32 * 30.0 * MONO_ADV + 64.0;
    fframes::svgr!(<g>
        <g opacity="0.9">{wave(1000.0, 400.0, 760.0, 150.0, 14.0, 77, 1.0, gain, EMBER, 6.0)}</g>
        <text x="148" y={520.0 + t_dy} opacity={t_o} font-family={SERIF} font-size="300" font-weight="400" letter-spacing="-6" fill={CREAM}>"ses"</text>
        <text x="160" y={650.0 + u_dy} opacity={u_o} font-family={SERIF} font-size="72" font-weight="400" fill={CREAM}>"Your script, in a cloned voice."</text>
        <g opacity={c_o} transform={tr(0.0, c_dy)}>
            <rect x="160" y="704" width={cmd_w} height="76" rx="38" fill={PANEL} stroke={LINE} stroke-width="2" />
            {mono(cmd.to_string(), 192.0, 752.0, 30.0, CREAM)}
        </g>
        <text x="160" y="892" opacity={m_o} font-family={SERIF} font-size="72" font-weight="400" fill={EMBER}>"ses.apphane.dev"</text>
        <text x="1760" y="890" text-anchor="end" opacity={m_o} font-family={MONO} font-size="28" font-weight="400" fill={DIM}>"MIT · runs locally · Qwen3-TTS + LavaSR"</text>
    </g>)
}
