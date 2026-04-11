import streamlit as st
import pandas as pd
from detector import detect
from scorer import calculate_score, get_score_label
from suggester import generate_rewrite
from classifier import predict_label

st.set_page_config(page_title="Requirement Ambiguity Detector", layout="wide")

st.title("Requirement Ambiguity Detector")
st.write("Analyze software requirement statements and detect ambiguity using rules and machine learning.")

text = st.text_area("Enter requirement:", height=150)

if st.button("Analyze"):
    if text.strip():
        detected_items = detect(text)
        score = calculate_score(detected_items)
        score_label = get_score_label(score)
        rewritten = generate_rewrite(text, detected_items)
        ml_label = predict_label(text)

        st.subheader("Analysis Summary")
        st.write(f"**ML Predicted Class:** {ml_label}")
        st.write(f"**Clarity Score:** {score}/100")
        st.write(f"**Quality Label:** {score_label}")

        if detected_items:
            st.subheader("Detected Issues")
            df = pd.DataFrame(detected_items)
            st.dataframe(df, use_container_width=True)

            st.subheader("Suggested Rewrite")
            st.info(rewritten)
        else:
            st.success("No ambiguity detected.")
    else:
        st.warning("Please enter a requirement sentence.")