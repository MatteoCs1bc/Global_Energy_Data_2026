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
st.markdown("Esplora i dati energetici e analizza il passaggio da energia **Primaria** a **Utile**, ispirato al framework *Ember - Age of Electricity*.")

# --- 2. FUNZIONI DI CARICAMENTO DATI ---
@st.cache_data
def load_data():
    file_path = "EI-Stats-Review-ALL-data (1).xlsx"
    
    # Helper per caricare i fogli in modo sicuro
    def get_sheet(sheet_name, cols_indices, col_names):
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name, skiprows=2)
            df = df.iloc[:, cols_indices].copy()
            df.columns = col_names
            df = df.dropna(subset=['Region'])
            # Pulisce i valori non numerici
            for col in df.columns[1:]:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        except Exception as e:
            st.error(f"Errore in {sheet_name}: {e}")
            return pd.DataFrame()

    # 1. Energia Primaria (Total Energy Supply) in Exajoules
    df_tes = get_sheet(
        'TES by fuel', 
        [0, 1, 2, 3, 4, 5, 6, 7], 
        ['Region', 'Oil', 'Natural Gas', 'Coal', 'Nuclear', 'Hydro', 'Renewables', 'Total']
    )
    
    # 2. Generazione Elettrica in TWh
    df_elec = get_sheet(
        'Elec generation by fuel', 
        [0, 1, 2, 3, 4, 5, 6, 7, 8], 
        ['Region', 'Oil', 'Natural Gas', 'Coal', 'Nuclear', 'Hydro', 'Renewables', 'Other', 'Total']
    )
    
    # 3. Capacità Installata (Megawatts) - Cerchiamo gli anni recenti
    try:
        df_solar_raw = pd.read_excel(file_path, sheet_name='Solar Installed Capacity', skiprows=2)
        df_wind_raw = pd.read_excel(file_path, sheet_name='Wind Installed Capacity', skiprows=2)
        
        # Estraiamo le colonne: Regione (0) e anno più recente, es 2023 (circa indice 24)
        df_cap = pd.DataFrame({'Region': df_solar_raw.iloc[:, 0]})
        df_cap['Solar MW'] = pd.to_numeric(df_solar_raw.iloc[:, 24], errors='coerce').fillna(0)
        df_cap['Wind MW'] = pd.to_numeric(df_wind_raw.iloc[:, 24], errors='coerce').fillna(0)
        df_cap = df_cap.dropna(subset=['Region'])
    except:
        df_cap = pd.DataFrame(columns=['Region', 'Solar MW', 'Wind MW'])

    return df_tes, df_elec, df_cap

df_tes, df_elec, df_cap = load_data()
if df_tes.empty:
    st.stop()

# Classificazione Aggregati vs Stati
aggregates_keywords = ['Total', 'World', 'Union', 'OECD', 'Non-OECD']
is_aggregate = df_tes['Region'].str.contains('|'.join(aggregates_keywords), case=False, na=False)

# --- 3. SIDEBAR E FILTRI ---
st.sidebar.header("Impostazioni")
view_type = st.sidebar.radio("Cosa vuoi analizzare?", ("Stati Singoli", "Aggregati / Continenti"))

regions_list = df_tes[~is_aggregate]['Region'].unique() if view_type == "Stati Singoli" else df_tes[is_aggregate]['Region'].unique()
selected_region = st.sidebar.selectbox("Seleziona Area:", [r for r in regions_list if r != 'Other'])

# Filtro dati per la regione
reg_tes = df_tes[df_tes['Region'] == selected_region].iloc[0] if not df_tes[df_tes['Region'] == selected_region].empty else None
reg_elec = df_elec[df_elec['Region'] == selected_region].iloc[0] if not df_elec[df_elec['Region'] == selected_region].empty else None
reg_cap = df_cap[df_cap['Region'] == selected_region].iloc[0] if not df_cap[df_cap['Region'] == selected_region].empty else None

if reg_tes is None or reg_elec is None:
    st.warning("Dati non sufficienti per la regione selezionata.")
    st.stop()

# --- 4. CALCOLI METRICHE CHIAVE ---
primary_total = reg_tes['Total']
elec_total_twh = reg_elec['Total']
elec_total_ej = elec_total_twh * 0.0036 # 1 TWh = 0.0036 EJ
rinnovabili_twh = reg_elec['Hydro'] + reg_elec['Renewables']
quota_rinnovabili = (rinnovabili_twh / elec_total_twh * 100) if elec_total_twh > 0 else 0
eff_sistema = (elec_total_ej / primary_total * 100) if primary_total > 0 else 0

st.header(f"Analisi Energetica: {selected_region}")

# Metriche principali
m1, m2, m3, m4 = st.columns(4)
m1.metric("Energia Primaria (TES)", f"{primary_total:.2f} EJ")
m2.metric("Generazione Elettrica", f"{elec_total_twh:.1f} TWh")
m3.metric("Copertura Rinnovabile (Elec)", f"{quota_rinnovabili:.1f} %")
m4.metric("Elettrificazione (Output vs Primaria)", f"{eff_sistema:.1f} %")

st.divider()

# --- 5. GRAFICI STATISTICI ---
tab_charts, tab_sankey = st.tabs(["📊 Statistiche e Mix", "🔄 Sankey (Ember-Style: Primaria -> Utile)"])

with tab_charts:
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("Mix Energia Primaria")
        tes_data = pd.DataFrame({'Fonte': ['Oil', 'Natural Gas', 'Coal', 'Nuclear', 'Hydro', 'Renewables'],
                                 'Valore (EJ)': [reg_tes['Oil'], reg_tes['Natural Gas'], reg_tes['Coal'], reg_tes['Nuclear'], reg_tes['Hydro'], reg_tes['Renewables']]})
        fig_tes = px.pie(tes_data, values='Valore (EJ)', names='Fonte', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig_tes, use_container_width=True)

    with c2:
        st.subheader("Generazione Elettrica")
        elec_data = pd.DataFrame({'Fonte': ['Oil', 'Natural Gas', 'Coal', 'Nuclear', 'Hydro', 'Renewables', 'Other'],
                                  'Valore (TWh)': [reg_elec['Oil'], reg_elec['Natural Gas'], reg_elec['Coal'], reg_elec['Nuclear'], reg_elec['Hydro'], reg_elec['Renewables'], reg_elec['Other']]})
        fig_elec = px.bar(elec_data, x='Fonte', y='Valore (TWh)', color='Fonte', color_discrete_sequence=px.colors.qualitative.Set2)
        st.plotly_chart(fig_elec, use_container_width=True)
        
    if reg_cap is not None:
        st.subheader("Parco Generazione Installato (Solo Solare/Eolico)")
        cap_data = pd.DataFrame({'Tecnologia': ['Solare', 'Eolico'], 'Capacità (MW)': [reg_cap['Solar MW'], reg_cap['Wind MW']]})
        st.bar_chart(cap_data.set_index('Tecnologia'))

# --- 6. SANKEY EMBER STYLE (PRIMARIA -> FINALE -> UTILE) ---
with tab_sankey:
    st.subheader("Come usiamo (e sprechiamo) l'energia?")
    st.markdown("""
    Questo diagramma applica le logiche del report **Ember** sui dati di quest'area. Mostra come le fonti *Termiche* 
    (Fossili e Nucleare) generino enormi quantità di calore sprecato, mentre le fonti *Elettro* (Rinnovabili e Idro) 
    siano intrinsecamente più efficienti nel produrre Lavoro e Calore utile.
    """)
    
    # 1. Input Primari
    primary_electro = reg_tes['Hydro'] + reg_tes['Renewables']
    primary_thermal = reg_tes['Oil'] + reg_tes['Natural Gas'] + reg_tes['Coal'] + reg_tes['Nuclear']
    
    # 2. Generazione Elettrica (Elettroni Finali) convertita in EJ
    final_electrons = elec_total_ej
    elec_from_electro = (reg_elec['Hydro'] + reg_elec['Renewables']) * 0.0036
    elec_from_thermal = (reg_elec['Oil'] + reg_elec['Natural Gas'] + reg_elec['Coal'] + reg_elec['Nuclear'] + reg_elec['Other']) * 0.0036
    
    # Efficienze medie globali (dal framework Ember)
    eff_electro_to_elec = 0.92
    eff_thermal_to_elec = 0.29
    
    # Calcolo imput per la generazione
    electro_to_elec_input = min(primary_electro, elec_from_electro / eff_electro_to_elec) if elec_from_electro > 0 else 0
    waste_electro_gen = max(0, electro_to_elec_input - elec_from_electro)
    
    thermal_to_elec_input = elec_from_thermal / eff_thermal_to_elec if elec_from_thermal > 0 else 0
    waste_thermal_gen = max(0, thermal_to_elec_input - elec_from_thermal)
    
    # Calcolo molecole dirette (usi termici e trasporti non elettrificati)
    thermal_to_mol_input = max(0, primary_thermal - thermal_to_elec_input)
    final_molecules = thermal_to_mol_input * 0.85
    waste_thermal_mol = thermal_to_mol_input * 0.15
    
    # 3. Utilizzo Finale (Split stimato dal report Ember: Elettroni 77% Lavoro/23% Calore | Molecole 48% Lavoro/52% Calore)
    elec_to_work_in = final_electrons * 0.77
    elec_to_heat_in = final_electrons * 0.23
    mol_to_work_in = final_molecules * 0.48
    mol_to_heat_in = final_molecules * 0.52
    
    # 4. Energia Utile e Spreco finale
    useful_work = (elec_to_work_in * 0.68) + (mol_to_work_in * 0.29)
    useful_heat = (elec_to_heat_in * 0.91) + (mol_to_heat_in * 0.64)
    
    waste_end_use = (elec_to_work_in * 0.32) + (elec_to_heat_in * 0.09) + (mol_to_work_in * 0.71) + (mol_to_heat_in * 0.36)
    total_waste = waste_electro_gen + waste_thermal_gen + waste_thermal_mol + waste_end_use

    # Costruzione Nodi e Link per Plotly
    nodes = ["Electro Sources", "Thermal Sources", "Electrons", "Molecules", "Useful Work", "Useful Heat", "Wasted Energy"]
    
    # Mappatura indici nodi
    # 0:Electro, 1:Thermal, 2:Electrons, 3:Molecules, 4:Work, 5:Heat, 6:Waste
    source = [0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3]
    target = [2, 6, 2, 3, 6, 4, 5, 6, 4, 5, 6]
    value = [
        elec_from_electro, waste_electro_gen, # Da Electro
        elec_from_thermal, final_molecules, waste_thermal_gen + waste_thermal_mol, # Da Thermal
        elec_to_work_in * 0.68, elec_to_heat_in * 0.91, (elec_to_work_in * 0.32) + (elec_to_heat_in * 0.09), # Da Elettroni
        mol_to_work_in * 0.29, mol_to_heat_in * 0.64, (mol_to_work_in * 0.71) + (mol_to_heat_in * 0.36) # Da Molecole
    ]

    colors = ['#2ca02c', '#d62728', '#17becf', '#ff7f0e', '#9467bd', '#e377c2', '#7f7f7f']

    fig_sankey = go.Figure(data=[go.Sankey(
        node=dict(pad=20, thickness=25, line=dict(color="black", width=0.5), label=nodes, color=colors),
        link=dict(source=source, target=target, value=value, hovertemplate='%{source.label} -> %{target.label}<br>%{value:.1f} EJ<extra></extra>')
    )])
    fig_sankey.update_layout(height=600, font_size=13, title_text="Flusso Termodinamico dell'Energia (Exajoules)")
    st.plotly_chart(fig_sankey, use_container_width=True)
