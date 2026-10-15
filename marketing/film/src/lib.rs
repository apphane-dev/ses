//! Silent ses film. The design tokens also produce the repository's brand assets.
mod identity;
mod kit;
mod ses;

use fframes::{
    AudioMap, Duration, FFramesContext, Frame, Scene, Scenes, Svgr, Video, include_media_dir,
};

pub const WIDTH: usize = 1920;
pub const HEIGHT: usize = 1080;
pub const FPS: usize = 30;
include_media_dir!(pub struct FilmMedia, "../../brand/fonts");

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Shot {
    Inputs,
    Parse,
    Synth,
    Gates,
    Output,
    Outro,
}
impl Shot {
    pub const ALL: [Self; 6] = [
        Self::Inputs,
        Self::Parse,
        Self::Synth,
        Self::Gates,
        Self::Output,
        Self::Outro,
    ];
    pub const fn index(self) -> usize {
        self as usize
    }
}
impl Scene for Shot {
    fn duration(&self) -> Duration<'_> {
        Duration::Seconds(ses::DURATIONS[self.index()])
    }
    fn name(&self) -> &'static str {
        ses::TITLES[self.index()]
    }
    fn render_frame<'a>(&'a self, frame: Frame, _ctx: &FFramesContext<'a, '_>) -> Svgr<'a> {
        ses::render(*self, frame.seconds())
    }
}

pub struct SesFilm;
impl Video for SesFilm {
    const FPS: usize = FPS;
    const WIDTH: usize = WIDTH;
    const HEIGHT: usize = HEIGHT;
    fn duration(&self) -> Duration<'_> {
        Duration::Auto
    }
    fn audio(&self) -> AudioMap<'_> {
        AudioMap::none()
    }
    fn define_scenes(&self) -> Scenes<'_> {
        Scenes::from(
            Shot::ALL
                .iter()
                .map(|shot| shot as &dyn Scene)
                .collect::<Vec<_>>(),
        )
    }
    fn render_frame<'a>(&'a self, frame: Frame, ctx: &FFramesContext<'a, '_>) -> Svgr<'a> {
        fframes::svgr!(<svg xmlns="http://www.w3.org/2000/svg" width={WIDTH} height={HEIGHT}>
            {ctx.render_scenes(&frame)}
        </svg>)
    }
}
