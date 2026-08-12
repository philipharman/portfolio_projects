import pandas as pd
import streamlit as st
import ast
import pycountry

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

    ### TEMPORARY - to move into bill_tagging flow later
    bodies = bills.legislative_body.dropna().unique()
    body_names = {}
    for body in bodies:
        if body != 'US':
            body_names[body] = pycountry.subdivisions.get(code=f'US-{body}').name
        else:
            body_names[body] = 'US Congress'
    bills['legislative_body_name'] = bills['legislative_body'].apply(lambda x: body_names.get(x))

    ### TEMPORARY - to move into bill_tagging flow later
    def categorize_sponsor_party(sponsors):
        parties = []
        for party in ['D', 'I', 'R', 'N']:
            party_sponsors = [sponsor for sponsor in sponsors if f'({party})' in sponsor]
            if party_sponsors:
                parties.append(party)
        parties = list(set(parties))
        if len(parties) > 1:
            return 'Bipartisan'
        if len(parties) == 1:
            parties_dict = {
                'D': 'Democratic',
                'I': 'Independent',
                'R': 'Republican',
                'N': 'Independent'
            }
            return parties_dict.get(parties[0])
    bills['sponsor_parties'] = bills['sponsors'].apply(categorize_sponsor_party)

    return bills