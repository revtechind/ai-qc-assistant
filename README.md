# AI QC Assistant - Gemini API

Aplikasi Streamlit untuk membantu membaca foto SPK dan menyusun laporan WhatsApp.

## Menjalankan
1. Install dependencies: `pip install -r requirements.txt`
2. Jalankan: `streamlit run app.py`
3. Masukkan Gemini API key pada sidebar.

## API Key
Buat API key di https://aistudio.google.com/app/apikey
Jangan commit API key ke GitHub. Untuk deployment Streamlit, simpan sebagai
`GEMINI_API_KEY` pada App Settings > Secrets, atau masukkan melalui sidebar.

## Catatan
Gemini API free tier memiliki batas kuota dan kebijakan data tersendiri. Jangan
unggah dokumen rahasia perusahaan tanpa persetujuan. Semua hasil AI wajib diverifikasi QC.
