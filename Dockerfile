FROM prefecthq/prefect:3.4.11-python3.12-kubernetes

RUN pip install --no-cache-dir \
    pandas scikit-learn numpy scipy spacy matplotlib seaborn nltk bs4 prefect_aws \
    pycountry sentence-transformers hdbscan requests && \
    python3 -m spacy download en_core_web_sm openpyxl 
