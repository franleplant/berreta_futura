use std::collections::HashMap;

const SPANISH: &str = include_str!("../../assets/typeset/hyph_es.dic");
const IGNORED: [&str; 6] = [
    "%",
    "#",
    "LEFTHYPHENMIN",
    "RIGHTHYPHENMIN",
    "COMPOUNDLEFTHYPHENMIN",
    "COMPOUNDRIGHTHYPHENMIN",
];
const TOTAL: usize = 6;
const LEFT: usize = 3;
const RIGHT: usize = 3;
pub const SHY: char = '\u{ad}';

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Hyphenation {
    pub english: bool,
    pub weasyprint69_skip: bool,
    pub limit_ladders: bool,
}

impl Hyphenation {
    #[cfg(test)]
    pub const PARITY: Self = Self {
        english: false,
        weasyprint69_skip: true,
        limit_ladders: false,
    };
    pub const SHIPPED: Self = Self {
        english: true,
        weasyprint69_skip: true,
        limit_ladders: true,
    };

    pub fn from_settings(setting: impl Fn(&str) -> Option<String>) -> Result<Self, String> {
        let flag = |key: &str, default: bool| match setting(key).as_deref() {
            None => Ok(default),
            Some("true") => Ok(true),
            Some("false") => Ok(false),
            Some(other) => Err(format!(
                "magazine.toml [render] {key} = {other}: expected true or false"
            )),
        };
        let shipped = Self::SHIPPED;
        Ok(Self {
            english: flag("hyphenate_english", shipped.english)?,
            weasyprint69_skip: flag("weasyprint69_hyphen_skip", shipped.weasyprint69_skip)?,
            ..shipped
        })
    }

    pub fn native(&self, locale: &str) -> bool {
        self.english && language(locale) == "en"
    }
}

fn language(locale: &str) -> String {
    locale.split(['-', '_']).next().unwrap_or("").to_lowercase()
}

pub struct Hyphenator {
    patterns: HashMap<Vec<char>, (usize, Vec<u8>)>,
    maxlen: usize,
}

impl Hyphenator {
    pub fn for_locale(locale: &str) -> Option<Result<Self, String>> {
        match language(locale).as_str() {
            "en" => None,
            "es" => Some(Ok(Self::parse(SPANISH))),
            _ => Some(Err(format!(
                "no hyphenation dictionary for locale {locale}; the reader hyphenates body prose \
                 in every language but English, so vendor its pyphen hyph_*.dic in \
                 mag/assets/typeset"
            ))),
        }
    }

    fn parse(dic: &str) -> Self {
        let mut patterns = HashMap::new();
        for line in dic.lines().skip(1).map(str::trim) {
            if line.is_empty() || IGNORED.iter().any(|prefix| line.starts_with(prefix)) {
                continue;
            }
            let (mut tags, mut values) = (Vec::new(), vec![0u8]);
            for c in line.chars() {
                match c.to_digit(10) {
                    Some(d) => *values.last_mut().expect("seeded") = d as u8,
                    None => {
                        tags.push(c);
                        values.push(0);
                    }
                }
            }
            let Some(start) = values.iter().position(|v| *v != 0) else {
                continue;
            };
            let end = values
                .iter()
                .rposition(|v| *v != 0)
                .expect("a nonzero value")
                + 1;
            patterns.insert(tags, (start, values[start..end].to_vec()));
        }
        let maxlen = patterns.keys().map(Vec::len).max().unwrap_or(0);
        Self { patterns, maxlen }
    }

    pub fn positions(&self, word: &str) -> Vec<usize> {
        let pointed: Vec<char> = format!(".{}.", word.to_lowercase()).chars().collect();
        let mut references = vec![0u8; pointed.len() + 1];
        for i in 0..pointed.len() - 1 {
            for j in i + 1..=(i + self.maxlen).min(pointed.len()) {
                let Some((offset, values)) = self.patterns.get(&pointed[i..j]) else {
                    continue;
                };
                for (k, value) in values.iter().enumerate() {
                    let slot = &mut references[i + offset + k];
                    *slot = (*slot).max(*value);
                }
            }
        }
        let length = word.chars().count();
        references
            .iter()
            .enumerate()
            .filter(|(i, r)| *r % 2 == 1 && *i >= 1 && (LEFT..=length - RIGHT).contains(&(i - 1)))
            .map(|(i, _)| i - 1)
            .collect()
    }

    fn word(&self, word: &str, out: &mut String) {
        let chars: Vec<char> = word.chars().collect();
        let points = match chars.len() >= TOTAL {
            true => self.positions(word),
            false => Vec::new(),
        };
        for (index, c) in chars.iter().enumerate() {
            if points.contains(&index) {
                out.push(SHY);
            }
            out.push(*c);
        }
    }

    pub fn text(&self, text: &str) -> String {
        let mut out = String::with_capacity(text.len());
        let mut word = String::new();
        for c in text.chars() {
            if c.is_alphanumeric() {
                word.push(c);
                continue;
            }
            self.word(&word, &mut out);
            word.clear();
            out.push(c);
        }
        self.word(&word, &mut out);
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn spanish() -> Hyphenator {
        Hyphenator::for_locale("es-AR")
            .expect("Spanish hyphenates")
            .expect("the dictionary parses")
    }

    fn syllables(word: &str) -> String {
        spanish().text(word).replace(SHY, "-")
    }

    #[test]
    fn spanish_words_divide_at_their_syllables_leaving_three_letters_each_side() {
        assert_eq!(syllables("responsabilidad"), "res-pon-sa-bi-li-dad");
        assert_eq!(
            syllables("internacionalización"),
            "inter-na-cio-na-li-za-ción"
        );
        assert_eq!(syllables("guiones"), "guio-nes");
        assert_eq!(syllables("renglón"), "ren-glón");
        assert_eq!(syllables("Compuesta"), "Com-puesta");
        assert_eq!(syllables("tipógrafo"), "tipó-grafo");
        assert_eq!(syllables("casa"), "casa");
        assert_eq!(syllables("ideas"), "ideas");
        assert_eq!(
            syllables("«responsabilidad» y renglón,"),
            "«res-pon-sa-bi-li-dad» y ren-glón,"
        );
    }

    #[test]
    fn english_hyphenation_ships_by_default_and_a_bad_value_is_refused() {
        let unset = Hyphenation::from_settings(|_| None).expect("defaults");
        assert_eq!(unset, Hyphenation::SHIPPED);
        assert!(unset.native("en") && unset.weasyprint69_skip && unset.limit_ladders);
        assert!(!Hyphenation::PARITY.native("en") && !Hyphenation::PARITY.limit_ladders);
        let off = Hyphenation::from_settings(|key| Some((key != "hyphenate_english").to_string()))
            .expect("booleans");
        assert!(!off.native("en-GB") && off.weasyprint69_skip && off.limit_ladders);
        let refused = Hyphenation::from_settings(|_| Some("yes".into())).expect_err("not a bool");
        assert!(refused.contains("hyphenate_english"), "{refused}");
    }

    #[test]
    fn english_is_not_hyphenated_and_an_unknown_language_is_refused() {
        assert!(Hyphenator::for_locale("en").is_none());
        assert!(Hyphenator::for_locale("en-GB").is_none());
        let refused = Hyphenator::for_locale("pt-BR").expect("not English");
        assert!(refused.err().expect("no dictionary").contains("pt-BR"));
    }
}
