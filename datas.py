import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Energy Data Explorer", layout="wide")
st.title("🌍 Energy Supply Explorer & Sankey Generator")
st.markdown("Esplora i dati del *Statistical Review of World Energy* filtrando per nazioni o aggregati continentali/globali.")

# --- CARICAMENTO DATI ---
@st.cache_data
def load_data():
    file_path = "EI-Stats-Review-ALL-data (1).xlsx"
    # Il foglio 'TES by fuel' ha l'intestazione vera e propria alla riga 3 (skiprows=2)
    try:
        df = pd.read_excel(file_path, sheet_name='TES by fuel', skiprows=2)
    except Exception as e:
        st.error(f"Errore nel caricamento del file Excel: {e}")
        return pd.DataFrame()

    # Rinominiamo la prima colonna (che contiene i nomi dei paesi/regioni)
    df = df.rename(columns={df.columns[0]: 'Region'})
    
    # Pulizia: rimuoviamo righe totalmente vuote
    df = df.dropna(subset=['Region'])
    
    # Selezioniamo solo le colonne di interesse per l'anno più recente (le prime 7 dopo 'Region')
    # Struttura attesa delle colonne: 'Region', 'Oil', 'Natural Gas', 'Coal', 'Nuclear energy', 'Hydro electric', 'Renew- ables', 'Total'
    cols_to_keep = ['Region', 'Oil', 'Natural Gas', 'Coal', 'Nuclear energy', 'Hydro electric', 'Renew- ables', 'Total']
    
    # Intercettiamo le colonne corrette (ignorando l'anno precedente a destra)
    df_clean = df.loc[:, cols_to_keep].copy()
    
    # Pulizia nomi fonti
    df_clean = df_clean.rename(columns={'Renew- ables': 'Renewables', 'Nuclear energy': 'Nuclear', 'Hydro electric': 'Hydro'})
    
    # Sostituiamo eventuali caratteri non numerici (es '-' per valori nulli) con 0
    for col in df_clean.columns[1:]:
        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0)
        
    return df_clean

df = load_data()

if df.empty:
    st.stop()

# --- CLASSIFICAZIONE STATI VS AGGREGATI ---
# Gli aggregati nel report di solito iniziano con "Total " oppure sono nomi specifici di macro-regioni
aggregates_keywords = ['Total', 'World', 'Union', 'OECD', 'Non-OECD']
is_aggregate = df['Region'].str.contains('|'.join(aggregates_keywords), case=False, na=False)

df_aggregates = df[is_aggregate]
df_countries = df[~is_aggregate & (df['Region'] != 'Other')] # Filtriamo via anche voci generiche

# --- SIDEBAR: FILTRI ---
st.sidebar.header("Impostazioni")
view_type = st.sidebar.radio("Cosa vuoi analizzare?", ("Stati Singoli", "Aggregati / Continenti"))

if view_type == "Stati Singoli":
    data_to_use = df_countries
    selection_label = "Seleziona uno Stato:"
else:
    data_to_use = df_aggregates
    selection_label = "Seleziona un Aggregato:"

selected_region = st.sidebar.selectbox(selection_label, data_to_use['Region'].unique())

# --- MAIN CONTENT ---
st.header(f"Analisi per: {selected_region}")

# Estrazione dei dati per la regione selezionata
region_data = data_to_use[data_to_use['Region'] == selected_region].iloc[0]
sources = ['Oil', 'Natural Gas', 'Coal', 'Nuclear', 'Hydro', 'Renewables']
values = [region_data[src] for src in sources]

# Metriche Rapide
col1, col2 = st.columns(2)
col1.metric("Totale Fornitura Energetica (Exajoules)", round(region_data['Total'], 2))
col2.metric("Fonte Principale", sources[values.index(max(values))])

st.divider()

# --- SEZIONE VISUALIZZAZIONI ---
tab1, tab2 = st.tabs(["Diagramma Sankey", "Dati Tabellari (Raw)"])

with tab1:
    st.subheader("Flusso del Mix Energetico (Sankey Diagram)")
    st.markdown("Visualizza come le diverse fonti energetiche compongono il totale dell'energia per l'area selezionata.")
    
    # Preparazione dati per Plotly Sankey
    # Nodi: 0-5 sono le fonti, 6 è la regione di destinazione
    labels = sources + [selected_region]
    
    # Colori per i nodi (opzionale, ma rende tutto più carino)
    colors = ['#444444', '#1f77b4', '#8c564b', '#ff7f0e', '#17becf', '#2ca02c', '#d62728']
    
    source_indices = list(range(len(sources)))
    target_indices = [len(sources)] * len(sources) # Tutti puntano all'ultimo nodo (la regione)
    
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=labels,
            color=colors
        ),
        link=dict(
            source=source_indices,
            target=target_indices,
            value=values,
            # Aggiungiamo un hover text per mostrare i valori esatti nel flusso
            hovertemplate='%{source.label} -> %{target.label}<br>Valore: %{value:.2f} Exajoules<extra></extra>'
        )
    )])
    
    fig.update_layout(title_text=f"Mix Energetico: {selected_region}", font_size=12, height=500)
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Dati Tabellari Filtrati")
    st.dataframe(data_to_use.set_index('Region'), use_container_width=True)
    
st.markdown("---")
st.caption("Dati estratti dal file: `EI-Stats-Review-ALL-data (1).xlsx`")
