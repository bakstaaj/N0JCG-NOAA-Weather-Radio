from pathlib import Path
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "publications"
OUT.mkdir(parents=True, exist_ok=True)
DOCX = OUT / "N0JCG_NOAA_Weather_Radio_User_Guide_v0.1.2.docx"

def shade(cell, fill):
    props = cell._tc.get_or_add_tcPr(); element = OxmlElement("w:shd"); element.set(qn("w:fill"), fill); props.append(element)

doc = Document()
section = doc.sections[0]; section.top_margin = Inches(.7); section.bottom_margin = Inches(.7); section.left_margin = Inches(.8); section.right_margin = Inches(.8)
styles = doc.styles
styles["Normal"].font.name = "Arial"; styles["Normal"].font.size = Pt(10); styles["Normal"].font.color.rgb = RGBColor(43,52,64)
for name, size, color in (("Title",30,"0A1F44"),("Heading 1",20,"0A1F44"),("Heading 2",14,"1565C0"),("Heading 3",11,"1565C0")):
    style = styles[name]; style.font.name = "Arial"; style.font.size = Pt(size); style.font.bold = True; style.font.color.rgb = RGBColor.from_string(color)
header = section.header.paragraphs[0]; header.text = "N0JCG  /  OPEN RADIO PLATFORM"; header.runs[0].font.color.rgb = RGBColor(21,101,192); header.runs[0].font.bold = True
footer = section.footer.paragraphs[0]; footer.alignment = WD_ALIGN_PARAGRAPH.CENTER; footer.add_run("N0JCG NOAA Weather Radio  |  v0.1.2  |  Receive-only by design")

title = doc.add_paragraph(style="Title"); title.add_run("N0JCG NOAA Weather Radio")
sub = doc.add_paragraph(); sub.add_run("Operator User Guide  |  Preview release v0.1.2").bold = True
doc.add_paragraph("A focused receive-only Raspberry Pi appliance for all seven US NOAA Weather Radio channels, FFT-directed strongest-channel selection, NFM audio, and operator-configurable SAME alert filters.")

def h(text, level=1): doc.add_heading(text, level=level)
def p(text): doc.add_paragraph(text)
def bullets(items):
    for item in items: doc.add_paragraph(item, style="List Bullet")
def steps(items):
    for item in items: doc.add_paragraph(item, style="List Number")

h("Safety and operating boundary")
p("This product has no transmit path. It is not an emergency alert replacement; keep an official weather receiver or other warning source available. A green application status proves software state, not RF coverage or the correctness of a warning.")
h("Hardware and identity")
p("Use a Raspberry Pi with current 64-bit Raspberry Pi OS, stable power, network access, an RTL-SDR with EEPROM serial 00000162, and a suitable VHF antenna. USB enumeration is not serial ownership; the application passes the required serial to RTL tools and does not use a temporary USB index.")
h("Installation")
steps(["From an MSYS2 UCRT64 shell, run ./deploy/install.sh --check-only.", "Run ./deploy/install.sh on the target Pi.", "Open http://<pi-address>:8086/ and confirm serial 00000162.", "Use systemctl status n0jcg-noaa-weather-radio and journalctl -u n0jcg-noaa-weather-radio for service evidence."])
h("First operation")
steps(["Confirm the receiver serial card shows 00000162.", "Press Start. The application surveys 162.395-162.555 MHz and starts browser audio on the strongest valid candidate.", "Review candidate cards; click any card to tune directly to that NOAA channel.", "Press Stop—the same button changes from Start to Stop—before disconnecting the receiver or changing USB hardware."])
p("Simulation mode is available with python3 -m n0jcg_noaa_weather_radio.server --simulate. It selects a deterministic test winner for software validation and is not live RF proof.")
h("NOAA channel plan")
table = doc.add_table(rows=1, cols=2); table.alignment = WD_TABLE_ALIGNMENT.CENTER; table.style = "Table Grid"
for cell, text in zip(table.rows[0].cells, ("Channel", "Frequency")):
    cell.text = text; shade(cell, "0A1F44"); cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER; run = cell.paragraphs[0].runs[0]; run.font.color.rgb = RGBColor(255,255,255); run.font.bold = True
for channel, frequency in (("WX1","162.400 MHz"),("WX2","162.425 MHz"),("WX3","162.450 MHz"),("WX4","162.475 MHz"),("WX5","162.500 MHz"),("WX6","162.525 MHz"),("WX7","162.550 MHz")):
    cells = table.add_row().cells; cells[0].text = channel; cells[1].text = frequency
h("FFT scan and audio")
p("The scanner scores power around each canonical channel from one wide survey. The highest SNR candidate is selected, then rtl_fm is started in narrow-FM mode at 48 kHz. The server supplies short 24 kHz mono WAV segments to the browser for scheduled playback. A high peak can still be interference; verify intelligible NOAA audio and inspect the other candidate values.")
h("SAME alerts")
p("Enter county FIPS codes and SAME event codes such as TOR or SVR, separated by commas. Empty fields accept all values. The test parser exercises syntax only; it does not prove that an over-the-air warning was received.")
bullets(["Record the raw header and UTC receipt time for live validation.", "Verify the tuned channel and intelligible 1050 Hz alert sequence.", "Treat a parsed test header as a software check, never as an operational warning."])
h("Registration")
p("The product has its own registration namespace, n0jcg-noaa-weather-radio. Open the hamburger menu to activate the product. Enter the N0JCG license S/N with prefix N0JCG-NWR- and the registered email address, then select Activate license. The application displays the product ID, license prefix, installation ID, and activation result there. Activation validates a signed, product-scoped lease for this installation and stores the credentials and lease under the private runtime license directory. While unregistered, the main dashboard continues to show the five-minute trial card and timer; both are removed after successful activation.")
h("Troubleshooting")
bullets(["No device: check rtl_test -d 00000162, USB power, permissions, and competing SDR owners.", "No candidates: check antenna, gain, local NOAA coverage, and rtl_power installation.", "Wrong winner: inspect all SNR values and reduce gain if the receiver is saturated.", "No SAME alert: validate with a live or recorded SAME fixture; browser state alone cannot prove decoder health.", "Shared receiver conflict: stop Air Traffic Center VHF audio before starting a live scan here."])
h("Release boundary")
p("v0.1.2 includes software tests, deterministic simulation, compact operator UI, direct channel tuning, scheduled browser WAV audio, product-scoped registration tools, conditional trial state, FFT scoring, NFM process control, SAME parsing, registration state, installer, package tooling, and this guide. Live USB, RF audio, antenna coverage, and end-to-end SAME acceptance remain target-hardware gates.")
doc.save(DOCX)
print(DOCX)
