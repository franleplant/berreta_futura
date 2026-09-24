use std::io::Write;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use flate2::write::DeflateEncoder;
use flate2::{Compression, Crc};

const DOS_DATE_1980_01_01: u16 = (1 << 5) | 1;
const EXTERNAL_ATTR: u32 = 0o100644 << 16;

fn files_under(root: &Path, out: &mut Vec<PathBuf>) -> Result<()> {
    for entry in
        std::fs::read_dir(root).with_context(|| format!("cannot list {}", root.display()))?
    {
        let path = entry?.path();
        if path.is_dir() {
            files_under(&path, out)?;
        } else if path.is_file() {
            out.push(path);
        }
    }
    Ok(())
}

fn header(
    signature: u32,
    central: bool,
    name: &str,
    crc: u32,
    sizes: (u32, u32),
    offset: u32,
) -> Vec<u8> {
    let mut bytes = signature.to_le_bytes().to_vec();
    if central {
        bytes.extend((3u16 << 8 | 20).to_le_bytes());
    }
    let flags: u16 = if name.is_ascii() { 0 } else { 0x800 };
    for half in [20u16, flags, 8, 0, DOS_DATE_1980_01_01] {
        bytes.extend(half.to_le_bytes());
    }
    for word in [crc, sizes.0, sizes.1] {
        bytes.extend(word.to_le_bytes());
    }
    bytes.extend((name.len() as u16).to_le_bytes());
    bytes.extend(0u16.to_le_bytes());
    if central {
        bytes.extend([0u8; 6]);
        bytes.extend(EXTERNAL_ATTR.to_le_bytes());
        bytes.extend(offset.to_le_bytes());
    }
    bytes.extend(name.as_bytes());
    bytes
}

pub fn archive_tree(root: &Path, destination: &Path) -> Result<PathBuf> {
    let mut files = vec![];
    files_under(root, &mut files)?;
    files.retain(|path| path != destination);
    files.sort_by_key(|path| path.to_string_lossy().replace('\\', "/"));
    let mut body = vec![];
    let mut directory = vec![];
    for path in &files {
        let name = path
            .strip_prefix(root)?
            .to_string_lossy()
            .replace('\\', "/");
        let data =
            std::fs::read(path).with_context(|| format!("cannot read {}", path.display()))?;
        let mut crc = Crc::new();
        crc.update(&data);
        let mut encoder = DeflateEncoder::new(vec![], Compression::default());
        encoder.write_all(&data)?;
        let packed = encoder.finish()?;
        let sizes = (packed.len() as u32, data.len() as u32);
        let offset = body.len() as u32;
        body.extend(header(0x0403_4b50, false, &name, crc.sum(), sizes, 0));
        body.extend(&packed);
        directory.extend(header(0x0201_4b50, true, &name, crc.sum(), sizes, offset));
    }
    let mut end = 0x0605_4b50u32.to_le_bytes().to_vec();
    end.extend([0u8; 4]);
    for _ in 0..2 {
        end.extend((files.len() as u16).to_le_bytes());
    }
    end.extend((directory.len() as u32).to_le_bytes());
    end.extend((body.len() as u32).to_le_bytes());
    end.extend(0u16.to_le_bytes());
    body.extend(directory);
    body.extend(end);
    std::fs::write(destination, body)
        .with_context(|| format!("cannot write {}", destination.display()))?;
    Ok(destination.to_path_buf())
}
