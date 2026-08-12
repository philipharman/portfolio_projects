import streamlit as st
import numpy as np

def build_sdg_filters(sdgs, bills):

    c1, c2= st.columns([1,2])
    with c1:
        sdg_options = sdgs['sdg_number_title'].unique()
        selected_sdg = st.selectbox(label="SDG", options = sdg_options, index=0)
    with c2:
        theme_options = np.sort(sdgs[sdgs.sdg_number_title == selected_sdg]['theme'].unique())
        selected_themes = st.pills(label="Themes", options = theme_options, selection_mode = 'multi')  

    c1, c2= st.columns([1,2])
    with c1:
        legislative_bodies = bills['legislative_body'].unique()
        selected_legislative_bodies = st.multiselect(label="Legislative Bodies", options = legislative_bodies)
    with c2:
        sponsor_parties = np.sort(bills['sponsor_parties'].dropna().unique())
        selected_sponsor_parties = st.pills(label="Sponsor Parties", options = sponsor_parties, selection_mode = 'multi')

    return selected_sdg, selected_themes, selected_legislative_bodies, selected_sponsor_parties


def apply_sdg_filter(bills, selected_sdg, selected_themes, selected_legislative_bodies, selected_sponsor_parties):
    bills_filtered = bills.copy()
    if selected_sdg:
        bills_filtered = bills_filtered[bills_filtered.sdg_number_title == selected_sdg]
    if selected_themes:
        bills_filtered = bills_filtered[bills_filtered.sdg_theme.isin(set(selected_themes))]
    if selected_legislative_bodies:
        bills_filtered = bills_filtered[bills_filtered.legislative_body.isin(set(selected_legislative_bodies))]
    if selected_sponsor_parties:
        bills_filtered = bills_filtered[bills_filtered.sponsor_parties.isin(set(selected_sponsor_parties))]
    return bills_filtered.sort_values(by = 'sdg_confidence', ascending=False)


def render_tab(sdgs, bills):

    # Apply SDG 
    selected_sdg, selected_themes, selected_legislative_bodies, selected_sponsor_parties = build_sdg_filters(sdgs, bills)

    # Apply filter
    bills_filtered = apply_sdg_filter(bills, selected_sdg, selected_themes, selected_legislative_bodies, selected_sponsor_parties)
    st.dataframe(bills_filtered)

    st.write(len(bills_filtered))