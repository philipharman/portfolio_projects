import streamlit as st
from data_loads import load_sdgs, load_format_tagged_bills
from ui import tab_home, tab_issues, tab_legislators

page_title = "SDG Policy Monitor"
st.set_page_config(
    page_title=page_title,
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)





def main():

    # Load data
    sdgs = load_sdgs()
    bills = load_format_tagged_bills()

    # Header
    st.header(page_title)
    st.caption("Tracking U.S. legislation through the lens of the UN Sustainable Development Goals")

    # Tabs
    tab_names = ['Home', 'Explore Issues', 'Explore Legislators']
    tabs = st.tabs(tab_names)
    with tabs[0]:
        tab_home.render_tab(sdgs)
    with tabs[1]:
        tab_issues.render_tab(sdgs, bills)
    with tabs[2]:
        pass




if __name__ == "__main__":
    main()
