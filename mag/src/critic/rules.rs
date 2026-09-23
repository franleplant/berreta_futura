use anyhow::{Context, Result};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};

use crate::critic::inspect::{
    difference, grayscale, inspect_page, point_below, render_review_pages, rgb_histogram, Gray,
    PageInspection, ReviewRasters, PAPER_WHITE, RASTER_DPI,
};
use crate::critic::metrics::{
    decode_rgb, ordered_map, resize, round_half_even, round_places, worker_count, Rgb,
};
use crate::critic::text::page_text;
use crate::impose::{
    cover_wrap_plan, imposed_reader_page_plan, section_reader_pages, A4_LANDSCAPE_POINTS,
};
use crate::model::shared::is_python_space;
use crate::parity::{trace_elements, Element, TextFace};

pub const GEOMETRY_TOLERANCE: f64 = 0.75;
pub const VOID_DOWNSAMPLE: u32 = 8;
pub const VOID_MIN_HEIGHT_POINTS: f64 = 96.0;
pub const VOID_MIN_WIDTH_FRACTION: f64 = 0.9;
pub const VOID_REPORT_LIMIT: usize = 3;
pub const VOID_TRAILING_TOLERANCE_POINTS: f64 = 16.0;
pub const TAIL_GAP_MIN_LIVE_FRACTION: f64 = 0.35;
pub const TAIL_BAND_HEIGHT_TOLERANCE_POINTS: f64 = 12.0;
pub const TAIL_BAND_ADJACENCY_TOLERANCE_POINTS: f64 = 8.0;
pub const TAIL_BAND_SYMMETRY_TOLERANCE_POINTS: f64 = 32.0;
pub const STUB_BODY_LINE_MINIMUM: usize = 5;
pub const DEFAULT_EDITORIAL_PAGE_CAP: i64 = 2;
pub const CROP_DPI: u32 = 300;
pub const OPENER_OFFSET_POINTS: f64 = 4.1;
pub const OPENER_FRAME_RGB: [u8; 3] = [23, 25, 28];
pub const OPENER_OFFSET_RGB: [u8; 3] = [240, 87, 56];
pub const OPENER_OFFSET_TOLERANCE_PIXELS: f64 = 2.0;
pub const OPENER_FRAME_MIN_RUN_FRACTION: f64 = 0.65;
pub const OPENER_CROP_FIDELITY_MAX_RGB_MAE: f64 = 8.0;
pub const OPENER_CROP_FRAME_MAX_EDGE_DELTA_INCHES: f64 = 0.01;
pub const CROP_MARGIN_POINTS: f64 = 24.0;
pub const CROP_CAPTION_ALLOWANCE_POINTS: f64 = 48.0;
pub const STUB_CROP_HEIGHT_POINTS: f64 = 220.0;
pub const TAIL_FALLBACK_CROP_HEIGHT_POINTS: f64 = 300.0;
pub const DEFAULT_ARTICLE_PAGE_CAP: i64 = 7;
const COVER_PLACEHOLDER: &str = r"(?i)(?:\.\.\.|\b(?:TODO|TBD)\b|\[insert\b)";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Issue {
    pub code: String,
    pub severity: String,
    pub message: String,
    pub page: Option<usize>,
}

impl Issue {
    pub fn as_row(&self) -> Value {
        match self.page {
            Some(page) => json!({
                "code": self.code,
                "severity": self.severity,
                "message": self.message,
                "page": page,
            }),
            None => json!({
                "code": self.code,
                "severity": self.severity,
                "message": self.message,
            }),
        }
    }
}

#[derive(Default)]
pub struct Recorder {
    pub issues: Vec<Issue>,
}

impl Recorder {
    pub fn at(&mut self, code: &str, severity: &str, message: String, page: usize) {
        self.push(code, severity, message, Some(page));
    }

    pub fn whole(&mut self, code: &str, severity: &str, message: String) {
        self.push(code, severity, message, None);
    }

    pub fn push(&mut self, code: &str, severity: &str, message: String, page: Option<usize>) {
        self.issues.push(Issue {
            code: code.to_string(),
            severity: severity.to_string(),
            message,
            page,
        });
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Void {
    pub x_points: f64,
    pub y_points: f64,
    pub width_points: f64,
    pub height_points: f64,
    pub width_fraction: f64,
    pub trailing: bool,
}

impl Void {
    pub fn as_row(&self) -> Value {
        json!({
            "x_points": self.x_points,
            "y_points": self.y_points,
            "width_points": self.width_points,
            "height_points": self.height_points,
            "width_fraction": self.width_fraction,
            "trailing": self.trailing,
        })
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct TailBand {
    pub y_points: f64,
    pub height_points: f64,
    pub declared_height_points: f64,
    pub gap_above_points: f64,
    pub gap_below_points: f64,
    pub centered: bool,
}

impl TailBand {
    pub fn as_row(&self) -> Value {
        json!({
            "y_points": self.y_points,
            "height_points": self.height_points,
            "declared_height_points": self.declared_height_points,
            "gap_above_points": self.gap_above_points,
            "gap_below_points": self.gap_below_points,
            "centered": self.centered,
        })
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct PageAnnotation {
    pub inspection: PageInspection,
    pub largest_void: Option<Void>,
    pub voids: Vec<Void>,
    pub tail_band: Option<TailBand>,
}

impl PageAnnotation {
    pub fn new(inspection: PageInspection) -> Self {
        Self {
            inspection,
            largest_void: None,
            voids: vec![],
            tail_band: None,
        }
    }

    pub fn as_row(&self) -> Value {
        let mut row = self.inspection.row();
        let map = row.as_object_mut().expect("an inspection row is an object");
        map.insert(
            "largest_void".into(),
            self.largest_void.map_or(Value::Null, |void| void.as_row()),
        );
        map.insert(
            "voids".into(),
            Value::Array(self.voids.iter().map(Void::as_row).collect()),
        );
        map.insert(
            "tail_band".into(),
            self.tail_band.map_or(Value::Null, |band| band.as_row()),
        );
        row
    }
}

pub fn crop(gray: &Gray, box_rect: [i64; 4]) -> Gray {
    let width = (box_rect[2] - box_rect[0]).max(0) as u32;
    let height = (box_rect[3] - box_rect[1]).max(0) as u32;
    let mut data = vec![0u8; width as usize * height as usize];
    for y in 0..height as i64 {
        for x in 0..width as i64 {
            let (source_x, source_y) = (box_rect[0] + x, box_rect[1] + y);
            if source_x < 0
                || source_y < 0
                || source_x >= gray.width as i64
                || source_y >= gray.height as i64
            {
                continue;
            }
            data[y as usize * width as usize + x as usize] =
                gray.data[source_y as usize * gray.width as usize + source_x as usize];
        }
    }
    Gray {
        width,
        height,
        data,
    }
}

pub fn mask_cells(gray: &Gray, factor: u32) -> Gray {
    let width = gray.width.div_ceil(factor);
    let height = gray.height.div_ceil(factor);
    let mut data = vec![0u8; width as usize * height as usize];
    for y in 0..gray.height {
        let row = (y / factor) as usize * width as usize;
        for x in 0..gray.width {
            if gray.data[y as usize * gray.width as usize + x as usize] != 0 {
                data[row + (x / factor) as usize] = 255;
            }
        }
    }
    Gray {
        width,
        height,
        data,
    }
}

pub fn largest_empty_rectangle(data: &[u8], columns: usize, rows_count: usize) -> [usize; 5] {
    let mut heights = vec![0usize; columns];
    let mut best = [0usize; 5];
    for row_index in 0..rows_count {
        let offset = row_index * columns;
        for (column, slot) in heights.iter_mut().enumerate() {
            *slot = if data[offset + column] == 0 {
                *slot + 1
            } else {
                0
            };
        }
        let mut stack: Vec<(usize, usize)> = vec![];
        for (column, &height) in heights.iter().chain([&0]).enumerate() {
            let mut start = column;
            while stack.last().is_some_and(|(_, top)| *top >= height) {
                let (popped, stacked_height) = stack.pop().expect("the stack is not empty");
                start = popped;
                let area = stacked_height * (column - start);
                if area > best[0] {
                    best = [
                        area,
                        column - start,
                        stacked_height,
                        start,
                        row_index + 1 - stacked_height,
                    ];
                }
            }
            stack.push((start, height));
        }
    }
    best
}

fn occupied_runs(data: &[u8], columns: usize, rows_count: usize) -> Vec<(usize, usize)> {
    let mut runs = vec![];
    let mut start: Option<usize> = None;
    for row_index in 0..rows_count {
        let offset = row_index * columns;
        let occupied = data[offset..offset + columns].iter().any(|&cell| cell != 0);
        match (occupied, start) {
            (true, None) => start = Some(row_index),
            (false, Some(from)) => {
                runs.push((from, row_index));
                start = None;
            }
            _ => {}
        }
    }
    if let Some(from) = start {
        runs.push((from, rows_count));
    }
    runs
}

pub fn locate_tail_band(
    data: &[u8],
    columns: usize,
    rows_count: usize,
    live: [i64; 4],
    scale: f64,
    declared_height: f64,
) -> Option<TailBand> {
    let runs = occupied_runs(data, columns, rows_count);
    let cell_points = VOID_DOWNSAMPLE as f64 * scale;
    let mut matched: Option<usize> = None;
    for (index, (run_start, run_end)) in runs.iter().enumerate() {
        let height = (run_end - run_start) as f64 * cell_points;
        if (height - declared_height).abs() <= TAIL_BAND_HEIGHT_TOLERANCE_POINTS {
            matched = Some(index);
        }
    }
    let index = matched?;
    let (run_start, run_end) = runs[index];
    let above_end = if index > 0 { runs[index - 1].1 } else { 0 };
    let below_start = if index + 1 < runs.len() {
        runs[index + 1].0
    } else {
        rows_count
    };
    let gap_above = (run_start - above_end) as f64 * cell_points;
    let gap_below = (below_start - run_end) as f64 * cell_points;
    Some(TailBand {
        y_points: round_places(
            (live[1] + (run_start * VOID_DOWNSAMPLE as usize) as i64) as f64 * scale,
            1,
        ),
        height_points: round_places((run_end - run_start) as f64 * cell_points, 1),
        declared_height_points: round_places(declared_height, 4),
        gap_above_points: round_places(gap_above, 1),
        gap_below_points: round_places(gap_below, 1),
        centered: (gap_above - gap_below).abs() <= TAIL_BAND_SYMMETRY_TOLERANCE_POINTS,
    })
}

pub fn abuts_tail_band(void: &Void, band: &TailBand) -> bool {
    let band_bottom = band.y_points + band.height_points;
    let void_bottom = void.y_points + void.height_points;
    (void_bottom - band.y_points).abs() <= TAIL_BAND_ADJACENCY_TOLERANCE_POINTS
        || (void.y_points - band_bottom).abs() <= TAIL_BAND_ADJACENCY_TOLERANCE_POINTS
}

fn live_box(rows: &[PageAnnotation], body_pages: &BTreeSet<usize>) -> Option<[i64; 4]> {
    let boxes: Vec<[u32; 4]> = rows
        .iter()
        .filter(|row| body_pages.contains(&row.inspection.page))
        .filter_map(|row| row.inspection.presence_bbox)
        .collect();
    if boxes.is_empty() {
        return None;
    }
    Some([
        boxes.iter().map(|box_rect| box_rect[0]).min()? as i64,
        boxes.iter().map(|box_rect| box_rect[1]).min()? as i64,
        boxes.iter().map(|box_rect| box_rect[2]).max()? as i64,
        boxes.iter().map(|box_rect| box_rect[3]).max()? as i64,
    ])
}

fn void_from_cell(cell: [usize; 5], live: [i64; 4], live_width: i64, scale: f64) -> Void {
    let step = VOID_DOWNSAMPLE as i64;
    let width_px = (cell[1] as i64 * step).min(live_width);
    let height_px = cell[2] as i64 * step;
    let x_px = live[0] + cell[3] as i64 * step;
    let y_px = live[1] + cell[4] as i64 * step;
    let trailing_gap = (live[3] - (y_px + height_px)) as f64 * scale;
    Void {
        x_points: round_places(x_px as f64 * scale, 1),
        y_points: round_places(y_px as f64 * scale, 1),
        width_points: round_places(width_px as f64 * scale, 1),
        height_points: round_places(height_px as f64 * scale, 1),
        width_fraction: round_places(width_px as f64 / live_width as f64, 3),
        trailing: trailing_gap <= VOID_TRAILING_TOLERANCE_POINTS,
    }
}

fn mask_cell(grid: &mut [u8], columns: usize, cell: [usize; 5]) {
    for masked_row in cell[4]..cell[4] + cell[2] {
        let offset = masked_row * columns;
        for masked_column in cell[3]..cell[3] + cell[1] {
            grid[offset + masked_column] = 255;
        }
    }
}

fn annotate_page(
    row: &mut PageAnnotation,
    raster: &Path,
    live: [i64; 4],
    declared_height: Option<f64>,
) -> Result<()> {
    let scale = 72.0 / RASTER_DPI as f64;
    let live_width = live[2] - live[0];
    let gray = grayscale(&decode_rgb(raster)?);
    let cells = mask_cells(
        &crop(&point_below(&gray, PAPER_WHITE), live),
        VOID_DOWNSAMPLE,
    );
    let (columns, rows_count) = (cells.width as usize, cells.height as usize);
    let data = cells.data;
    let mut grid = data.clone();
    for _ in 0..VOID_REPORT_LIMIT {
        let cell = largest_empty_rectangle(&grid, columns, rows_count);
        if cell[0] == 0 {
            break;
        }
        let void = void_from_cell(cell, live, live_width, scale);
        if row.largest_void.is_none() {
            row.largest_void = Some(void);
        }
        if void.height_points >= VOID_MIN_HEIGHT_POINTS
            && void.width_fraction >= VOID_MIN_WIDTH_FRACTION
        {
            row.voids.push(void);
        }
        mask_cell(&mut grid, columns, cell);
    }
    if let Some(height) = declared_height {
        row.tail_band = locate_tail_band(&data, columns, rows_count, live, scale, height);
    }
    Ok(())
}

pub fn annotate_void_geometry(
    rendered_pages: &[PathBuf],
    rows: &mut [PageAnnotation],
    body_pages: &BTreeSet<usize>,
    tail_bands: &BTreeMap<usize, f64>,
) -> Result<Option<[f64; 4]>> {
    let scale = 72.0 / RASTER_DPI as f64;
    let Some(live) = live_box(rows, body_pages) else {
        return Ok(None);
    };
    let rounded = [
        round_places(live[0] as f64 * scale, 1),
        round_places(live[1] as f64 * scale, 1),
        round_places(live[2] as f64 * scale, 1),
        round_places(live[3] as f64 * scale, 1),
    ];
    if live[2] - live[0] < VOID_DOWNSAMPLE as i64 || live[3] - live[1] < VOID_DOWNSAMPLE as i64 {
        return Ok(Some(rounded));
    }
    for row in rows.iter_mut() {
        let page = row.inspection.page;
        if !body_pages.contains(&page)
            || row.inspection.presence_bbox.is_none()
            || page > rendered_pages.len()
        {
            continue;
        }
        annotate_page(
            row,
            &rendered_pages[page - 1],
            live,
            tail_bands.get(&page).copied(),
        )?;
    }
    Ok(Some(rounded))
}

fn frame_runs(image: &Rgb, color_tolerance: i32) -> Vec<(u32, u32, u32)> {
    let minimum_run = (image.width as f64 * OPENER_FRAME_MIN_RUN_FRACTION) as u32;
    let mut runs = vec![];
    for y in 0..image.height / 2 {
        let mut start: Option<u32> = None;
        for x in 0..=image.width {
            let is_frame = x < image.width && {
                let at = (y as usize * image.width as usize + x as usize) * 3;
                image.data[at..at + 3]
                    .iter()
                    .zip(OPENER_FRAME_RGB)
                    .all(|(&channel, target)| {
                        (channel as i32 - target as i32).abs() <= color_tolerance
                    })
            };
            match (is_frame, start) {
                (true, None) => start = Some(x),
                (false, Some(from)) => {
                    if x - from >= minimum_run {
                        runs.push((from, x, y));
                    }
                    start = None;
                }
                _ => {}
            }
        }
    }
    runs
}

fn border_box(runs: &[(u32, u32, u32)]) -> Option<[u32; 4]> {
    let longest = runs.iter().map(|(from, to, _)| to - from).max()?;
    let border: Vec<&(u32, u32, u32)> = runs
        .iter()
        .filter(|(from, to, _)| to - from + 2 >= longest)
        .collect();
    Some([
        border.iter().map(|(from, _, _)| *from).min()?,
        border.iter().map(|(_, _, y)| *y).min()?,
        border.iter().map(|(_, to, _)| *to).max()?,
        border.iter().map(|(_, _, y)| *y).max()? + 1,
    ])
}

pub fn opener_frame_bbox(image: &Rgb, color_tolerance: i32) -> Option<[u32; 4]> {
    let runs = frame_runs(image, color_tolerance);
    if runs.is_empty() {
        return None;
    }
    border_box(&runs)
}

fn frame_message(frame_delta: Option<f64>, frames_match: bool) -> String {
    match (frame_delta, frames_match) {
        (None, true) => "no illustration frame detected in either raster".to_string(),
        (Some(delta), _) => format!("frame edge delta {delta:.4}in"),
        (None, false) => "illustration frame detected in only one raster".to_string(),
    }
}

pub fn inspect_opener_crop_fidelity(crop_path: &Path, reader_page_path: &Path) -> Result<Value> {
    let reference = decode_rgb(reader_page_path)?;
    let source = decode_rgb(crop_path)?;
    let normalized = resize(
        &source,
        (reference.width, reference.height),
        (0.0, 0.0, source.width as f64, source.height as f64),
    );
    let histogram = rgb_histogram(&difference(&normalized, &reference)?);
    let channel_values = reference.width as f64 * reference.height as f64 * 3.0;
    let total: u64 = histogram
        .iter()
        .enumerate()
        .map(|(index, &count)| (index % 256) as u64 * count as u64)
        .sum();
    let rgb_mae = total as f64 / channel_values;
    let crop_frame = opener_frame_bbox(&normalized, 24);
    let reference_frame = opener_frame_bbox(&reference, 24);
    let mut frames_match = crop_frame.is_some() && reference_frame.is_some();
    let frame_delta = match (crop_frame, reference_frame) {
        (Some(one), Some(other)) => Some(
            one.iter()
                .zip(other)
                .map(|(&edge, other_edge)| (edge as i64 - other_edge as i64).unsigned_abs())
                .max()
                .expect("a bounding box has four edges") as f64
                / RASTER_DPI as f64,
        ),
        (None, None) => {
            frames_match = true;
            None
        }
        _ => None,
    };
    let passed = rgb_mae <= OPENER_CROP_FIDELITY_MAX_RGB_MAE
        && frames_match
        && frame_delta.is_none_or(|delta| delta <= OPENER_CROP_FRAME_MAX_EDGE_DELTA_INCHES);
    Ok(json!({
        "pass": passed,
        "rgb_mae": round_places(rgb_mae, 4),
        "maximum_rgb_mae": OPENER_CROP_FIDELITY_MAX_RGB_MAE,
        "frame_edge_delta_inches": frame_delta.map(|delta| round_places(delta, 4)),
        "maximum_frame_edge_delta_inches": OPENER_CROP_FRAME_MAX_EDGE_DELTA_INCHES,
        "normalized_pixels": [reference.width, reference.height],
        "message": format!("RGB MAE {rgb_mae:.2}/255; {}.", frame_message(frame_delta, frames_match)),
    }))
}

fn orange_at(image: &Rgb, x: u32, y: u32) -> bool {
    let at = (y as usize * image.width as usize + x as usize) * 3;
    image.data[at..at + 3] == OPENER_OFFSET_RGB
}

pub fn inspect_opener_offset(path: &Path) -> Result<Value> {
    let image = decode_rgb(path)?;
    let runs = frame_runs(&image, 0);
    if runs.is_empty() {
        return Ok(json!({
            "pass": false,
            "message": "The critic could not locate the long near-black illustration frame.",
        }));
    }
    let frame = border_box(&runs).expect("a non-empty run list has a border box");
    let [left, top, right, bottom] = frame;
    let search = (4.0f64)
        .max(round_half_even(OPENER_OFFSET_POINTS * RASTER_DPI as f64 / 72.0 * 3.0) as f64)
        as u32;
    let right_orange: Vec<(u32, u32)> = (top..image.height.min(bottom + search))
        .flat_map(|y| (right..image.width.min(right + search)).map(move |x| (x, y)))
        .filter(|&(x, y)| orange_at(&image, x, y))
        .collect();
    let bottom_orange: Vec<(u32, u32)> = (bottom..image.height.min(bottom + search))
        .flat_map(|y| (left..image.width.min(right + search)).map(move |x| (x, y)))
        .filter(|&(x, y)| orange_at(&image, x, y))
        .collect();
    if right_orange.is_empty() || bottom_orange.is_empty() {
        return Ok(json!({
            "pass": false,
            "frame_bbox_pixels": [left, top, right, bottom],
            "message": "The critic could not locate orange beyond both the frame's right and bottom edges.",
        }));
    }
    Ok(offset_verdict(frame, &right_orange, &bottom_orange))
}

fn offset_verdict(
    frame: [u32; 4],
    right_orange: &[(u32, u32)],
    bottom_orange: &[(u32, u32)],
) -> Value {
    let [left, top, right, bottom] = frame.map(i64::from);
    let offset_x = bottom_orange
        .iter()
        .map(|(x, _)| *x as i64)
        .min()
        .expect("orange below")
        - left;
    let offset_y = right_orange
        .iter()
        .map(|(_, y)| *y as i64)
        .min()
        .expect("orange right")
        - top;
    let extension_x = right_orange
        .iter()
        .map(|(x, _)| *x as i64)
        .max()
        .expect("orange right")
        + 1
        - right;
    let extension_y = bottom_orange
        .iter()
        .map(|(_, y)| *y as i64)
        .max()
        .expect("orange below")
        + 1
        - bottom;
    let expected = OPENER_OFFSET_POINTS * RASTER_DPI as f64 / 72.0;
    let values = [offset_x, offset_y, extension_x, extension_y];
    let passed = values
        .iter()
        .all(|&value| (value as f64 - expected).abs() <= OPENER_OFFSET_TOLERANCE_PIXELS);
    json!({
        "pass": passed,
        "frame_bbox_pixels": [left, top, right, bottom],
        "offset_pixels": [offset_x, offset_y],
        "extension_pixels": [extension_x, extension_y],
        "expected_offset_pixels": round_places(expected, 2),
        "tolerance_pixels": OPENER_OFFSET_TOLERANCE_PIXELS,
        "message": format!(
            "Measured orange start {offset_x}px right and {offset_y}px down, with {extension_x}px right and {extension_y}px bottom extension; expected {expected:.1}px on every edge."
        ),
    })
}

pub fn normalized(raw: &str) -> String {
    raw.split(is_python_space)
        .filter(|piece| !piece.is_empty())
        .collect::<Vec<_>>()
        .join(" ")
}

pub fn spread_text(elements: &[Element], media: [f64; 4]) -> String {
    let middle = if media[2] - media[0] > media[3] - media[1] {
        (media[0] + media[2]) / 2.0
    } else {
        f64::INFINITY
    };
    let (left, right): (Vec<_>, Vec<_>) = elements
        .iter()
        .filter_map(|element| match element {
            Element::Text { s, m, .. } => Some((s.as_str(), m[4] as f64 / 100.0)),
            _ => None,
        })
        .partition(|(_, x)| *x < middle);
    left.into_iter()
        .chain(right)
        .map(|(s, _)| s)
        .collect::<Vec<_>>()
        .join(" ")
}

#[derive(Debug, Clone)]
pub struct Leg {
    pub raw: Vec<String>,
    pub normalized: Vec<String>,
    pub media: Vec<[f64; 4]>,
}

impl Leg {
    pub fn pages(&self) -> usize {
        self.media.len()
    }

    fn normalized_page(&self, page: usize) -> &str {
        self.normalized
            .get(page - 1)
            .map(String::as_str)
            .unwrap_or("")
    }

    pub fn all_a4_landscape(&self) -> bool {
        !self.media.is_empty()
            && self.media.iter().all(|media| {
                (media[2] - media[0] - A4_LANDSCAPE_POINTS.0).abs() <= GEOMETRY_TOLERANCE
                    && (media[3] - media[1] - A4_LANDSCAPE_POINTS.1).abs() <= GEOMETRY_TOLERANCE
            })
    }

    pub fn size(&self, page: usize) -> (f64, f64) {
        let media = self.media[page - 1];
        (media[2] - media[0], media[3] - media[1])
    }
}

fn media_boxes(pdf: &Path) -> Result<Vec<[f64; 4]>> {
    let document =
        lopdf::Document::load(pdf).with_context(|| format!("reading {}", pdf.display()))?;
    let mut boxes = vec![];
    for (_, id) in document.get_pages() {
        let mut current = id;
        let media = loop {
            let dictionary = document.get_dictionary(current)?;
            if let Ok(value) = dictionary.get(b"MediaBox") {
                let array = document.dereference(value)?.1.as_array()?;
                let mut out = [0.0f64; 4];
                for (slot, item) in out.iter_mut().zip(array) {
                    *slot = match document.dereference(item)?.1 {
                        lopdf::Object::Integer(value) => *value as f64,
                        lopdf::Object::Real(value) => *value as f64,
                        other => anyhow::bail!("MediaBox carries {other:?}"),
                    };
                }
                break out;
            }
            match dictionary.get(b"Parent") {
                Ok(lopdf::Object::Reference(parent)) => current = *parent,
                _ => anyhow::bail!("page {current:?} has no MediaBox"),
            }
        };
        boxes.push(media);
    }
    Ok(boxes)
}

pub fn read_leg(pdf: &Path, fonts: &BTreeMap<String, TextFace>) -> Result<Leg> {
    let media = media_boxes(pdf)?;
    let traced = trace_elements(pdf, 1, media.len() as u32, fonts)?;
    Ok(Leg {
        raw: traced.iter().map(|page| page_text(page)).collect(),
        normalized: traced
            .iter()
            .zip(&media)
            .map(|(page, box_points)| normalized(&spread_text(page, *box_points)))
            .collect(),
        media,
    })
}

#[derive(Debug, Clone, PartialEq)]
pub struct Spread {
    pub side: usize,
    pub sheet: usize,
    pub face: &'static str,
    pub left_reader_page: Option<usize>,
    pub right_reader_page: Option<usize>,
    pub text_order_matches: bool,
}

impl Spread {
    pub fn as_row(&self) -> Value {
        json!({
            "side": self.side,
            "sheet": self.sheet,
            "face": self.face,
            "left_reader_page": self.left_reader_page,
            "right_reader_page": self.right_reader_page,
            "text_order_matches": self.text_order_matches,
        })
    }
}

pub fn booklet_spread_checks(
    reader: &Leg,
    booklet: &Leg,
    spreads: &[(Option<usize>, Option<usize>)],
) -> Vec<Spread> {
    let reader_pages = reader.pages();
    let within = |page: Option<usize>| page.filter(|number| *number <= reader_pages);
    spreads
        .iter()
        .enumerate()
        .map(|(index, &(left, right))| {
            let side_index = index + 1;
            let expected = [left, right]
                .into_iter()
                .filter_map(within)
                .map(|page| reader.normalized_page(page))
                .filter(|text| !text.is_empty())
                .collect::<Vec<_>>()
                .join(" ");
            let actual = if side_index <= booklet.pages() {
                booklet.normalized_page(side_index)
            } else {
                ""
            };
            Spread {
                side: side_index,
                sheet: side_index.div_ceil(2),
                face: if side_index % 2 == 1 {
                    "outside"
                } else {
                    "inside"
                },
                left_reader_page: within(left),
                right_reader_page: within(right),
                text_order_matches: actual == expected,
            }
        })
        .collect()
}

fn json_truthy(value: Option<&Value>) -> bool {
    match value {
        None | Some(Value::Null) => false,
        Some(Value::Bool(flag)) => *flag,
        Some(Value::Number(number)) => number.as_f64().is_some_and(|value| value != 0.0),
        Some(Value::String(text)) => !text.is_empty(),
        Some(Value::Array(items)) => !items.is_empty(),
        Some(Value::Object(map)) => !map.is_empty(),
    }
}

fn numeric(value: Option<&Value>) -> Option<f64> {
    match value {
        Some(Value::Bool(flag)) => Some(f64::from(u8::from(*flag))),
        Some(Value::Number(number)) => number.as_f64(),
        _ => None,
    }
}

fn manifest_json(destination: &Path) -> Value {
    let path = destination.join("edition-manifest.json");
    if !path.is_file() {
        return Value::Null;
    }
    std::fs::read_to_string(&path)
        .ok()
        .and_then(|text| serde_json::from_str(&text).ok())
        .unwrap_or(Value::Null)
}

pub fn manifest_layout(destination: &Path) -> Value {
    match manifest_json(destination).get("layout") {
        Some(layout) if layout.is_object() => layout.clone(),
        _ => json!({}),
    }
}

pub fn manifest_opener_article_ids(destination: &Path) -> Vec<String> {
    let manifest = manifest_json(destination);
    let Some(Value::Array(articles)) = manifest.get("inputs").and_then(|it| it.get("articles"))
    else {
        return vec![];
    };
    articles
        .iter()
        .filter(|row| row.get("opener_art").is_some_and(Value::is_object))
        .filter_map(|row| row.get("id").and_then(Value::as_str))
        .map(str::to_string)
        .collect()
}

fn rows_of<'a>(layout: &'a Value, key: &str) -> &'a [Value] {
    match layout.get(key) {
        Some(Value::Array(items)) => items,
        _ => &[],
    }
}

pub fn printed_tail_bands(
    layout: &Value,
    article_last_pages: &BTreeMap<String, usize>,
) -> BTreeMap<usize, f64> {
    let mut bands = BTreeMap::new();
    for entry in rows_of(layout, "tail_arts") {
        if !entry.is_object() || !json_truthy(entry.get("printed")) {
            continue;
        }
        let article = match entry.get("article") {
            Some(Value::String(text)) => text.clone(),
            Some(Value::Null) | None => "None".to_string(),
            Some(other) => other.to_string(),
        };
        if let (Some(height), Some(page)) = (
            numeric(entry.get("height_points")),
            article_last_pages.get(&article),
        ) {
            bands.insert(*page, height);
        }
    }
    bands
}

pub fn declared_editorial_cap(layout: &Value) -> i64 {
    match layout.get("maximum_editorial_pages") {
        Some(Value::Number(number)) if number.is_i64() => {
            let declared = number.as_i64().unwrap_or(0);
            if declared >= 1 {
                declared.min(DEFAULT_EDITORIAL_PAGE_CAP)
            } else {
                DEFAULT_EDITORIAL_PAGE_CAP
            }
        }
        _ => DEFAULT_EDITORIAL_PAGE_CAP,
    }
}

pub struct Imposition {
    pub spreads: Vec<Spread>,
    pub interior_pages: Vec<usize>,
    pub interior_spreads: Vec<Spread>,
    pub cover_pages: Vec<usize>,
    pub cover_spreads: Vec<Spread>,
}

pub struct Legs {
    pub reader: Leg,
    pub booklet: Leg,
    pub interior: Leg,
    pub cover: Leg,
}

fn ordered(pages: Result<Vec<usize>>, page_count: usize) -> Vec<usize> {
    if page_count >= 4 {
        pages.unwrap_or_default()
    } else {
        vec![]
    }
}

pub fn imposition_checks(
    recorder: &mut Recorder,
    legs: &Legs,
    rasters: &ReviewRasters,
) -> Result<Imposition> {
    let page_count = legs.reader.pages();
    if rasters.reader.len() != page_count {
        recorder.whole(
            "raster-page-count",
            "error",
            format!(
                "Rasterizer produced {} pages for a {page_count}-page PDF.",
                rasters.reader.len()
            ),
        );
    }
    if rasters.booklet.len() != legs.booklet.pages() {
        recorder.whole(
            "booklet-raster-page-count",
            "error",
            format!(
                "Rasterizer produced {} sides for a {}-side booklet.",
                rasters.booklet.len(),
                legs.booklet.pages()
            ),
        );
    }
    let expected = imposed_reader_page_plan(&section_reader_pages(page_count, "all")?);
    let spreads = booklet_spread_checks(&legs.reader, &legs.booklet, &expected);
    if !spreads.iter().all(|row| row.text_order_matches) {
        recorder.whole(
            "booklet-page-order",
            "error",
            "One or more booklet sides do not contain the expected left/right reader page pair."
                .to_string(),
        );
    }
    let interior_pages = ordered(section_reader_pages(page_count, "interior"), page_count);
    let interior_plan = imposed_reader_page_plan(&interior_pages);
    let interior_spreads = booklet_spread_checks(&legs.reader, &legs.interior, &interior_plan);
    if legs.interior.pages() != interior_plan.len() {
        recorder.whole(
            "interior-booklet-side-count",
            "error",
            format!(
                "Interior booklet has {} sides; {} are expected for reader pages 3-{}.",
                legs.interior.pages(),
                interior_plan.len(),
                page_count - 2
            ),
        );
    }
    if !legs.interior.all_a4_landscape() {
        recorder.whole(
            "interior-booklet-geometry",
            "error",
            "Every interior booklet side must be landscape A4.".to_string(),
        );
    }
    if !interior_spreads.iter().all(|row| row.text_order_matches) {
        recorder.whole(
            "interior-booklet-page-order",
            "error",
            "One or more interior booklet sides do not contain the expected left/right reader page pair."
                .to_string(),
        );
    }
    let cover_pages = ordered(section_reader_pages(page_count, "cover"), page_count);
    let cover_plan = if page_count >= 4 {
        cover_wrap_plan(page_count)?
    } else {
        vec![]
    };
    let cover_spreads = booklet_spread_checks(&legs.reader, &legs.cover, &cover_plan);
    cover_booklet_checks(recorder, legs, rasters, &cover_spreads, cover_plan.len());
    if !page_count.is_multiple_of(4) {
        recorder.whole(
            "signature-page-count",
            "error",
            format!("Reader page count {page_count} is not a multiple of four."),
        );
    }
    Ok(Imposition {
        spreads,
        interior_pages,
        interior_spreads,
        cover_pages,
        cover_spreads,
    })
}

fn cover_booklet_checks(
    recorder: &mut Recorder,
    legs: &Legs,
    rasters: &ReviewRasters,
    cover_spreads: &[Spread],
    expected_sides: usize,
) {
    if legs.cover.pages() != expected_sides {
        recorder.whole(
            "cover-booklet-side-count",
            "error",
            format!(
                "Cover booklet has {} sides; {expected_sides} are expected for the single-sided wrap.",
                legs.cover.pages()
            ),
        );
    }
    if !legs.cover.all_a4_landscape() {
        recorder.whole(
            "cover-booklet-geometry",
            "error",
            "Every cover booklet side must be landscape A4.".to_string(),
        );
    }
    if !cover_spreads.iter().all(|row| row.text_order_matches) {
        recorder.whole(
            "cover-booklet-page-order",
            "error",
            "The cover booklet must impose the back cover beside the front cover on its single outside side."
                .to_string(),
        );
    }
    if rasters.cover_booklet.len() != legs.cover.pages() {
        recorder.whole(
            "cover-booklet-raster-side-count",
            "error",
            format!(
                "Rasterizer produced {} sides for a {}-side cover booklet.",
                rasters.cover_booklet.len(),
                legs.cover.pages()
            ),
        );
    }
}

pub fn opener_offset_checks(
    recorder: &mut Recorder,
    illustrated: &[String],
    toc: &BTreeMap<String, usize>,
    rendered_pages: &[PathBuf],
) -> Result<Vec<Value>> {
    let mut checks = vec![];
    for article in illustrated {
        let page = toc.get(article).copied();
        let Some(page) = page.filter(|number| (1..=rendered_pages.len()).contains(number)) else {
            checks.push(json!({
                "article": article,
                "page": page,
                "pass": false,
                "message": "The packaged opener declaration has no valid article start page in the contents map.",
            }));
            recorder.push(
                "article-opener-offset-shadow",
                "error",
                format!("Article '{article}' declares opener art but has no valid reader page on which to verify its offset."),
                page,
            );
            continue;
        };
        let measured = inspect_opener_offset(&rendered_pages[page - 1])?;
        let mut row = json!({"article": article, "page": page});
        let map = row.as_object_mut().expect("an object");
        for (key, value) in measured.as_object().expect("a measurement object") {
            map.insert(key.clone(), value.clone());
        }
        if !measured["pass"].as_bool().unwrap_or(false) {
            recorder.at(
                "article-opener-offset-shadow",
                "error",
                format!(
                    "Article '{article}' does not have a true {}pt down-right orange illustration offset. {}",
                    format_g(OPENER_OFFSET_POINTS),
                    measured["message"].as_str().unwrap_or_default()
                ),
                page,
            );
        }
        checks.push(row);
    }
    Ok(checks)
}

fn format_g(value: f64) -> String {
    let text = format!("{value:.6}");
    let trimmed = text.trim_end_matches('0').trim_end_matches('.');
    trimmed.to_string()
}

#[derive(Debug, Clone, PartialEq)]
pub struct FlagCrop {
    pub page: usize,
    pub kind: &'static str,
    pub span: Option<(f64, f64)>,
}

pub struct RowContext<'a> {
    pub inside_cover_pages: &'a BTreeSet<usize>,
    pub last_page_numbers: &'a BTreeSet<usize>,
    pub live_area_points: Option<[f64; 4]>,
    pub article_last_pages: &'a BTreeMap<String, usize>,
}

fn void_span(void: &Void) -> Option<(f64, f64)> {
    Some((
        void.y_points - CROP_MARGIN_POINTS,
        void.y_points + void.height_points + CROP_MARGIN_POINTS,
    ))
}

fn tail_gap_issue(
    recorder: &mut Recorder,
    flags: &mut Vec<FlagCrop>,
    context: &RowContext,
    page: usize,
    void: &Void,
) {
    let Some(live) = context.live_area_points else {
        return;
    };
    let live_height = live[3] - live[1];
    if void.height_points < TAIL_GAP_MIN_LIVE_FRACTION * live_height {
        return;
    }
    let slug = context
        .article_last_pages
        .iter()
        .find(|(_, last)| **last == page)
        .map(|(name, _)| name.as_str())
        .unwrap_or("unknown article");
    recorder.at(
        "article-tail-gap",
        "review",
        format!(
            "'{slug}' ends leaving a {:.0} pt trailing blank ({:.0}% of the live area) with no tail art printed; consider approving tail art for this article.",
            void.height_points,
            void.height_points / live_height * 100.0
        ),
        page,
    );
    flags.push(FlagCrop {
        page,
        kind: "void",
        span: void_span(void),
    });
}

fn void_issues(
    recorder: &mut Recorder,
    flags: &mut Vec<FlagCrop>,
    context: &RowContext,
    row: &PageAnnotation,
) {
    let page = row.inspection.page;
    for void in &row.voids {
        if void.trailing && context.last_page_numbers.contains(&page) {
            if row.tail_band.is_none() {
                tail_gap_issue(recorder, flags, context, page, void);
            }
            continue;
        }
        if row
            .tail_band
            .as_ref()
            .is_some_and(|band| abuts_tail_band(void, band))
        {
            continue;
        }
        recorder.at(
            "whitespace-void",
            "review",
            format!(
                "A {:.0}x{:.0} pt white void starts {:.0} pt down the live area; confirm the whitespace is doing design work.",
                void.width_points, void.height_points, void.y_points
            ),
            page,
        );
        flags.push(FlagCrop {
            page,
            kind: "void",
            span: void_span(void),
        });
    }
}

pub fn page_row_issues(
    recorder: &mut Recorder,
    rows: &[PageAnnotation],
    context: &RowContext,
) -> Vec<FlagCrop> {
    let mut flags = vec![];
    for row in rows {
        let page = row.inspection.page;
        if context.inside_cover_pages.contains(&page) {
            if !row.inspection.blank {
                recorder.at(
                    "inside-cover-reader-not-blank",
                    "error",
                    "Inside front and inside back covers must be completely blank (a pure-white raster with no extractable text)."
                        .to_string(),
                    page,
                );
            }
        } else if row.inspection.ink_free {
            recorder.at(
                "blank-page",
                "error",
                "Rendered page is completely blank.".to_string(),
                page,
            );
        } else if row.inspection.sparse {
            recorder.at(
                "sparse-page",
                "review",
                format!(
                    "Ink coverage is only {:.4}; confirm that the whitespace is intentional.",
                    row.inspection.ink_ratio
                ),
                page,
            );
            flags.push(FlagCrop {
                page,
                kind: "sparse",
                span: None,
            });
        }
        if !row.inspection.standalone_punctuation_lines.is_empty() {
            recorder.at(
                "orphan-punctuation",
                "error",
                "A line contains only punctuation, which usually indicates a broken display title."
                    .to_string(),
                page,
            );
        }
        void_issues(recorder, &mut flags, context, row);
    }
    flags
}

pub fn stub_and_tail_issues(
    recorder: &mut Recorder,
    article_last_pages: &BTreeMap<String, usize>,
    rows: &[PageAnnotation],
    layout: &Value,
    flags: &mut Vec<FlagCrop>,
) {
    for (slug, last_page) in article_last_pages {
        if !(1..=rows.len()).contains(last_page) {
            continue;
        }
        let line_count = rows[last_page - 1].inspection.body_text_lines;
        if line_count < STUB_BODY_LINE_MINIMUM {
            recorder.at(
                "article-stub-last-page",
                "review",
                format!(
                    "The final page of '{slug}' carries only {line_count} line(s) of running text; consider re-cutting the break so the article does not end on a stub."
                ),
                *last_page,
            );
            flags.push(FlagCrop {
                page: *last_page,
                kind: "stub",
                span: Some((0.0, STUB_CROP_HEIGHT_POINTS)),
            });
        }
    }
    for entry in rows_of(layout, "tail_arts") {
        if !entry.is_object() {
            continue;
        }
        if json_truthy(entry.get("declared")) && !json_truthy(entry.get("printed")) {
            let article = match entry.get("article").and_then(Value::as_str) {
                Some(text) if !text.is_empty() => text,
                _ => "unknown article",
            };
            let reason = match entry.get("drop_reason").and_then(Value::as_str) {
                Some(text) if !text.is_empty() => text,
                _ => "no drop reason recorded",
            };
            recorder.whole(
                "tail-art-dropped",
                "review",
                format!(
                    "Tail art declared for '{article}' was not printed ({reason}); confirm the drop is intentional."
                ),
            );
        }
    }
}

pub fn booklet_side_issues(
    recorder: &mut Recorder,
    spreads: &[Spread],
    rows: &[PageInspection],
    inside_cover_pages: &BTreeSet<usize>,
    codes: (&str, &str),
) -> BTreeSet<usize> {
    let inside_sides: BTreeSet<usize> = spreads
        .iter()
        .filter(|row| {
            let pair: BTreeSet<usize> = [row.left_reader_page, row.right_reader_page]
                .into_iter()
                .flatten()
                .collect();
            pair == *inside_cover_pages
        })
        .map(|row| row.side)
        .collect();
    for row in rows {
        let side = row.page;
        if inside_sides.contains(&side) {
            if !row.blank {
                recorder.at(codes.0, "error", inside_message(codes.0), side);
            }
        } else if row.ink_free {
            recorder.at(codes.1, "error", blank_message(codes.1), side);
        }
    }
    inside_sides
}

fn inside_message(code: &str) -> String {
    match code {
        "inside-cover-booklet-not-blank" => {
            "The imposed side containing both inside covers must be completely blank (a pure-white raster with no extractable text)."
        }
        _ => {
            "The cover booklet's inside side must be completely blank (a pure-white raster with no extractable text)."
        }
    }
    .to_string()
}

fn blank_message(code: &str) -> String {
    match code {
        "blank-booklet-side" => "Rendered home-booklet side is completely blank.",
        _ => "The cover booklet's outer side carries no ink; it must print the back cover beside the front cover.",
    }
    .to_string()
}

pub struct Contents<'a> {
    pub toc: &'a BTreeMap<String, usize>,
    pub article_pages: &'a BTreeMap<String, usize>,
    pub editorial_pages: Option<i64>,
    pub actual_contents_pages: i64,
    pub maximum_contents_pages: i64,
}

pub fn contents_issues(
    recorder: &mut Recorder,
    reader: &Leg,
    layout: &Value,
    contents: &Contents,
) -> i64 {
    let cover_text = if reader.pages() > 0 {
        reader.raw.first().map(String::as_str).unwrap_or("")
    } else {
        ""
    };
    let placeholder = regex::Regex::new(COVER_PLACEHOLDER).expect("the pattern compiles");
    if placeholder.is_match(cover_text) {
        recorder.at(
            "cover-placeholder-copy",
            "error",
            "Cover typography contains placeholder or ellipsis copy.".to_string(),
            1,
        );
    }
    if !(1..=contents.maximum_contents_pages).contains(&contents.actual_contents_pages) {
        recorder.whole(
            "contents-pagination",
            "error",
            format!(
                "Contents uses {} pages; between 1 and {} are expected for {} entries.",
                contents.actual_contents_pages,
                contents.maximum_contents_pages,
                contents.toc.len()
            ),
        );
    }
    let page_count = reader.pages();
    if contents
        .toc
        .values()
        .any(|page| *page < 4 || *page > page_count)
    {
        recorder.whole(
            "contents-folio-range",
            "error",
            "A contents folio points outside the body page range.".to_string(),
        );
    }
    article_cap_issues(recorder, layout, contents.article_pages);
    let cap = declared_editorial_cap(layout);
    if contents.editorial_pages.is_some_and(|pages| pages > cap) {
        recorder.whole(
            "editorial-page-cap",
            "error",
            format!(
                "The opening editorial occupies {} reader pages; this edition allows {cap}.",
                contents.editorial_pages.unwrap_or_default()
            ),
        );
    }
    cap
}

fn article_cap_issues(
    recorder: &mut Recorder,
    layout: &Value,
    article_pages: &BTreeMap<String, usize>,
) {
    for (slug, count) in article_pages {
        let cap = layout
            .get("article_page_caps")
            .and_then(|caps| caps.get(slug))
            .and_then(Value::as_i64)
            .unwrap_or(DEFAULT_ARTICLE_PAGE_CAP);
        if *count as i64 <= cap {
            continue;
        }
        let verbatim = layout
            .get("article_content_modes")
            .and_then(|modes| modes.get(slug))
            .and_then(Value::as_str)
            == Some("verbatim");
        recorder.whole(
            "article-page-cap",
            if verbatim { "review" } else { "error" },
            format!(
                "Article {slug} exceeds its reader page cap{}",
                if verbatim {
                    " (verbatim: warning only)."
                } else {
                    "."
                }
            ),
        );
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct CropSpec {
    pub page: usize,
    pub kind: String,
    pub subject: Option<String>,
    pub region: [f64; 4],
}

fn clamped(
    reader: &Leg,
    page: usize,
    kind: &str,
    subject: Option<String>,
    region: Option<[f64; 4]>,
) -> CropSpec {
    let (width, height) = reader.size(page);
    let region = region.unwrap_or([0.0, 0.0, width, height]);
    CropSpec {
        page,
        kind: kind.to_string(),
        subject,
        region: [
            0.0f64.max(region[0].min(width)),
            0.0f64.max(region[1].min(height)),
            0.0f64.max(region[2].min(width)),
            0.0f64.max(region[3].min(height)),
        ],
    }
}

pub fn figure_crop_regions(layout: &Value, reader: &Leg) -> Vec<(usize, String, [f64; 4])> {
    let page_count = reader.pages();
    let mut out = vec![];
    for entry in rows_of(layout, "figures") {
        if !entry.is_object() {
            continue;
        }
        let Some(page) = entry
            .get("page")
            .and_then(Value::as_u64)
            .map(|page| page as usize)
        else {
            continue;
        };
        if !(1..=page_count).contains(&page) {
            continue;
        }
        let Some(Value::Array(box_points)) = entry.get("box_points") else {
            continue;
        };
        if box_points.len() != 4 {
            continue;
        }
        let numbers: Vec<f64> = box_points.iter().filter_map(Value::as_f64).collect();
        if numbers.len() != 4 {
            continue;
        }
        let (x, y, box_width, box_height) = (numbers[0], numbers[1], numbers[2], numbers[3]);
        let (_, height) = reader.size(page);
        let top = height - y - box_height;
        let subject = entry
            .get("id")
            .and_then(Value::as_str)
            .filter(|text| !text.is_empty())
            .or_else(|| entry.get("figure_id").and_then(Value::as_str))
            .unwrap_or("")
            .to_string();
        out.push((
            page,
            subject,
            [
                x - CROP_MARGIN_POINTS,
                top - CROP_MARGIN_POINTS,
                x + box_width + CROP_MARGIN_POINTS,
                top + box_height + CROP_MARGIN_POINTS + CROP_CAPTION_ALLOWANCE_POINTS,
            ],
        ));
    }
    out
}

pub fn review_crop_plan(
    reader: &Leg,
    toc: &BTreeMap<String, usize>,
    layout: &Value,
    printed_bands: &BTreeMap<usize, f64>,
    rows: &[PageAnnotation],
    flags: &[FlagCrop],
) -> Vec<CropSpec> {
    let page_count = reader.pages();
    let mut specs = vec![];
    for page in toc.values().copied().collect::<BTreeSet<usize>>() {
        if !(1..=page_count).contains(&page) {
            continue;
        }
        let opening: Vec<&str> = toc
            .iter()
            .filter(|(_, folio)| **folio == page)
            .map(|(slug, _)| slug.as_str())
            .collect();
        specs.push(clamped(
            reader,
            page,
            "opener",
            Some(opening.join(", ")),
            None,
        ));
    }
    for (page, subject, region) in figure_crop_regions(layout, reader) {
        specs.push(clamped(reader, page, "figure", Some(subject), Some(region)));
    }
    for page in printed_bands.keys().copied() {
        if !(1..=page_count.min(rows.len())).contains(&page) {
            continue;
        }
        let (width, height) = reader.size(page);
        let region = match rows[page - 1].tail_band {
            None => [
                0.0,
                height - TAIL_FALLBACK_CROP_HEIGHT_POINTS,
                width,
                height,
            ],
            Some(band) => [
                0.0,
                band.y_points - CROP_MARGIN_POINTS,
                width,
                band.y_points + band.height_points + CROP_MARGIN_POINTS,
            ],
        };
        specs.push(clamped(reader, page, "tail", None, Some(region)));
    }
    for flag in flags {
        if !(1..=page_count).contains(&flag.page) {
            continue;
        }
        let (width, _) = reader.size(flag.page);
        let region = flag.span.map(|(from, to)| [0.0, from, width, to]);
        specs.push(clamped(reader, flag.page, flag.kind, None, region));
    }
    specs
}

fn render_crop_page(reader_pdf: &Path, page_number: usize, output_dir: &Path) -> Result<PathBuf> {
    std::fs::create_dir_all(output_dir)
        .with_context(|| format!("cannot create {}", output_dir.display()))?;
    let stem = format!("page-{page_number:03}");
    let completed = std::process::Command::new("pdftoppm")
        .args(["-png", "-r", &CROP_DPI.to_string()])
        .args([
            "-f",
            &page_number.to_string(),
            "-l",
            &page_number.to_string(),
        ])
        .arg(reader_pdf)
        .arg(output_dir.join(&stem))
        .output()
        .context("Render criticism requires Poppler's pdftoppm executable.")?;
    let mut matches: Vec<PathBuf> = std::fs::read_dir(output_dir)?
        .filter_map(|entry| entry.ok().map(|entry| entry.path()))
        .filter(|path| {
            path.file_name()
                .and_then(|name| name.to_str())
                .is_some_and(|name| name.starts_with(&format!("{stem}-")) && name.ends_with(".png"))
        })
        .collect();
    matches.sort();
    if completed.status.success() {
        if let Some(first) = matches.first() {
            return Ok(first.clone());
        }
    }
    let stderr = String::from_utf8_lossy(&completed.stderr);
    let stdout = String::from_utf8_lossy(&completed.stdout);
    let detail = [stderr.trim(), stdout.trim(), "unknown Poppler error"]
        .into_iter()
        .find(|candidate| !candidate.is_empty())
        .unwrap_or("unknown Poppler error");
    anyhow::bail!("Could not rasterize reader page {page_number} for crops: {detail}")
}

fn crop_rgb(image: &Rgb, box_rect: [u32; 4]) -> Rgb {
    let width = box_rect[2] - box_rect[0];
    let height = box_rect[3] - box_rect[1];
    let mut data = Vec::with_capacity(width as usize * height as usize * 3);
    for y in box_rect[1]..box_rect[3] {
        let row = (y as usize * image.width as usize + box_rect[0] as usize) * 3;
        data.extend_from_slice(&image.data[row..row + width as usize * 3]);
    }
    Rgb {
        width,
        height,
        data,
    }
}

fn write_png(path: &Path, image: &Rgb) -> Result<()> {
    let file =
        std::fs::File::create(path).with_context(|| format!("cannot create {}", path.display()))?;
    let mut encoder = png::Encoder::new(std::io::BufWriter::new(file), image.width, image.height);
    encoder.set_color(png::ColorType::Rgb);
    encoder.set_depth(png::BitDepth::Eight);
    let mut writer = encoder.write_header()?;
    writer.write_image_data(&image.data)?;
    Ok(())
}

fn crop_name(base: &str, used: &mut BTreeSet<String>) -> String {
    let mut name = base.to_string();
    let mut suffix = 2;
    while used.contains(&name) {
        name = format!("{base}-{suffix}");
        suffix += 1;
    }
    used.insert(name.clone());
    name
}

fn crop_box(image: &Rgb, region: [f64; 4]) -> Option<[u32; 4]> {
    let scale = CROP_DPI as f64 / 72.0;
    let box_rect = [
        (region[0] * scale).floor().max(0.0) as u32,
        (region[1] * scale).floor().max(0.0) as u32,
        image.width.min((region[2] * scale).ceil().max(0.0) as u32),
        image.height.min((region[3] * scale).ceil().max(0.0) as u32),
    ];
    (box_rect[2] > box_rect[0] && box_rect[3] > box_rect[1]).then_some(box_rect)
}

pub fn write_review_crops(
    reader_pdf: &Path,
    crops_dir: &Path,
    destination: &Path,
    specs: &[CropSpec],
) -> Result<(Vec<PathBuf>, Vec<Value>)> {
    if specs.is_empty() {
        return Ok((vec![], vec![]));
    }
    std::fs::create_dir_all(crops_dir)
        .with_context(|| format!("cannot create {}", crops_dir.display()))?;
    let scratch = crops_dir.join("pages-at-300");
    let pages: Vec<usize> = specs
        .iter()
        .map(|spec| spec.page)
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect();
    let rasters = ordered_map(
        |page: &usize| render_crop_page(reader_pdf, *page, &scratch),
        &pages,
        Some(worker_count(pages.len(), None)),
    );
    let outcome = rasters.and_then(|rasters| {
        let rendered: BTreeMap<usize, PathBuf> = pages.iter().copied().zip(rasters).collect();
        emit_crops(crops_dir, destination, specs, &rendered)
    });
    std::fs::remove_dir_all(&scratch).ok();
    outcome
}

fn emit_crops(
    crops_dir: &Path,
    destination: &Path,
    specs: &[CropSpec],
    rendered: &BTreeMap<usize, PathBuf>,
) -> Result<(Vec<PathBuf>, Vec<Value>)> {
    let mut used = BTreeSet::new();
    let mut outputs = vec![];
    let mut rows = vec![];
    for spec in specs {
        let name = crop_name(&format!("crop-p{:02}-{}", spec.page, spec.kind), &mut used);
        let target = crops_dir.join(format!("{name}.png"));
        let image = decode_rgb(&rendered[&spec.page])?;
        let Some(box_rect) = crop_box(&image, spec.region) else {
            continue;
        };
        write_png(&target, &crop_rgb(&image, box_rect))?;
        outputs.push(target.clone());
        rows.push(json!({
            "path": target.strip_prefix(destination).unwrap_or(&target).to_string_lossy(),
            "page": spec.page,
            "kind": spec.kind,
            "subject": spec.subject,
            "region_points": spec.region.map(|value| round_places(value, 1)),
            "ppi": CROP_DPI,
        }));
    }
    Ok((outputs, rows))
}

pub fn opener_crop_fidelity_checks(
    recorder: &mut Recorder,
    crop_rows: &[Value],
    rendered_pages: &[PathBuf],
    destination: &Path,
) -> Result<Vec<Value>> {
    let mut checks = vec![];
    for crop in crop_rows {
        if crop["kind"].as_str() != Some("opener") {
            continue;
        }
        let page = crop["page"].as_u64().unwrap_or(0) as usize;
        if !(1..=rendered_pages.len()).contains(&page) {
            continue;
        }
        let region = &crop["region_points"];
        let reference = decode_rgb(&rendered_pages[page - 1])?;
        let expected = [2usize, 3].map(|index| {
            round_half_even(region[index].as_f64().unwrap_or(0.0) * RASTER_DPI as f64 / 72.0)
        });
        if (reference.width as i64 - expected[0]).abs() > 1
            || (reference.height as i64 - expected[1]).abs() > 1
        {
            continue;
        }
        let measured = inspect_opener_crop_fidelity(
            &destination.join(crop["path"].as_str().unwrap_or_default()),
            &rendered_pages[page - 1],
        )?;
        let mut row = json!({"page": page, "path": crop["path"]});
        let map = row.as_object_mut().expect("an object");
        for (key, value) in measured.as_object().expect("a measurement object") {
            map.insert(key.clone(), value.clone());
        }
        if !measured["pass"].as_bool().unwrap_or(false) {
            recorder.at(
                "article-opener-crop-fidelity",
                "error",
                format!(
                    "Full-page opener crop for reader page {page} does not match the final-PDF page raster. {}",
                    measured["message"].as_str().unwrap_or_default()
                ),
                page,
            );
        }
        checks.push(row);
    }
    Ok(checks)
}

pub struct Inputs<'a> {
    pub reader_pdf: &'a Path,
    pub booklet_pdf: &'a Path,
    pub interior_booklet_pdf: &'a Path,
    pub cover_booklet_pdf: &'a Path,
    pub destination: &'a Path,
    pub toc: &'a BTreeMap<String, usize>,
    pub article_pages: &'a BTreeMap<String, usize>,
    pub editorial_pages: Option<i64>,
    pub fonts: &'a BTreeMap<String, TextFace>,
}

pub struct Critique {
    pub result: &'static str,
    pub issues: Vec<Issue>,
    pub pages: Vec<PageAnnotation>,
    pub booklet_pages: Vec<PageInspection>,
    pub cover_booklet_pages: Vec<PageInspection>,
    pub spreads: Vec<Spread>,
    pub interior_reader_pages: Vec<usize>,
    pub interior_spreads: Vec<Spread>,
    pub cover_reader_pages: Vec<usize>,
    pub cover_spreads: Vec<Spread>,
    pub cover_booklet_inside_sides: BTreeSet<usize>,
    pub live_area_points: Option<[f64; 4]>,
    pub opener_offsets: Vec<Value>,
    pub opener_crop_fidelity: Vec<Value>,
    pub crops: Vec<Value>,
    pub crop_paths: Vec<PathBuf>,
    pub rasters: ReviewRasters,
    pub contents_pages: i64,
    pub maximum_contents_pages: i64,
    pub editorial_page_cap: i64,
}

impl Critique {
    pub fn decisions(&self) -> Value {
        json!({
            "result": self.result,
            "issues": self.issues.iter().map(Issue::as_row).collect::<Vec<Value>>(),
        })
    }
}

fn inspect_leg(rasters: &[PathBuf], leg: &Leg) -> Result<Vec<PageInspection>> {
    rasters
        .iter()
        .enumerate()
        .filter(|(index, _)| *index < leg.pages())
        .map(|(index, path)| inspect_page(path, index + 1, &leg.raw[index]))
        .collect()
}

pub struct Geometry {
    pub inside_cover_pages: BTreeSet<usize>,
    pub body_pages: BTreeSet<usize>,
    pub maximum_contents_pages: i64,
    pub actual_contents_pages: i64,
}

pub fn geometry(page_count: usize, toc: &BTreeMap<String, usize>) -> Geometry {
    let inside_cover_pages: BTreeSet<usize> = [2, page_count - 1].into_iter().collect();
    let maximum_contents_pages = (toc.len().div_ceil(8)).max(1) as i64;
    let first_body_page = toc
        .values()
        .copied()
        .min()
        .map(|page| page as i64)
        .unwrap_or(3 + maximum_contents_pages);
    let actual_contents_pages = first_body_page - 3;
    let contents: BTreeSet<usize> = (3..3 + actual_contents_pages.max(0))
        .map(|page| page as usize)
        .collect();
    let body_pages = (3..page_count.saturating_sub(1))
        .filter(|page| !inside_cover_pages.contains(page) && !contents.contains(page))
        .collect();
    Geometry {
        inside_cover_pages,
        body_pages,
        maximum_contents_pages,
        actual_contents_pages,
    }
}

fn read_legs(inputs: &Inputs) -> Result<Legs> {
    Ok(Legs {
        reader: read_leg(inputs.reader_pdf, inputs.fonts)?,
        booklet: read_leg(inputs.booklet_pdf, inputs.fonts)?,
        interior: read_leg(inputs.interior_booklet_pdf, inputs.fonts)?,
        cover: read_leg(inputs.cover_booklet_pdf, inputs.fonts)?,
    })
}

struct Prepared {
    legs: Legs,
    rasters: ReviewRasters,
    layout: Value,
    illustrated: Vec<String>,
    review_dir: PathBuf,
    pages: Vec<PageAnnotation>,
    booklet_pages: Vec<PageInspection>,
    cover_booklet_pages: Vec<PageInspection>,
}

fn prepare(inputs: &Inputs) -> Result<Prepared> {
    let legs = read_legs(inputs)?;
    let review_dir = inputs.destination.join("render-review");
    if review_dir.exists() {
        std::fs::remove_dir_all(&review_dir)
            .with_context(|| format!("cannot clear {}", review_dir.display()))?;
    }
    std::fs::create_dir_all(&review_dir)
        .with_context(|| format!("cannot create {}", review_dir.display()))?;
    let rasters = render_review_pages(
        inputs.reader_pdf,
        inputs.booklet_pdf,
        inputs.cover_booklet_pdf,
        &review_dir,
    )?;
    let pages = inspect_leg(&rasters.reader, &legs.reader)?
        .into_iter()
        .map(PageAnnotation::new)
        .collect();
    let booklet_pages = inspect_leg(&rasters.booklet, &legs.booklet)?;
    let cover_booklet_pages = inspect_leg(&rasters.cover_booklet, &legs.cover)?;
    Ok(Prepared {
        layout: manifest_layout(inputs.destination),
        illustrated: manifest_opener_article_ids(inputs.destination),
        legs,
        rasters,
        review_dir,
        pages,
        booklet_pages,
        cover_booklet_pages,
    })
}

struct Placement {
    live_area_points: Option<[f64; 4]>,
    crops: Vec<Value>,
    crop_paths: Vec<PathBuf>,
    opener_crop_fidelity: Vec<Value>,
}

fn placement_decisions(
    recorder: &mut Recorder,
    inputs: &Inputs,
    prepared: &mut Prepared,
    shape: &Geometry,
) -> Result<Placement> {
    let article_last_pages: BTreeMap<String, usize> = inputs
        .article_pages
        .iter()
        .filter(|(slug, count)| inputs.toc.contains_key(*slug) && **count > 0)
        .map(|(slug, count)| (slug.clone(), inputs.toc[slug] + count - 1))
        .collect();
    let last_page_numbers: BTreeSet<usize> = article_last_pages.values().copied().collect();
    let bands = printed_tail_bands(&prepared.layout, &article_last_pages);
    let live_area_points = annotate_void_geometry(
        &prepared.rasters.reader,
        &mut prepared.pages,
        &shape.body_pages,
        &bands,
    )?;
    let context = RowContext {
        inside_cover_pages: &shape.inside_cover_pages,
        last_page_numbers: &last_page_numbers,
        live_area_points,
        article_last_pages: &article_last_pages,
    };
    let mut flags = page_row_issues(recorder, &prepared.pages, &context);
    stub_and_tail_issues(
        recorder,
        &article_last_pages,
        &prepared.pages,
        &prepared.layout,
        &mut flags,
    );
    let specs = review_crop_plan(
        &prepared.legs.reader,
        inputs.toc,
        &prepared.layout,
        &bands,
        &prepared.pages,
        &flags,
    );
    let (crop_paths, crops) = write_review_crops(
        inputs.reader_pdf,
        &prepared.review_dir.join("crops"),
        inputs.destination,
        &specs,
    )?;
    let opener_crop_fidelity = opener_crop_fidelity_checks(
        recorder,
        &crops,
        &prepared.rasters.reader,
        inputs.destination,
    )?;
    Ok(Placement {
        live_area_points,
        crops,
        crop_paths,
        opener_crop_fidelity,
    })
}

pub fn inspect_render(inputs: &Inputs) -> Result<Critique> {
    let mut prepared = prepare(inputs)?;
    let page_count = prepared.legs.reader.pages();
    let mut recorder = Recorder::default();
    let imposition = imposition_checks(&mut recorder, &prepared.legs, &prepared.rasters)?;
    let opener_offsets = opener_offset_checks(
        &mut recorder,
        &prepared.illustrated,
        inputs.toc,
        &prepared.rasters.reader,
    )?;
    let shape = geometry(page_count, inputs.toc);
    let placement = placement_decisions(&mut recorder, inputs, &mut prepared, &shape)?;
    booklet_side_issues(
        &mut recorder,
        &imposition.spreads,
        &prepared.booklet_pages,
        &shape.inside_cover_pages,
        ("inside-cover-booklet-not-blank", "blank-booklet-side"),
    );
    let cover_booklet_inside_sides = booklet_side_issues(
        &mut recorder,
        &imposition.cover_spreads,
        &prepared.cover_booklet_pages,
        &shape.inside_cover_pages,
        ("cover-booklet-inside-not-blank", "blank-cover-booklet-side"),
    );
    let editorial_page_cap = contents_issues(
        &mut recorder,
        &prepared.legs.reader,
        &prepared.layout,
        &Contents {
            toc: inputs.toc,
            article_pages: inputs.article_pages,
            editorial_pages: inputs.editorial_pages,
            actual_contents_pages: shape.actual_contents_pages,
            maximum_contents_pages: shape.maximum_contents_pages,
        },
    );
    let issues = recorder.issues;
    Ok(Critique {
        result: if issues.iter().any(|row| row.severity == "error") {
            "fail"
        } else {
            "pass"
        },
        issues,
        pages: prepared.pages,
        booklet_pages: prepared.booklet_pages,
        cover_booklet_pages: prepared.cover_booklet_pages,
        spreads: imposition.spreads,
        interior_reader_pages: imposition.interior_pages,
        interior_spreads: imposition.interior_spreads,
        cover_reader_pages: imposition.cover_pages,
        cover_spreads: imposition.cover_spreads,
        cover_booklet_inside_sides,
        live_area_points: placement.live_area_points,
        opener_offsets,
        opener_crop_fidelity: placement.opener_crop_fidelity,
        crops: placement.crops,
        crop_paths: placement.crop_paths,
        rasters: prepared.rasters,
        contents_pages: shape.actual_contents_pages,
        maximum_contents_pages: shape.maximum_contents_pages,
        editorial_page_cap,
    })
}
