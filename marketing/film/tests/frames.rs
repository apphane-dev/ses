use fframes::{
    CpuFrameRenderer, Previewer, RenderOptions, StaticMediaProvider, Video, diagnostics::Severity,
    snapshot,
};
use ses_film::{FPS, FilmMedia, SesFilm, Shot};

#[test]
fn every_frame_is_valid_and_silent() {
    let media = FilmMedia::prepare().unwrap();
    let options = RenderOptions {
        media: Some(&media),
        default_font: "IBM Plex Mono",
        ..Default::default()
    };
    let mut previewer = Previewer::new(&SesFilm, &options).unwrap();
    let report = previewer.timeline_report();
    assert!(report.audio.is_empty());
    assert!(
        SesFilm
            .audio()
            .used_audio_files::<Vec<&str>>()
            .is_none_or(|files| files.is_empty())
    );
    assert_eq!(previewer.timeline().duration_in_frames, 32 * FPS);
    assert_eq!(Shot::ALL.len(), 6);
    for frame in 0..32 * FPS {
        let report = previewer.inspect(frame).unwrap();
        let problems: Vec<_> = report
            .diagnostics
            .iter()
            .filter(|d| d.severity >= Severity::Warning)
            .map(|d| &d.message)
            .collect();
        assert!(problems.is_empty(), "frame {frame}: {problems:?}");
    }
}

#[test]
fn settled_frames_match_reviewed_snapshots() {
    let media = FilmMedia::prepare().unwrap();
    let options = RenderOptions {
        media: Some(&media),
        scale_resolution: 0.5,
        default_font: "IBM Plex Mono",
        ..Default::default()
    };
    let mut previewer = Previewer::new(&SesFilm, &options).unwrap();
    snapshot::assert_frames(
        &mut previewer,
        &mut CpuFrameRenderer::default(),
        &["#0@50%", "#1@50%", "#2@50%", "#3@50%", "#4@50%", "#5@50%"],
        &snapshot::SnapshotOptions {
            directory: std::path::PathBuf::from("_frame_snapshots"),
            ..Default::default()
        },
    );
}
