use crate::caller::{Caller, ModelSpec};
use crate::modelcard::squash;
use crate::util::{prompts_path, read};
use anyhow::{bail, ensure, Context, Result};
use serde::Deserialize;

pub const BRIEF_SUBJECTS: [&str; 4] = [
    "company_news",
    "science",
    "distant_research",
    "standards_transition",
];
const FEATURE_SUBJECTS: [&str; 5] = [
    "model_launch",
    "product_release",
    "engineering",
    "applied_research",
    "essay",
];
const VOTES: usize = 3;

#[derive(Deserialize)]
struct Verdict {
    subject: String,
    evidence: String,
}

pub fn parse_subject(reply: &str, article: &str) -> Result<String> {
    let body = reply
        .trim()
        .trim_start_matches("```json")
        .trim_start_matches("```")
        .trim_end_matches("```")
        .trim();
    let verdict: Verdict = serde_json::Deserializer::from_str(body)
        .into_iter()
        .next()
        .context("the reply holds no JSON object")??;
    let subject = verdict.subject.as_str();
    if !BRIEF_SUBJECTS.contains(&subject) && !FEATURE_SUBJECTS.contains(&subject) {
        bail!(
            "subject {subject:?} is not one of {}, {}",
            BRIEF_SUBJECTS.join(", "),
            FEATURE_SUBJECTS.join(", ")
        );
    }
    if !squash(article).contains(&squash(&verdict.evidence)) {
        bail!(
            "the evidence {:?} is not on the page; copy it character for character",
            verdict.evidence
        );
    }
    Ok(verdict.subject)
}

pub fn majority(subjects: &[String]) -> Option<String> {
    let briefs: Vec<&String> = subjects
        .iter()
        .filter(|s| BRIEF_SUBJECTS.contains(&s.as_str()))
        .collect();
    (briefs.len() * 2 > subjects.len()).then(|| {
        briefs
            .iter()
            .max_by_key(|s| briefs.iter().filter(|o| o == s).count())
            .map(|s| (*s).clone())
            .unwrap_or_default()
    })
}

pub fn detect_brief(caller: &Caller, label: &str, article: &str) -> Result<Option<String>> {
    Ok(majority(&subjects(caller, label, article)?))
}

pub fn subjects(caller: &Caller, label: &str, article: &str) -> Result<Vec<String>> {
    let prompt = format!("{}\n{article}", read(&prompts_path("brief-detect.md"))?);
    let spec = ModelSpec::parse("sonnet")?;
    let votes: Vec<Result<String>> = std::thread::scope(|scope| {
        let handles: Vec<_> = (1..=VOTES)
            .map(|n| {
                let (prompt, spec) = (&prompt, &spec);
                scope.spawn(move || {
                    caller.call_with_parse(&format!("{label} vote{n}"), spec, prompt, |reply| {
                        parse_subject(reply, article)
                    })
                })
            })
            .collect();
        handles
            .into_iter()
            .map(|h| h.join().unwrap_or_else(|_| bail!("a vote panicked")))
            .collect()
    });
    let (cast, failed): (Vec<_>, Vec<_>) = votes.into_iter().partition(Result::is_ok);
    let cast: Vec<String> = cast.into_iter().flatten().collect();
    if let Some(Err(e)) = failed.into_iter().next() {
        ensure!(cast.len() * 2 > VOTES, "too few votes came back: {e:#}");
    }
    Ok(cast)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_brief_needs_most_votes_and_names_the_commonest_brief_subject() {
        let v = |s: &[&str]| s.iter().map(ToString::to_string).collect::<Vec<_>>();
        assert_eq!(
            majority(&v(&["science", "science", "essay"])),
            Some("science".into())
        );
        assert_eq!(
            majority(&v(&["company_news", "science", "science"])),
            Some("science".into())
        );
        assert_eq!(majority(&v(&["science", "essay", "engineering"])), None);
        assert_eq!(
            majority(&v(&["model_launch", "model_launch", "company_news"])),
            None
        );
    }

    #[test]
    fn a_subject_must_be_known_and_its_evidence_on_the_page() {
        let page = "Today we acquire Pierre. It ships next week.";
        assert_eq!(
            parse_subject(
                r#"{"subject": "company_news", "evidence": "Today we acquire Pierre."}"#,
                page
            )
            .unwrap(),
            "company_news"
        );
        assert!(parse_subject(
            r#"{"subject": "gossip", "evidence": "It ships next week."}"#,
            page
        )
        .is_err());
        assert!(parse_subject(
            r#"{"subject": "science", "evidence": "Proteins fold."}"#,
            page
        )
        .is_err());
    }
}
