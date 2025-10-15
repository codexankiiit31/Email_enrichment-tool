import streamlit as st
import pandas as pd
from email_enricher1 import EnrichmentEngine
from io import BytesIO
import os
import time
import logging

# -----------------------------
# Ensure log folder exists
# -----------------------------
LOG_FOLDER = "log"
os.makedirs(LOG_FOLDER, exist_ok=True)
LOG_FILE = os.path.join(LOG_FOLDER, "enrichment_app.log")

# -----------------------------
# Logging Configuration
# -----------------------------
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Console logging
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
console_handler.setFormatter(formatter)
logging.getLogger("").addHandler(console_handler)
logging.info("📌 Application started. Logs are saved in 'log/enrichment_app.log'")

# -----------------------------
# Page Config
# -----------------------------
st.set_page_config(page_title="📧 Email Enrichment Tool", layout="wide")
st.title("📧 Email → Company / Sector Identification Tool")
st.caption("Automatically enrich emails to identify **company**, **university**, **person name**, and **business sector**.")

# -----------------------------
# Initialize Enrichment Engine
# -----------------------------
@st.cache_resource(show_spinner=False)
def load_engine():
    logging.info("Loading EnrichmentEngine...")
    engine = EnrichmentEngine()
    logging.info("EnrichmentEngine loaded successfully.")
    return engine

engine = load_engine()
os.makedirs("output", exist_ok=True)

# -----------------------------
# Tabs: Single vs Batch
# -----------------------------
tab1, tab2 = st.tabs(["✉️ Single Email", "📂 Batch Upload"])

# ====================================================
# SINGLE EMAIL ENRICHMENT
# ====================================================
with tab1:
    st.subheader("Enrich a Single Email")
    with st.form("single_email_form"):
        single_email = st.text_input("Enter Email Address", placeholder="e.g. john.doe@company.com")
        submitted = st.form_submit_button("Enrich Email")
        
    if submitted:
        clean_email = single_email.strip()
        if not clean_email:
            st.warning("⚠️ Please enter a valid email address.")
            logging.warning("Empty email input.")
        else:
            logging.info(f"Starting enrichment for {clean_email}")
            with st.spinner(f"🔍 Enriching `{clean_email}`..."):
                result = engine.enrich_email(clean_email)
            
            if "error" in result:
                st.error(result["error"])
                logging.error(f"Error enriching {clean_email}: {result['error']}")
            else:
                st.success("✅ Enrichment Complete!")
               
                st.dataframe(pd.DataFrame([result]), use_container_width=True, height=100)
                
                # Prepare Excel download
                output = BytesIO()
                pd.DataFrame([result]).to_excel(output, index=False, engine='openpyxl')
                output.seek(0)
                download_name = f"enriched_{clean_email.replace('@','_').replace('.','_')}.xlsx"
                st.download_button(
                    label="⬇️ Download Enriched Result (Excel)",
                    data=output,
                    file_name=download_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                logging.info(f"Excel file prepared for {clean_email}.")

# ====================================================
# BATCH EMAIL ENRICHMENT
# ====================================================
with tab2:
    st.subheader("Bulk Email Enrichment")
    st.caption("Upload a CSV or Excel file with a column named **`Email`**.")
    uploaded_file = st.file_uploader("Choose a CSV or Excel file", type=["csv", "xlsx"])
    
    if uploaded_file:
        try:
            if uploaded_file.name.endswith(".xlsx"):
                df = pd.read_excel(uploaded_file)
            else:
                df = pd.read_csv(uploaded_file)
            logging.info(f"File read successfully: {uploaded_file.name}")
        except Exception as e:
            st.error(f"❌ Failed to read file: {e}")
            logging.error(f"Failed to read uploaded file {uploaded_file.name}: {e}")
            st.stop()
        
        if "Email" not in df.columns:
            st.error("❌ File must have a column named 'Email'.")
        else:
            emails = df["Email"].dropna().astype(str).str.strip()
            total = len(emails)
            if total == 0:
                st.warning("The 'Email' column is empty.")
            else:
                st.info(f"📬 Found **{total}** emails. Enrichment will start below.")

                # Progress and metrics
                progress_bar = st.progress(0)
                status_text = st.empty()
                results = []
                start_time = time.time()

                for idx, email in enumerate(emails):
                    try:
                        res = engine.enrich_email(email)
                    except Exception as e:
                        res = {"email": email, "error": str(e)}
                    results.append(res)
                    
                    progress_bar.progress((idx + 1) / total)
                    status_text.text(f"🔄 Processing {idx + 1}/{total}: {email}")
                
                end_time = time.time()
                elapsed = end_time - start_time

                st.success(f"✅ Batch Enrichment Complete in {elapsed:.1f} seconds!")

                results_df = pd.DataFrame(results)
                with st.expander("See Full Results"):
                    st.dataframe(results_df, use_container_width=True, height=400)

                # Summary metrics
                success_count = sum(1 for r in results if "error" not in r)
                fail_count = total - success_count
                col1, col2 = st.columns(2)
                col1.metric("✅ Success", success_count)
                col2.metric("❌ Failed", fail_count)

                # Download Excel
                output = BytesIO()
                results_df.to_excel(output, index=False, engine='openpyxl')
                output.seek(0)
                st.download_button(
                    label="⬇️ Download Enriched Results (Excel)",
                    data=output,
                    file_name="enriched_emails.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                logging.info("Batch Excel file prepared for download.")
