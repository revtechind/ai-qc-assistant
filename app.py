import os, io, base64, json, re
from datetime import date
import streamlit as st
import pandas as pd
from PIL import Image
from openai import OpenAI

st.set_page_config(page_title="AI QC Assistant", page_icon="🔎", layout="centered")

st.title("🔎 AI QC Assistant")
st.caption("Foto satu SPK → AI membaca data dan baris stabilo → teks laporan siap disalin ke WhatsApp.")

with st.sidebar:
    st.header("Pengaturan")
    api_key = st.text_input("OpenAI API key", type="password", value=os.getenv("OPENAI_API_KEY", ""))
    model = st.text_input("Model Vision", value=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    st.caption("API key digunakan untuk mengirim foto ke layanan AI. Pastikan kebijakan perusahaan mengizinkan penggunaan layanan eksternal.")

st.subheader("1. Foto SPK")
spk_file = st.file_uploader("Unggah foto SPK yang sudah berisi hasil ukur dan stabilo", type=["jpg", "jpeg", "png", "webp"])

st.subheader("2. Informasi tambahan")
left, right = st.columns(2)
with left:
    report_date = st.text_input("Tanggal laporan", value=date.today().strftime("%d-%m-%Y"))
    division = st.text_input("Divisi", placeholder="Contoh: MILLING")
with right:
    operator = st.text_input("Operator", placeholder="Nama operator jika diketahui")
    additional = st.text_input("Tambahan / tindak lanjut", placeholder="Contoh: Diisi PPIC")

st.caption("Informasi yang tidak tersedia di SPK tidak akan ditebak. Anda dapat mengisinya setelah AI selesai membaca.")

if "qc_result" not in st.session_state:
    st.session_state.qc_result = None

def to_data_url(upload):
    img = Image.open(io.BytesIO(upload.getvalue())).convert("RGB")
    img.thumbnail((2600, 2600))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=94)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

def analyze(upload):
    client = OpenAI(api_key=api_key)
    instruction = r"""
Anda adalah asisten pengetikan laporan ketidaksesuaian QC. Tugas Anda menyalin informasi dari SATU foto SPK/drawing yang sudah memuat hasil ukur. Foto dapat miring, berisi cetakan teknik dan tulisan tangan, serta beberapa warna stabilo.

ATURAN:
1. Baca identitas SPK dan drawing yang benar-benar terlihat. Jangan menggabungkan informasi dari contoh lain.
2. Deteksi SEMUA baris/dimensi/angka yang ditandai stabilo warna apa pun. Stabilo adalah penanda temuan yang perlu dimasukkan ke laporan, bukan bukti otomatis bahwa ukurannya NG.
3. Untuk setiap penandaan, ambil nama/jenis dimensi, nilai drawing/standar yang tertulis pada drawing, dan angka aktual tulisan tangan yang berkaitan. Pertahankan tanda desimal, Ø, ±, rentang, dan satuan.
4. Jangan menebak angka yang buram, tertutup stabilo, atau ambigu. Isi null dan jelaskan bagian yang perlu dikonfirmasi.
5. Jangan menghitung atau mengarang toleransi jika tidak tercetak jelas. Jangan menyatakan “melebihi toleransi” kecuali batas toleransi dapat dibaca dengan jelas.
6. Jika angka aktual menunjukkan rentang, pertahankan sebagai teks rentang, jangan mengubahnya menjadi satu angka.
7. Ambil customer, nomor SPK, SO, nama part/unit, type/SN, material, dan informasi relevan lain jika terlihat.
8. Kategori laporan gunakan “Dimensi” jika temuan berupa ukuran; jika tidak jelas, null.
9. Keluaran hanya JSON valid dengan skema:
{
 "tanggal_dokumen": null,
 "customer": null,
 "nomor_spk": null,
 "nomor_so": null,
 "nama_part": null,
 "type_sn": null,
 "divisi": null,
 "material": null,
 "temuan": [
   {"uraian": null, "drawing": null, "aktual": null, "satuan": null,
    "teks_laporan": null, "confidence": "tinggi|sedang|rendah",
    "perlu_konfirmasi": false, "catatan": null}
 ],
 "kategori": null,
 "operator": null,
 "catatan_tambahan": null,
 "informasi_lain": null
}
Field teks_laporan berisi kalimat singkat Bahasa Indonesia berdasarkan data yang terbaca, tetapi jangan menyimpulkan penyebab kerusakan.
Jika tidak ada stabilo yang dapat dikenali, temuan harus array kosong.
"""
    response = client.responses.create(
        model=model,
        input=[{"role":"user","content":[
            {"type":"input_text","text":instruction + "\nBaca foto SPK berikut."},
            {"type":"input_image","image_url":to_data_url(upload),"detail":"high"}
        ]}],
        store=False
    )
    raw = response.output_text.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I)
    return json.loads(raw)

if st.button("🔍 BACA SPK DENGAN AI", type="primary", use_container_width=True, disabled=spk_file is None):
    if not api_key:
        st.error("Masukkan OpenAI API key di sidebar terlebih dahulu.")
    else:
        try:
            with st.spinner("AI sedang membaca SPK dan menelusuri baris yang diberi stabilo..."):
                st.session_state.qc_result = analyze(spk_file)
            st.success("Pembacaan selesai. Periksa seluruh hasil sebelum membuat laporan.")
        except Exception as exc:
            st.error(f"Pembacaan gagal: {exc}")

data = st.session_state.qc_result
if data:
    st.divider()
    st.subheader("3. Periksa dan koreksi identitas")
    fields = [
        ("customer","Customer"),("nomor_spk","Nomor SPK"),("nomor_so","SO"),
        ("nama_part","Unit Barang/Part"),("type_sn","Type/SN"),
        ("material","Material")
    ]
    edited = {}
    cols = st.columns(2)
    for i,(key,label) in enumerate(fields):
        with cols[i%2]:
            edited[key] = st.text_input(label, value=str(data.get(key) or ""), key="field_"+key)
    edited["divisi"] = st.text_input("Divisi", value=division or str(data.get("divisi") or ""), key="field_divisi")
    edited["tanggal"] = st.text_input("Tanggal laporan", value=report_date, key="field_tanggal")
    edited["operator"] = st.text_input("Operator", value=operator or str(data.get("operator") or ""), key="field_operator")
    edited["tambahan"] = st.text_input("Tambahan", value=additional or str(data.get("catatan_tambahan") or ""), key="field_tambahan")

    st.subheader("4. Periksa hasil pembacaan dimensi stabilo")
    st.caption("Edit langsung jika tulisan tangan atau angka drawing kurang tepat. Hapus baris yang bukan temuan.")
    rows = data.get("temuan") or []
    df = pd.DataFrame(rows, columns=["uraian","drawing","aktual","satuan","teks_laporan","confidence","perlu_konfirmasi","catatan"])
    if df.empty:
        st.warning("AI belum menemukan baris stabilo. Periksa foto atau ambil ulang dengan pencahayaan dan fokus yang lebih baik.")
    else:
        edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic", key="findings_editor")
    kategori_default = data.get("kategori") or ("Dimensi" if rows else "")
    kategori = st.text_input("Kategori (Visual/Dimensi/Fungsi)", value=kategori_default)
    st.caption("Jika ada nilai dengan confidence rendah atau perlu_konfirmasi, pastikan dikoreksi sebelum laporan dikirim.")

    if not df.empty:
        final_rows = edited_df.to_dict(orient="records")
    else:
        final_rows = []

    def clean(v):
        if v is None: return ""
        try:
            if pd.isna(v): return ""
        except Exception: pass
        return str(v).strip()

    lines = [
        "*LAPORAN HARIAN KETIDAKSESUAIAN*",
        f"Tanggal : {clean(edited['tanggal'])}",
        "",
        f"* Customer : {clean(edited['customer']) or '-'}",
        f"* SPK : {clean(edited['nomor_spk']) or '-'}",
        f"* SO : {clean(edited['nomor_so']) or '-'}",
        f"* Unit Barang/Part : {clean(edited['nama_part']) or '-'}",
    ]
    if clean(edited["type_sn"]): lines.append(f"* Type/SN : {clean(edited['type_sn'])}")
    if clean(edited["material"]): lines.append(f"* Material : {clean(edited['material'])}")
    if clean(edited["divisi"]): lines.append(f"* Divisi : {clean(edited['divisi'])}")
    lines.append("* Ketidaksesuaian:")
    if final_rows:
        for row in final_rows:
            desc = clean(row.get("teks_laporan"))
            if not desc:
                uraian = clean(row.get("uraian")) or "Dimensi"
                drawing = clean(row.get("drawing")) or "belum terbaca"
                aktual = clean(row.get("aktual")) or "belum terbaca"
                satuan = clean(row.get("satuan"))
                desc = f"{uraian.upper()} (DRAWING {drawing} ; AKTUAL {aktual}{(' '+satuan) if satuan else ''})"
            lines.append("  " + desc)
    else:
        lines.append("  [Tidak ada baris stabilo yang terbaca — periksa SPK]")
    lines += [
        f"* Kategori (Visual/Dimensi/Fungsi) : {clean(kategori) or '-'}",
        f"* Operator : {clean(edited['operator']) or '-'}",
        f"* Tambahan : {clean(edited['tambahan']) or '-'}"
    ]
    report_text = "\n".join(lines)

    st.divider()
    st.subheader("5. Laporan siap disalin ke WhatsApp")
    st.text_area("Preview laporan", value=report_text, height=360)
    st.code(report_text, language=None)
    st.download_button("⬇️ Unduh teks laporan (.txt)", data=report_text.encode("utf-8"),
                       file_name=f"Laporan_Ketidaksesuaian_{re.sub(r'[^A-Za-z0-9_-]+','_',edited['nomor_spk'] or 'SPK')}.txt",
                       mime="text/plain", use_container_width=True)
    st.success("Salin teks dari kotak laporan di atas, lalu tempelkan ke WhatsApp. Periksa kembali angka dan identitas sebelum dikirim.")

st.divider()
st.caption("AI QC Assistant membantu pengetikan, bukan menggantikan pemeriksaan atau keputusan QC. Data yang tidak terbaca harus dikonfirmasi oleh petugas. Jangan unggah dokumen rahasia tanpa izin perusahaan.")
