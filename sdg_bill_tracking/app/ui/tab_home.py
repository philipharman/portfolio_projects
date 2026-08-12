import streamlit as st
import numpy as np


def render_tab(sdgs):
    temp = sdgs.groupby(['sdg_number_title', 'sdg_number']).theme.aggregate(list).reset_index().sort_values(by='sdg_number')[['sdg_number_title', 'theme']]
    temp.theme = temp.theme.apply(lambda x: ' - ' + '\n - '.join(np.sort(list(set(x)))))
    temp.columns = ['SDG', 'Issue Areas']
    st.table(temp[['SDG', 'Issue Areas']])