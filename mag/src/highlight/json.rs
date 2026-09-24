use std::collections::HashMap;

#[derive(Clone, Copy, PartialEq)]
enum Mode {
    Idle,
    Str { escape: bool, unicode: u8 },
    Space,
    Constant,
    Number { float: bool },
    Punct,
    Line,
    Block { closer: bool },
    Slash,
}

struct Json<'a> {
    text: &'a str,
    classes: &'a HashMap<String, String>,
    out: Vec<(String, String)>,
    queue: Vec<(&'static str, usize, usize)>,
    start: usize,
    mode: Mode,
}

const SPACE: &str = " \n\r\t";
const CONSTANT: &str = "truefalsenull";
const INTEGER: &str = "-0123456789";
const PUNCT: &str = "{}[],";

pub fn tokens(text: &str, classes: &HashMap<String, String>) -> Vec<(String, String)> {
    let mut json = Json {
        text,
        classes,
        out: Vec::new(),
        queue: Vec::new(),
        start: 0,
        mode: Mode::Idle,
    };
    for (stop, c) in text.char_indices() {
        if json.finish(stop, c) {
            json.start = stop;
            json.dispatch(stop, c);
        }
    }
    json.end();
    json.out
}

impl Json<'_> {
    fn yield_(&mut self, token: &str, from: usize, to: usize) {
        let class = self.classes.get(token).cloned().unwrap_or_default();
        self.out.push((class, self.text[from..to].to_owned()));
    }

    fn flush(&mut self, tag: bool) {
        for (token, from, to) in std::mem::take(&mut self.queue) {
            let token = if tag && token == "String.Double" {
                "Name.Tag"
            } else {
                token
            };
            self.yield_(token, from, to);
        }
    }

    fn defer(&mut self, token: &'static str, to: usize) {
        match self.queue.is_empty() {
            true => self.yield_(token, self.start, to),
            false => self.queue.push((token, self.start, to)),
        }
    }

    fn finish(&mut self, stop: usize, c: char) -> bool {
        match self.mode {
            Mode::Str { .. } => {
                self.string(stop, c);
                return false;
            }
            Mode::Block { closer } => {
                self.mode = Mode::Block { closer: c == '*' };
                if c != '*' && closer && c == '/' {
                    self.defer("Comment.Multiline", stop + 1);
                    self.mode = Mode::Idle;
                }
                return false;
            }
            Mode::Space if SPACE.contains(c) => return false,
            Mode::Constant if CONSTANT.contains(c) => return false,
            Mode::Number { .. } if INTEGER.contains(c) => return false,
            Mode::Number { .. } if ".eE+".contains(c) => {
                self.mode = Mode::Number { float: true };
                return false;
            }
            Mode::Punct if PUNCT.contains(c) => return false,
            Mode::Line if c != '\n' => return false,
            Mode::Slash if c == '/' || c == '*' => {
                self.mode = if c == '/' {
                    Mode::Line
                } else {
                    Mode::Block { closer: false }
                };
                return false;
            }
            Mode::Space => self.defer("Text.Whitespace", stop),
            Mode::Constant => self.yield_("Keyword.Constant", self.start, stop),
            Mode::Number { float } => self.yield_(
                if float {
                    "Number.Float"
                } else {
                    "Number.Integer"
                },
                self.start,
                stop,
            ),
            Mode::Punct => self.yield_("Punctuation", self.start, stop),
            Mode::Line => self.defer("Comment.Single", stop),
            Mode::Slash => {
                self.flush(false);
                self.yield_("Error", self.start, stop);
            }
            Mode::Idle => {}
        }
        self.mode = Mode::Idle;
        true
    }

    fn string(&mut self, stop: usize, c: char) {
        let Mode::Str { escape, unicode } = self.mode else {
            return;
        };
        self.mode = match (unicode, escape, c) {
            (1.., _, _) if c.is_ascii_hexdigit() => Mode::Str {
                escape: unicode > 1,
                unicode: unicode - 1,
            },
            (1.., _, _) => Mode::Str {
                escape: false,
                unicode: 0,
            },
            (0, true, 'u') => Mode::Str {
                escape: true,
                unicode: 4,
            },
            (0, true, _) => Mode::Str {
                escape: false,
                unicode: 0,
            },
            (0, false, '\\') => Mode::Str {
                escape: true,
                unicode: 0,
            },
            (0, false, '"') => {
                self.queue.push(("String.Double", self.start, stop + 1));
                Mode::Idle
            }
            _ => self.mode,
        };
    }

    fn dispatch(&mut self, stop: usize, c: char) {
        self.mode = match c {
            '"' => Mode::Str {
                escape: false,
                unicode: 0,
            },
            _ if SPACE.contains(c) => Mode::Space,
            'f' | 'n' | 't' => {
                self.flush(false);
                Mode::Constant
            }
            _ if INTEGER.contains(c) => {
                self.flush(false);
                Mode::Number { float: false }
            }
            ':' => {
                self.flush(true);
                Mode::Punct
            }
            _ if PUNCT.contains(c) => {
                self.flush(false);
                Mode::Punct
            }
            '/' => Mode::Slash,
            _ => {
                self.flush(false);
                self.yield_("Error", stop, stop + c.len_utf8());
                Mode::Idle
            }
        };
    }

    fn end(&mut self) {
        self.flush(false);
        let token = match self.mode {
            Mode::Str { .. } | Mode::Block { .. } | Mode::Slash => "Error",
            Mode::Number { float: true } => "Number.Float",
            Mode::Number { float: false } => "Number.Integer",
            Mode::Constant => "Keyword.Constant",
            Mode::Space => "Text.Whitespace",
            Mode::Punct => "Punctuation",
            Mode::Line => "Comment.Single",
            Mode::Idle => return,
        };
        self.yield_(token, self.start, self.text.len());
    }
}
