use fframes::{EncoderOptions, RenderOptions, StaticMediaProvider, cli};
use fframes_skia_renderer::{
    SkiaFFramesRenderer, SkiaPipelineConcurrencyPolicy, SkiaPipelineConfig, vulkan::SkiaVulkanCtx,
};
use ses_film::{FilmMedia, HEIGHT, SesFilm, WIDTH};
use std::process::ExitCode;

fn run() -> Result<ExitCode, Box<dyn std::error::Error>> {
    let media = FilmMedia::prepare()?;
    let gpu = SkiaVulkanCtx::new(WIDTH, HEIGHT)?;
    let backend = SkiaFFramesRenderer::new_vulkan(
        &gpu,
        SkiaPipelineConfig {
            concurrency_policy: SkiaPipelineConcurrencyPolicy::MaxPerformance,
            ..Default::default()
        },
    )?;
    Ok(cli::new(
        &SesFilm,
        RenderOptions {
            media: Some(&media),
            default_font: "IBM Plex Mono",
            video_encoder_options: EncoderOptions {
                preferred_encoder: Some("libx264"),
                codec_params: Some(&[("crf", "18"), ("preset", "medium"), ("tune", "animation")]),
                ..Default::default()
            },
            ..Default::default()
        },
    )
    .backend(backend)
    .preview(fframes_native_player::cli_preview)
    .default_output("deliverables/ses.mp4")
    .run())
}
fn main() -> ExitCode {
    match run() {
        Ok(code) => code,
        Err(error) => {
            eprintln!("ses-film: {error}");
            ExitCode::FAILURE
        }
    }
}
