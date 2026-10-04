use super::kinds::{ContentMode, ExtractStyle, FigureFit, FigureLayout, FigureTone, TailArtFit};
use serde::{Deserialize, Deserializer, Serialize};

fn text_or_number<'de, D: Deserializer<'de>>(deserializer: D) -> Result<String, D::Error> {
    #[derive(Deserialize)]
    #[serde(untagged)]
    enum Scalar {
        Text(String),
        Number(i64),
    }
    Ok(match Scalar::deserialize(deserializer)? {
        Scalar::Text(text) => text,
        Scalar::Number(number) => number.to_string(),
    })
}

macro_rules! rows {
    ($($name:ident { $($(#[$meta:meta])* $field:ident: $type:ty),+ $(,)? })+) => {$(
        #[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
        #[serde(default, deny_unknown_fields)]
        pub struct $name {
            $($(#[$meta])* pub $field: $type),+
        }
    )+};
}

rows! {
    EditionFile {
        schema_version: Option<i64>,
        id: String,
        #[serde(deserialize_with = "text_or_number")]
        issue_number: String,
        title: String,
        subtitle: Option<String>,
        publication_date: String,
        status: Option<String>,
        distribution: Option<String>,
        language: Option<String>,
        locale: Option<String>,
        sources: Vec<String>,
        art_direction_path: Option<String>,
        tail_art_fit: Option<TailArtFit>,
        editorial: Option<String>,
        format: Format,
        cover: Cover,
        articles: Vec<ArticleRow>,
        sections: Vec<SectionRow>,
        closing_plates: Vec<PlateRow>,
    }
    Format {
        article_opener: Option<String>,
        target_pages: Option<i64>,
        max_article_pages: Option<i64>,
        max_editorial_pages: Option<i64>,
        binding: Option<String>,
        home_sheet: Option<String>,
        trim: Option<String>,
    }
    Cover {
        art_path: Option<String>,
        headline: Option<String>,
        deck: Option<String>,
        edition_label: Option<String>,
        back_text: Option<String>,
        footer_caption: Option<String>,
        layout: Option<String>,
    }
    ArticleRow {
        id: String,
        title: String,
        short_title: String,
        display_emphasis: Option<String>,
        opener_variant: String,
        author: String,
        author_note: Option<String>,
        content_mode: Option<ContentMode>,
        minimum_reader_pages: Option<i64>,
        source_ids: Vec<String>,
        manuscript: String,
        opener_art: Option<OpenerArtRow>,
        tail_art_path: Option<String>,
        key_ideas: Option<Vec<String>>,
        figures: Vec<FigureRow>,
        extracts: Vec<ExtractRow>,
    }
    OpenerArtRow {
        path: String,
        alt_text: String,
        credit: String,
    }
    FigureRow {
        id: String,
        source_id: String,
        path: String,
        caption: String,
        credit: String,
        alt_text: String,
        anchor: String,
        layout: Option<FigureLayout>,
        tone: Option<FigureTone>,
        fit: Option<FigureFit>,
    }
    ExtractRow {
        id: String,
        source_id: String,
        begin: String,
        end: String,
        style: Option<ExtractStyle>,
        caption: String,
        anchor: String,
    }
    SectionRow {
        kind: String,
        title: Option<String>,
        path: String,
    }
    PlateRow {
        title: String,
        art_path: String,
    }
    TranslationFile {
        schema_version: Option<i64>,
        language: String,
        source_language: String,
        locale: Option<String>,
        fallback_locale: Option<String>,
        policy: Option<Policy>,
        title: Option<String>,
        subtitle: Option<String>,
        cover: Cover,
        closing_plate_titles: Vec<String>,
        editorial: Option<EditorialRow>,
        articles: Option<Vec<TranslatedArticleRow>>,
        sections: Option<Vec<SectionRow>>,
    }
    Policy {
        register: Option<String>,
        regional_preference: Option<String>,
        fallback: Option<String>,
        figure_art_labels: Option<String>,
        prohibited_fallbacks: Vec<String>,
    }
    EditorialRow {
        path: String,
    }
    TranslatedArticleRow {
        id: String,
        title: String,
        short_title: String,
        display_emphasis: Option<String>,
        author: Option<String>,
        author_note: Option<String>,
        manuscript: String,
        key_ideas: Option<Vec<String>>,
        figures: Option<Vec<LocalizedFigureRow>>,
        extracts: Option<Vec<LocalizedExtractRow>>,
    }
    LocalizedFigureRow {
        id: String,
        caption: String,
        credit: String,
        alt_text: String,
        anchor: String,
    }
    LocalizedExtractRow {
        id: String,
        caption: String,
        anchor: String,
    }
    SourceRecord {
        id: String,
        title: String,
        author: Option<String>,
        url: String,
        captured_at: String,
        published_at: Option<String>,
        tags: Vec<String>,
        synopsis: Option<String>,
    }
}
