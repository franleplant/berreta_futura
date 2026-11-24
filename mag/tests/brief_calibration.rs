use mag::brief::{majority, subjects};
use mag::caller::Caller;
use std::fs;
use std::path::Path;

const BRIEFS: [&str; 8] = [
    "how-claude-designed-protein-binders-against-scor-ac67a5f1",
    "donating-agent-skills-to-the-agentic-ai-foundati-bdc7b775",
    "early-progress-on-accelerating-drug-development-dcad83d8",
    "working-with-academic-communities-to-build-scien-fe7d7660",
    "openai-to-acquire-pierre-computer-company-inc-27c88439",
    "the-post-quantum-future-of-web-privacy-0788fb80",
    "sparks-of-weight-space-programming-llms-can-nati-f9ecf66c",
    "teaching-ai-to-build-scientific-models-8a424d75",
];

const LAUNCHES: [&str; 6] = [
    "gemini-4-argon-our-next-era-of-frontier-intellig-6381db25",
    "introducing-claude-opus-5-5-0dd3bed5",
    "introducing-claude-fable-5-2-and-claude-mythos-5-a989f158",
    "introducing-gpt-6-2-astra-and-sol-0fb76b8d",
    "introducing-inkling-2-mini-89c1b500",
    "introducing-gemini-4-neon-f539fcda",
];

fn first_sources(edition: &str) -> Vec<String> {
    let plan = fs::read_to_string(format!("editions/{edition}/plan.yaml")).unwrap();
    let mut out = Vec::new();
    let mut lines = plan.lines();
    while let Some(line) = lines.next() {
        if line.trim() == "source_ids:" {
            if let Some(first) = lines.next() {
                out.push(first.trim().trim_start_matches("- ").to_string());
            }
        }
    }
    out
}

#[test]
#[ignore = "calls the model once per source; run with --ignored from mag/"]
fn briefs_are_the_news_and_launch_posts_stay_features() {
    std::env::set_current_dir("..").unwrap();
    let mut ids: Vec<String> = ["017", "018", "019", "020", "021", "022", "023"]
        .iter()
        .flat_map(|e| first_sources(e))
        .chain(BRIEFS.iter().chain(&LAUNCHES).map(ToString::to_string))
        .collect();
    ids.sort();
    ids.dedup();
    let raw = std::env::temp_dir().join("mag-brief-calibration");
    fs::create_dir_all(&raw).unwrap();
    let caller = Caller::new(&raw);
    let verdicts: Vec<(String, String)> = std::thread::scope(|scope| {
        let handles: Vec<_> = ids
            .iter()
            .map(|id| {
                let caller = &caller;
                scope.spawn(move || {
                    let article = fs::read_to_string(
                        Path::new("library/sources").join(id).join("article.md"),
                    )
                    .unwrap();
                    let verdict = match subjects(caller, &format!("brief {id}"), &article) {
                        Ok(votes) => format!(
                            "{}\t{}",
                            majority(&votes).unwrap_or_else(|| "feature".to_string()),
                            votes.join(",")
                        ),
                        Err(e) => format!("error: {e:#}"),
                    };
                    (id.clone(), verdict)
                })
            })
            .collect();
        handles.into_iter().map(|h| h.join().unwrap()).collect()
    });
    let table: String = verdicts
        .iter()
        .map(|(id, verdict)| format!("{verdict}\t{id}\n"))
        .collect();
    fs::create_dir_all(".magazine").unwrap();
    fs::write(".magazine/brief-calibration.tsv", &table).unwrap();
    println!("{table}");
    let verdict = |id: &str| {
        let found = &verdicts.iter().find(|(v, _)| v == id).unwrap().1;
        found.split('\t').next().unwrap_or_default().to_string()
    };
    let missed: Vec<&str> = BRIEFS
        .into_iter()
        .filter(|id| verdict(id) == "feature" || verdict(id).starts_with("error"))
        .collect();
    let launched: Vec<&str> = LAUNCHES
        .into_iter()
        .filter(|id| verdict(id) != "feature")
        .collect();
    assert!(missed.is_empty(), "briefs kept as features: {missed:?}");
    assert!(
        launched.is_empty(),
        "launch posts turned into briefs: {launched:?}"
    );
}
