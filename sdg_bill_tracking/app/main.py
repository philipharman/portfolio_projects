import pandas as pd
import streamlit as st
import ast

@st.cache_data(show_spinner=False)
def load_sdgs():
    sdgs = pd.read_csv('https://portfolio-project-files.s3.eu-west-1.amazonaws.com/sdg-bill-tracking/sdg_indicators_corpus.csv')
    sdg_dict = sdgs[['SDG No.', 'SDG']].drop_duplicates().set_index('SDG No.').to_dict()['SDG']
    target_dict = sdgs[['Target No.', 'Target']].drop_duplicates().set_index('Target No.').to_dict()['Target']
    return sdgs, sdg_dict, target_dict


@st.cache_data(show_spinner=False)
def load_format_tagged_bills(sdg_dict, target_dict):
    bills = pd.read_csv('https://portfolio-project-files.s3.eu-west-1.amazonaws.com/sdg-bill-tracking/tagged_bills.csv')
    bills['sponsors'] = bills['sponsors'].apply(lambda x: ast.literal_eval(x))
    bills['tagged_sdg_text'] = bills.tagged_sdg.apply(lambda x: [sdg_dict[i] for i in x] if type(x) is list else None)
    bills['tagged_target_text'] = bills.tagged_target.apply(lambda x: [target_dict[i] for i in x] if type(x) is list else None)
    return bills


def build_sdg_filters(sdgs):
    sdg_options = sdgs['SDG'].unique()
    target_options = sdgs['Target'].unique()
    c1, c2 = st.columns(2)
    with c1:
        selected_sdgs = st.multiselect(label="Select SDG(s):", options = sdg_options)
    with c2:
        if selected_sdgs:
            target_options = sdgs[sdgs.SDG.isin(selected_sdgs)]['Target'].unique()
        selected_targets = st.multiselect(label="Select Target(s):", options = target_options)
    return selected_sdgs, selected_targets


def apply_sdg_filter(bills, selected_sdgs, selected_targets):
    bills_filtered = bills.copy()
    if selected_sdgs:
        bills_filtered = bills_filtered[bills_filtered.tagged_sdg_text.apply(lambda x: len(set(x) & set(selected_sdgs)) > 0)]
    if selected_targets:
        bills_filtered = bills_filtered[bills_filtered.tagged_target_text.apply(lambda x: len(set(x) & set(selected_targets)) > 0)]

    return bills_filtered


def main():

    # Load data
    sdgs, sdg_dict, target_dict = load_sdgs()
    bills = load_format_tagged_bills(sdg_dict, target_dict)

    # Header
    st.header('SDG Tracking')
    st.dataframe(sdgs)

    # SDG / Target filter
    selected_sdgs, selected_targets = build_sdg_filters(sdgs)

    # Apply filter
    bills_filtered = apply_sdg_filter(bills, selected_sdgs, selected_targets)
    st.dataframe(bills_filtered)



if __name__ == "__main__":
    main()
