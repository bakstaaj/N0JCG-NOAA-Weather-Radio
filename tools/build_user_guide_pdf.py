from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image, PageBreak

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "publications" / "N0JCG_NOAA_Weather_Radio_User_Guide_v0.1.4.pdf"
SCREENSHOTS = ROOT / "docs" / "assets"
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="N0Title", parent=styles["Title"], fontSize=26, textColor=colors.HexColor("#0A1F44"), spaceAfter=8))
styles.add(ParagraphStyle(name="N0H1", parent=styles["Heading1"], fontSize=16, textColor=colors.HexColor("#0A1F44"), spaceBefore=12, spaceAfter=5))
styles.add(ParagraphStyle(name="N0Body", parent=styles["BodyText"], fontSize=9.5, leading=13, textColor=colors.HexColor("#2B3440"), spaceAfter=6))

def P(text, style="N0Body"):
    return Paragraph(text, styles[style])

def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#66788A"))
    canvas.drawString(.7 * inch, .35 * inch, "N0JCG NOAA Weather Radio | v0.1.4 | Receive-only by design")
    canvas.drawRightString(7.8 * inch, .35 * inch, f"Page {doc.page}")
    canvas.restoreState()

story = [P("N0JCG NOAA Weather Radio", "N0Title"), P("Operator User Guide | Preview release v0.1.4"), P("A focused receive-only Raspberry Pi appliance for all seven US NOAA Weather Radio channels, FFT-directed strongest-channel selection, NFM audio, and operator-configurable SAME alert filters.")]
metadata_rows = [[P("<b>Metadata</b>"), P("<b>Value</b>")]] + [[P(key), P(value)] for key, value in (("Product", "N0JCG NOAA Weather Radio"), ("Product ID", "n0jcg-noaa-weather-radio"), ("Document", "Operator user guide"), ("Version", "0.1.4"), ("Status", "Preview"), ("Receiver", "RTL-SDR serial 00000162"), ("Audience", "Operators and installers"), ("Owner", "N0JCG"))]
metadata = Table(metadata_rows, colWidths=[1.7 * inch, 4.8 * inch]); metadata.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A1F44")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#D7E0EB")), ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#EAF4FB")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
story.extend([Spacer(1, 8), metadata, PageBreak(), P("Contents", "N0H1")])
story.extend(P(item) for item in ("1. What N0JCG NOAA Weather Radio does", "2. Safety and operating boundary", "3. Hardware and identity", "4. Installation", "5. First operation", "6. NOAA channel plan", "7. FFT scan and browser audio", "8. SAME alerts", "9. Registration and trial access", "10. Troubleshooting", "11. Release boundary"))
story.append(PageBreak())
story.append(P("1. What N0JCG NOAA Weather Radio does", "N0H1"))
story.append(P("N0JCG NOAA Weather Radio is a receive-only Raspberry Pi appliance for all seven US NOAA Weather Radio channels. It uses FFT scoring to select the strongest candidate, provides narrow-FM browser audio, and supports operator-configurable SAME alert filters."))
dashboard = Image(str(SCREENSHOTS / "dashboard-live-v0.1.4.png"), width=6.7 * inch, height=6.7 * inch * 720 / 1280)
dashboard.hAlign = "CENTER"
story.extend([dashboard, P("Figure 1. Compact dashboard with receiver identity, trial status, Start/Stop control, and FFT-ranked NOAA candidates.")])

sections = {
    "2. Safety and operating boundary": ["This product has no transmit path. It is not an emergency alert replacement; keep an official weather receiver or other warning source available. A green application status proves software state, not RF coverage or the correctness of a warning."],
    "3. Hardware and identity": ["Use a Raspberry Pi with current 64-bit Raspberry Pi OS, stable power, network access, an RTL-SDR with EEPROM serial <b>00000162</b>, and a suitable VHF antenna. USB enumeration is not serial ownership; the application passes the required serial to RTL tools and does not use a temporary USB index."],
    "4. Installation": ["1. From an MSYS2 UCRT64 shell, run <font name='Courier'>./deploy/install.sh --check-only</font>.<br/>2. Run <font name='Courier'>./deploy/install.sh</font> on the target Pi.<br/>3. Open <font name='Courier'>http://&lt;pi-address&gt;:8086/</font> and confirm serial 00000162.<br/>4. Use systemctl status and journalctl for service evidence."],
    "5. First operation": ["1. Confirm the receiver serial card shows 00000162.<br/>2. Press Start. The application surveys 162.395-162.555 MHz and starts browser audio on the strongest valid candidate.<br/>3. Review candidate cards; click any card to tune directly to that NOAA channel.<br/>4. Press Stop—the same button changes from Start to Stop—before disconnecting the receiver or changing USB hardware.", "Simulation mode selects a deterministic test winner for software validation and is not live RF proof."],
    "7. FFT scan and browser audio": ["The scanner scores power around each canonical channel from one wide survey. The highest SNR candidate is selected, then rtl_fm is started in narrow-FM mode at 48 kHz. The server supplies short 24 kHz mono WAV segments to the browser for scheduled playback. A high peak can still be interference; verify intelligible NOAA audio."],
    "8. SAME alerts": ["Enter county FIPS codes and SAME event codes such as TOR or SVR, separated by commas. Empty fields accept all values. The test parser exercises syntax only; it does not prove that an over-the-air warning was received.", "Record the raw header and UTC receipt time for live validation. Verify the tuned channel and intelligible 1050 Hz alert sequence."],
    "9. Registration and trial access": ["The product has its own registration namespace, n0jcg-noaa-weather-radio. Open the hamburger menu to activate the product. Enter the N0JCG license S/N with prefix N0JCG-NWR- and the registered email address, then select Activate license. The application displays the product ID, license prefix, installation ID, and activation result there. Activation validates a signed, product-scoped lease for this installation and stores the credentials and lease under the private runtime license directory. While unregistered, the main dashboard continues to show the five-minute trial card and timer; both are removed after successful activation."],
    "10. Troubleshooting": ["No device: check rtl_test -d 00000162, USB power, permissions, and competing SDR owners.<br/>No candidates: check antenna, gain, local NOAA coverage, and rtl_power installation.<br/>Wrong winner: inspect all SNR values and reduce gain if the receiver is saturated.<br/>No SAME alert: validate with a live or recorded SAME fixture.<br/>Shared receiver conflict: stop Air Traffic Center VHF audio before starting a live scan here."],
    "11. Release boundary": ["v0.1.4 includes software tests, deterministic simulation, compact operator UI, direct channel tuning, scheduled browser WAV audio, product-scoped registration tools, conditional trial state, FFT scoring, NFM process control, SAME parsing, registration state, installer, package tooling, updated registration documentation, current live screenshots, and this guide. Live USB, RF audio, antenna coverage, and end-to-end SAME acceptance remain target-hardware gates."]
}
for heading, paragraphs in sections.items():
    story.append(P(heading, "N0H1"))
    story.extend(P(item) for item in paragraphs)
    if heading == "9. Registration and trial access":
        registration = Image(str(SCREENSHOTS / "registration-menu-live-v0.1.4.png"), width=6.7 * inch, height=6.7 * inch * 720 / 1280)
        registration.hAlign = "CENTER"
        story.extend([registration, P("Figure 2. Registration details shown in the operator menu; enter the product license S/N and registered email before activation.")])

story.append(P("6. NOAA channel plan", "N0H1"))
rows = [[P("<b>Channel</b>"), P("<b>Frequency</b>")]]
for channel, frequency in (("WX1", "162.400 MHz"), ("WX2", "162.425 MHz"), ("WX3", "162.450 MHz"), ("WX4", "162.475 MHz"), ("WX5", "162.500 MHz"), ("WX6", "162.525 MHz"), ("WX7", "162.550 MHz")):
    rows.append([channel, frequency])
table = Table(rows, colWidths=[2.2 * inch, 2.5 * inch])
table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A1F44")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#D7E0EB")), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F8FC")]), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
story.insert(-1, table)

SimpleDocTemplate(str(OUT), pagesize=letter, rightMargin=.7 * inch, leftMargin=.7 * inch, topMargin=.65 * inch, bottomMargin=.75 * inch, title="N0JCG NOAA Weather Radio User Guide").build(story, onFirstPage=footer, onLaterPages=footer)
print(OUT)
