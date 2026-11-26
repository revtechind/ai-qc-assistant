import json
import re
from datetime import date
from io import BytesIO

import streamlit as st
from PIL import Image
from google import genai
from google.genai import types

st.set_page_config(
    page_title="AI QC Assistant",
    page_icon="🔎",
    layout="wide",
)

st.title("🔎 AI QC Assistant")
st.caption(
    "Membantu membaca foto SPK dan menyusun laporan WhatsApp. "
    "Keputusan dan verifikasi QC tetap dilakukan petugas."
)

# Ambil API key dari Streamlit Secrets.
secret_key = ""
try:
    secret_key = st.secrets.get("GEMINI_API_KEY", "")
except Exception:
    secret_key = ""

with st.sidebar:
    st.header("Pengaturan AI")
    typed_key = st.text_input(
        "Google Gemini API Key (opsional jika sudah disimpan di Secrets)",
        type="password",
        help="Jangan bagikan API key dan jangan masukkan ke GitHub.",
    )
    model_name = st.selectbox(
        "Model Gemini",
        ["gemini-3.5-flash-lite"],
        index=0,
    )
    st.caption("API key dari Streamlit Secrets digunakan otomatis jika kolom di atas kosong.")

api_key = typed_key.strip() or secret_key

st.info(
    "Unggah satu foto SPK. Usahakan foto fokus, tidak miring, pencahayaan cukup, "
    "dan seluruh bagian identitas, gambar/dimensi, tulisan tangan, serta stabilo terlihat."
)

col_a, col_b = st.columns(2)
with col_a:
    tanggal = st.date_input("Tanggal laporan", value=date.today())
    divisi = st.text_input("Divisi", placeholder="Contoh: QC Machining")
with col_b:
    operator = st.text_input("Operator", placeholder="Nama operator")
    tambahan = st.text_input("Tambahan / tindak lanjut", placeholder="Keterangan tambahan")

uploaded_file = st.file_uploader(
    "Foto SPK (pilih satu gambar)",
    type=["jpg", "jpeg", "png", "webp"],
)

PROMPT = """
Anda adalah asisten pengetikan laporan QC machining. Baca foto SPK yang diberikan.
Tugas Anda hanya menyalin informasi yang benar-benar terlihat. Jangan mengambil
keputusan lulus/gagal (OK/NG), jangan mengarang toleransi, penyebab, tindakan, atau angka.

Petunjuk:
1. Identifikasi customer, nomor SPK, nomor SO, nama unit/part, Type/SN, dan material
   jika benar-benar terbaca.
2. Temukan baris/area yang diberi stabilo/highlighter. Warna stabilo apa pun dapat
   menjadi penanda baris yang perlu dicatat. Stabilo TIDAK otomatis berarti NG.
3. Untuk setiap baris yang ditandai, salin karakteristik/dimensi, standar atau ukuran
   pada gambar, toleransi yang tercetak, nilai aktual tulisan tangan, dan satuan jika terbaca.
4. Pertahankan simbol Ø, ±, tanda plus/minus, koma/titik desimal, rentang, dan satuan.
5. Jika angka/tulisan tidak jelas, tulis "PERLU KONFIRMASI". Jangan menebak.
6. Jangan menentukan status kesesuaian. Status harus "Belum ditentukan - verifikasi QC".
7. Jika baris stabilo tidak dapat dikenali, jelaskan dalam catatan umum.

Keluarkan HANYA JSON valid dengan struktur:
{
  "metadata": {
    "customer": "",
    "spk": "",
    "so": "",
    "part": "",
    "type_sn": "",
    "material": ""
  },
  "findings": [
    {
      "karakteristik": "",
      "standar": "",
      "aktual": "",
      "satuan": "",
      "catatan_keterbacaan": ""
    }
  ],
  "catatan_umum": [],
  "status_verifikasi": "Belum ditentukan - verifikasi QC"
}
Gunakan string kosong jika informasi tidak tersedia. Jangan menambah field lain.
"""

def parse_json_response(raw_text: str) -> dict:
    """Parse JSON, including if the model unexpectedly wraps it in Markdown fences."""
    cleaned = (raw_text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        first = cleaned.find("{")
        last = cleaned.rfind("}")
        if first != -1 and last > first:
            return json.loads(cleaned[first:last + 1])
        raise

if "qc_result" not in st.session_state:
    st.session_state.qc_result = None

if st.button("🔎 BACA SPK DENGAN GEMINI", type="primary", use_container_width=True):
    if not api_key:
        st.error(
            "API key belum ditemukan. Periksa Streamlit Secrets: "
            'GEMINI_API_KEY = "API_KEY_KAMU".'
        )
    elif uploaded_file is None:
        st.error("Silakan unggah satu foto SPK terlebih dahulu.")
    else:
        try:
            image = Image.open(BytesIO(uploaded_file.getvalue())).convert("RGB")
            # Batasi dimensi gambar agar unggahan tidak terlalu besar.
            image.thumbnail((2400, 2400))
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=92)

            client = genai.Client(api_key=api_key)
            with st.spinner("Gemini sedang membaca foto SPK..."):
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        PROMPT,
                        types.Part.from_bytes(
                            data=buffer.getvalue(),
                            mime_type="image/jpeg",
                        ),
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1,
                    ),
                )

            st.session_state.qc_result = parse_json_response(response.text)
            st.success("Pembacaan selesai. Periksa dan koreksi hasilnya sebelum digunakan.")
        except Exception as exc:
            st.error(
                "Pembacaan gagal. Periksa koneksi internet, API key, kuota, "
                "nama model, dan kualitas foto."
            )
            st.code(str(exc))

result = st.session_state.qc_result

if result:
    metadata = result.get("metadata") or {}

    st.subheader("1. Periksa identitas SPK")
    left, right = st.columns(2)
    with left:
        customer = st.text_input("Customer", value=metadata.get("customer", ""), key="customer")
        spk = st.text_input("Nomor SPK", value=metadata.get("spk", ""), key="spk")
        so = st.text_input("Nomor SO", value=metadata.get("so", ""), key="so")
    with right:
        part = st.text_input("Unit barang / Part", value=metadata.get("part", ""), key="part")
        type_sn = st.text_input("Type / SN", value=metadata.get("type_sn", ""), key="type_sn")
        material = st.text_input("Material", value=metadata.get("material", ""), key="material")

    st.subheader("2. Periksa dimensi/baris yang ditandai stabilo")
    findings = result.get("findings") or []
    edited_findings = []

    if findings:
        for index, item in enumerate(findings):
            heading = item.get("karakteristik") or f"Baris {index + 1}"
            with st.expander(f"Baris {index + 1}: {heading}", expanded=True):
                characteristic = st.text_input(
                    "Karakteristik / dimensi",
                    value=item.get("karakteristik", ""),
                    key=f"characteristic_{index}",
                )
                standard = st.text_input(
                    "Standar / toleransi terbaca",
                    value=item.get("standar", ""),
                    key=f"standard_{index}",
                )
                actual = st.text_input(
                    "Aktual tulisan tangan",
                    value=item.get("aktual", ""),
                    key=f"actual_{index}",
                )
                unit = st.text_input(
                    "Satuan",
                    value=item.get("satuan", ""),
                    key=f"unit_{index}",
                )
                readability = st.text_area(
                    "Catatan keterbacaan",
                    value=item.get("catatan_keterbacaan", ""),
                    key=f"readability_{index}",
                )
                edited_findings.append({
                    "karakteristik": characteristic,
                    "standar": standard,
                    "aktual": actual,
                    "satuan": unit,
                    "catatan_keterbacaan": readability,
                })
    else:
        st.warning(
            "AI belum menemukan baris stabilo yang dapat diidentifikasi. "
            "Periksa foto SPK secara manual."
        )

    general_notes = result.get("catatan_umum") or []
    notes_text = st.text_area(
        "Catatan umum dari pembacaan AI",
        value="\n".join(str(note) for note in general_notes),
    )

    st.subheader("3. Laporan WhatsApp")
    report_lines = [
        "*LAPORAN HARIAN KETIDAKSESUAIAN*",
        "",
        f"Tanggal : {tanggal.strftime('%d-%m-%Y')}",
        f"* Customer : {customer}",
        f"* SPK : {spk}",
        f"* SO : {so}",
        f"* Unit Barang/Part : {part}",
    ]
    if type_sn:
        report_lines.append(f"* Type/SN : {type_sn}")
    if material:
        report_lines.append(f"* Material : {material}")
    if divisi:
        report_lines.append(f"* Divisi : {divisi}")

    report_lines.extend(["", "*Ketidaksesuaian / Dimensi yang ditandai:*"])
    if edited_findings:
        for index, item in enumerate(edited_findings, start=1):
            report_lines.append(f"{index}. {item['karakteristik'] or 'PERLU KONFIRMASI'}")
            report_lines.append(f"   - Standar: {item['standar'] or 'PERLU KONFIRMASI'}")
            report_lines.append(f"   - Aktual: {item['aktual'] or 'PERLU KONFIRMASI'}")
            if item["satuan"]:
                report_lines.append(f"   - Satuan: {item['satuan']}")
            if item["catatan_keterbacaan"]:
                report_lines.append(f"   - Catatan: {item['catatan_keterbacaan']}")
    else:
        report_lines.append("Baris stabilo belum teridentifikasi; perlu pemeriksaan manual.")

    report_lines.extend([
        "",
        "* Status: Belum ditentukan - verifikasi QC",
        f"* Operator : {operator}",
        f"* Tambahan : {tambahan}",
    ])
    if notes_text.strip():
        report_lines.extend(["", "*Catatan pembacaan AI:*", notes_text.strip()])
    report_lines.extend([
        "",
        "_Mohon verifikasi angka, toleransi, dan status oleh petugas QC sebelum laporan dikirim._",
    ])

    report_text = "\n".join(report_lines)
    st.text_area(
        "Teks laporan (siap disalin ke WhatsApp)",
        value=report_text,
        height=420,
    )
    st.download_button(
        "Unduh laporan TXT",
        data=report_text,
        file_name="laporan_qc.txt",
        mime="text/plain",
    )

st.divider()
st.caption(
    "AI hanya membantu pengetikan dan dapat salah membaca tulisan tangan, dimensi, "
    "atau penanda stabilo. Petugas QC wajib memverifikasi seluruh data. "
    "Jangan unggah dokumen rahasia perusahaan tanpa persetujuan."
)
