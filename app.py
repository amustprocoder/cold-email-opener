"""Streamlit front end for the same code as opener.py:  streamlit run app.py"""

import os

import pandas as pd
import streamlit as st

from opener import run
from src.cost import LOG

st.set_page_config(page_title="Cold-email opener", page_icon="✉️")
st.title("Website → 3-line cold-email opener")
st.caption("Paste a company's website. The tool reads the site, drafts three lines for the founder, and shows the "
           "quote behind each line so you can check it before you send anything. Every run is costed.")

# Streamlit Cloud keeps the key in st.secrets; local runs use the environment variable.
try:
    if "GEMINI_API_KEY" in st.secrets and not os.environ.get("GEMINI_API_KEY"):
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

SAMPLES = ["plausible.io", "linear.app", "buttondown.com"]
if "url" not in st.session_state:
    st.session_state.url = ""

st.write("Try one:")
cols = st.columns(len(SAMPLES))
for col, s in zip(cols, SAMPLES):
    if col.button(s, use_container_width=True):
        st.session_state.url = s
        st.session_state.go = True

url = st.text_input("Or type any website", key="url", placeholder="plausible.io")
go = st.button("Draft opener", type="primary") or st.session_state.pop("go", False)

if go and st.session_state.url:
    with st.spinner("Reading the site and drafting..."):
        try:
            out = run(st.session_state.url)
        except RuntimeError as e:
            st.error(str(e))
            st.stop()
    st.subheader(out.get("company") or out["site"]["domain"])
    if out.get("founder_hint"):
        st.write(f"Founder named on site: **{out['founder_hint']}**")
    for c in out["checks"]:
        if c["grounded"] is False:
            st.warning(f"{c['line']}\n\nUnverified: the quote was not found on the page. Check before sending.")
        else:
            st.write(c["line"])
    with st.expander("Evidence from the site", expanded=True):
        for i, c in enumerate(out["checks"], 1):
            st.write(f"{i}. {c['evidence'] if c['kind'] == 'fact' else '(bridge line about us, no site fact)'}")
        if out.get("note"):
            st.write(f"Note: {out['note']}")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Cost", f"${out['cost_usd']:.5f}")
    m2.metric("Tokens in / out", f"{out['tokens_in']} / {out['tokens_out']}")
    m3.metric("Seconds", out["seconds"])
    m4.metric("Verified", f"{out['grounded']}/2")
    st.caption(f"{out['model']} · text from {out['site']['source']} ({out['site']['chars']} chars) · "
               f"at this cost, 1,000 runs a day is about ${out['cost_usd'] * 1000:.2f} a day")

with st.expander("Run log (runs.csv): every call, costed"):
    if os.path.exists(LOG):
        df = pd.read_csv(LOG)
        st.dataframe(df.iloc[::-1], use_container_width=True, hide_index=True)
        st.caption(f"{len(df)} runs · total ${df['cost_usd'].sum():.4f} · "
                   f"average ${df['cost_usd'].mean():.5f} per run · average {df['seconds'].mean():.1f} s")
    else:
        st.write("No runs yet.")
