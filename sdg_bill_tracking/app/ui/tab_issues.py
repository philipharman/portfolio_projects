import streamlit as st
import numpy as np


""""
################################################################
FILTERS
################################################################
"""

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
        legislative_bodies = list(bills['legislative_body_name'].unique())
        legislative_bodies.remove('US Congress')
        selected_legislative_bodies = st.multiselect(label="Legislative Bodies", options = ['US Congress'] + legislative_bodies)
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
        bills_filtered = bills_filtered[bills_filtered.legislative_body_name.isin(set(selected_legislative_bodies))]
    if selected_sponsor_parties:
        bills_filtered = bills_filtered[bills_filtered.sponsor_parties.isin(set(selected_sponsor_parties))]
    return bills_filtered.sort_values(by = 'sdg_confidence', ascending=False)



""""
################################################################
UI COMPONENTS
################################################################
"""

# Summary numbers
def display_summary_numbers(bills_filtered):
    total_bills = bills_filtered.bill_file.nunique()
    st.write(f"## {f'{total_bills:,}'} \n ##### Bills")

    total_legislators = bills_filtered.sponsors.explode().nunique()
    st.write(f"## {f'{total_legislators:,}'} \n ##### Legislators")
    
    total_bodies = bills_filtered.legislative_body.nunique()
    st.write(f"## {f'{total_bodies:,}'} \n ##### Legislative Bodies")


# Engaged legislators
def engaged_legislators(bills_filtered, top_n=4):

    st.write('## Top Sponsors')

    # Get top legislators by number of sponsored bills
    top_legislators = bills_filtered.explode('sponsors').groupby(['sponsors', 'legislative_body_name']).bill_file.nunique().reset_index().sort_values(by='bill_file', ascending=False).head(top_n)
    top_legislators_themes = bills_filtered.explode('sponsors').groupby(['sponsors', 'legislative_body_name', 'sdg_theme']).bill_file.nunique().reset_index().sort_values(by='bill_file', ascending=False)

    def render_legislator(row):

        # Field definitions
        sponsor = row['sponsors']
        legislative_body = row['legislative_body_name']
        total_bills = row['bill_file']
        top_themes = ' | '.join(top_legislators_themes[(top_legislators_themes['sponsors'] == sponsor) & (top_legislators_themes['legislative_body_name'] == legislative_body)].head(1).sdg_theme)

        # Display
        st.write(f"**{sponsor}**")
        st.write(legislative_body)
        st.write(f"Related bills: {total_bills}")
        st.write(f"Top issue: {top_themes}")

    for _, row in top_legislators.iterrows():
        render_legislator(row)



""""
################################################################
MAIN
################################################################
"""

def render_tab(sdgs, bills):

    # Build & apply filters
    selected_sdg, selected_themes, selected_legislative_bodies, selected_sponsor_parties = build_sdg_filters(sdgs, bills)
    bills_filtered = apply_sdg_filter(bills, selected_sdg, selected_themes, selected_legislative_bodies, selected_sponsor_parties)

    # Column displays
    cols = st.columns([1,3,2], border=True)
    with cols[0]:
        display_summary_numbers(bills_filtered)

    with cols[1]:

        st.write('## Recent Legislation')

        def show_recent_bills(bills, statuses, top_n = 3):
            status_bills = bills[bills['status'].isin(statuses)].sort_values(by = 'status_date', ascending=False).head(top_n)
            for bill in status_bills.itertuples():
                st.write(f"**{bill.bill_number}**: {bill.title} ({bill.legislative_body_name}) - {bill.status_date}")

        status_cols = st.columns(3)

        with status_cols[0]:
            st.warning('#### Newly Filed')
            statuses = ['Introduced']
            show_recent_bills(bills_filtered, statuses)

        with status_cols[1]:
            st.info('#### In Progress')
            statuses = ['Engrossed']
            show_recent_bills(bills_filtered, statuses)

        with status_cols[2]:
            st.success('#### Passed')
            statuses = ['Passed', 'Enrolled']
            show_recent_bills(bills_filtered, statuses)

    with cols[2]:
        engaged_legislators(bills_filtered, top_n=4)

    st.divider()
    st.dataframe(bills_filtered)