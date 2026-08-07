import pandas as pd
import streamlit as st
import ast

@st.cache_data(show_spinner=False)
def load_sdgs():
    sdgs = pd.read_csv('https://portfolio-project-files.s3.eu-west-1.amazonaws.com/sdg-bill-tracking/sdg_theme_corpus.csv')
    sdgs['sdg_number_title'] = sdgs.apply(lambda row: ' - '.join([str(row['sdg_number']), row['sdg_title']]), axis=1)
    return sdgs


@st.cache_data(show_spinner=False)
def load_format_tagged_bills():
    bills = pd.read_csv('https://portfolio-project-files.s3.eu-west-1.amazonaws.com/sdg-bill-tracking/tagged_bills.csv')
    bills['sponsors'] = bills['sponsors'].apply(lambda x: ast.literal_eval(x))
    bills['sdg_number_title'] = bills.apply(lambda row: ' - '.join([str(int(row['sdg_number'])), row['sdg_title']]) if type(row['sdg_title']) is str else None, axis=1)
    return bills


def build_sdg_filters(sdgs):
    sdg_options = sdgs['sdg_number_title'].unique()
    theme_options = sdgs['theme'].unique()
    c1, c2 = st.columns(2)
    with c1:
        selected_sdgs = st.multiselect(label="Select SDG(s):", options = sdg_options)
    with c2:
        if selected_sdgs:
            theme_options = sdgs[sdgs.sdg_number_title.isin(selected_sdgs)]['theme'].unique()
        selected_themes = st.multiselect(label="Select theme(s):", options = theme_options)
    return selected_sdgs, selected_themes


def apply_sdg_filter(bills, selected_sdgs, selected_themes):
    bills_filtered = bills.copy()
    if selected_sdgs:
        bills_filtered = bills_filtered[bills_filtered.sdg_number_title.isin(set(selected_sdgs))]
    if selected_themes:
        bills_filtered = bills_filtered[bills_filtered.sdg_theme.isin(set(selected_themes))]

    return bills_filtered


def main():

    # Load data
    sdgs = load_sdgs()
    bills = load_format_tagged_bills()

    # Header
    st.header('SDG Tracking')
    st.dataframe(sdgs)

    # SDG / theme filter
    selected_sdgs, selected_themes = build_sdg_filters(sdgs)

    # Apply filter
    bills_filtered = apply_sdg_filter(bills, selected_sdgs, selected_themes)
    st.dataframe(bills_filtered)



if __name__ == "__main__":
    main()
