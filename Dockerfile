FROM python:3.12-slim

RUN pip install --no-cache-dir \
    pandas scikit-learn numpy scipy spacy matplotlib seaborn nltk bs4 prefect_aws \
    pycountry sentence-transformers hdbscan requests && \
    python3 -m spacy download en_core_web_sm openpyxl 
