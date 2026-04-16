#!/usr/bin/env node
/**
 * resume_docx.js — Generate a formatted resume .docx from structured data
 * Matches reference styling: Times New Roman, justified bullets, Symbol bullets
 * Usage: node resume_docx.js <input.json>
 * Input JSON: { company_blocks, project_rows, skills_rows, professional_summary, output_path }
 */

const path = require('path');
const fs   = require('fs');

let docx;
try {
  docx = require('docx');
} catch (_) {
  // Fallback: project-local install (resume/node_modules/docx) — portable across sessions
  docx = require(path.join(__dirname, 'node_modules', 'docx'));
}

const {
  Document, Packer, Paragraph, TextRun,
  AlignmentType, TabStopType, LevelFormat, BorderStyle,
} = docx;

// ─────────────────────────────────────────────────────────
// Design constants — extracted from reference document XML
// ─────────────────────────────────────────────────────────
const FONT         = 'Times New Roman';
const BODY         = 20;     // 10pt in half-points
const NAME_SIZE    = 32;     // 16pt for name

// Page + margins (DXA = twentieths of a point)
const PAGE_W       = 12240;  // 8.5"
const PAGE_H       = 15840;  // 11"
const MARGIN_TOP   = 1080;   // 0.75" top
const MARGIN_LR    = 720;    // 0.5" left & right  (bottom comes from LAYOUT.marginBottom)
const CONTENT_W    = PAGE_W - 2 * MARGIN_LR;  // 10800 DXA = 7.5"

// Indent for company header lines (hanging so first line is flush)
const HDR_LEFT     = 180;
const HDR_HANG     = 180;

// Bullet indentation (reference: left=720, hang=360)
const BULL_LEFT    = 720;
const BULL_HANG    = 360;

// Spacer font size (tiny → minimal inter-company gap)
const SPACER_FONT_SZ = 4;   // 2pt font → ~3pt line height

// ── Runtime layout — set once per document inside buildResume() ─────────────
// Overridden by data.layout from Python's tier chooser; defaults = T0.
let LAYOUT = {
  line:         220,   // body line spacing (DXA; 240 = exact single)
  sectionBefore: 320,  // before section header = gap below last bullet (DXA; 320 ≈ 16pt)
  sectionAfter:  180,  // after section header border = gap above first content (DXA; 180 ≈ 9pt)
  marginBottom:  720,  // bottom page margin (DXA)
};

// ─────────────────────────────────────────────────────────
// Company metadata (fixed — mirrors handcrafted resume)
// ─────────────────────────────────────────────────────────
const COMPANY_META = {
  'GOJEK': {
    display:  'Gojek',
    desc:     '(SE Asia ride-hailing super app serving 20M+ riders)',
    location: 'Gurgaon, India',
    dates:    'Jan 2025 \u2013 Jul 2025',
    title:    'Senior Software Engineer \u2013 Supply & Marketplace Strategy',
  },
  'HEVO DATA': {
    display:  'Hevo Data',
    desc:     '(Sequoia-backed ELT data platform)',
    location: 'Bengaluru, India',
    dates:    'Nov 2023 \u2013 Jan 2025',
    title:    'Software Engineer 2',
  },
  'INTUIT': {
    display:  'Intuit',
    desc:     '(QuickBooks Online, MSE: Monetization Services & Experiences)',
    location: 'Bengaluru, India',
    dates:    'Aug 2022 \u2013 Oct 2023',
    title:    'Software Engineer 2',
  },
  'OPTUM': {
    display:  'Optum',
    desc:     '(health-tech & data-analytics arm of UnitedHealth Group)',
    location: 'Gurgaon, India',
    dates:    'Jul 2020 \u2013 Aug 2022',
    title:    'Software Engineer',
  },
};

// ─────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────
function run(text, opts = {}) {
  return new TextRun({ text, font: FONT, size: BODY, ...opts });
}

// Section header: ALL CAPS bold, thin bottom border (sz=4 = 0.5pt)
// spacing.before = gap above header; spacing.after = gap below header border line
function sectionHeader(title) {
  return new Paragraph({
    spacing: { before: LAYOUT.sectionBefore, after: LAYOUT.sectionAfter, line: LAYOUT.line },
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: '000000', space: 1 } },
    children: [ run(title, { bold: true }) ],
  });
}

// Company/school header line with right-tab date
// boldParts = bold text runs, normalPart = un-bold suffix, date = right-aligned
function headerLine({ boldParts, normalPart, date }) {
  return new Paragraph({
    spacing: { line: LAYOUT.line },
    tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_W }],
    indent:   { left: HDR_LEFT, hanging: HDR_HANG },
    children: [
      ...boldParts.map(t => run(t, { bold: true })),
      run(normalPart),
      run('\t' + date),
    ],
  });
}

// Italic subtitle (role / degree) — un-bold, flush left
function subtitleLine(text) {
  return new Paragraph({
    spacing: { line: LAYOUT.line },
    children: [ run(text, { italics: true }) ],
  });
}

function projectHeaderLine({ company, date }) {
  return new Paragraph({
    spacing: { line: LAYOUT.line },
    tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_W }],
    indent:   { left: HDR_LEFT, hanging: HDR_HANG },
    children: [
      run(company || '', { bold: true }),
      run(date ? '\t' + date : ''),
    ],
  });
}

// Bullet paragraph — justified, indent from numbering config
function bulletPara(children) {
  return new Paragraph({
    spacing:   { line: LAYOUT.line },
    numbering:  { reference: 'resume-bullets', level: 0 },
    alignment:  AlignmentType.BOTH,
    children,
  });
}

// Plain text bullet
function textBullet(text) {
  return bulletPara([ run(text) ]);
}

// Skills bullet: "Bold label: normal text" — or plain if no label
function skillsBullet(boldLabel, text) {
  if (boldLabel) {
    return bulletPara([
      run(boldLabel + ':', { bold: true }),
      run(' ' + text),
    ]);
  }
  return bulletPara([ run(text) ]);
}

// Thin spacer paragraph (between companies/schools within a section)
// Uses a tiny font size so the line height is minimal (~3pt gap)
function spacer() {
  return new Paragraph({
    children: [ new TextRun({ text: '', font: FONT, size: SPACER_FONT_SZ }) ],
  });
}

// ─────────────────────────────────────────────────────────
// Build full resume document
// ─────────────────────────────────────────────────────────
function buildResume(data) {
  // Apply layout tier from Python (or keep defaults)
  if (data.layout) {
    if (data.layout.line          != null) LAYOUT.line          = data.layout.line;
    if (data.layout.section_before != null) LAYOUT.sectionBefore = data.layout.section_before;
    if (data.layout.section_after  != null) LAYOUT.sectionAfter  = data.layout.section_after;
    if (data.layout.margin_bottom  != null) LAYOUT.marginBottom  = data.layout.margin_bottom;
  }

  const children = [];

  // ── NAME HEADER ──────────────────────────────────────
  // Thick bottom border (sz=12 = 1.5pt) acts as the visual divider
  children.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: '000000', space: 1 } },
    children: [ new TextRun({
      text:      'AKSHAT PATHAK',
      font:      FONT,
      size:      NAME_SIZE,
      bold:      true,
      smallCaps: true,
    }) ],
  }));

  // Contact line — centered, no border, small gap below (before summary or EDUCATION header)
  children.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 40 },
    children: [ new TextRun({
      text: 'Los Angeles, CA \u2022 Akshat.Pathak.2027@marshall.usc.edu \u2022 (213) 325-0609 \u2022 linkedin.com/in/akshats-pathak',
      font: FONT,
      size: BODY,
    }) ],
  }));

  // ── PROFESSIONAL SUMMARY section (optional — only rendered if non-empty) ──
  // Header is track-dependent:
  //   PM track    → 'PRODUCT MANAGEMENT'   (ATS: signals PM identity)
  //   NonPM track → 'PROFESSIONAL EXPERIENCE'
  // The Python runner sets data.summary_section_header accordingly.
  if (data.professional_summary && data.professional_summary.trim()) {
    const summaryHeader = (data.summary_section_header || 'PRODUCT MANAGEMENT');
    children.push(sectionHeader(summaryHeader));
    children.push(new Paragraph({
      spacing:   { line: LAYOUT.line },
      alignment: AlignmentType.BOTH,
      children:  [ run(data.professional_summary.trim()) ],
    }));
  }

  // ── EDUCATION ────────────────────────────────────────
  children.push(sectionHeader('EDUCATION'));

  // USC
  children.push(headerLine({
    boldParts:  ['University of Southern California, Marshall School of Business'],
    normalPart: ' \u2013 Los Angeles, CA',
    date:       'May 2027',
  }));
  children.push(subtitleLine('Master of Business Administration (STEM)'));
  children.push(textBullet('Honors: Dean\u2019s Merit Scholarship'));
  children.push(textBullet('Leadership: AVP Alumni Relations, South Asian Business Association; AVP External Relations, High Tech Association'));

  // Thapar
  children.push(spacer());
  children.push(headerLine({
    boldParts:  ['Thapar Institute of Engineering and Technology'],
    normalPart: ' \u2013 Patiala, India',
    date:       'August 2020',
  }));
  children.push(subtitleLine('Bachelor of Engineering, Computer Engineering \u2014 GPA 3.73'));
  children.push(textBullet('Honors: Merit Scholarship (2\u00d7); Published AI-based Fake News Detection research (Springer, 2020; 90+ citations)'));
  children.push(textBullet('Leadership: General Secretary, Creative Computing Society \u2013 drove 1,000+ participants and secured $30K in sponsorships'));

  // ── EXPERIENCE ───────────────────────────────────────
  children.push(sectionHeader('EXPERIENCE'));

  for (let i = 0; i < data.company_blocks.length; i++) {
    const block = data.company_blocks[i];
    const meta  = COMPANY_META[block.key];
    if (!meta) {
      console.warn(`[WARN] Unknown company key: "${block.key}" — skipping.`);
      continue;
    }
    if (i > 0) children.push(spacer());
    children.push(headerLine({
      boldParts:  [meta.display],
      normalPart: ` ${meta.desc} \u2013 ${meta.location}`,
      date:       meta.dates,
    }));
    children.push(subtitleLine(meta.title));
    for (const bt of block.bullets) {
      children.push(textBullet(bt));
    }
  }

  // ── PROJECTS & CONSULTING (optional, primarily for non-PM routes) ───────
  if (Array.isArray(data.project_rows) && data.project_rows.length > 0) {
    children.push(sectionHeader('PROJECTS & CONSULTING'));
    for (let i = 0; i < data.project_rows.length; i++) {
      const row = data.project_rows[i];
      if (!row) continue;
      if (i > 0) children.push(spacer());

      if (row.company || row.date) {
        children.push(projectHeaderLine({
          company: row.company || '',
          date: row.date || '',
        }));
      }
      if (row.title) {
        children.push(subtitleLine(row.title));
      }
      for (const bt of (row.bullets || [])) {
        if (!bt || !bt.trim()) continue;
        children.push(textBullet(bt.trim()));
      }
    }
  }

  // ── SKILLS & INTERESTS ───────────────────────────────
  children.push(sectionHeader('SKILLS & INTERESTS'));

  for (const row of data.skills_rows) {
    if (!row.text && !row.bold_label) continue;
    children.push(skillsBullet(row.bold_label || null, row.text || ''));
  }

  // ── ASSEMBLE DOCUMENT ────────────────────────────────
  return new Document({
    numbering: {
      config: [{
        reference: 'resume-bullets',
        levels: [{
          level:     0,
          format:    LevelFormat.BULLET,
          text:      '\uF0B7',   // bullet in Symbol font private-use area
          alignment: AlignmentType.LEFT,
          style: {
            run: {
              font: 'Symbol',
            },
            paragraph: {
              indent: { left: BULL_LEFT, hanging: BULL_HANG },
            },
          },
        }],
      }],
    },
    sections: [{
      properties: {
        page: {
          size:   { width: PAGE_W, height: PAGE_H },
          margin: { top: MARGIN_TOP, right: MARGIN_LR, bottom: LAYOUT.marginBottom, left: MARGIN_LR },
        },
      },
      children,
    }],
  });
}

// ─────────────────────────────────────────────────────────
// Entry point
// ─────────────────────────────────────────────────────────
const inputPath = process.argv[2];
if (!inputPath) {
  console.error('Usage: node resume_docx.js <input.json>');
  process.exit(1);
}

let data;
try {
  data = JSON.parse(fs.readFileSync(inputPath, 'utf-8'));
} catch (e) {
  console.error('ERROR:' + e.message);
  process.exit(1);
}

const doc = buildResume(data);
Packer.toBuffer(doc)
  .then(buf => {
    fs.writeFileSync(data.output_path, buf);
    console.log('OK:' + data.output_path);
  })
  .catch(err => {
    console.error('ERROR:' + err.message);
    process.exit(1);
  });
