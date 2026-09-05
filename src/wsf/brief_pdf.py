"""Printable intelligence product for a packet."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from wsf.briefing_standards import packet_presentation
from wsf.packet import Packet, ProductBrief

INK = colors.HexColor("#17211d")
MUTED = colors.HexColor("#5f6b65")
RULE = colors.HexColor("#d4d8d3")
HEAD = colors.HexColor("#eeebe3")
ACCENT = colors.HexColor("#006b55")


def _plain(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("σ", " sigma")
        .replace("–", "-")
        .replace("—", " - ")
    )


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "kicker": ParagraphStyle(
            "kicker",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=ACCENT,
            spaceAfter=2 * mm,
        ),
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=3 * mm,
        ),
        "meta": ParagraphStyle(
            "meta",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=MUTED,
            spaceAfter=2 * mm,
        ),
        "h": ParagraphStyle(
            "h",
            parent=base["Heading2"],
            keepWithNext=True,
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=INK,
            spaceBefore=5 * mm,
            spaceAfter=2 * mm,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=INK,
            alignment=TA_JUSTIFY,
            spaceAfter=2.2 * mm,
        ),
        "cell": ParagraphStyle(
            "cell",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=INK,
        ),
        "cellh": ParagraphStyle(
            "cellh",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=10,
            textColor=MUTED,
        ),
        "warn": ParagraphStyle(
            "warn",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#a54c00"),
            spaceAfter=3 * mm,
            spaceBefore=1 * mm,
        ),
    }


def _table(header: list[str], rows: list[list[str]], widths: list[float]) -> Table:
    styles = _styles()
    data = [[Paragraph(_plain(cell), styles["cellh"]) for cell in header]]
    for row in rows:
        data.append([Paragraph(_plain(cell), styles["cell"]) for cell in row])
    grid = Table(data, colWidths=widths, repeatRows=1)
    grid.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEAD),
                ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("GRID", (0, 0), (-1, -1), 0.3, RULE),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, ACCENT),
            ]
        )
    )
    return grid


def _header_footer(packet: Packet):
    def draw(canvas, doc) -> None:
        canvas.saveState()
        width, height = A4
        canvas.setStrokeColor(ACCENT)
        canvas.setLineWidth(1.2)
        canvas.line(18 * mm, height - 12 * mm, width - 18 * mm, height - 12 * mm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(ACCENT)
        canvas.drawString(18 * mm, height - 10 * mm, "COLLECTION CUEING DESK")
        canvas.setFillColor(MUTED)
        canvas.drawRightString(width - 18 * mm, height - 10 * mm, "OSINT  |  UNCLASSIFIED")
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.4)
        canvas.line(18 * mm, 14 * mm, width - 18 * mm, 14 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 8 * mm, f"{packet.notice_id}  ·  {packet.packet_id}")
        canvas.drawRightString(width - 18 * mm, 8 * mm, f"{doc.page}")
        canvas.restoreState()

    return draw


def write_brief_pdf(packet: Packet, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()
    usable = A4[0] - 36 * mm
    story: list = []
    product = packet.product
    if product is None:
        story.append(Paragraph(_plain(f"Brief {packet.notice_id}"), styles["title"]))
        story.append(
            Paragraph(
                _plain(
                    f"Cutoff {packet.clocks.knowledge_cutoff.isoformat()} ({packet.clocks.mode})."
                ),
                styles["meta"],
            )
        )
    else:
        story.append(Paragraph("PREPARATORY ACTIVITY WATCH", styles["kicker"]))
        product = ProductBrief.model_validate(packet_presentation(packet.model_dump()))
        story.append(Paragraph(_plain(product.headline), styles["title"]))
        story.append(
            Paragraph(
                _plain(
                    f"{product.period}  |  Information available by {product.available_by}  |  "
                    f"{packet.clocks.mode}"
                ),
                styles["meta"],
            )
        )
        story.append(
            Paragraph(
                _plain(
                    f"Analytic state: {product.analytic_state_label}  |  "
                    f"AnCR: {product.confidence}  |  "
                    f"Change: {product.change}"
                ),
                styles["meta"],
            )
        )
        story.append(Paragraph("BLUF", styles["h"]))
        story.append(Paragraph(_plain(product.bluf), styles["body"]))
        story.append(
            Paragraph(
                _plain(
                    f"Analytical confidence: {product.confidence}. {product.confidence_rationale}"
                ),
                styles["body"],
            )
        )
        story.append(Paragraph("Source assessment", styles["h"]))
        story.append(Paragraph(_plain(product.source_assessment), styles["meta"]))
        if product.keys:
            story.append(Paragraph(_plain("Keys: " + "; ".join(product.keys)), styles["meta"]))
        for warning in product.availability_warnings:
            story.append(Paragraph(_plain(warning), styles["warn"]))
        story.append(Paragraph("Assessment", styles["h"]))
        for para in product.assessment:
            story.append(Paragraph(_plain(para), styles["body"]))
        if product.watchlist:
            story.append(Paragraph("Why this is on the watchlist", styles["h"]))
            story.append(
                _table(
                    ["Indicator", "Observation", "Analytic significance"],
                    [
                        [row["indicator"], row["observation"], row["implication"]]
                        for row in product.watchlist
                    ],
                    [32 * mm, 70 * mm, usable - 102 * mm],
                )
            )
            story.append(Spacer(1, 2 * mm))
        for caveat in product.caveats:
            story.append(Paragraph(_plain(caveat), styles["meta"]))
        if product.hypotheses:
            story.append(Paragraph("Competing explanations", styles["h"]))
            story.append(
                Paragraph(
                    "Likelihoods use the PHIA Probability Yardstick.",
                    ParagraphStyle("yardstick", parent=styles["meta"], keepWithNext=True),
                )
            )
            story.append(
                _table(
                    ["Hypothesis", "Likelihood", "What would discriminate"],
                    [
                        [row["hypothesis"], row["fit"], row["discriminate"]]
                        for row in product.hypotheses
                    ],
                    [40 * mm, 38 * mm, usable - 78 * mm],
                )
            )
        if product.collection:
            story.append(Paragraph("Collection requirements", styles["h"]))
            for row in product.collection:
                story.append(
                    Paragraph(
                        f"<b>{_plain(row['rank'])}. {_plain(row['title'])}.</b> "
                        f"{_plain(row['why'])}",
                        styles["body"],
                    )
                )
        if product.analyst_note:
            story.append(Paragraph("Analyst note", styles["h"]))
            story.append(Paragraph(_plain(product.analyst_note), styles["body"]))

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=(packet.product.headline if packet.product else packet.notice_id),
        author="WSD collection cueing desk",
        subject=f"{packet.notice_id} {packet.clocks.mode}",
    )
    draw = _header_footer(packet)
    doc.build(story, onFirstPage=draw, onLaterPages=draw)
    return path


def brief_pdf_path(evidence_path: Path) -> Path:
    return evidence_path.with_name("brief.pdf")


def render_existing_packet(project_root: Path, scenario_id: str, packet_id: str) -> Path:
    from wsf.packet import packet_path

    evidence = packet_path(project_root, scenario_id, packet_id)
    if not evidence.is_file():
        raise FileNotFoundError(f"unknown packet {scenario_id}/{packet_id}")
    packet = Packet.model_validate_json(evidence.read_text(encoding="utf-8"))
    return write_brief_pdf(packet, brief_pdf_path(evidence))
