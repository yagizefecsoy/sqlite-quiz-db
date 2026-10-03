"""rapor.html dosyasını Microsoft Edge (headless) ile Proje_Raporu.pdf'e çevirir."""
import subprocess
from pathlib import Path

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
klasor = Path(__file__).resolve().parent
kaynak = klasor / "rapor.html"
hedef = klasor / "Proje_Raporu.pdf"

subprocess.run(
    [EDGE, "--headless", "--disable-gpu", "--no-pdf-header-footer",
     f"--print-to-pdf={hedef}", kaynak.as_uri()],
    check=True,
)
print(f"PDF oluşturuldu: {hedef}")
