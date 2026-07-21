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
st.markdown("Esplora i dati energetici analizzando i **flussi** di transizione, l'**elettrificazione** e la termodinamica (**Sankey**).")

# --- MAPPA COLORI ---
color_map = {
    'Coal': '#1F2937',        # Grigio molto scuro / quasi Nero
    'Oil': '#4B5563',         # Grigio medio
    'Natural Gas': '#9CA3AF', # Grigio chiaro
    'Nuclear': '#A855F7',     # Viola
    'Hydro': '#3B82F6',       # Blu
    'Solar': '#FACC15',       # Giallo
    'Wind': '#22C55E',        # Verde
    'Biomass/Geo': '#8B4513', # Marrone
    'Renewables': '#22C55E',  # Verde (per aggregati generici)
    'Other': '#D1D5DB'        # Grigio chiarissimo
}

# --- 2. FUNZIONI DI CARICAMENTO DATI ---
@st.cache_data
def load_data():
    file_path = "EI-Stats-Review-ALL-data (1).xlsx"
    
    # 1. Energia Primaria (TES by fuel) - Estraiamo 2024 e 2025
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
    
    # 2. Generazione Elettrica (2025) - INDICI CORRETTI!
    try:
        df_elec_raw = pd.read_excel(file_path, sheet_name='Elec generation by fuel', skiprows=2)
        df_elec = df_elec_raw.iloc[:, [0, 9, 10, 11, 12, 13, 14, 15, 16]].copy()
        df_elec.columns = ['Region', 'Oil', 'Natural Gas', 'Coal', 'Nuclear', 'Hydro', 'Renewables', 'Other', 'Total']
        df_elec = df_elec.dropna(subset=['Region'])
        for col in df_elec.columns[1:]:
            df_elec[col] = pd.to_numeric(df_elec[col], errors='coerce').fillna(0)
    except: df_elec = pd.DataFrame()

    # Estrazione dettagli rinnovabili 2025 (colonna 61)
    def extract_ren_2025(sheet):
        try:
            df = pd.read_excel(file_path, sheet_name=sheet, skiprows=2)
            df = df.iloc[:, [0, 61]].copy()
            df.columns = ['Region', 'Value']
            df = df.dropna(subset=['Region'])
            df['Value'] = pd.to_numeric(df['Value'], errors='coerce').fillna(0)
            return df.set_index('Region')['Value']
        except: return pd.Series(dtype=float)

    solar = extract_ren_2025('Solar Generation - TWh')
    wind = extract_ren_2025('Wind Generation - TWh')
    bio = extract_ren_2025('Geo Biomass Other - TWh')
    df_ren_breakdown = pd.DataFrame({'Solar': solar, 'Wind': wind, 'Biomass/Geo': bio}).reset_index()

    # 3. Serie Storiche generiche
    def get_historical_sheet(sheet_name):
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name, skiprows=2)
            df = df.rename(columns={df.columns[0]: 'Region'})
            df = df.dropna(subset=['Region'])
            year_cols = [c for c in df.columns if isinstance(c, (int, float)) and 1900 < c < 2100]
            df_melt = df.melt(id_vars=['Region'], value_vars=year_cols, var_name='Year', value_name='Value')
            df_melt['Value'] = pd.to_numeric(df_melt['Value'], errors='coerce').fillna(0)
            return df_melt
        except: return pd.DataFrame()

    df_tes_hist = get_historical_sheet('Total Energy Supply (TES) -EJ')
    df_elec_hist = get_historical_sheet('Electricity Generation - TWh')
    df_dc_hist = get_historical_sheet('Data Centre Demand')
    
    return df_tes_flows, df_elec, df_ren_breakdown, df_tes_hist, df_elec_hist, df_dc_hist

df_tes_flows, df_elec, df_ren_breakdown, df_tes_hist, df_elec_hist, df_dc_hist = load_data()
if df_tes_flows.empty:
    st.stop()

# Classificazione Aggregati
aggregates_keywords = ['Total', 'World', 'Union', 'OECD', 'Non-OECD']
is_aggregate = df_tes_flows['Region'].str.contains('|'.join(aggregates_keywords), case=False, na=False)

# --- 3. SIDEBAR E FILTRI ---
st.sidebar.header("Impostazioni")
view_type = st.sidebar.radio("Analisi:", ("Stati Singoli", "Aggregati / Continenti"))

regions_list = df_tes_flows[~is_aggregate]['Region'].unique() if view_type == "Stati Singoli" else df_tes_flows[is_aggregate]['Region'].unique()
selected_region = st.sidebar.selectbox("Seleziona Area:", sorted([r for r in regions_list if r != 'Other']))

# --- 4. PREPARAZIONE DATI REGIONALI ---
reg_tes_25 = df_tes_flows[(df_tes_flows['Region'] == selected_region) & (df_tes_flows['Year'] == 2025)].iloc[0]
reg_tes_24 = df_tes_flows[(df_tes_flows['Region'] == selected_region) & (df_tes_flows['Year'] == 2024)].iloc[0]
reg_elec = df_elec[df_elec['Region'] == selected_region].iloc[0] if not df_elec[df_elec['Region'] == selected_region].empty else None
reg_ren = df_ren_breakdown[df_ren_breakdown['Region'] == selected_region].iloc[0] if not df_ren_breakdown[df_ren_breakdown['Region'] == selected_region].empty else None

primary_total = reg_tes_25['Total']
elec_total_twh = reg_elec['Total'] if reg_elec is not None else 0
elec_total_ej = elec_total_twh * 0.0036
rinnovabili_twh = (reg_elec['Hydro'] + reg_elec['Renewables']) if reg_elec is not None else 0
quota_rinnovabili = (rinnovabili_twh / elec_total_twh * 100) if elec_total_twh > 0 else 0
eff_sistema = (elec_total_ej / primary_total * 100) if primary_total > 0 else 0

st.header(f"Dashboard: {selected_region}")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Energia Primaria (2025)", f"{primary_total:.2f} EJ")
m2.metric("Generazione Elettrica", f"{elec_total_twh:.1f} TWh")
m3.metric("Copertura Rinnovabile", f"{quota_rinnovabili:.1f} %")
m4.metric("Indice di Elettrificazione", f"{eff_sistema:.1f} %")

st.divider()

# --- 5. TABS ---
tab_trend, tab_charts, tab_sankey = st.tabs(["📈 Trend e Transizione", "📊 Statistiche 2025", "🔄 Sankey Termodinamico"])

# --- TAB 1: TREND STORICI E FLUSSI ---
with tab_trend:
    st.subheader("La transizione nei Flussi (Delta 2024 vs 2025)")
    sources = ['Coal', 'Natural Gas', 'Oil', 'Nuclear', 'Hydro', 'Renewables']
    deltas = [{'Fonte': src, 'Variazione (EJ)': reg_tes_25[src] - reg_tes_24[src]} for src in sources]
    df_deltas = pd.DataFrame(deltas)
    
    fig_delta = px.bar(df_deltas, x='Fonte', y='Variazione (EJ)', color='Fonte',
                       color_discrete_map=color_map, title=f"Variazione Fornitura Energetica ({selected_region})")
    st.plotly_chart(fig_delta, use_container_width=True)

    colA, colB = st.columns(2)
    with colA:
        st.subheader("Elettrificazione Storica")
        reg_tes_h = df_tes_hist[df_tes_hist['Region'] == selected_region]
        reg_elec_h = df_elec_hist[df_elec_hist['Region'] == selected_region]
        if not reg_tes_h.empty and not reg_elec_h.empty:
            merged_h = pd.merge(reg_tes_h, reg_elec_h, on='Year', suffixes=('_TES', '_ELEC'))
            merged_h['Elec_Share_%'] = (merged_h['Value_ELEC'] * 0.0036) / merged_h['Value_TES'] * 100
            fig_elec_hist = px.line(merged_h, x='Year', y='Elec_Share_%')
            fig_elec_hist.update_traces(line_color='#22C55E', line_width=3)
            st.plotly_chart(fig_elec_hist, use_container_width=True)

    with colB:
        st.subheader("Domanda Data Center")
        reg_dc = df_dc_hist[df_dc_hist['Region'].str.contains(selected_region, case=False, na=False)]
        if not reg_dc.empty:
            fig_dc = px.bar(reg_dc, x='Year', y='Value', text_auto='.1f')
            fig_dc.update_traces(marker_color='#3B82F6')
            st.plotly_chart(fig_dc, use_container_width=True)
        else:
            st.info("Dati specifici sui Data Center non tracciati per questa area.")

# --- TAB 2: STATISTICHE 2025 CON MIX CORRETTO ---
with tab_charts:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Mix Energia Primaria (Stock 2025)")
        tes_data = pd.DataFrame({'Fonte': sources, 'Valore (EJ)': [reg_tes_25[s] for s in sources]})
        fig_tes = px.pie(tes_data, values='Valore (EJ)', names='Fonte', hole=0.4, color='Fonte', color_discrete_map=color_map)
        st.plotly_chart(fig_tes, use_container_width=True)

    with c2:
        if reg_elec is not None and reg_ren is not None:
            st.subheader("Mix Generazione Elettrica (2025)")
            # Mix dettagliato: sostituiamo "Renewables" con i suoi 3 sottomenù
            elec_src_detailed = ['Coal', 'Natural Gas', 'Oil', 'Nuclear', 'Hydro', 'Biomass/Geo', 'Solar', 'Wind', 'Other']
            elec_vals = [
                reg_elec['Coal'], reg_elec['Natural Gas'], reg_elec['Oil'], reg_elec['Nuclear'], reg_elec['Hydro'],
                reg_ren['Biomass/Geo'], reg_ren['Solar'], reg_ren['Wind'], reg_elec['Other']
            ]
            elec_data = pd.DataFrame({'Fonte': elec_src_detailed, 'Valore (TWh)': elec_vals})
            fig_elec = px.bar(elec_data, x='Fonte', y='Valore (TWh)', color='Fonte', color_discrete_map=color_map)
            st.plotly_chart(fig_elec, use_container_width=True)

# --- TAB 3: SANKEY EMBER STYLE ---
with tab_sankey:
    st.subheader("Da Energia Primaria a Energia Utile")
    
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
        
        waste_end_use = (elec_to_work_in * 0.32) + (elec_to_heat_in * 0.09) + (mol_to_work_in * 0.71) + (mol_to_heat_in * 0.36)

        nodes = ["Fonti Elettro (Rinn/Idro)", "Fonti Termiche (Foss/Nuc)", "Elettroni", "Molecole", "Lavoro Utile", "Calore Utile", "Energia Sprecata"]
        source = [0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3]
        target = [2, 6, 2, 3, 6, 4, 5, 6, 4, 5, 6]
        value = [
            elec_from_electro, waste_electro_gen,
            elec_from_thermal, final_molecules, waste_thermal_gen + waste_thermal_mol,
            elec_to_work_in * 0.68, elec_to_heat_in * 0.91, (elec_to_work_in * 0.32) + (elec_to_heat_in * 0.09),
            mol_to_work_in * 0.29, mol_to_heat_in * 0.64, (mol_to_work_in * 0.71) + (mol_to_heat_in * 0.36)
        ]

        # Colori Sankey in linea con le richieste
        colors = ['#22C55E', '#4B5563', '#3B82F6', '#9CA3AF', '#F59E0B', '#EF4444', '#1F2937']

        fig_sankey = go.Figure(data=[go.Sankey(
            node=dict(pad=20, thickness=25, line=dict(color="black", width=0.5), label=nodes, color=colors),
            link=dict(source=source, target=target, value=value, hovertemplate='%{source.label} -> %{target.label}<br>%{value:.1f} EJ<extra></extra>')
        )])
        fig_sankey.update_layout(height=600, font_size=13)
        st.plotly_chart(fig_sankey, use_container_width=True)
