import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# --- 1. CONFIGURAZIONE PAGINA E INTESTAZIONE ---
st.set_page_config(page_title="Energy Data Explorer", layout="wide")
st.title("🌍 Energy Supply & Ember-Style Sankey")

st.markdown(
    "<div style='font-size:0.8em; color:#888; margin-top:-8px; margin-bottom:8px;'>"
    "Sviluppato da <b>Matteo De Piccoli</b> e <b>cs1bc</b><br>"
    "Autore di <a href='https://www.peoplepub.it/pagina-prodotto/avete-rotto-l-atomo' "
    "target='_blank' style='color:#888;'><i>Avete rotto l'atomo</i></a><br>"
    "<a href='https://unbelclima.it/' target='_blank' "
    "style='color:#16A34A; text-decoration:none;'>🌍 Ci Sarà un Bel Clima</a>"
    "</div>",
    unsafe_allow_html=True
)
st.markdown("Esplora i dati energetici analizzando i **flussi** di transizione, l'**elettrificazione** e la termodinamica (**Sankey**). Ispirato al framework *Ember - Age of Electricity*.")

# --- 2. FUNZIONI DI CARICAMENTO DATI ---
@st.cache_data
def load_data():
    file_path = "EI-Stats-Review-ALL-data (1).xlsx"
    
    # Helper generico per estrarre la regione
    def get_basic_sheet(sheet_name, cols_indices, col_names):
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name, skiprows=2)
            df = df.iloc[:, cols_indices].copy()
            df.columns = col_names
            df = df.dropna(subset=['Region'])
            for col in df.columns[1:]:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        except: return pd.DataFrame()

    # Helper per estrarre serie storiche
    def get_historical_sheet(sheet_name):
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name, skiprows=2)
            df = df.rename(columns={df.columns[0]: 'Region'})
            df = df.dropna(subset=['Region'])
            # Tiene solo le colonne che sono anni (interi o float > 1900)
            year_cols = [c for c in df.columns if isinstance(c, (int, float)) and 1900 < c < 2100]
            df_melt = df.melt(id_vars=['Region'], value_vars=year_cols, var_name='Year', value_name='Value')
            df_melt['Value'] = pd.to_numeric(df_melt['Value'], errors='coerce').fillna(0)
            return df_melt
        except: return pd.DataFrame()

    # 1. Energia Primaria (TES by fuel) - Estraiamo sia 2024 che 2025 per calcolare i flussi
    df_tes_flows = pd.DataFrame()
    try:
        df_tes_raw = pd.read_excel(file_path, sheet_name='TES by fuel', skiprows=2)
        cols_24 = [0, 1, 2, 3, 4, 5, 6, 7]
        cols_25 = [0, 8, 9, 10, 11, 12, 13, 14]
        names = ['Region', 'Oil', 'Natural Gas', 'Coal', 'Nuclear', 'Hydro', 'Renewables', 'Total']
        
        df_24 = df_tes_raw.iloc[:, cols_24].copy()
        df_24.columns = names
        df_24['Year'] = 2024
        
        df_25 = df_tes_raw.iloc[:, cols_25].copy()
        df_25.columns = names
        df_25['Year'] = 2025
        
        df_tes_flows = pd.concat([df_24, df_25]).dropna(subset=['Region'])
        for col in names[1:]:
            df_tes_flows[col] = pd.to_numeric(df_tes_flows[col], errors='coerce').fillna(0)
    except Exception as e: st.error(f"Errore TES by fuel: {e}")
    
    # 2. Generazione Elettrica (2025)
    df_elec = get_basic_sheet('Elec generation by fuel', [0, 8, 9, 10, 11, 12, 13, 14, 15], 
                              ['Region', 'Oil', 'Natural Gas', 'Coal', 'Nuclear', 'Hydro', 'Renewables', 'Other', 'Total'])
    
    # 3. Serie Storiche
    df_tes_hist = get_historical_sheet('Total Energy Supply (TES) -EJ')
    df_elec_hist = get_historical_sheet('Electricity Generation - TWh')
    df_dc_hist = get_historical_sheet('Data Centre Demand') # Nuova metrica
    
    return df_tes_flows, df_elec, df_tes_hist, df_elec_hist, df_dc_hist

df_tes_flows, df_elec, df_tes_hist, df_elec_hist, df_dc_hist = load_data()
if df_tes_flows.empty:
    st.stop()

# Classificazione
aggregates_keywords = ['Total', 'World', 'Union', 'OECD', 'Non-OECD']
is_aggregate = df_tes_flows['Region'].str.contains('|'.join(aggregates_keywords), case=False, na=False)

# --- 3. SIDEBAR E FILTRI ---
st.sidebar.header("Impostazioni")
view_type = st.sidebar.radio("Analisi:", ("Stati Singoli", "Aggregati / Continenti"))

regions_list = df_tes_flows[~is_aggregate]['Region'].unique() if view_type == "Stati Singoli" else df_tes_flows[is_aggregate]['Region'].unique()
selected_region = st.sidebar.selectbox("Seleziona Area:", sorted([r for r in regions_list if r != 'Other']))

# --- 4. PREPARAZIONE DATI REGIONALI ---
# Prendiamo i dati del 2025 come "correnti"
reg_tes_25 = df_tes_flows[(df_tes_flows['Region'] == selected_region) & (df_tes_flows['Year'] == 2025)].iloc[0]
reg_tes_24 = df_tes_flows[(df_tes_flows['Region'] == selected_region) & (df_tes_flows['Year'] == 2024)].iloc[0]
reg_elec = df_elec[df_elec['Region'] == selected_region]
reg_elec = reg_elec.iloc[0] if not reg_elec.empty else None

primary_total = reg_tes_25['Total']
elec_total_twh = reg_elec['Total'] if reg_elec is not None else 0
elec_total_ej = elec_total_twh * 0.0036
rinnovabili_twh = (reg_elec['Hydro'] + reg_elec['Renewables']) if reg_elec is not None else 0
quota_rinnovabili = (rinnovabili_twh / elec_total_twh * 100) if elec_total_twh > 0 else 0
eff_sistema = (elec_total_ej / primary_total * 100) if primary_total > 0 else 0

st.header(f"Dashboard: {selected_region}")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Energia Primaria", f"{primary_total:.2f} EJ")
m2.metric("Generazione Elettrica", f"{elec_total_twh:.1f} TWh")
m3.metric("Copertura Rinnovabile", f"{quota_rinnovabili:.1f} %")
m4.metric("Indice di Elettrificazione", f"{eff_sistema:.1f} %")

st.divider()

# --- 5. TABS ---
tab_trend, tab_charts, tab_sankey = st.tabs(["📈 Trend e Transizione (Novità)", "📊 Statistiche 2025", "🔄 Sankey Termodinamico"])

# --- TAB 1: TREND STORICI E FLUSSI ---
with tab_trend:
    st.subheader("La transizione nei Flussi (Delta 2024 vs 2025)")
    st.markdown("Il framework di Ember si concentra sui *flussi* (chi cattura la nuova domanda) anziché sugli stock. Questo grafico mostra la variazione netta anno su anno.")
    
    # Calcolo Delta
    sources = ['Oil', 'Natural Gas', 'Coal', 'Nuclear', 'Hydro', 'Renewables']
    deltas = []
    for src in sources:
        delta = reg_tes_25[src] - reg_tes_24[src]
        deltas.append({'Fonte': src, 'Variazione (EJ)': delta})
    df_deltas = pd.DataFrame(deltas)
    
    # Colori per i delta: verde se rinnovabili positive, rosso/grigio per fossili
    fig_delta = px.bar(df_deltas, x='Fonte', y='Variazione (EJ)', color='Fonte',
                       title=f"Variazione Fornitura Energetica 2024-2025 ({selected_region})",
                       color_discrete_sequence=px.colors.qualitative.Prism)
    st.plotly_chart(fig_delta, use_container_width=True)

    colA, colB = st.columns(2)
    
    with colA:
        st.subheader("Elettrificazione Storica")
        st.markdown("Quota di energia elettrica generata rispetto all'energia primaria totale.")
        reg_tes_h = df_tes_hist[df_tes_hist['Region'] == selected_region]
        reg_elec_h = df_elec_hist[df_elec_hist['Region'] == selected_region]
        
        if not reg_tes_h.empty and not reg_elec_h.empty:
            merged_h = pd.merge(reg_tes_h, reg_elec_h, on='Year', suffixes=('_TES', '_ELEC'))
            # Converto TWh in EJ (*0.0036) e calcolo la percentuale
            merged_h['Elec_Share_%'] = (merged_h['Value_ELEC'] * 0.0036) / merged_h['Value_TES'] * 100
            
            fig_elec_hist = px.line(merged_h, x='Year', y='Elec_Share_%', title="Tasso di Elettrificazione (%)")
            fig_elec_hist.update_traces(line_color='#16A34A', line_width=3)
            st.plotly_chart(fig_elec_hist, use_container_width=True)
        else:
            st.info("Dati storici non disponibili per questa regione.")

    with colB:
        st.subheader("Nuova Domanda: Data Centers")
        st.markdown("Consumo elettrico stimato per i Data Center (TWh).")
        reg_dc = df_dc_hist[df_dc_hist['Region'].str.contains(selected_region, case=False, na=False)]
        
        if not reg_dc.empty:
            fig_dc = px.bar(reg_dc, x='Year', y='Value', title="Domanda Data Center (TWh)", text_auto='.1f')
            fig_dc.update_traces(marker_color='#3B82F6')
            st.plotly_chart(fig_dc, use_container_width=True)
        else:
            st.info(f"Dati specifici sui Data Center non tracciati isolatamente per: {selected_region}.")


# --- TAB 2: STATISTICHE 2025 ---
with tab_charts:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Mix Energia Primaria (Stock 2025)")
        tes_data = pd.DataFrame({'Fonte': sources, 'Valore (EJ)': [reg_tes_25[s] for s in sources]})
        fig_tes = px.pie(tes_data, values='Valore (EJ)', names='Fonte', hole=0.4)
        st.plotly_chart(fig_tes, use_container_width=True)

    with c2:
        if reg_elec is not None:
            st.subheader("Mix Generazione Elettrica (2025)")
            elec_src = ['Oil', 'Natural Gas', 'Coal', 'Nuclear', 'Hydro', 'Renewables', 'Other']
            elec_data = pd.DataFrame({'Fonte': elec_src, 'Valore (TWh)': [reg_elec[s] for s in elec_src]})
            fig_elec = px.bar(elec_data, x='Fonte', y='Valore (TWh)', color='Fonte')
            st.plotly_chart(fig_elec, use_container_width=True)

# --- TAB 3: SANKEY EMBER STYLE ---
with tab_sankey:
    st.subheader("Da Energia Primaria a Energia Utile")
    st.markdown("Simulazione delle perdite termodinamiche. I nodi 'Wasted Energy' mostrano la perdita intrinseca della combustione di fonti termiche.")
    
    if reg_elec is not None:
        primary_electro = reg_tes_25['Hydro'] + reg_tes_25['Renewables']
        primary_thermal = reg_tes_25['Oil'] + reg_tes_25['Natural Gas'] + reg_tes_25['Coal'] + reg_tes_25['Nuclear']
        
        final_electrons = elec_total_ej
        elec_from_electro = (reg_elec['Hydro'] + reg_elec['Renewables']) * 0.0036
        elec_from_thermal = (reg_elec['Oil'] + reg_elec['Natural Gas'] + reg_elec['Coal'] + reg_elec['Nuclear'] + reg_elec['Other']) * 0.0036
        
        eff_electro_to_elec = 0.92
        eff_thermal_to_elec = 0.29
        
        electro_to_elec_input = min(primary_electro, elec_from_electro / eff_electro_to_elec) if elec_from_electro > 0 else 0
        waste_electro_gen = max(0, electro_to_elec_input - elec_from_electro)
        
        thermal_to_elec_input = elec_from_thermal / eff_thermal_to_elec if elec_from_thermal > 0 else 0
        waste_thermal_gen = max(0, thermal_to_elec_input - elec_from_thermal)
        
        thermal_to_mol_input = max(0, primary_thermal - thermal_to_elec_input)
        final_molecules = thermal_to_mol_input * 0.85
        waste_thermal_mol = thermal_to_mol_input * 0.15
        
        elec_to_work_in = final_electrons * 0.77
        elec_to_heat_in = final_electrons * 0.23
        mol_to_work_in = final_molecules * 0.48
        mol_to_heat_in = final_molecules * 0.52
        
        useful_work = (elec_to_work_in * 0.68) + (mol_to_work_in * 0.29)
        useful_heat = (elec_to_heat_in * 0.91) + (mol_to_heat_in * 0.64)
        
        waste_end_use = (elec_to_work_in * 0.32) + (elec_to_heat_in * 0.09) + (mol_to_work_in * 0.71) + (mol_to_heat_in * 0.36)

        nodes = ["Electro Sources", "Thermal Sources", "Electrons", "Molecules", "Useful Work", "Useful Heat", "Wasted Energy"]
        source = [0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3]
        target = [2, 6, 2, 3, 6, 4, 5, 6, 4, 5, 6]
        value = [
            elec_from_electro, waste_electro_gen,
            elec_from_thermal, final_molecules, waste_thermal_gen + waste_thermal_mol,
            elec_to_work_in * 0.68, elec_to_heat_in * 0.91, (elec_to_work_in * 0.32) + (elec_to_heat_in * 0.09),
            mol_to_work_in * 0.29, mol_to_heat_in * 0.64, (mol_to_work_in * 0.71) + (mol_to_heat_in * 0.36)
        ]

        colors = ['#2ca02c', '#d62728', '#17becf', '#ff7f0e', '#9467bd', '#e377c2', '#7f7f7f']

        fig_sankey = go.Figure(data=[go.Sankey(
            node=dict(pad=20, thickness=25, line=dict(color="black", width=0.5), label=nodes, color=colors),
            link=dict(source=source, target=target, value=value, hovertemplate='%{source.label} -> %{target.label}<br>%{value:.1f} EJ<extra></extra>')
        )])
        fig_sankey.update_layout(height=600, font_size=13)
        st.plotly_chart(fig_sankey, use_container_width=True)
