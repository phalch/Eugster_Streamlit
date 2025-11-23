from datetime import time, timedelta, datetime
from pathlib import Path
import os
from math import ceil

import numpy as np
import pandas as pd
from openpyxl import load_workbook
import matplotlib.pyplot as plt  # au cas où
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# ========================= BASE DIR =========================

BASE_DIR = Path(__file__).resolve().parent

print("Dossier utilisé :", BASE_DIR)
print("Fichier CSV existe ?", (BASE_DIR / "ogd-smn_pay_h_historical_2020-2029.csv").exists())

# ========================= FONCTIONS CACHÉES =========================

@st.cache_data
def load_meteosuisse(base_dir: Path) -> pd.DataFrame:
    return pd.read_csv(
        base_dir / "ogd-smn_pay_h_historical_2020-2029.csv",
        delimiter=';',
        header=None,
        usecols=[1, 26],
        skiprows=lambda x: x < 35065 or x > 43854,
        names=['Datetime', 'Irradiance'],
        encoding='ISO-8859-1'
    )


@st.cache_data
def load_entnahme_eugster(base_dir: Path) -> pd.DataFrame:
    return pd.read_excel(base_dir / "Entnahme_Eugster.xlsx", usecols="A:B")


@st.cache_data
def load_grab(base_dir: Path) -> pd.DataFrame:
    return pd.read_excel(base_dir / "grab1.xlsx", header=None, usecols="A:B")


@st.cache_data
def load_tarif_table(base_dir: Path) -> pd.DataFrame:
    return pd.read_excel(base_dir / "Tarif.xlsx", sheet_name="Thal-Pro 2", usecols="B")


@st.cache_data
def load_tarif_workbook_values(base_dir: Path):
    wb_tarif = load_workbook(base_dir / "Tarif.xlsx")
    sheet_tarif = wb_tarif["Thal-Pro 2"]
    TZ1E = sheet_tarif["H8"].value
    TZ2E = sheet_tarif["H9"].value
    TZ1H = sheet_tarif["H10"].value
    TZ2H = sheet_tarif["H11"].value
    VG = sheet_tarif["H12"].value
    DE1 = sheet_tarif["F17"].value
    DE2 = sheet_tarif["H17"].value
    DH11 = sheet_tarif["F18"].value
    DH12 = sheet_tarif["H18"].value
    DH21 = sheet_tarif["F19"].value
    DH22 = sheet_tarif["H19"].value
    return TZ1E, TZ2E, TZ1H, TZ2H, VG, DE1, DE2, DH11, DH12, DH21, DH22


# ==================================== CONFIG STREAMLIT & STYLE ==================

st.set_page_config(page_title="Dashboard Grab–Eugster", layout="wide")

st.markdown("""
<style>
.big-title {
    font-size: 2.3rem;
    font-weight: 700;
    margin-bottom: 0.2rem;
}
.subtitle {
    color: #555;
    margin-bottom: 1.5rem;
}

/* Nouveau style des cartes d'indicateurs */
.metric-card {
    padding: 0.9rem 1.1rem;
    border-radius: 0.9rem;
    border: 1px solid #e3e7ef;
    background: linear-gradient(135deg, #fafbff, #f3f4ff);
    box-shadow: 0 2px 6px rgba(15, 23, 42, 0.08);
    display: flex;
    flex-direction: column;
    justify-content: center;
}

/* Centrer le contenu dans la carte */
.metric-card .stMetric {
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* --- Style bleu pour les indicateurs en kWh --- */
.metric-kwh {
    background: linear-gradient(135deg, #e8f2ff, #dbe9ff);
    border: 1px solid #c5d9ff;
    box-shadow: 0 2px 5px rgba(0, 64, 160, 0.15);
}

/* --- Style vert pour les indicateurs en CHF --- */
.metric-chf {
    background: linear-gradient(135deg, #e9fbe8, #d8f7d4);
    border: 1px solid #b7ecb0;
    box-shadow: 0 2px 5px rgba(0, 140, 40, 0.15);
}

/* Taille des valeurs KPI */
div[data-testid="stMetricValue"] {
    font-size: 1.5rem !important;
    font-weight: 600 !important;
}

/* Taille des labels KPI */
div[data-testid="stMetricLabel"] {
    font-size: 0.7rem !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="big-title">Dashboard Grab – Eugster</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Analyse énergétique Grab → Eugster, année 2024</div>', unsafe_allow_html=True)


#======================================= SELECTION OF TOPICS ====================================

Pp_default = 60.0   # kWp
Wf_default = 1000.0 # kWh/kWp/an
mo_default = "Januar"
topic_default = "Grab: PV Energie"   # correspond au label ci-dessous

dM = pd.DataFrame({
    "Label": [
        "Grab: PV Energie",
        "Grab: Eigenverbrauch",
        "Grab: Uberschuss",
        "Grab: EVU Ergänzung",
        "Eugster: EVU Energie ohne Grab Energie",
        "Eugster: Grab Energie",
        "Eugster: EVU Ergänzung",
        "Grab: Restüberschuss"
    ]
})
dM.columns = ["libelle"]
dM["abbrev"] = [
    "kWh_Solar",            # PV Leistung
    "kWh_EV Grab",          # EVU Energie Lieferung an Grab (EV=Eigenverbrauch), ohne PV
    "UG1",                  # Überschuss Grab
    "EVUGSKWH",             # EVU Energie Lieferung an Grab mit PV
    "kWh_EVU_Eugster",      # EVU Energie Lieferung an Eugster ohne Grab Energie
    "kWh_Grab_Eugster",     # Grab Energie Lieferung an Eugster
    "kWh_EVU_Grab_Eugster", # EVU Energie an Eugster zusätzlich zur Grab Energie
    "Rest_U"                # Restüberschuss
]
dico = pd.Series(dM["abbrev"].values, index=dM["libelle"]).to_dict()

# ===================================== DASHBOARD (SIDEBAR) ==================

mois_liste = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember"
]

themes_liste = list(dico.keys())

st.sidebar.markdown("### ⚙️ Paramètres")

# Période
with st.sidebar.expander("Sélection de la période", expanded=True):
    mo = st.selectbox(
        "Choisir le mois",
        mois_liste,
        index=mois_liste.index(mo_default) if mo_default in mois_liste else 0,
        key="mois_select"
    )

# Fenêtre horaire
with st.sidebar.expander("Fenêtre horaire d’analyse", expanded=True):
    heure_debut, heure_fin = st.slider(
        "Plage horaire (heures)",
        min_value=0,
        max_value=23,
        value=(5, 20),
        step=1
    )

if heure_debut > heure_fin:
    heure_debut, heure_fin = heure_fin, heure_debut

H1 = f"{int(heure_debut):02d}:00"
H2 = f"{int(heure_fin):02d}:00"

# Paramètres techniques
with st.sidebar.expander("Paramètres techniques", expanded=True):
    Pp = st.slider(
        "Peak Power Pp (kWp)",
        min_value=20.0,
        max_value=120.0,
        value=float(Pp_default),
        step=10.0
    )

    Wf = st.slider(
        "Wandlungsfaktor Wf (kWh/kWp/an)",
        min_value=900.0,
        max_value=1200.0,
        value=float(Wf_default),
        step=50.0
    )

# Tarif Grab / EVU
with st.sidebar.expander("Tarif", expanded=True):
    tt = st.slider(
        "Ratio Tarif Grab / EVU",
        min_value=0.20,
        max_value=1.00,
        value=0.50,
        step=0.05,
        help="0.50 = Grab facture 50% du tarif EVU"
    )

# Thème
with st.sidebar.expander("Thème à visualiser", expanded=True):
    topic = st.selectbox(
        "Choisir le thème",
        themes_liste,
        index=themes_liste.index(topic_default) if topic_default in themes_liste else 0,
        key="topic_select"
    )

abbr = dico.get(topic, "Abréviation inconnue")
if abbr == "Abréviation inconnue":
    st.sidebar.warning("Abréviation inconnue pour ce thème.\nVérifiez le fichier Excel.")


#======================================= DATA LOADING METEOSUISSE ====================================

Station = "Altenrhein"
Year = "Year 2024"

df = load_meteosuisse(BASE_DIR)

index = pd.date_range(start="2024-01-01 00:00", end="2024-12-31 23:00", freq="h")
dt = pd.DataFrame(index=index)
col_to_transfer = df["Irradiance"]
dt["Irradiance"] = col_to_transfer.values
Totaldt = dt["Irradiance"].sum()

# Stündliche Solar Energie (kWh)
dt["Irradiance"] = dt["Irradiance"] * Wf * Pp / Totaldt
dt = dt.round(0)
dt = dt.rename(columns={"Irradiance": "kWh_Solar"})

# Production solaire mensuelle
monthly_solar = dt["kWh_Solar"].resample("ME").sum()
monthly_solar.index = monthly_solar.index.strftime("%b")
df_solar = monthly_solar.reset_index()
df_solar.columns = ["Monat", "kWh_Solar"]


#====================================== DATA LOADING EUGSTER =========================

dE = load_entnahme_eugster(BASE_DIR)
dE["Zeitstempel"] = pd.to_datetime(dE["Zeitstempel"], errors="coerce")
dE["Wert [kWh]"] = pd.to_numeric(dE["Wert [kWh]"], errors="coerce")
dE = dE.rename(columns={"Wert [kWh]": "kWh_EVU_Eugster", "Zeitstempel": "dateTime"})
dE.set_index("dateTime", inplace=True)

#===================================== NEW GENERIC DATA FRAME =======================

dE_h = dE.resample("h").agg({"kWh_EVU_Eugster": lambda x: x.sum() * 1})
dE_h = dE_h[dE_h.index < pd.to_datetime("2025-1-1 00:00")]

# Intégration PV
dE_h["kWh_Solar"] = dt["kWh_Solar"].values

#======================================== DATA LOADING GRAB ========================

dG = load_grab(BASE_DIR)
dG = dG.dropna(subset=[0]).sort_values(0).set_index(0)
dG_extended = dG.reindex(dE_h.index, fill_value=0)
dE_h["kWh_EV Grab"] = dG_extended

#=================================================== TARIFF  =================================================

dates = pd.date_range(start="2024-01-01 00:00", periods=168, freq="h")
dt_tarif = load_tarif_table(BASE_DIR)

end_date = "2024-12-31 23:00"
total_hours = int((pd.to_datetime(end_date) - dates[0]).total_seconds() / 3600) + 1

dt_tarif = pd.concat([dt_tarif] * ((total_hours + 164) // len(dt_tarif)), ignore_index=True)
dt_tarif = dt_tarif.iloc[:total_hours]
timeframe = pd.date_range(start="2024-01-01 00:00", end="2024-12-31 23:00", freq="h")
dt_tarif.insert(0, "timeframe", timeframe)
dt_tarif = dt_tarif.dropna(subset=["timeframe"]).sort_values("timeframe").set_index("timeframe")

(
    TZ1E, TZ2E, TZ1H, TZ2H,
    VG, DE1, DE2, DH11, DH12, DH21, DH22
) = load_tarif_workbook_values(BASE_DIR)

dt_tarif.loc[(dt_tarif.index >= DE1) & (dt_tarif.index <= DE2) & (dt_tarif["Tarif"] == '"TZ2"'), "Tarif"] = TZ2E
dt_tarif.loc[(dt_tarif.index >= DE1) & (dt_tarif.index <= DE2) & (dt_tarif["Tarif"] == '"TZ1"'), "Tarif"] = TZ1E
dt_tarif.loc[(dt_tarif.index >= DH11) & (dt_tarif.index <= DH12) & (dt_tarif["Tarif"] == '"TZ2"'), "Tarif"] = TZ2H
dt_tarif.loc[(dt_tarif.index >= DH11) & (dt_tarif.index <= DH12) & (dt_tarif["Tarif"] == '"TZ1"'), "Tarif"] = TZ1H
dt_tarif.loc[(dt_tarif.index >= DH21) & (dt_tarif.index <= DH22) & (dt_tarif["Tarif"] == '"TZ2"'), "Tarif"] = TZ2H
dt_tarif.loc[(dt_tarif.index >= DH21) & (dt_tarif.index <= DH22) & (dt_tarif["Tarif"] == '"TZ1"'), "Tarif"] = TZ1H

dE_h["Tarif CHF"] = dt_tarif["Tarif"]
dE_h["Tarif CHF"] = pd.to_numeric(dE_h["Tarif CHF"], errors="coerce")

TZ1EG = tt * TZ1E
TZ2EG = tt * TZ2E
TZ1HG = tt * TZ1H
TZ2HG = tt * TZ2H

dt_tarif.loc[(dt_tarif.index >= DE1) & (dt_tarif.index <= DE2) & (dt_tarif["Tarif"] == TZ2E), "Tarif"] = TZ2EG
dt_tarif.loc[(dt_tarif.index >= DE1) & (dt_tarif.index <= DE2) & (dt_tarif["Tarif"] == TZ1E), "Tarif"] = TZ1EG
dt_tarif.loc[(dt_tarif.index >= DH11) & (dt_tarif.index <= DH12) & (dt_tarif["Tarif"] == TZ2H), "Tarif"] = TZ2HG
dt_tarif.loc[(dt_tarif.index >= DH21) & (dt_tarif.index <= DH22) & (dt_tarif["Tarif"] == TZ2H), "Tarif"] = TZ2HG
dt_tarif.loc[(dt_tarif.index >= DH21) & (dt_tarif.index <= DH22) & (dt_tarif["Tarif"] == TZ1H), "Tarif"] = TZ1HG

dE_h["Tarif CHF_G"] = dt_tarif["Tarif"]
dE_h["Tarif CHF_G"] = pd.to_numeric(dE_h["Tarif CHF_G"], errors="coerce")


#============================================= RESULTS ==========================================

# EVU Rechnung an Eugster (ohne Grab)
dE_h["CHF_EVU_Eugster"] = dE_h["kWh_EVU_Eugster"] * dE_h["Tarif CHF"]
EVUEKW = round(dE_h["kWh_EVU_Eugster"].sum(), 0)
EVUECHF = round(dE_h["CHF_EVU_Eugster"].sum(), 0)

# EVU Rechnung an Grab (ohne Panels)
dE_h["CHF_EVU_Grab"] = dE_h["kWh_EV Grab"] * dE_h["Tarif CHF"]
EVUGCH = round(dE_h["CHF_EVU_Grab"].sum(), 0)

# Überschuss Grab
dE_h["UG"] = dE_h["kWh_Solar"] - dE_h["kWh_EV Grab"]
dE_h["UG1"] = dE_h["UG"].clip(lower=0)
monthly_sum_UG1 = dE_h["UG1"].resample("ME").sum()
UG = round(dE_h["UG1"].sum(), 0)

# EVU Energie Lieferung und Rechnung an Grab (mit PV)
dE_h["EVUGSKWH"] = -dE_h["UG"].mask(dE_h["UG"] > 0, 0)
dE_h["EVUGSCHF"] = dE_h["EVUGSKWH"] * dE_h["Tarif CHF"]
EVUGSCH = round(dE_h["EVUGSCHF"].sum(), 0)

# Restüberschuss Grab
dE_h["Rest_U"] = (dE_h["UG1"] - dE_h["kWh_EVU_Eugster"]).clip(lower=0)
monthly_sum_RestU = dE_h["Rest_U"].resample("ME").sum()
RestU = round(dE_h["Rest_U"].sum(), 0)

# Energie Lieferung Grab an Eugster
dE_h["kWh_Grab_Eugster"] = dE_h["UG1"] - dE_h["Rest_U"]
monthly_sum_GE = dE_h["kWh_Grab_Eugster"].resample("ME").sum()
GE = round(dE_h["kWh_Grab_Eugster"].sum(), 0)

# Rechnung Grab an Eugster
dE_h["GewinnGrab"] = dE_h["kWh_Grab_Eugster"] * dE_h["Tarif CHF_G"]
monthly_sum_P1 = dE_h["GewinnGrab"].resample("ME").sum()
P1 = round(dE_h["GewinnGrab"].sum(), 0)

# Vergütung EVU an Grab
P2 = round(RestU * VG, 0)

# EVU Energie Lieferung an Eugster als Ergänzung zur Energie Lieferung Grab
dE_h["kWh_EVU_Grab_Eugster"] = dE_h["kWh_EVU_Eugster"] - dE_h["kWh_Grab_Eugster"]
monthly_sum_EVUGE = dE_h["kWh_EVU_Grab_Eugster"].resample("ME").sum()
EVUGE = round(dE_h["kWh_EVU_Grab_Eugster"].sum(), 0)

# EVU Rechnung Lieferung an Eugster als Ergänzung
dE_h["CHF-EVU-Grab_Eugster"] = dE_h["kWh_EVU_Grab_Eugster"] * dE_h["Tarif CHF"]
EVUGECH = round(dE_h["CHF-EVU-Grab_Eugster"].sum(), 0)

# Gewinn Eugster
GewinnE = EVUECHF - EVUGECH - P1

# Gewinn Grab
dE_h["GewinnEVU"] = dE_h["kWh_Grab_Eugster"] * dE_h["Tarif CHF"]
P = round(dE_h["GewinnEVU"].sum(), 0)
GewinnG = EVUGCH - EVUGSCH + P1 + P2

# ================== TABLEAUX ÉCONOMIQUES ==================

t1 = [
    ["Struktur", "EVU CHF/kWh", "Grab CHF/kWh"],
    ["Timezeit 1 Sommer", TZ1E, TZ1EG],
    ["Timezeit 2 Sommer", TZ2E, TZ2EG],
    ["Timezeit 1 Winter", TZ1H, TZ1HG],
    ["Timezeit 2 Winter", TZ2H, TZ2HG],
    ["Vergütung", VG, np.nan],
]

t2 = [
    ["Lieferung", "Betrag CHF"],
    ["EVU ohne Grab_Solar", EVUECHF],
    ["EVU mit Grab_Solar", EVUGECH],
    ["Grab_Solar", P1],
    ["Total mit Grab_Solar", EVUGECH + P1],
    ["Gewinn", EVUECHF - EVUGECH - P1],
]

t3 = [
    ["Lieferung", "Betrag CHF"],
    ["EVU ohne Panels", EVUGCH],
    ["EVU mit Panel", EVUGSCH],
    ["Verkauf an Eugster", P1],
    ["Vergütung EVU", P2],
    ["Gewinn", EVUGCH - EVUGSCH + P1 + P2],
]


#================================= FONCTION D'ANALYSE & GRAPHIQUES ========================================

def run_analysis(mo: str, topic: str, abbr: str, H1: str, H2: str):
    if abbr not in dE_h.columns:
        st.error(f"❌ La colonne '{abbr}' n'existe pas dans les données. Choisissez un autre thème.")
        return None, None, None

    mois = {
        "Januar": 1, "Februar": 2, "März": 3, "April": 4,
        "Mai": 5, "Juni": 6, "Juli": 7, "August": 8,
        "September": 9, "Oktober": 10, "November": 11, "Dezember": 12
    }

    dE_h["month"] = dE_h.index.month
    dE_hs = {i: dE_h[dE_h["month"] == i] for i in range(1, 13)}

    i = mois[mo]

    weekdays = dE_hs[i][dE_hs[i].index.dayofweek < 5]
    weekends = dE_hs[i][dE_hs[i].index.dayofweek >= 5]

    if weekdays.empty and weekends.empty:
        st.error("❌ Pas de données pour le mois sélectionné.")
        return None, None, None

    df_filtered1 = weekdays[abbr].between_time(H1, H2) if not weekdays.empty else pd.Series(dtype=float)
    df_filtered2 = weekends[abbr].between_time(H1, H2) if not weekends.empty else pd.Series(dtype=float)

    if df_filtered1.empty and df_filtered2.empty:
        st.error("❌ Pas de données dans la plage horaire sélectionnée.")
        return None, None, None

    hourly_avg1 = df_filtered1.groupby(df_filtered1.index.hour).mean()
    hourly_avg2 = df_filtered2.groupby(df_filtered2.index.hour).mean()

    all_hours = sorted(set(hourly_avg1.index.tolist()) | set(hourly_avg2.index.tolist()))
    hourly_avg1 = hourly_avg1.reindex(all_hours)
    hourly_avg2 = hourly_avg2.reindex(all_hours)

    heures_reelles = np.array(all_hours, dtype=int)

    df_plot1 = pd.DataFrame({
        "Heure": np.concatenate([heures_reelles, heures_reelles]),
        "Valeur": np.concatenate([
            hourly_avg1.values.astype(float),
            hourly_avg2.values.astype(float)
        ]),
        "Type": (["Weekdays"] * len(heures_reelles)) + (["Weekends"] * len(heures_reelles)),
    })

    fig1 = px.bar(
        df_plot1,
        x="Heure",
        y="Valeur",
        color="Type",
        barmode="group",
        labels={"Heure": "Heure", "Valeur": "kWh"},
        title=f"{topic} – Profil journalier moyen ({mo}) [{H1}–{H2}]"
    )
    fig1.update_layout(
        xaxis=dict(dtick=1),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=60, b=40, l=40, r=10),
        title_font=dict(size=20),
    )

    x_labels = np.array([
        "Januar", "Februar", "März", "April", "Mai", "Juni",
        "Juli", "August", "September", "Oktober", "November", "Dezember"
    ])
    y1m = np.array(monthly_sum_UG1.values)
    y2m = np.array(monthly_sum_RestU.values)

    df_plot2 = pd.DataFrame({
        "Monat": np.concatenate([x_labels, x_labels]),
        "kWh": np.concatenate([y1m, y2m]),
        "Typ": (["Überschuss Grab"] * len(x_labels)) + (["Restüberschuss"] * len(x_labels)),
    })

    fig2 = px.bar(
        df_plot2,
        x="Monat",
        y="kWh",
        color="Typ",
        barmode="group",
        labels={"Monat": "Monat", "kWh": "Monatliche Leistung (kWh)"},
        title="Überschuss (Grab / Restüberschuss)"
    )
    fig2.update_layout(
        xaxis=dict(type="category"),
        margin=dict(t=60, b=40, l=40, r=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        title_font=dict(size=20),
    )

    y3m = np.array(monthly_sum_GE.values)
    y4m = np.array(monthly_sum_EVUGE.values)

    df_plot3 = pd.DataFrame({
        "Monat": np.concatenate([x_labels, x_labels]),
        "kWh": np.concatenate([y3m, y4m]),
        "Quelle": (["Grab (Solar)"] * len(x_labels)) + (["EVU"] * len(x_labels)),
    })

    fig3 = px.bar(
        df_plot3,
        x="Monat",
        y="kWh",
        color="Quelle",
        barmode="group",
        labels={"Monat": "Monat", "kWh": "Monatliche Leistung (kWh)"},
        title="Energie Verbrauch Eugster (Grab vs EVU)"
    )
    fig3.update_layout(
        xaxis=dict(type="category"),
        margin=dict(t=60, b=40, l=40, r=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        title_font=dict(size=20),
    )

    return fig1, fig2, fig3


# ================== ANALYSE & AFFICHAGE ==================

fig1, fig2, fig3 = run_analysis(mo, topic, abbr, H1, H2)

if fig1 is not None:
    st.markdown("### Jährliche KPIs")

    indic1 = RestU
    indic2 = GE
    indic3 = EVUEKW
    indic4 = GewinnE
    indic5 = GewinnG

    colp1, colp2, colp3, colp4, colp5 = st.columns(5)

    with colp1:
        st.markdown('<div class="metric-card metric-kwh">', unsafe_allow_html=True)
        st.metric("Lieferung EVU an Eugster (ohne Grab)", f"{indic3:,.0f} kWh".replace(",", "’"))
        st.markdown('</div>', unsafe_allow_html=True)

    with colp2:
        st.markdown('<div class="metric-card metric-kwh">', unsafe_allow_html=True)
        st.metric("Lieferung Grab an Eugster", f"{indic2:,.0f}".replace(",", "’") + " kWh")
        st.markdown('</div>', unsafe_allow_html=True)

    with colp3:
        st.markdown('<div class="metric-card metric-kwh">', unsafe_allow_html=True)
        st.metric("Restüberschuss", f"{indic1:,.0f} kWh".replace(",", "’"))
        st.markdown('</div>', unsafe_allow_html=True)

    with colp4:
        st.markdown('<div class="metric-card metric-chf">', unsafe_allow_html=True)
        st.metric("Gewinn Eugster", f"{indic4:,.0f} CHF".replace(",", "’"))
        st.markdown('</div>', unsafe_allow_html=True)

    with colp5:
        st.markdown('<div class="metric-card metric-chf">', unsafe_allow_html=True)
        st.metric("Gewinn Grab", f"{indic5:,.0f} CHF".replace(",", "’"))
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Profil journalier moyen",
        "📊 Überschuss (mensuel)",
        "⚡ Consommation Eugster (mensuel)",
        "📑 Tableaux économiques"
    ])

    with tab1:
        st.plotly_chart(fig1, width="stretch")

    with tab2:
        st.plotly_chart(fig2, width="stretch")

    with tab3:
        st.plotly_chart(fig3, width="stretch")

    with tab4:
        style_header = [
            {
                "selector": "th",
                "props": [
                    ("background-color", "#f0f0f0"),
                    ("font-weight", "bold"),
                    ("text-align", "center"),
                    ("padding", "6px 8px"),
                    ("white-space", "nowrap"),
                ],
            },
            {"selector": ".row_heading", "props": [("display", "none")]},
            {"selector": ".blank", "props": [("display", "none")]},
        ]

        common_cell_style = {
            "text-align": "left",
            "padding": "4px 8px",
            "border": "1px solid #ddd",
        }

        st.subheader("Tarif Struktur")
        st.markdown(f"**Ratio Grab / EVU : {tt:.2f}**")

        df_t1 = pd.DataFrame(t1[1:], columns=t1[0])
        df_t1_styled = (
            df_t1.style
            .set_table_styles(style_header)
            .set_properties(**common_cell_style)
            .format(
                subset=["EVU CHF/kWh", "Grab CHF/kWh"],
                formatter="{:,.3f}".format,
                na_rep=""
            )
        )

        col_tarif, _ = st.columns([1, 2])
        with col_tarif:
            st.table(df_t1_styled)

        st.markdown("---")

        col_left, col_right = st.columns(2)

        # ---- Eugster – Jährlicher Aufwand (CHF) ----
        with col_left:
            st.subheader("Eugster – Jährlicher Aufwand (CHF)")

            df_t2 = pd.DataFrame(t2[1:], columns=t2[0]).copy()
            df_t2["Betrag CHF"] = pd.to_numeric(df_t2["Betrag CHF"], errors="coerce")

            evu_ohne = df_t2.loc[df_t2["Lieferung"] == "EVU ohne Grab_Solar", "Betrag CHF"].iloc[0]
            evu_mit = df_t2.loc[df_t2["Lieferung"] == "EVU mit Grab_Solar", "Betrag CHF"].iloc[0]
            grab_solar = df_t2.loc[df_t2["Lieferung"] == "Grab_Solar", "Betrag CHF"].iloc[0]
            total_mit = df_t2.loc[df_t2["Lieferung"] == "Total mit Grab_Solar", "Betrag CHF"].iloc[0]
            gain_val = df_t2.loc[df_t2["Lieferung"] == "Gewinn", "Betrag CHF"].iloc[0]

            x_vals_all = [1, 2, 3, 4, 5]
            ticktext = ["EVU", "EVU", "Einkauf Grab", "Total", "Gewinn"]

            fig_eugster = go.Figure()
            blues = px.colors.sequential.Blues
            greens = px.colors.sequential.Greens

            fig_eugster.add_trace(go.Bar(
                name="ohne Grab",
                x=[1],
                y=[evu_ohne],
                base=[0],
                marker_color=blues[6],
                text=[evu_ohne],
                texttemplate="%{text:.0f}",
                textposition="outside",
            ))

            x_mit = [2, 3, 4, 5]
            y_mit = [evu_mit, grab_solar, total_mit, gain_val]
            base_mit = [0, evu_mit, 0, total_mit]

            color_main = blues[3]
            color_gain = greens[3]
            colors_mit = [color_main, color_main, color_main, color_gain]

            fig_eugster.add_trace(go.Bar(
                name="mit Grab",
                x=x_mit,
                y=y_mit,
                base=base_mit,
                marker_color=colors_mit,
                text=y_mit,
                texttemplate="%{text:.0f}",
                textposition="outside",
            ))

            fig_eugster.update_layout(
                barmode="overlay",
                xaxis=dict(
                    tickmode="array",
                    tickvals=x_vals_all,
                    ticktext=ticktext,
                    title=""
                ),
                yaxis=dict(title="CHF"),
                title="",
                legend=dict(
                    title="",
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                margin=dict(t=20, b=40, l=40, r=10),
                bargap=0.3,
                height=400
            )

            st.plotly_chart(fig_eugster, width="stretch")

        # ---- Grab – Jahresbilanz (CHF) ----
        with col_right:
            st.subheader("Grab – Jahresbilanz (CHF)")

            df_t3 = pd.DataFrame(t3[1:], columns=t3[0]).copy()
            df_t3["Betrag CHF"] = pd.to_numeric(df_t3["Betrag CHF"], errors="coerce")

            evu_ohne = df_t3.loc[df_t3["Lieferung"] == "EVU ohne Panels", "Betrag CHF"].iloc[0]
            evu_mit = df_t3.loc[df_t3["Lieferung"] == "EVU mit Panel", "Betrag CHF"].iloc[0]
            verkauf = df_t3.loc[df_t3["Lieferung"] == "Verkauf an Eugster", "Betrag CHF"].iloc[0]
            verguetung = df_t3.loc[df_t3["Lieferung"] == "Vergütung EVU", "Betrag CHF"].iloc[0]
            gewinn = df_t3.loc[df_t3["Lieferung"] == "Gewinn", "Betrag CHF"].iloc[0]

            x_ohne = [1]
            y_ohne = [evu_ohne]

            col2 = evu_mit
            col3 = -verkauf
            col4 = -verguetung
            col5 = gewinn

            x_mit = [2, 3, 4, 5]
            y_mit = [col2, col3, col4, col5]

            base_mit = [
                0,
                col2,
                col2 + col3,
                col2 + col3 + col4,
            ]

            blues = px.colors.sequential.Blues
            greens = px.colors.sequential.Greens
            color_ohne = blues[6]
            colors_mit = [blues[3], blues[3], blues[3], greens[3]]

            def fmt(v):
                return f"{v:,.0f}".replace(",", "’")

            fig_grab = go.Figure()

            fig_grab.add_trace(go.Bar(
                name="ohne PV",
                x=x_ohne,
                y=y_ohne,
                base=[0],
                marker_color=color_ohne,
                text=[fmt(y_ohne[0])],
                textposition="outside"
            ))

            fig_grab.add_trace(go.Bar(
                name="mit PV",
                x=x_mit,
                y=y_mit,
                base=base_mit,
                marker_color=colors_mit,
                text=[fmt(v) for v in y_mit],
                textposition="outside"
            ))

            fig_grab.update_layout(
                barmode="overlay",
                xaxis=dict(
                    tickmode="array",
                    tickvals=[1, 2, 3, 4, 5],
                    ticktext=[
                        "EVU",
                        "EVU",
                        "Verkauf Eugster",
                        "Vergütung",
                        "Gewinn"
                    ],
                    title=""
                ),
                yaxis=dict(title="CHF"),
                legend=dict(
                    title="",
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                margin=dict(t=20, b=40, l=40, r=10),
                bargap=0.3,
                height=400
            )

            st.plotly_chart(fig_grab, width="stretch")

else:
    st.info("Ajustez les paramètres dans la barre latérale.")