use clap::ValueEnum;

macro_rules! kinds {
    ($($name:ident { $first:ident = $first_text:literal $(, $variant:ident = $text:literal)* $(,)? })+) => {$(
        #[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash, ValueEnum, serde::Serialize, serde::Deserialize)]
        pub enum $name {
            #[default]
            #[serde(rename = $first_text)]
            #[value(name = $first_text)]
            $first,
            $(
                #[serde(rename = $text)]
                #[value(name = $text)]
                $variant
            ),*
        }

        impl std::fmt::Display for $name {
            fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
                f.write_str(self.as_str())
            }
        }

        impl $name {
            pub const ALL: &'static [Self] = &[Self::$first $(, Self::$variant)*];

            pub fn as_str(self) -> &'static str {
                match self {
                    Self::$first => $first_text,
                    $(Self::$variant => $text),*
                }
            }

            pub fn parse(text: &str) -> Result<Self, String> {
                <Self as ValueEnum>::from_str(text, false)
                    .map_err(|_| format!("{text:?} is not one of {}", Self::names()))
            }

            pub fn names() -> String {
                Self::ALL.iter().map(|kind| kind.as_str()).collect::<Vec<_>>().join(", ")
            }
        }
    )+};
}

kinds! {
    ContentMode { Article = "article", InANutshell = "in_a_nutshell", Verbatim = "verbatim" }
    PrintLayout { A5 = "a5", Columns = "columns", Single = "single" }
    RenderOperation {
        MeasureArticle = "measure_article",
        MeasureEdition = "measure_edition",
        RenderEdition = "render_edition"
    }
    ArtPurpose { Cover = "cover", Opener = "opener", Tail = "tail", Closing = "closing", CastSheet = "cast-sheet" }
    FigureLayout {
        EvidenceBand = "evidence_band",
        EvidenceBandProse = "evidence_band_prose",
        AdaptiveBand = "adaptive_band",
        CompactBand = "compact_band",
        ColumnPlate = "column_plate",
        LandscapePlate = "landscape_plate",
        LandscapePlateAfter = "landscape_plate_after",
        FullBand = "full_band",
        RotatedPlate = "rotated_plate"
    }
    FigureTone { Auto = "auto", Keep = "keep", Invert = "invert" }
    FigureFit { Auto = "auto", Keep = "keep" }
    ExtractStyle { Code = "code", Quote = "quote" }
    TailArtFit { Cover = "cover", Contain = "contain" }
}
