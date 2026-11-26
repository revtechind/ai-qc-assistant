import json
import re
from datetime import date
from io import BytesIO

import streamlit as st
from PIL import Image
from google import genai
from google.genai import types

st.set_page_config(page_title="AI QC Assistant", page_icon="🔎", layout="wide")

st.title("🔎 AI QC Assistant")
st.caption("Membantu membaca SPK dan menyusun teks laporan WhatsApp. Keputusan QC tetap dilakukan petugas.")

# API key can be supplied through Streamlit Secrets or entered temporarily in the sidebar.
secret_key = ""
try:
    secret_key = st.secrets.get("GEMINI_API_KEY", "")
except Exception:
    pass

with st.sidebar:
    st.header("Pengaturan AI")
    entered_key = st.text_input(
        "Google Gemini API Key",
        type="password",
        help="Buat API key gratis di Google AI Studio. Jangan bagikan key ini."
    )
    model_name = st.selectbox(
        "Model",
        ["gemini-2.5-flash-lite", "gemini-2.5-flash"],
        index=0,
        help="Ketersediaan model dan kuota gratis dapat berubah."
    )
    st.caption("Gunakan API key pribadi. Jangan masukkan key ke GitHub atau kirim melalui chat.")

api_key = entered_key.strip() or secret_key

st.info(
    "Unggah satu foto SPK yang memperlihatkan identitas pekerjaan, gambar/dimensi, "
    "angka aktual tulisan tangan, dan baris yang diberi stabilo. Pastikan foto fokus, "
    "tidak miring, dan seluruh bagian penting terlihat."
)

col1, col2 = st.columns(2)
with col1:
    divisi = st.text_input("Divisi", placeholder="Contoh: BUBUT")
    operator = st.text_input("Operator", placeholder="Nama operator")
with col2:
    tanggal = st.date_input("Tanggal laporan", value=date.today())
    tambahan = st.text_input("Tambahan / tindak lanjut", placeholder="Contoh: Diisi PPIC")

uploaded = st.file_uploader("Foto SPK (1 gambar)", type=["jpg", "jpeg", "png", "webp"])

PROMPT = r"""
Anda adalah asisten pengetikan laporan QC machining. Baca foto SPK yang diberikan.
Tugas Anda hanya menyalin informasi yang benar-benar terlihat. Jangan mengambil keputusan
lulus/gagal (OK/NG), jangan mengarang toleransi, penyebab, tindakan, atau angka.

Prioritas:
1. Identifikasi nomor SPK, customer, SO, nama unit/part, type/SN, material bila terbaca.
2. Temukan baris/area yang diberi stabilo/highlighter. Warna stabilo apa pun dapat dianggap
   sebagai penanda baris yang perlu dicatat. Jangan menganggap stabilo berarti NG.
3. Untuk setiap baris yang ditandai, salin nama karakteristik/dimensi, standar atau ukuran
   pada gambar, toleransi yang tercetak, nilai aktual tulisan tangan, dan satuannya jika
   benar-benar terbaca.
4. Pertahankan tanda Ø, ±, titik/koma desimal, tanda plus/minus, rentang, dan satuan.
5. Jika tulisan atau angka tidak jelas, isi string "PERLU KONFIRMASI" pada bagian terkait
   dan jelaskan bagian yang tidak terbaca. Jangan menebak.
6. Jangan membuat kesimpulan status kesesuaian. Beri status "Belum ditentukan - verifikasi QC".
7. Jika tidak ada baris yang jelas ditandai, sebutkan bahwa baris stabilo tidak teridentifikasi.

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
Gunakan string kosong jika informasi tidak tersedia. Jangan menambah field di luar struktur.
"""

def extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise

if "qc_data" not in st.session_state:
    st.session_state.qc_data = None

if st.button("🔎 BACA SPK DENGAN GEMINI", type="primary", use_container_width=True):
    if not api_key:
        st.error("Masukkan Google Gemini API Key di sidebar terlebih dahulu.")
    elif uploaded is None:
        st.error("Unggah satu foto SPK terlebih dahulu.")
    else:
        try:
            image_bytes = uploaded.getvalue()
            pil_image = Image.open(BytesIO(image_bytes)).convert("RGB")
            # Resize very large photos to reduce upload size while retaining readable detail.
            max_side = 2200
            if max(pil_image.size) > max_side:
                pil_image.thumbnail((max_side, max_side))
            image_buffer = BytesIO()
            pil_image.save(image_buffer, format="JPEG", quality=92)
            client = genai.Client(api_key=api_key)
            with st.spinner("Gemini sedang membaca SPK. Mohon tunggu..."):
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        PROMPT,
                        types.Part.from_bytes(data=image_buffer.getvalue(), mime_type="image/jpeg")
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1,
                    ),
                )
            st.session_state.qc_data = extract_json(response.text)
            st.success("Pembacaan selesai. Periksa dan koreksi semua hasil sebelum digunakan.")
        except Exception as e:
            st.error("Pembacaan gagal. Periksa API key, kuota, koneksi internet, dan format foto.")
            st.code(str(e))

data = st.session_state.qc_data
if data:
    st.subheader("1. Periksa identitas SPK")
    meta = data.get("metadata", {})
    m1, m2 = st.columns(2)
    with m1:
        customer = st.text_input("Customer", value=meta.get("customer", ""))
        spk = st.text_input("Nomor SPK", value=meta.get("spk", ""))
        so = st.text_input("Nomor SO", value=meta.get("so", ""))
    with m2:
        part = st.text_input("Unit barang / Part", value=meta.get("part", ""))
        type_sn = st.text_input("Type / SN", value=meta.get("type_sn", ""))
        material = st.text_input("Material", value=meta.get("material", ""))

    st.subheader("2. Periksa hasil pembacaan dimensi yang ditandai")
    findings = data.get("findings", [])
    if findings:
        edited = []
        for i, item in enumerate(findings):
            with st.expander(f"Baris {i+1}: {item.get('karakteristik') or 'Karakteristik belum terbaca'}", expanded=True):
                karakteristik = st.text_input("Karakteristik / dimensi", value=item.get("karakteristik", ""), key=f"k{i}")
                standar = st.text_input("Standar / toleransi terbaca", value=item.get("standar", ""), key=f"s{i}")
                aktual = st.text_input("Aktual tulisan tangan", value=item.get("aktual", ""), key=f"a{i}")
                satuan = st.text_input("Satuan", value=item.get("satuan", ""), key=f"u{i}")
                catatan = st.text_area("Catatan keterbacaan", value=item.get("catatan_keterbacaan", ""), key=f"c{i}")
                edited.append({
                    "karakteristik": karakteristik,
                    "standar": standar,
                    "aktual": aktual,
                    "satuan": satuan,
                    "catatan_keterbacaan": catatan,
                })
    else:
        st.warning("AI tidak menemukan baris stabilo yang dapat diidentifikasi. Periksa foto secara manual.")
        edited = []

    notes = data.get("catatan_umum", [])
    notes_text = "\n".join(str(x) for x in notes)
    notes_text = st.text_area("Catatan umum dari pembacaan AI", value=notes_text)

    st.subheader("3. Laporan WhatsApp")
    lines = [
        "*LAPORAN HARIAN KETIDAKSESUAIAN*",
        "",
        f"Tanggal : {tanggal.strftime('%d-%m-%Y')}",
        f"* Customer : {customer}",
        f"* SPK : {spk}",
        f"* SO : {so}",
        f"* Unit Barang/Part : {part}",
    ]
    if type_sn:
        lines.append(f"* Type/SN : {type_sn}")
    if material:
        lines.append(f"* Material : {material}")
    if divisi:
        lines.append(f"* Divisi : {divisi}")
    lines += ["", "*Ketidaksesuaian / Dimensi yang ditandai:*"]
    if edited:
        for i, item in enumerate(edited, 1):
            lines.append(f"{i}. {item['karakteristik'] or 'PERLU KONFIRMASI'}")
            lines.append(f"   - Standar: {item['standar'] or 'PERLU KONFIRMASI'}")
            lines.append(f"   - Aktual: {item['aktual'] or 'PERLU KONFIRMASI'}")
            if item["satuan"]:
                lines.append(f"   - Satuan: {item['satuan']}")
            if item["catatan_keterbacaan"]:
                lines.append(f"   - Catatan: {item['catatan_keterbacaan']}")
    else:
        lines.append("Baris stabilo belum teridentifikasi; perlu pemeriksaan manual.")
    lines += [
        "",
        "* Status: Belum ditentukan - verifikasi QC",
        f"* Operator : {operator}",
        f"* Tambahan : {tambahan}",
    ]
    if notes_text.strip():
        lines += ["", "*Catatan pembacaan AI:*", notes_text.strip()]
    lines += ["", "_Mohon verifikasi angka, toleransi, dan status oleh petugas QC sebelum laporan dikirim._"]
    report = "\n".join(lines)
    st.text_area("Teks laporan (siap disalin ke WhatsApp)", value=report, height=420)
    st.download_button("Unduh laporan TXT", data=report, file_name="laporan_qc.txt", mime="text/plain")

st.divider()
st.caption(
    "AI QC Assistant hanya membantu pengetikan. AI dapat salah membaca tulisan tangan, "
    "dimensi, atau stabilo. Petugas QC wajib memverifikasi seluruh data. "
    "Hindari mengunggah dokumen rahasia tanpa persetujuan perusahaan."
)
