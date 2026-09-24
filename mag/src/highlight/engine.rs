use anyhow::{anyhow, bail, Result};
use fancy_regex::{Captures, Regex};
use serde_json::Value;
use std::collections::HashMap;

pub struct Lexer {
    states: HashMap<String, Vec<Rule>>,
    extended: bool,
}

struct Rule {
    regex: Regex,
    action: Action,
    next: Next,
}

enum Action {
    Skip,
    Token(String),
    Groups(Vec<Action>),
    Call(Call),
}

struct Call {
    kind: String,
    class: String,
    error: String,
    content: String,
    flag: bool,
}

enum Next {
    Stay,
    Pop(usize),
    Push(Vec<String>),
}

#[derive(Default)]
struct Context {
    pos: usize,
    stack: Vec<String>,
    out: Vec<(String, String)>,
    indent_stack: Vec<i64>,
    indent: i64,
    next_indent: i64,
    block_scalar_indent: Option<i64>,
}

impl Lexer {
    pub fn new(table: &Value) -> Result<Self> {
        let flags = table["flags"].as_str().unwrap_or_default();
        let states = table["states"]
            .as_object()
            .ok_or_else(|| anyhow!("lexer without states"))?
            .iter()
            .map(|(name, rules)| {
                let rules = rules.as_array().into_iter().flatten();
                let rules = rules
                    .map(|rule| Rule::new(rule, flags))
                    .collect::<Result<_>>()?;
                Ok((name.clone(), rules))
            })
            .collect::<Result<_>>()?;
        Ok(Self {
            states,
            extended: table["extended"].as_bool().unwrap_or(false),
        })
    }

    pub fn tokens(&self, text: &str) -> Result<Vec<(String, String)>> {
        let mut ctx = Context {
            stack: vec!["root".into()],
            indent: -1,
            ..Context::default()
        };
        let mut idle = 0usize;
        loop {
            let before = (ctx.pos, ctx.stack.len());
            let rules = self.states.get(ctx.stack.last().unwrap());
            let rules = rules.ok_or_else(|| anyhow!("unknown lexer state"))?;
            if !self.step(rules, text, &mut ctx)? && !self.fallback(text, &mut ctx) {
                return Ok(ctx.out);
            }
            idle = if (ctx.pos, ctx.stack.len()) == before {
                idle + 1
            } else {
                0
            };
            if idle > 1000 {
                bail!("lexer stopped advancing at byte {}", ctx.pos);
            }
        }
    }

    fn step(&self, rules: &[Rule], text: &str, ctx: &mut Context) -> Result<bool> {
        for rule in rules {
            let Some(m) = rule.regex.captures_from_pos(text, ctx.pos)? else {
                continue;
            };
            let end = m.get(0).map_or(ctx.pos, |g| g.end());
            match &rule.action {
                Action::Skip if !self.extended => ctx.pos = end,
                Action::Skip => {}
                Action::Token(class) => {
                    ctx.out.push((class.clone(), m[0].to_owned()));
                    ctx.pos = end;
                }
                Action::Groups(groups) => {
                    groups_(groups, &m, ctx)?;
                    ctx.pos = end;
                }
                Action::Call(call) => call.run(&m[0], m.get(0).unwrap().start(), &m, ctx),
            }
            rule.next.apply(&mut ctx.stack);
            return Ok(true);
        }
        Ok(false)
    }

    fn fallback(&self, text: &str, ctx: &mut Context) -> bool {
        let Some(c) = text[ctx.pos..].chars().next() else {
            return false;
        };
        if c == '\n' {
            ctx.stack = vec!["root".into()];
            let class = if self.extended { "" } else { "w" };
            ctx.out.push((class.into(), "\n".into()));
        } else {
            ctx.out.push(("err".into(), c.to_string()));
        }
        ctx.pos += c.len_utf8();
        true
    }
}

fn groups_(groups: &[Action], m: &Captures, ctx: &mut Context) -> Result<()> {
    for (index, action) in groups.iter().enumerate() {
        let group = m.get(index + 1);
        match (action, group) {
            (Action::Token(class), Some(g)) if !g.as_str().is_empty() => {
                ctx.out.push((class.clone(), g.as_str().to_owned()))
            }
            (Action::Call(call), Some(g)) => {
                ctx.pos = g.start();
                call.run(g.as_str(), g.start(), m, ctx);
            }
            (Action::Groups(_), _) => bail!("nested bygroups are not supported"),
            _ => {}
        }
    }
    Ok(())
}

impl Rule {
    fn new(rule: &Value, flags: &str) -> Result<Self> {
        let pattern = rule[0]
            .as_str()
            .ok_or_else(|| anyhow!("rule without pattern"))?;
        let flags = if flags.is_empty() {
            String::new()
        } else {
            format!("(?{flags})")
        };
        let regex = Regex::new(&format!("{flags}\\G(?:{})", translate(pattern)))
            .map_err(|e| anyhow!("pattern {pattern:?}: {e}"))?;
        Ok(Self {
            regex,
            action: action(&rule[1])?,
            next: next(&rule[2])?,
        })
    }
}

fn translate(pattern: &str) -> String {
    let mut out = String::with_capacity(pattern.len());
    let mut chars = pattern.chars().peekable();
    let mut class = false;
    while let Some(c) = chars.next() {
        match c {
            '\\' => {
                let escaped = chars.next().unwrap_or('\\');
                match escaped {
                    'Z' => out.push_str("\\z"),
                    _ => {
                        out.push('\\');
                        out.push(escaped);
                    }
                }
            }
            '[' if class => out.push_str("\\["),
            '&' | '~' if class => {
                out.push('\\');
                out.push(c);
            }
            '[' => {
                class = true;
                out.push(c);
                for lead in ['^', ']'] {
                    if chars.peek() == Some(&lead) {
                        out.push_str(if lead == ']' { "\\]" } else { "^" });
                        chars.next();
                    }
                }
            }
            ']' if class => {
                class = false;
                out.push(c);
            }
            _ => out.push(c),
        }
    }
    out
}

fn action(value: &Value) -> Result<Action> {
    if value.is_null() {
        return Ok(Action::Skip);
    }
    let text = |key: &str| value[key].as_str().unwrap_or_default().to_owned();
    if let Some(groups) = value["g"].as_array() {
        return Ok(Action::Groups(
            groups.iter().map(action).collect::<Result<_>>()?,
        ));
    }
    if value["f"].is_string() {
        return Ok(Action::Call(Call {
            kind: text("f"),
            class: text("t"),
            error: text("e"),
            content: text("c"),
            flag: value["flag"].as_bool().unwrap_or(false),
        }));
    }
    match value["t"].as_str() {
        Some(class) => Ok(Action::Token(class.to_owned())),
        None => bail!("unknown action {value}"),
    }
}

fn next(value: &Value) -> Result<Next> {
    if value.is_null() {
        return Ok(Next::Stay);
    }
    if let Some(n) = value.as_i64() {
        return Ok(Next::Pop(n.unsigned_abs() as usize));
    }
    if let Some(state) = value.as_str() {
        return Ok(Next::Push(vec![state.to_owned()]));
    }
    let states = value
        .as_array()
        .ok_or_else(|| anyhow!("bad state {value}"))?;
    Ok(Next::Push(
        states
            .iter()
            .map(|s| s.as_str().unwrap_or_default().to_owned())
            .collect(),
    ))
}

impl Next {
    fn apply(&self, stack: &mut Vec<String>) {
        match self {
            Next::Stay => {}
            Next::Pop(n) => stack.truncate(stack.len().saturating_sub(*n).max(1)),
            Next::Push(states) => {
                for state in states {
                    match state.as_str() {
                        "#pop" if stack.len() > 1 => drop(stack.pop()),
                        "#pop" => {}
                        "#push" => stack.push(stack.last().unwrap().clone()),
                        _ => stack.push(state.clone()),
                    }
                }
            }
        }
    }
}

impl Call {
    fn run(&self, text: &str, start: usize, m: &Captures, ctx: &mut Context) {
        let end = start + text.len();
        let emit =
            |ctx: &mut Context, class: &str, text: &str| ctx.out.push((class.into(), text.into()));
        match self.kind.as_str() {
            "something" if text.is_empty() => {}
            "something" => {
                emit(ctx, &self.class, text);
                ctx.pos = end;
            }
            "reset_indent" => {
                ctx.indent_stack.clear();
                ctx.indent = -1;
                ctx.next_indent = 0;
                ctx.block_scalar_indent = None;
                emit(ctx, &self.class, text);
                ctx.pos = end;
            }
            "save_indent" => self.save_indent(text, end, ctx),
            "set_indent" => {
                if ctx.indent < ctx.next_indent {
                    ctx.indent_stack.push(ctx.indent);
                    ctx.indent = ctx.next_indent;
                }
                if !self.flag {
                    ctx.next_indent += text.chars().count() as i64;
                }
                emit(ctx, &self.class, text);
                ctx.pos = end;
            }
            "set_block_scalar_indent" => {
                ctx.block_scalar_indent = None;
                if text.is_empty() {
                    return;
                }
                if let Some(Ok(increment)) = m.get(1).map(|g| g.as_str().parse::<i64>()) {
                    ctx.block_scalar_indent = Some(ctx.indent.max(0) + increment);
                }
                emit(ctx, &self.class, text);
                ctx.pos = end;
            }
            "parse_block_scalar_empty_line" => {
                let width = text.chars().count() as i64;
                match ctx.block_scalar_indent {
                    Some(indent) if width > indent => {
                        let (head, tail) = text.split_at(indent as usize);
                        emit(ctx, &self.class, head);
                        emit(ctx, &self.content, tail);
                    }
                    _ if !text.is_empty() => emit(ctx, &self.class, text),
                    _ => {}
                }
                ctx.pos = end;
            }
            "parse_block_scalar_indent" => {
                let width = text.chars().count() as i64;
                let floor = match ctx.block_scalar_indent {
                    None => ctx.indent.max(0) + 1,
                    Some(indent) => indent,
                };
                if width < floor {
                    ctx.stack.pop();
                    ctx.stack.pop();
                    return;
                }
                ctx.block_scalar_indent.get_or_insert(width);
                if !text.is_empty() {
                    emit(ctx, &self.class, text);
                    ctx.pos = end;
                }
            }
            "parse_plain_scalar_indent" => {
                if text.chars().count() as i64 <= ctx.indent {
                    ctx.stack.pop();
                    ctx.stack.pop();
                    return;
                }
                if !text.is_empty() {
                    emit(ctx, &self.class, text);
                    ctx.pos = end;
                }
            }
            kind => unreachable!("yaml callback {kind}"),
        }
    }

    fn save_indent(&self, text: &str, end: usize, ctx: &mut Context) {
        let mut text = text.to_owned();
        let mut extra = String::new();
        if self.flag {
            ctx.next_indent = text.chars().count() as i64;
            if ctx.next_indent < ctx.indent {
                while ctx.next_indent < ctx.indent {
                    ctx.indent = ctx.indent_stack.pop().unwrap_or(-1);
                }
                if ctx.next_indent > ctx.indent {
                    let cut = py_index(text.len(), ctx.indent);
                    extra = text[cut..].to_owned();
                    text.truncate(cut);
                }
            }
        } else {
            ctx.next_indent += text.chars().count() as i64;
        }
        if !text.is_empty() {
            ctx.out.push((self.class.clone(), text));
        }
        if !extra.is_empty() {
            ctx.out.push((self.error.clone(), extra));
        }
        ctx.pos = end;
    }
}

fn py_index(len: usize, index: i64) -> usize {
    match index < 0 {
        true => len.saturating_sub(index.unsigned_abs() as usize),
        false => (index as usize).min(len),
    }
}
