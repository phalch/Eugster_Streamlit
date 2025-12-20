
import streamlit as st
from datetime import time, timedelta, datetime
from pathlib import Path
from math import ceil

import hashlib
import numpy as np
import pandas as pd
from openpyxl import load_workbook
import matplotlib.pyplot as plt  # au cas où
import plotly.express as px
import plotly.graph_objects as go

from Panelverlust import dr, du, A  # comme dans ta page 02



from pathlib import Path
import hashlib
import streamlit as st

from pathlib import Path
import hashlib
import streamlit as st

# =========================
# ✅ VERSIONING PERSISTANT
# =========================

VERSION_FILE      = Path("version.txt")
SCRIPT_FILE       = Path(__file__)
HASH_FILE         = Path(".last_hash")
LAST_VERSION_FILE = Path(".last_version")  # ✅ nouveau

def normalize_version(v: str) -> str:
    v = (v or "").strip()
    if not v:
        return "V2.0"
    if not v.upper().startswith("V"):
        v = "V" + v
    body = v[1:]
    if "." not in body:
        return f"V{body}.0"          # ex: V3 -> V3.0
    major, minor = body.split(".", 1)
    if minor == "":
        minor = "0"
    return f"V{int(major)}.{int(minor)}"

# 1) init version si absent
if not VERSION_FILE.exists():
    VERSION_FILE.write_text("V2.0")

current_version = normalize_version(VERSION_FILE.read_text())

# 2) hash du script
current_hash = hashlib.sha256(SCRIPT_FILE.read_bytes()).hexdigest()
last_hash = HASH_FILE.read_text().strip() if HASH_FILE.exists() else ""

# 3) détecter changement manuel de version.txt → reset hash (pas d’incrément)
last_version_seen = LAST_VERSION_FILE.read_text().strip() if LAST_VERSION_FILE.exists() else ""
if last_version_seen != current_version:
    # ✅ tu as modifié V2 -> V3, ou V2.17 -> V3.0 etc.
    HASH_FILE.write_text(current_hash)          # reset: considérer le script "déjà pris en compte"
    LAST_VERSION_FILE.write_text(current_version)
    last_hash = current_hash                    # empêche un bump immédiat

# 4) éviter les bumps multiples dus aux reruns Streamlit
if "last_bumped_hash" not in st.session_state:
    st.session_state["last_bumped_hash"] = None

# 5) bump minor uniquement si le script a changé
if (current_hash != last_hash) and (st.session_state["last_bumped_hash"] != current_hash):
    major, minor = current_version.replace("V", "").split(".")
    new_version = f"V{int(major)}.{int(minor) + 1}"

    VERSION_FILE.write_text(new_version)
    HASH_FILE.write_text(current_hash)
    LAST_VERSION_FILE.write_text(new_version)

    current_version = new_version
    st.session_state["last_bumped_hash"] = current_hash

st.sidebar.markdown(f"### 🧾 Version : {current_version}")
# ========================= CONFIG GLOBALE =========================

st.set_page_config(
    page_title="Dashboard Grab – Eugster",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ========================= STYLES =========================

def apply_global_style():
    st.markdown(
        """
        <style>
        html, body, [class*="css"]  {
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif;
        }

        .main > div {
            max-width: 1200px;
            margin: 0 auto;
        }

        .big-title {
            font-size: 2.4rem;
            font-weight: 700;
            margin-bottom: 0.3rem;
        }

        .subtitle {
            color: #5f6368;
            font-size: 0.95rem;
            margin-bottom: 1.5rem;
        }

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

        .metric-card .stMetric {
            text-align: center;
        }

        .metric-kwh {
            background: linear-gradient(135deg, #e8f2ff, #dbe9ff);
            border: 1px solid #c5d9ff;
            box-shadow: 0 2px 5px rgba(0, 64, 160, 0.15);
        }

        .metric-chf {
            background: linear-gradient(135deg, #e9fbe8, #d8f7d4);
            border: 1px solid #b7ecb0;
            box-shadow: 0 2px 5px rgba(0, 140, 40, 0.15);
        }

        div[data-testid="stMetricValue"] {
            font-size: 1.5rem !important;
            font-weight: 600 !important;
        }

        div[data-testid="stMetricLabel"] {
            font-size: 0.7rem !important;
        }

        .stTabs [data-baseweb="tab"] {
            font-size: 1.1rem;
            font-weight: 600;
        }
        .stTabs [data-baseweb="tab"] p {
            font-size: 1.1rem;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

apply_global_style()

st.markdown('<div class="big-title">Dashboard Grab – Eugster</div>', unsafe_allow_html=True)


# ========================= BASE DIR =========================

BASE_DIR = Path(__file__).resolve().parent

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
    TZ1E  = sheet_tarif["H8"].value        
    TZ2E  = sheet_tarif["H9"].value
    TZ1H  = sheet_tarif["H10"].value
    TZ2H  = sheet_tarif["H11"].value
    TZ1EP = sheet_tarif["J8"].value
    TZ2EP = sheet_tarif["J9"].value
    TZ1HP = sheet_tarif["J10"].value
    TZ2HP = sheet_tarif["J11"].value
    DE1   = sheet_tarif["F17"].value
    DE2   = sheet_tarif["H17"].value
    DH11  = sheet_tarif["F18"].value
    DH12  = sheet_tarif["H18"].value
    DH21  = sheet_tarif["F19"].value
    DH22  = sheet_tarif["H19"].value

# Netztarif (ohne Swissgrid)
    Tnetz = sheet_tarif["L8"].value

    return TZ1E, TZ2E, TZ1H, TZ2H, TZ1EP, TZ2EP, TZ1HP, TZ2HP, DE1, DE2, DH11, DH12, DH21, DH22, Tnetz


# ========================= PARAMÈTRES DE BASE =========================

Pp_default    = 70.0   # kWp
Wf_default    = 950.0  # kWh/kWp/an
mo_default    = "März"
topic_default = "Grab: PV Energie"
pr            = -0.005
Jahr          = 1

dM = pd.DataFrame({
    "Label": [
        "Grab: Solarenergieertrag",
        "Grab: Eigenverbrauch",
        "Grab: Uberschuss",
        "Grab: Zusatzenergie von TB Thal",
        "Eugster: TB Thal Energie (ohne Grab Energie",
        "Eugster: Grab Energie",
        "Eugster: Zusatzenergie von TB Thal",
        "Grab: Restüberschuss nach Energie lieferung an Grab"
    ]
})

dM.columns = ["libelle"]
dM["abbrev"] = [
    "kWh_Solar",
    "kWh_EV Grab",
    "UG1",
    "EVUGSKWH",
    "kWh_EVU_Eugster",
    "kWh_Grab_Eugster",
    "kWh_EVU_Grab_Eugster",
    "Rest_U",
]
dico = pd.Series(dM["abbrev"].values, index=dM["libelle"]).to_dict()

mois_liste = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember"
]
themes_liste = list(dico.keys())

# ========================= SIDEBAR – PARAMÈTRES COMMUNS =========================

st.sidebar.markdown("## ⚙️ Bruttodaten – erstes Jahr ")

# --- Paramètres techniques (Rohdaten) ---
with st.sidebar.expander("Technische Parameter - Installation", expanded=True):
    Pp = st.slider(
        "Peak Power Pp (kWp)",
        min_value=20.0,
        max_value=120.0,
        value=float(Pp_default),
        step=10.0,
        key="Pp",
    )
    st.caption("Hinweis: Die erforderliche Modulfläche für 1 kWp beträgt zwischen 4 und 6 m²")
    Wf = st.slider(
        "Wandlungsfaktor Wf (kWh/kWp/an)",
        min_value=900.0,
        max_value=1200.0,
        value=float(Wf_default),
        step=50.0,
        key="Wf",
    )


# --- Tarife (Bruttodaten + 15 ans) ---
with st.sidebar.expander("💶 Tarifparameter – Jahr 1", expanded=True):
    tt = st.slider(
        "Ratio Tarif Pro Grab/TB Thal",
        min_value=0.20,
        max_value=1.00,
        value=0.50,
        step=0.05,
        key="tt",
        help="0.50 = Grab Tarif: 50% TB Thal Tarif"
    )

    tleg = st.slider(
        "Ratio Tarif Standard Grab/TB Thal",
        min_value=0.20,
        max_value=1.00,
        value=0.50,
        step=0.05,
        key="tleg",
        help="0.50 = Grab Tarif: 50% TB Thal Tarif"
    )

    VG = st.slider(
        "Vergütungstarif (Rp./kWh)",
        min_value=0.0,
        max_value=15.0,
        value=6.0,
        step=0.5,
        key="VG",
    )

# --- RLEG ---
with st.sidebar.expander("Restüberschuss", expanded=True):
    RLEG = st.slider(
        "davon % der Privat LEG Kunden",
        min_value=0,
        max_value=90,
        value=50,
        step=10,
        key="RLEG",
        help="50 = 50% des Restüberschusses für Privat LEG Kunden",
    )

# --- Thème ---
with st.sidebar.expander("Tagesprofil ", expanded=True):
    topic = st.selectbox(
        "Thema auswählen",
        themes_liste,
        index=themes_liste.index(topic_default) if topic_default in themes_liste else 0,
        key="topic_select",
    )

# --- Période & heure ---
with st.sidebar.expander("🕒 Auswertungszeitraum", expanded=True):
    mo = st.selectbox(
        "Monat auswählen",
        mois_liste,
        index=mois_liste.index(mo_default) if mo_default in mois_liste else 0,
        key="mois_select",
    )

    heure_debut, heure_fin = st.slider(
        "Stunden auswählen",
        min_value=0,
        max_value=23,
        value=(5, 20),
        step=1,
        key="heure_range",
    )

if heure_debut > heure_fin:
    heure_debut, heure_fin = heure_fin, heure_debut

H1 = f"{int(heure_debut):02d}:00"
H2 = f"{int(heure_fin):02d}:00"


abbr = dico.get(topic, "Abréviation inconnue")
if abbr == "Abréviation inconnue":
    st.sidebar.warning("Abréviation inconnue pour ce thème.\nVérifiez le fichier Excel.")

# ========================= PARAMÈTRES SUPPL. – SIMULATION 15 ANS =========================
st.sidebar.markdown("### 💰 Wirtschaftliche Simulation - 10Jahre + ")


PK_default     = 5_000            # Projektkostten bestehend aus Kundenprojekt und Infrastrukturprojekt
PVrealisierung = 1_000            # Infrastrukturprojekt (zum Beispiel Offerteanfrage für PV)
ES_default     = 0.20
Sa_default     = 0.20
Un_rate        = 3 / 1000
N_YEARS        = 15



with st.sidebar.expander("Annuitäten", expanded=True):
   

    # --- Valeur par défaut basée sur Pp ---
    IK_default_sim = int(1000 * Pp)

    # --- Initialisation ---
    if "IK_sim" not in st.session_state:
        st.session_state["IK_sim"] = IK_default_sim

    # --- Synchronisation automatique ---
    if st.session_state["IK_sim"] != IK_default_sim:
        st.session_state["IK_sim"] = IK_default_sim

    # --- NUMBER INPUT IK ---
    IK_sim = st.number_input(
    "Investition PV (CHF) – 15 Jahre",
    min_value=10_000,
    max_value=200_000,
    step=5_000,
    key="IK_sim",
    format="%d"
    )
    st.caption('Als Standardwert wird eine Investition von 1’000 CHF/kWp angenommen')

    P_sim = st.slider(
        "Abschreibungsdauer (Jahre)",
        min_value=5,
        max_value=25,
        value=10,
        step=1,
        key="P_sim",
    )
    z_sim = st.slider(
        "Zinssatz (%)",
        min_value=0.0,
        max_value=5.0,
        value=1.0,
        step=0.25,
        key="z_sim",
    )

with st.sidebar.expander("Tarife & Kosten (15 Jahre)", expanded=True):
    
    tevu_sim = st.slider(
        "Tarifentwicklung TB Thal  p.a.",
        min_value=0.0,
        max_value=0.05,
        value=0.02,
        step=0.005,
        key="tevu_sim",
    )

    st.caption("Betriebskosten: 2 Rp./kWh bei Verkauf an Dritte (nicht parametrierbar)")
    tbet_sim = 0.02

    st.caption("Jährlicher PV Verlust: fix 0.5 % (nicht parametrierbar)")
    pr_sim = -0.005

    st.caption("Steuersatz: 20 % (nicht parametrierbar)")

# conversions
SV_sim = 322 * Pp
r_sim  = z_sim / 100.0
tgra_change = tevu_sim
tleg_change = tevu_sim

st.sidebar.markdown("---")
st.sidebar.markdown("### Simulation – Parameterübersicht")

st.sidebar.write(f"📐 **Peak Power** : {Pp:.0f} kWp")
st.sidebar.write(f"💰 **Investition PV** : {IK_sim:,.0f} CHF".replace(",", "’"))
st.sidebar.write(f"🎯 **Abschreibungsdauer** : {P_sim} ans")
st.sidebar.write(f"📈 **Tarifentwicklung** : {tevu_sim*100:.1f} % / an")
st.sidebar.write(f"🧾 **Subvention** : {SV_sim:,.0f} CHF".replace(",", "’"))


#======================================
#        LADEN ROHDATEN – Erstes Jahr 
#======================================

# ========================= Meteo =======================
Station = "Altenrhein"
Year    = "Year 2024"

df_meteo = load_meteosuisse(BASE_DIR)

index = pd.date_range(start="2024-01-01 00:00", end="2024-12-31 23:00", freq="h")
dt = pd.DataFrame(index=index)
dt["Irradiance"] = df_meteo["Irradiance"].values
Totaldt = dt["Irradiance"].sum()

dt["Irradiance"] = dt["Irradiance"] * Wf * Pp / Totaldt
dt = dt.round(0)
dt = dt.rename(columns={"Irradiance": "kWh_Solar"})

monthly_solar = dt["kWh_Solar"].resample("ME").sum()
monthly_solar.index = monthly_solar.index.strftime("%b")
df_solar = monthly_solar.reset_index()
df_solar.columns = ["Monat", "kWh_Solar"]

# --- Eugster ---
dE = load_entnahme_eugster(BASE_DIR)
dE["Zeitstempel"] = pd.to_datetime(dE["Zeitstempel"], errors="coerce")
dE["Wert [kWh]"]   = pd.to_numeric(dE["Wert [kWh]"], errors="coerce")
dE = dE.rename(columns={"Wert [kWh]": "kWh_EVU_Eugster", "Zeitstempel": "dateTime"})
dE.set_index("dateTime", inplace=True)

dE_h = dE.resample("h").agg({"kWh_EVU_Eugster": lambda x: x.sum() * 1})
dE_h = dE_h[dE_h.index < pd.to_datetime("2025-1-1 00:00")]

dE_h["kWh_Solar"] = (dt["kWh_Solar"].values) * (1 + pr) ** (Jahr - 1)
kWh_Solar = round(dE_h["kWh_Solar"].sum(), 0)

# --- Grab ---
dG = load_grab(BASE_DIR)
dG = dG.dropna(subset=[0]).sort_values(0).set_index(0)
dG_extended = dG.reindex(dE_h.index, fill_value=0)
dE_h["kWh_EV Grab"] = dG_extended

# --- Tarife EVU / Grab / Privat / LEG ---

dates = pd.date_range(start="2024-01-01 00:00", periods=168, freq="h")
dt_tarif = load_tarif_table(BASE_DIR)

end_date   = "2024-12-31 23:00"
total_hours = int((pd.to_datetime(end_date) - dates[0]).total_seconds() / 3600) + 1

dt_tarif = pd.concat([dt_tarif] * ((total_hours + 164) // len(dt_tarif)), ignore_index=True)
dt_tarif = dt_tarif.iloc[:total_hours]
timeframe = pd.date_range(start="2024-01-01 00:00", end="2024-12-31 23:00", freq="h")
dt_tarif.insert(0, "timeframe", timeframe)
dt_tarif = dt_tarif.dropna(subset=["timeframe"]).sort_values("timeframe").set_index("timeframe")

(
    TZ1E, TZ2E, TZ1H, TZ2H, TZ1EP, TZ2EP, TZ1HP, TZ2HP,
    DE1, DE2, DH11, DH12, DH21, DH22, Tnetz
) = load_tarif_workbook_values(BASE_DIR)

# EVU Pro
dt_tarif.loc[(dt_tarif.index >= DE1) & (dt_tarif.index <= DE2) & (dt_tarif["Tarif"] == '"TZ2"'), "Tarif"] = TZ2E
dt_tarif.loc[(dt_tarif.index >= DE1) & (dt_tarif.index <= DE2) & (dt_tarif["Tarif"] == '"TZ1"'), "Tarif"] = TZ1E
dt_tarif.loc[(dt_tarif.index >= DH11) & (dt_tarif.index <= DH12) & (dt_tarif["Tarif"] == '"TZ2"'), "Tarif"] = TZ2H
dt_tarif.loc[(dt_tarif.index >= DH11) & (dt_tarif.index <= DH12) & (dt_tarif["Tarif"] == '"TZ1"'), "Tarif"] = TZ1H
dt_tarif.loc[(dt_tarif.index >= DH21) & (dt_tarif.index <= DH22) & (dt_tarif["Tarif"] == '"TZ2"'), "Tarif"] = TZ2H
dt_tarif.loc[(dt_tarif.index >= DH21) & (dt_tarif.index <= DH22) & (dt_tarif["Tarif"] == '"TZ1"'), "Tarif"] = TZ1H

dE_h["Tarif CHF"] = pd.to_numeric(
    dt_tarif["Tarif"].reindex(dE_h.index),
    errors="coerce"
)
dt_base = dt_tarif.copy()

# Tarif Grab Pro
TZ1EG = tt * TZ1E
TZ2EG = tt * TZ2E
TZ1HG = tt * TZ1H
TZ2HG = tt * TZ2H

dt_G = dt_base.copy()
dt_G.loc[(dt_G.index >= DE1) & (dt_G.index <= DE2) & (dt_G["Tarif"] == TZ2E), "Tarif"]   = TZ2EG
dt_G.loc[(dt_G.index >= DE1) & (dt_G.index <= DE2) & (dt_G["Tarif"] == TZ1E), "Tarif"]   = TZ1EG
dt_G.loc[(dt_G.index >= DH11) & (dt_G.index <= DH12) & (dt_G["Tarif"] == TZ2H), "Tarif"] = TZ2HG
dt_G.loc[(dt_G.index >= DH11) & (dt_G.index <= DH12) & (dt_G["Tarif"] == TZ1H), "Tarif"] = TZ1HG
dt_G.loc[(dt_G.index >= DH21) & (dt_G.index <= DH22) & (dt_G["Tarif"] == TZ2H), "Tarif"] = TZ2HG
dt_G.loc[(dt_G.index >= DH21) & (dt_G.index <= DH22) & (dt_G["Tarif"] == TZ1H), "Tarif"] = TZ1HG

dE_h["Tarif CHF_G"] = pd.to_numeric(
    dt_G["Tarif"].reindex(dE_h.index),
    errors="coerce"
)

# Tarif EVU Privat
# Netz Tarif
dt_P = dt_base.copy()
dt_P.loc[(dt_P.index >= DE1) & (dt_P.index <= DE2) & (dt_P["Tarif"] == TZ2E), "Tarif"] = TZ2EP
dt_P.loc[(dt_P.index >= DE1) & (dt_P.index <= DE2) & (dt_P["Tarif"] == TZ1E), "Tarif"] = TZ1EP
dt_P.loc[(dt_P.index >= DH11) & (dt_P.index <= DH12) & (dt_P["Tarif"] == TZ2H), "Tarif"] = TZ2HP
dt_P.loc[(dt_P.index >= DH11) & (dt_P.index <= DH12) & (dt_P["Tarif"] == TZ1H), "Tarif"] = TZ1HP
dt_P.loc[(dt_P.index >= DH21) & (dt_P.index <= DH22) & (dt_P["Tarif"] == TZ2H), "Tarif"] = TZ2HP
dt_P.loc[(dt_P.index >= DH21) & (dt_P.index <= DH22) & (dt_P["Tarif"] == TZ1H), "Tarif"] = TZ1HP

dE_h["Tarif CH_P"] = pd.to_numeric(dt_P["Tarif"].reindex(dE_h.index),errors="coerce")


# Tarif Grab Standard
dE_h["Tarif LEG"] = tleg * dE_h["Tarif CH_P"]


#=============================================
#  ERGEBNISSE DES ERSTEN BETRIEBSJAHRES
#=============================================

# Die Solarenergieerzeugung der Photovoltaikmodule kann x Jahre nach der Inbetriebnahme geschätzt werden (verlust pr per annum)
# Die daraus abgeleiteten Variablen werden entsprechend angepasst.
JahrX = 1
dE_h["kWh_Solar"] = (dt["kWh_Solar"].values) * (1 + pr) ** (JahrX - 1)
kWh_Solar = round(dE_h["kWh_Solar"].sum(), 0)

# EVUECHF: Rechnung EVU an Eugster ohne Stromlieferung von Grab
dE_h["CHF_EVU_Eugster"] = dE_h["kWh_EVU_Eugster"] * dE_h["Tarif CHF"]
EVUEKW                  = round(dE_h["kWh_EVU_Eugster"].sum(), 0)
EVUECHF                 = round(dE_h["CHF_EVU_Eugster"].sum(), 0)

# EVUGCH: Rechnung EVU an Grab ohne PV
dE_h["CHF_EVU_Grab"]    = dE_h["kWh_EV Grab"] * dE_h["Tarif CH_P"]
EVUGCH                  = round(dE_h["CHF_EVU_Grab"].sum(), 0)

# UG: Überschuss Grab
dE_h["UG"]      = dE_h["kWh_Solar"] - dE_h["kWh_EV Grab"]
dE_h["UG1"]     = dE_h["UG"].clip(lower=0)
monthly_sum_UG1 = dE_h["UG1"].resample("ME").sum()
UG              = round(dE_h["UG1"].sum(), 0)

# EIG:  PV Eigenverbrauch Grab
dE_h["EIG"]     = dE_h["kWh_Solar"]-dE_h["UG1"] 
EIG             = dE_h["EIG"].sum()


# EVUGSCH: Rechnung EVU → Grab mit PV
dE_h["EVUGSKWH"] = -dE_h["UG"].mask(dE_h["UG"] > 0, 0)
dE_h["EVUGSCHF"] = dE_h["EVUGSKWH"] * dE_h["Tarif CH_P"]
EVUGSCH          = round(dE_h["EVUGSCHF"].sum(),0)

#print("EVUGCH=",EVUGCH, "EVUGSCH=", EVUGSCH, "EIG=",EIG,"tarif=",(EVUGCH-EVUGSCH)/EIG)

# Rest_U: Restüberschuss nach Lieferung Grab → Eugster
dE_h["Rest_U"]     = (dE_h["UG1"] - dE_h["kWh_EVU_Eugster"]).clip(lower=0)
monthly_sum_RestU  = dE_h["Rest_U"].resample("ME").sum()
RestU              = round(dE_h["Rest_U"].sum(), 0)
print("RestU=",RestU)

# GE: Energielieferung Grab → Eugster (kWh)
dE_h["kWh_Grab_Eugster"] = dE_h["UG1"] - dE_h["Rest_U"]
monthly_sum_GE = dE_h["kWh_Grab_Eugster"].resample("ME").sum()
GE = round(dE_h["kWh_Grab_Eugster"].sum(), 0)

# G1: Rechnung  Grab → Eugster 
dE_h["GewinnGrab"] = dE_h["kWh_Grab_Eugster"] * dE_h["Tarif CHF_G"]
monthly_sum_P1 = dE_h["GewinnGrab"].resample("ME").sum()
G1 = round(dE_h["GewinnGrab"].sum(), 0)

# G2: Rechnung Grab  Standard Kunden
dE_h["kWh_LEG"] = RLEG / 100 * dE_h["Rest_U"]
ULEG = round(dE_h["kWh_LEG"].sum(), 0)
dE_h["CHF_LEG"] = dE_h["kWh_LEG"] * dE_h["Tarif LEG"]
G2 = round(dE_h["CHF_LEG"].sum(), 0)

# Ver_U: Verbleibender Überschuss nach Lieferung an Eugster und LEG Kunden
dE_h["V_U"] = (1 - RLEG / 100) * dE_h["Rest_U"]
Ver_U = round(dE_h["V_U"].sum(), 0)

# G3 Vergütung Verbeibender Überschuss 
G3 = round(Ver_U * VG / 100, 0)

# EVUGE: EVU Energie Lieferung an Eugster als Ergänzung zur Grab Energie Lieferung
dE_h["kWh_EVU_Grab_Eugster"] = dE_h["kWh_EVU_Eugster"] - dE_h["kWh_Grab_Eugster"]
monthly_sum_EVUGE = dE_h["kWh_EVU_Grab_Eugster"].resample("ME").sum()
EVUGE = round(dE_h["kWh_EVU_Grab_Eugster"].sum(), 0)

# EVUGECH: EVU Rechung an Eugster als Ergänzung zur Grab Energie Lieferung
dE_h["CHF-EVU-Grab_Eugster"] = dE_h["kWh_EVU_Grab_Eugster"] * dE_h["Tarif CHF"]
EVUGECH = round(dE_h["CHF-EVU-Grab_Eugster"].sum(), 0)

# Gewinn
GewinnE = EVUECHF - EVUGECH - G1             # Gewinn Eugster
GewinnG = EVUGCH - EVUGSCH + G1 + G2 + G3    # Gewinn Grab

#==============#
# ✅    LEG
#==============#

# Tarifgrenze Standard vEVG, LEG 40%(2), LEG 20% Rabatte (3)
lg0     = round(TZ1EP*Tnetz*tt,2)                # vZEV oder vEVG
lg1     =round((TZ1EP-(60/100)*Tnetz)*tt,2)      # LEG 40% Rabatte
lg2     =round ((TZ1EP-(80/100)*Tnetz)*tt,2)     # LEG 20% Rabatte

# tleg max
tleg0max=1.0
tleg1max=1.0-0.6*Tnetz/TZ1EP
tleg2max=1.0-0.8*Tnetz/TZ1EP

# Gewin in % Standard LEG Kunden  

Gewinnleg0 = round(TZ1EP * (1.0 - tleg),2)
Gewinnleg0 = Gewinnleg0 if Gewinnleg0 >= 0 else np.nan

Gewinnleg1 = round(Gewinnleg0 - 0.6 * Tnetz,2)
Gewinnleg1 = Gewinnleg1 if Gewinnleg1 >= 0 else np.nan

Gewinnleg2   = round(Gewinnleg0 - 0.8 * Tnetz,2)   
Gewinnleg2   = Gewinnleg2 if Gewinnleg2 >= 0 else np.nan
GewinnPrivat = round(TZ1EP-VG/100-0.8*Tnetz,2)



# ========================= FONCTION ANALYSE ROHDATEN =========================

def run_analysis(mo: str, topic: str, abbr: str, H1: str, H2: str):
    if abbr not in dE_h.columns:
        st.error(f"❌ La colonne '{abbr}' n'existe pas dans les données. Choisissez un autre thème.")
        return None, None, None

    mois_map = {
        "Januar": 1, "Februar": 2, "März": 3, "April": 4,
        "Mai": 5, "Juni": 6, "Juli": 7, "August": 8,
        "September": 9, "Oktober": 10, "November": 11, "Dezember": 12
    }

    dE_h["month"] = dE_h.index.month
    dE_hs = {i: dE_h[dE_h["month"] == i] for i in range(1, 13)}

    i = mois_map[mo]

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
        labels={"Heure": "Stunden", "Valeur": "kWh"},
        title=f"{topic} – Tagesprofil ({mo}) [{H1}–{H2}]"
    )
    fig1.update_layout(
        xaxis=dict(dtick=1),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=16)),
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
        title="Überschuss Grab & Restüberschuss"
    )
    fig2.update_layout(
        xaxis=dict(dtick=1),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=16)),
        margin=dict(t=60, b=40, l=40, r=10),
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
        xaxis=dict(dtick=1),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=16)),
        margin=dict(t=60, b=40, l=40, r=10),
        title_font=dict(size=20),
    )

    return fig1, fig2, fig3


# =========================      FONCTION DE PROJECTION 15 ANS =========================

def compute_projection(
    val_EVUECHF, val_EVUGCH, val_UG,
    IK, Pp, P, z, r, ES, Sa, SV,
    PK, Un_rate, tevu, tgra, tleg, tbet, pr,
    N_YEARS, VG, val_EVUGECH, val_EVUGSCH,
    val_G1, val_G2, val_G3, val_GE, val_RestU, val_EIG,
):

    Jahre = range(1, N_YEARS + 1)
    df = pd.DataFrame(index=Jahre)
    df.index.name = "Jahr"

    # ================================
    # ✅ Construction des coefficients a, b, c dans dr
    # ================================
    for col in du.columns:
        y = du[col].values.astype(float)
        a, b, c = np.linalg.solve(A, y)
        dr.loc["a", col] = a
        dr.loc["b", col] = b
        dr.loc["c", col] = c

    # ================================
    # ✅ Fonction sécurisée d'évaluation
    # ================================
    def y_for_x(dr_local, col_name, x_val):

        if col_name not in dr_local.columns:
            raise ValueError(f"❌ Colonne inexistante dans dr : {col_name}")

        if not all(k in dr_local.index for k in ["a", "b", "c"]):
            raise ValueError("❌ dr doit contenir les lignes 'a', 'b', 'c'")

        a = float(dr_local.loc["a", col_name])
        b = float(dr_local.loc["b", col_name])
        c = float(dr_local.loc["c", col_name])

        return a * x_val**2 + b * x_val + c

   
    # ================================
    # ✅ NORMALISATION DES GRANDEURS
    # ================================

    # --- EVUECHF ---
    PW_EVUECHF = [EVUECHF * ((1 + tevu) ** (jahr - 1)) for jahr in Jahre]

    # ----EVUGCH ---
    PW_EVUGCH  = [EVUGCH * ((1 + tevu) ** (jahr - 1)) for jahr in Jahre]

    # --- G1 ---
    G1_ref = y_for_x(dr, "G1", 1)
    scale_G1 = val_G1 / G1_ref if G1_ref != 0 else 0

    PW_G1 = [
        scale_G1 * y_for_x(dr, "G1", jahr) * ((1 + tgra) ** (jahr - 1))
        for jahr in Jahre
    ]

    # --- G2 ---
    G2_ref = y_for_x(dr, "G2", 1)
    scale_G2 = val_G2 / G2_ref if G2_ref != 0 else 0

    PW_G2 = [
        scale_G2 * y_for_x(dr, "G2", jahr) * ((1 + tleg) ** (jahr - 1))
        for jahr in Jahre
    ]

    # --- G3 ---
    G3_ref = y_for_x(dr, "G3", 1)
    scale_G3 = val_G3 / G3_ref if G3_ref != 0 else 0

    PW_G3 = [
        scale_G3 * y_for_x(dr, "G3", jahr) * ((1 + VG / 100) ** (jahr - 1))
        for jahr in Jahre
    ]

    # --- EVUGSCH ---
    EVUGSCH_ref = y_for_x(dr, "EVUGSCH", 1)
    scale_EVUGSCH = val_EVUGSCH / EVUGSCH_ref if EVUGSCH_ref != 0 else 0

    PW_EVUGSCH = [
        scale_EVUGSCH * y_for_x(dr, "EVUGSCH", jahr) * ((1 + tevu) ** (jahr - 1))
        for jahr in Jahre
    ]

    # --- EVUGECH ---
    EVUGECH_ref = y_for_x(dr, "EVUGECH", 1)
    scale_EVUGECH = val_EVUGECH / EVUGECH_ref if EVUGECH_ref != 0 else 0

    PW_EVUGECH = [
        scale_EVUGECH * y_for_x(dr, "EVUGECH", jahr) * ((1 + tevu) ** (jahr - 1))
        for jahr in Jahre
    ]

    # --- GE 
    GE_ref = y_for_x(dr, "GE", 1)
    scale_GE = val_GE / GE_ref if GE_ref != 0 else 0

    PW_GE = [
        scale_GE * y_for_x(dr, "GE", jahr)
        for jahr in Jahre
    ]

    # --- RestU
    RestU_ref = y_for_x(dr, "RestU", 1)
    scale_RestU = val_RestU/ RestU_ref if RestU_ref != 0 else 0

    PW_RestU = [
        scale_RestU * y_for_x(dr, "RestU", jahr)
        for jahr in Jahre
    ]

    # --- EIG
    EIG_ref = y_for_x(dr, "EIG", 1)
    scale_EIG = val_EIG/ EIG_ref if EIG_ref != 0 else 0

    PW_EIG = [
        scale_EIG * y_for_x(dr, "EIG", jahr)
        for jahr in Jahre
    ]

    #---- Pp
    PW_Pp = [Pp*(1+pr)**jahr for jahr in Jahre]

    # ================================
    # ✅ Construction du DataFrame
    # ================================
    df["EVUECHF"]  = PW_EVUECHF
    df["EVUGCH"]   = PW_EVUGCH
    df["EVUGSCH"]  = PW_EVUGSCH
    df["EVUGECH"]  = PW_EVUGECH
    df["G1"]       = PW_G1
    df["G2"]       = PW_G2
    df["G3"]       = PW_G3
    df["GE"]       = PW_GE
    df["RestU"]    = PW_RestU
    df["EIG"]      = PW_EIG
    df["Pp"]       = PW_Pp

    df = df.round(0).reset_index()

    # ================================
    # ✅ Résultats économiques
    # ================================
    df["UmsatzG"]     = df["EVUGCH"] - df["EVUGSCH"] + df["G1"] + df["G2"] + df["G3"]
    df["Cash in"]     = df["G1"] + df["G2"] + df["G3"]

    # ================================
    # ✅ Tableau d’amortissement
    # ================================
    def tableau_amortissement(C, P, r):
        capital = C
        amort_base = C / P
        data = []

        for jahr in range(1, P + 1):
            zins = capital * r
            ann = amort_base + zins
            capital -= amort_base
            data.append([jahr, capital, zins, ann])

        dc = pd.DataFrame(data, columns=["Jahr", "Kapital_rest", "Zins", "Annuität"])
        return dc

    dc = tableau_amortissement(IK + PK - SV, P, r).round(0)

    df = df.merge(dc[["Jahr", "Annuität", "Zins", "Kapital_rest"]],
                  on="Jahr", how="left")

    df["Annuität"] = df["Annuität"].fillna(0)
    df["Zins"]     = df["Zins"].fillna(0)

    # ================================
    # ✅ Charges, impôts, profits
    # ================================
    df["Steuerabzug"] = 0.0
    if 2 in df["Jahr"].values:
        df.loc[df["Jahr"] == 2, "Steuerabzug"] = (IK + PK - SV) * ES

    df["Betrieb"]   = (df["GE"] + df["RestU"] * (RLEG/100))*tbet
    df["Unterhalt"] = Un_rate * IK

    df["Kosten"] = df["Annuität"] + df["Unterhalt"] + df["Betrieb"]

    df["Steuer"] = ((df["Cash in"] - df["Zins"] - df["Betrieb"] - df["Unterhalt"]- df["EVUGSCH"]) * Sa).clip(lower=0)

    df["Profit_Grab"]      = df["UmsatzG"] + df["Steuerabzug"] - df["Kosten"] - df["Steuer"]
    df["Cumulate_Grab"]    = df["Profit_Grab"].cumsum()

    df["Profit_Eugster"]   = df["EVUECHF"] - df["EVUGECH"] - df["G1"]
    df["Cumulate_Eugster"] = df["Profit_Eugster"].cumsum()
    df["Cumulate_Cash_in"] = df["Cash in"].cumsum()

    # ==========================================
    # ✅ Aufschlüsselung pro kWh (nach 10 Jahre)
    # ==========================================
    # Cumul à 10 ans
    df["Cumulate_Unterhalt"] = df["Unterhalt"].cumsum()
    df["Cumulate_Zins"]      = df["Zins"].cumsum()
    df["Cumulate_Steuer"]    = df["Steuer"].cumsum()
    df["Cumulate_Betrieb"]   = df["Betrieb"].cumsum()
    df["Cumulate_RestU"]     = df["RestU"].cumsum()           # gelieferte Energie an LEG Kunden
    df["Cumulate_GE"]        = df["GE"].cumsum()             # gelieferte Energie an Eugster
    df["Cumulate_G1"]        = df["G1"].cumsum()             # Rechnung an Eugster
    df["Cumulate_G2"]        = df["G2"].cumsum()             # Rechnung an LEG Kunden
    df["Cumulate_G3"]        = df["G3"].cumsum()             # Vergütung von EVU an Eugster
    df["Cumulate_EVUGSCH"]   = df["EVUGSCH"].cumsum()        # Rechnung EVU an Grab mit PV
    df["Cumulate_EVUGCH"]    = df["EVUGCH"].cumsum()         # Rechnung EVU an Grab ohne PV
    df["Cumulate_EIG"]       = df["EIG"].cumsum()            # PV Eigenverbrauch Grab
    df["Cumulate_Pp"]        = df["Pp"].cumsum()             # Peak Power

    row10 = df.loc[df["Jahr"] == 10]
    if row10.empty:
        raise ValueError("Jahr 10 n'existe pas dans df (N_YEARS doit être >= 10).")

    Unterhalt_10 = float(row10["Cumulate_Unterhalt"].iloc[0])
    Zins_10      = float(row10["Cumulate_Zins"].iloc[0])
    Steuer_10    = float(row10["Cumulate_Steuer"].iloc[0])
    Betrieb_10   = float(row10["Cumulate_Betrieb"].iloc[0])
    RestU_10    = float(row10["Cumulate_RestU"].iloc[0])
    GE_10        = float(row10["Cumulate_GE"].iloc[0])
    G1_10        = float(row10["Cumulate_G1"].iloc[0])
    G2_10        = float(row10["Cumulate_G2"].iloc[0])
    G3_10        = float(row10["Cumulate_G3"].iloc[0])
    EVUGSCH_10   = float(row10["Cumulate_EVUGSCH"].iloc[0])
    EVUGCH_10    = float(row10["Cumulate_EVUGCH"].iloc[0])
    EIG_10       = float(row10["Cumulate_EIG"].iloc[0])
    Pp_10        = float(row10["Cumulate_Pp"].iloc[0])

    # Energie 10 ans 
    energie_10 = Wf*Pp_10

    # Verbleibender Überschuss
    Ver_U_10 =(1-RLEG/100)*RestU_10   
    ULEG_10  =RLEG/100*RestU_10                                                                  

    # Gestehungskosten (10 ans)
    kosten_10 = (IK + PVrealisierung - SV) * (1 - ES) + Unterhalt_10
    GKosten   = kosten_10 / energie_10

    # Summe Cash
    SC = G1_10 + G2_10 + G3_10

    # Zins PV (Schätzung)
    Zins_PV=Zins_10*(IK-SV+PVrealisierung)/((IK-SV+PK)*energie_10)

    # Zins Projekt Kunde
    Zins_K=Zins_10*(PK-PVrealisierung)/((IK-SV+PK)*(GE_10+ULEG_10))

    # Steuer
    Steuer_RU  =(Steuer_10*G3_10/SC)/Ver_U_10
    Steuer_E   =(Steuer_10*G1_10/SC)/GE_10
    if ULEG_10 > 0 and SC != 0:
        Steuer_LEG = (Steuer_10 * G2_10 / SC) / ULEG_10
    else:
        Steuer_LEG = 0.0

   
    # Eigenverbrauch
    # pro kWh
    DEII = 0.0                                               # Indirekte Kosten/kWh                                # Selbstkosten/kWh
    DEIV = (EVUGCH_10 - EVUGSCH_10) / EIG_10                 # Verkaufskosten/kWh                                     
    DEIZ = Zins_PV                                           # Zins/kWh
    DEIS = 0.0                                               # Steuer/kWh
    # Gewinn Total
    UmE= EVUGCH_10 - EVUGSCH_10
    GwE = UmE- (GKosten+DEII+DEIZ+DEIS)*EIG_10                                                       
                                      

    # Restüberschuss
    # pro kWh
    DRUI = 0.0
    DRUV = VG/100
    DRUZ = Zins_PV
    DRUS = Steuer_RU
    # Gewinn Total
    UmRU = VG*Ver_U_10/100
    GwRU = UmRU -(GKosten+DRUI+DRUZ+DRUS)*Ver_U_10

    # Eugster
    # pro kWh
    DEGI = tbet + (PK - PVrealisierung) * G1_10 / ((G1_10 + G2_10)* GE_10)
    DEGV = G1_10 / GE_10
    DEGZ = Zins_PV + Zins_K
    DEGS = Steuer_E
    # Gewinn Total
    UmEG = G1_10 
    GwEG = UmEG-(GKosten+DEGI+DEGZ+DEGS)*GE_10

    #LEG Standard
    # pro kWh
    if ULEG_10 > 0:  
        denom = (G1_10 + G2_10)
        if denom != 0:
            DELI = (tbet + (PK - PVrealisierung) * (G2_10 / denom)) / ULEG_10
        else:
            DELI = 0.0
        DELV = G2_10 / ULEG_10
    else:
        DELI = 0.0
        DELV = 0.0
    DELZ = Zins_PV+Zins_K
    DELS = Steuer_LEG
    #Gewinn Total
    UmEL=G2_10
    GwEL=UmEL-(GKosten+DELI+DELZ+DELS)*ULEG_10 


    kwh10 = {
        "GKosten": float(GKosten), "kosten_10" : float(kosten_10), 
        "DEII": float(DEII), "DEIV": float(DEIV), "DEIZ": float(DEIZ), "DEIS": float(DEIS),
        "DRUI": float(DRUI), "DRUV": float(DRUV), "DRUZ": float(DRUZ), "DRUS": float(DRUS),
        "DEGI": float(DEGI), "DEGV": float(DEGV), "DEGZ": float(DEGZ), "DEGS": float(DEGS),
        "DELI": float(DELI), "DELV": float(DELV), "DELZ": float(DELZ), "DELS": float(DELS),
        "UmE":float(UmE), "GwE":float(GwE), "UmRU": float(UmRU), "GwRU":float(GwRU), "UmEG": float(UmEG), "GwEG": float(GwEG), 
        "UmEL":float(UmEL),"GwEL":float(GwEL),
    }

    return df, kwh10
    

# ========================= CALCUL SIMULATION 15 ANS =========================

df_15, kwh10 = compute_projection(
    val_EVUECHF=EVUECHF,
    val_EVUGCH=EVUGCH,
    val_UG=UG,

    IK=IK_sim,
    Pp=Pp,
    P=P_sim,
    z=z_sim,
    r=r_sim,
    ES=ES_default,
    Sa=Sa_default,
    SV=SV_sim,

    PK=PK_default,
    Un_rate=Un_rate,

    tevu=tevu_sim,
    tgra=tgra_change,
    tleg=tleg_change,
    tbet=tbet_sim,
    pr=pr_sim,

    N_YEARS=N_YEARS,
    VG=VG,

    val_EVUGECH=EVUGECH,
    val_EVUGSCH=EVUGSCH,

    val_G1=G1,
    val_G2=G2,
    val_G3=G3,

    val_GE=GE,
    val_RestU=RestU,
    val_EIG=EIG
)

df_10 = df_15[df_15["Jahr"] <= 10].copy()

if len(df_10) > 0:
    kpi_grab_10     = df_10["Cumulate_Grab"].iloc[-1]
    kpi_grab_15     = df_15["Cumulate_Grab"].iloc[-1]
    kpi_eugster_10  = df_10["Cumulate_Eugster"].iloc[-1]
else:
    kpi_grab_10 = kpi_grab_15 = kpi_eugster_10 = np.nan

if not np.isnan(kpi_grab_10) and IK_sim > 0:
    kpi_rendite_10 = (1 + kpi_grab_10 / (IK_sim + PK_default)) ** (1/10) - 1
else: 
    kpi_rendite_10 = np.nan

if not np.isnan(kpi_grab_15) and IK_sim > 0:
    kpi_rendite_15 = (1 + kpi_grab_15 / (IK_sim + PK_default)) ** (1/15) - 1
else:
    kpi_rendite_15 = np.nan

# ========================= LAYOUT AVEC ONGLET ROHDATEN / 15 ANS =========================

tab_roh, tab_sim = st.tabs([
    "📊 Bruttodaten des ersten Betriebsjahres",
    "📈 15-Jahre Wirtschaftssimulation",
])

# ---------- ONGLET ROHDATEN ----------
with tab_roh:
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
            st.metric("Nettogewinn Eugster", f"{indic4:,.0f} CHF".replace(",", "’"))
            st.markdown('</div>', unsafe_allow_html=True)

        with colp5:
            st.markdown('<div class="metric-card metric-chf">', unsafe_allow_html=True)
            st.metric("Bruttogewinn Grab", f"{indic5:,.0f} CHF".replace(",", "’"))
            st.markdown('</div>', unsafe_allow_html=True)

        subtab1, subtab2, subtab3, subtab4, subtab5 = st.tabs([
                "📈 Tagesprofil",
                "📊 Überschuss (monatlich)",
                "⚡  Stromverbrauch Eugster(monatlich)",
                "📑 Jahresergebnis",
                "👤 Privatkunden",
        ])

        with subtab1:
            st.plotly_chart(fig1, use_container_width=True)

        with subtab2:
            st.plotly_chart(fig2, use_container_width=True)

        with subtab3:
            st.plotly_chart(fig3, use_container_width=True)

        # --- Tableaux économiques 
        with subtab4:
            t1 = [
                ["Struktur", "TB Thal Pro (CHF/kWh)", "Grab Pro (CHF/kWh)", "TB Thal Standard (CHF/kWh)", "Grab Standard (CHF/kWh)"],
                ["Tarifzeit 1 Sommer",  TZ1E,  TZ1EG,  TZ1EP, tleg * TZ1EP],
                ["Tarifzeit 2 Sommer",  TZ2E,  TZ2EG, TZ2EP, tleg * TZ2EP],
                ["Tarifzeit 1 Winter",  TZ1H,  TZ1HG, TZ1HP, tleg * TZ2HP],
                ["Tarifzeit 2 Winter",  TZ2H,  TZ2HG, TZ2HP, tleg * TZ2HP],
                ["Vergütung",           VG/100, np.nan, np.nan, np.nan],
            ]

            t2 = [
                ["Lieferung", "Betrag CHF"],
                ["EVU ohne Grab_Solar", EVUECHF],
                ["EVU mit Grab_Solar", EVUGECH],
                ["Grab_Solar", G1],
                ["Total mit Grab_Solar", EVUGECH + G1],
                ["Gewinn", EVUECHF - EVUGECH - G1],
            ]

            t3 = [
                ["Lieferung", "Betrag CHF"],
                ["EVU ohne Panels", EVUGCH],
                ["EVU mit Panel", EVUGSCH],
                ["Verkauf an Eugster", G1],
                ["Vergütung EVU", G2 + G3],
                ["Gewinn", EVUGCH - EVUGSCH + G1 + G2 + G3],
            ]

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
            st.markdown(
                f"**Pro Grab/ TB Thal : {tt:.2f}** &nbsp;&nbsp;&nbsp; "
                f"**Standard Grab/TB Thal: {tleg:.2f}**"
            )

            df_t1 = pd.DataFrame(t1[1:], columns=t1[0])
            df_t1_styled = (
                df_t1.style
                .set_table_styles(style_header)
                .set_properties(**common_cell_style)
                .format(
                    subset=[
                        "TB Thal Pro (CHF/kWh)",
                        "Grab Pro (CHF/kWh)",
                        "TB Thal Standard (CHF/kWh)",
                        "Grab Standard (CHF/kWh)"
                    ],
                    formatter="{:,.3f}".format,
                    na_rep=""
                )
            )
            st.table(df_t1_styled)

            st.markdown("---")

            col_left, col_right = st.columns(2)

            # Eugster - Jahresbilanz
            with col_left:
                st.subheader("Eugster – Jahresergebnis")

                df_t2 = pd.DataFrame(t2[1:], columns=t2[0]).copy()
                df_t2["Betrag CHF"] = pd.to_numeric(df_t2["Betrag CHF"], errors="coerce")

                evu_ohne = df_t2.loc[df_t2["Lieferung"] == "EVU ohne Grab_Solar", "Betrag CHF"].iloc[0]
                evu_mit = df_t2.loc[df_t2["Lieferung"] == "EVU mit Grab_Solar", "Betrag CHF"].iloc[0]
                grab_solar = df_t2.loc[df_t2["Lieferung"] == "Grab_Solar", "Betrag CHF"].iloc[0]
                total_mit = df_t2.loc[df_t2["Lieferung"] == "Total mit Grab_Solar", "Betrag CHF"].iloc[0]
                gain_val  = df_t2.loc[df_t2["Lieferung"] == "Gewinn", "Betrag CHF"].iloc[0]

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
                    xaxis=dict(tickmode="array", tickvals=x_vals_all, ticktext=ticktext, title=""),
                    yaxis=dict(title="CHF"),
                    legend=dict(
                        title="",
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="right",
                        x=1,
                        font=dict(size=20),
                    ),
                    margin=dict(t=20, b=40, l=40, r=10),
                    bargap=0.3,
                    height=400,
                )

                st.plotly_chart(fig_eugster, use_container_width=True)

            # Grab – Jahresbilanz
            with col_right:
                st.subheader("Grab – Jahresergebnis")

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
                base_mit = [0, col2, col2 + col3, col2 + col3 + col4]

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
                    textposition="outside",
                ))

                fig_grab.add_trace(go.Bar(
                    name="mit PV",
                    x=x_mit,
                    y=y_mit,
                    base=base_mit,
                    marker_color=colors_mit,
                    text=[fmt(v) for v in y_mit],
                    textposition="outside",
                ))

                fig_grab.update_layout(
                    barmode="overlay",
                    xaxis=dict(
                        tickmode="array",
                        tickvals=[1, 2, 3, 4, 5],
                        ticktext=["EVU", "EVU", "Verkauf Eugster", "Vergütung", "Gewinn"],
                        title="",
                    ),
                    yaxis=dict(title="CHF"),
                    legend=dict(
                        title="",
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="right",
                        x=1,
                        font=dict(size=20),
                    ),
                    margin=dict(t=20, b=40, l=40, r=10),
                    bargap=0.3,
                    height=400,
                )
                st.plotly_chart(fig_grab, use_container_width=True)

            with subtab5:
                    
                st.subheader("Privatkunden – Variantenvergleich")
                st.markdown(
                        f"""
            **Tarif TB Thal Standard :** {TZ1EP:.3f} CHF/kWh  
            **Tarif TB Grab Standard :** {(tleg * TZ1EP):.3f} CHF/kWh – Dieser Wert ist einstellbar mit dem Schieberegler «Ratio Tarif Standard»
            """
                )

                # 1) DF "calcul" (types numériques propres)
                df_privat = pd.DataFrame(
                    [
                        ["vEGB",     round(tleg * TZ1EP, 3), round(tleg0max * TZ1EP, 3), Gewinnleg0],
                        ["LEG 40%",  round(tleg * TZ1EP, 3), round(tleg1max * TZ1EP, 3), Gewinnleg1],
                        ["LEG 20%",  round(tleg * TZ1EP, 3), round(tleg2max * TZ1EP, 3), Gewinnleg2],
                        ["Privat",   np.nan,               np.nan,               GewinnPrivat],
                    ],
                    columns=[
                        "Variante",
                        "Standard Tarif Grab (CHF/kWh)",
                        "Maximaler anwendbarer Tarif (CHF/kWh)",
                        "Kundengewinn CHF/kWh",
                    ],
                )

                # 2) DF "affichage" (strings → plus d'erreur Arrow)
                df_show = df_privat.copy()

                def fmt_num(v, nd=3):
                    return "nicht anwendbar" if pd.isna(v) else f"{v:.{nd}f}"

                df_show["Standard Tarif Grab (CHF/kWh)"] = df_show["Standard Tarif Grab (CHF/kWh)"].map(lambda v: fmt_num(v, 3))
                df_show["Maximaler anwendbarer Tarif (CHF/kWh)"] = df_show["Maximaler anwendbarer Tarif (CHF/kWh)"].map(lambda v: fmt_num(v, 3))
                df_show["Kundengewinn CHF/kWh"] = df_show["Kundengewinn CHF/kWh"].map(lambda v: fmt_num(v, 3))

                # ✅ 3) Remplacement de use_container_width
                st.dataframe(df_show, hide_index=True, width="stretch")
    else:
      st.info("Ajustez les paramètres dans la barre latérale.")

# ---------- ONGLET SIMULATION 15 ANS ----------
def waterfall_kwh(title: str, gkosten: float, indirekt: float, verkauf: float, marge: float, gewinn: float):
    labels  = ["Gestehungskosten", "Indirekte Kosten", "Verkaufspreis", "Marge", "Gewinn"]
    y       = [gkosten, indirekt, verkauf, -marge, gewinn]
    measure = ["relative", "relative", "relative", "relative", "relative"]

    fig = go.Figure(
        go.Waterfall(
            name=title,
            orientation="v",
            x=labels,
            y=y,
            measure=measure,
            text=[f"{v:.4f}" for v in y],
            textposition="outside",
            increasing=dict(marker=dict(color="#0B2A5B")),
            decreasing=dict(marker=dict(color="#0B2A5B")),
            totals=dict(marker=dict(color="#0B2A5B")),
        )
    )
    fig.update_layout(
        title=title,
        showlegend=False,
        yaxis_title="CHF/kWh",
        margin=dict(t=60, b=40, l=40, r=10),
        height=380,
    )
    return fig

with tab_sim:
    st.markdown("### KPIs – Synthese 10 Jahre")

    df_10 = df_15[df_15["Jahr"] <= 10].copy()

    if len(df_10) > 0:
        kpi_grab_10    = df_10["Cumulate_Grab"].iloc[-1]
        kpi_grab_15    = df_15["Cumulate_Grab"].iloc[-1]
        kpi_eugster_10 = df_10["Cumulate_Eugster"].iloc[-1]
    else:
        kpi_grab_10 = kpi_grab_15 = kpi_eugster_10 = np.nan

    if not np.isnan(kpi_grab_10) and IK_sim > 0:
        kpi_rendite_10 = (1 + kpi_grab_10 / (IK_sim + PK_default)) ** (1/10) - 1
    else:
        kpi_rendite_10 = np.nan

    if not np.isnan(kpi_grab_15) and IK_sim > 0:
        kpi_rendite_15 = (1 + kpi_grab_15 / (IK_sim + PK_default)) ** (1/15) - 1
    else:
        kpi_rendite_15 = np.nan

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        st.metric("Peak Power", f"{Pp:.0f} kWp")
    with col2:
        st.metric("Investition Panels", f"{IK_sim:,.0f} CHF".replace(",", "’"))
    with col3:
        st.metric("Kumul. Ertrag Eugster (10 J.)", f"{kpi_eugster_10:,.0f} CHF".replace(",", "’") if not np.isnan(kpi_eugster_10) else "n/a")
    with col4:
        st.metric("Kumul. Ertrag Grab (10 J.)", f"{kpi_grab_10:,.0f} CHF".replace(",", "’") if not np.isnan(kpi_grab_10) else "n/a")
    with col5:
        st.metric("Rendite Grab (10 J.)", f"{kpi_rendite_10*100:,.1f} %".replace(",", "’") if not np.isnan(kpi_rendite_10) else "n/a")
    with col6:
        st.metric("Rendite Grab (15 J.)", f"{kpi_rendite_15*100:,.1f} %".replace(",", "’") if not np.isnan(kpi_rendite_15) else "n/a")

    st.markdown("---")

    sub1, sub2, sub3, sub4 = st.tabs([
        "📈 Erträge und Abschreibungen (1–10 Jahre)",
        "💸 Investition und Kosten (10 Jahre)",
        "🧩 Aufschlüsselung nach Dienstleistung",
        "🧩 Aufschlüsselung pro kWh (nach 10 Jahre)",
    ])

    with sub1:
        required_cols = ["Cumulate_Grab", "Kapital_rest"]
        missing_cols = [c for c in required_cols if c not in df_10.columns]
        if missing_cols:
            st.error(f"Fehlende Spalten in df_10: {missing_cols}")
        else:
            import plotly.express as px
            df_plot = df_10.copy().reset_index(drop=True)
            df_plot["Jahr"] = range(1, len(df_plot) + 1)
            df_long = df_plot.melt(
                id_vars="Jahr",
                value_vars=["Cumulate_Grab", "Kapital_rest"],
                var_name="Typ",
                value_name="Wert",
            )
            label_map = {"Cumulate_Grab": "Erträge", "Kapital_rest": "Zum Abschreiben"}
            df_long["Typ"] = df_long["Typ"].map(label_map)

            fig = px.bar(df_long, x="Jahr", y="Wert", color="Typ", barmode="group", labels={"Jahr":"Jahr","Wert":"CHF"})
            fig.update_layout(xaxis=dict(dtick=1), margin=dict(t=40,b=40,l=40,r=10), legend=dict(orientation="h", y=1.02, x=1, xanchor="right"))
            st.plotly_chart(fig, use_container_width=True)

    with sub2:
        import plotly.graph_objects as go
        total_projekt     = PK_default
        total_subvention  = SV_sim
        total_steuerabzug = df_10["Steuerabzug"].sum()
        total_unterhalt   = df_10["Unterhalt"].sum()
        total_betrieb     = df_10["Betrieb"].sum()
        total_steuer      = df_10["Steuer"].sum()
        zins_10           = df_10["Zins"].sum()

        labels_oneoff = ["Investition", "Projektkosten", "Subvention", "Steuerabzug", "One-off Total"]
        values_oneoff = [IK_sim, total_projekt, -total_subvention, -total_steuerabzug, IK_sim + total_projekt - total_subvention - total_steuerabzug]
        measures_oneoff = ["relative","relative","relative","relative","total"]

        labels_wieder = ["Unterhalt", "Betrieb", "Steuer", "Zinsen", "Wiederk. Kosten 10 J."]
        values_wieder = [total_unterhalt, total_betrieb, total_steuer, zins_10, total_unterhalt + total_betrieb + total_steuer + zins_10]
        measures_wieder = ["relative","relative","relative","relative","total"]

        cL, cR = st.columns(2)
        with cL:
            fig = go.Figure(go.Waterfall(orientation="v", x=labels_oneoff, y=values_oneoff, measure=measures_oneoff))
            fig.update_layout(title="Investition", yaxis_title="CHF", margin=dict(t=50,b=40,l=40,r=10))
            st.plotly_chart(fig, use_container_width=True)
        with cR:
            fig = go.Figure(go.Waterfall(orientation="v", x=labels_wieder, y=values_wieder, measure=measures_wieder))
            fig.update_layout(title="Wiederkehrende Kosten", yaxis_title="CHF", margin=dict(t=50,b=40,l=40,r=10))
            st.plotly_chart(fig, use_container_width=True)

    with sub3:
        st.subheader("Aufschlüsselung nach Dienstleistung")

        def gain_color(gewinn: float):
            blue_light = "#aec7e8 "  # Gewinn positif
            red        = "#d62728"   # Gewinn négatif
            return blue_light if gewinn >= 0 else red

        UMSATZ_BLUE = '#1f77b4'     # ✅ bleu foncé (Umsatz)

        um_gw = [
            ("Eigenverbrauch", float(kwh10["UmE"]),  float(kwh10["GwE"]),  "svc_eigenverbrauch"),
            ("Restüberschuss", float(kwh10["UmRU"]), float(kwh10["GwRU"]), "svc_restueberschuss"),
            ("Eugster",        float(kwh10["UmEG"]), float(kwh10["GwEG"]), "svc_eugster"),
            ("LEG Standard",   float(kwh10["UmEL"]), float(kwh10["GwEL"]), "svc_leg_standard"),
        ]

        ymax = max(max(abs(u), abs(g)) for _, u, g, _ in um_gw) * 1.10

        def mini_umsatz_gewinn(title: str, umsatz: float, gewinn: float, ymax: float):
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=["Umsatz"], y=[umsatz], name="Umsatz",
                marker=dict(color=UMSATZ_BLUE),              # ✅ bleu foncé
            ))
            fig.add_trace(go.Bar(
                x=["Gewinn"], y=[gewinn], name="Gewinn",
                marker=dict(color=gain_color(gewinn)),       # ✅ bleu clair / rouge
            ))
            fig.update_layout(
                title=title,
                barmode="group",
                yaxis_title="CHF",
                yaxis=dict(range=[-ymax, ymax]),
                margin=dict(t=70, b=40, l=20, r=20),
                height=320,
                showlegend=False,
            )
            return fig

        c1, c2, c3, c4 = st.columns(4)
        for col, (title, u, g, key) in zip([c1, c2, c3, c4], um_gw):
            with col:
                fig = mini_umsatz_gewinn(title, u, g, ymax)
                st.plotly_chart(fig, width="stretch", key=key)

    with sub4:
        st.subheader("Aufschlüsselung pro kWh (nach 10 Jahre)")

        def wf_colors(gewinn: float):
            blue = "#1f77b4"
            red  = "#d62728"
            return blue, red, (blue if gewinn >= 0 else red)

        col_left, col_right = st.columns(2)

        # ======================================
        # 1) Eigenverbrauch
        # ======================================
        with col_left:
            verkaufspreis = float(kwh10["DEIV"])
            gestehung     = float(kwh10["GKosten"])
            indirekt      = float(kwh10["DEII"])
            zins          = float(kwh10["DEIZ"])
            steuer        = float(kwh10["DEIS"])

            gewinn = verkaufspreis - gestehung - indirekt - zins - steuer

            labels   = ["Verkaufspreis", "Gestehungskosten", "Indirekte Kosten", "Zins", "Steuer", "Gewinn"]
            values   = [verkaufspreis, -gestehung, -indirekt, -zins, -steuer, gewinn]
            measures = ["relative", "relative", "relative", "relative", "relative", "total"]

            inc, dec, tot = wf_colors(gewinn)

            fig_eig = go.Figure(go.Waterfall(
                orientation="v",
                x=labels,
                y=values,
                measure=measures,
                text=[f"{v:.4f}" for v in values],
                textposition="outside",
                increasing=dict(marker=dict(color=inc)),
                decreasing=dict(marker=dict(color=dec)),
                totals=dict(marker=dict(color=tot)),
            ))
            fig_eig.update_layout(
                title="Eigenverbrauch",
                yaxis_title="CHF/kWh",
                margin=dict(t=90, b=40, l=40, r=10),
                height=420,
                showlegend=False,
            )
            st.plotly_chart(fig_eig, use_container_width=True, key="wf_eigenverbrauch")

        # ======================================
        # 2) Rest Überschuss
        # ======================================
        with col_right:
            verkaufspreis = float(kwh10["DRUV"])
            gestehung     = float(kwh10["GKosten"])
            indirekt      = float(kwh10["DRUI"])
            zins          = float(kwh10["DRUZ"])
            steuer        = float(kwh10["DRUS"])

            gewinn = verkaufspreis - gestehung - indirekt - zins - steuer

            labels   = ["Verkaufspreis", "Gestehungskosten", "Indirekte Kosten", "Zins", "Steuer","Gewinn"]
            values   = [verkaufspreis, -gestehung, -indirekt, -zins,- steuer, gewinn]
            measures = ["relative", "relative", "relative", "relative", "relative","total"]

            inc, dec, tot = wf_colors(gewinn)

            fig_ru = go.Figure(go.Waterfall(
                orientation="v",
                x=labels,
                y=values,
                measure=measures,
                text=[f"{v:.4f}" for v in values],
                textposition="outside",
                increasing=dict(marker=dict(color=inc)),
                decreasing=dict(marker=dict(color=dec)),
                totals=dict(marker=dict(color=tot)),
            ))
            fig_ru.update_layout(
                title="Rest Überschuss",
                yaxis_title="CHF/kWh",
                margin=dict(t=90, b=40, l=40, r=10),
                height=420,
                showlegend=False,
            )
            st.plotly_chart(fig_ru, use_container_width=True, key="wf_restueberschuss")

        # ======================================
        # 3) Eugster + 4) Standard LEG (dessous)
        # ======================================
        col_eug, col_leg = st.columns(2)

        # --- 3) Eugster ---
        with col_eug:
            verkaufspreis = float(kwh10["DEGV"])
            gestehung     = float(kwh10["GKosten"])
            indirekt      = float(kwh10["DEGI"])
            zins          = float(kwh10["DEGZ"])
            steuer        = float(kwh10["DEGS"])

            gewinn = verkaufspreis - gestehung - indirekt - zins - steuer

            labels   = ["Verkaufspreis", "Gestehungskosten", "Indirekte Kosten", "Zins", "Steuer", "Gewinn"]
            values   = [verkaufspreis, -gestehung, -indirekt, -zins, -steuer, gewinn]
            measures = ["relative", "relative", "relative", "relative", "relative", "total"]

            inc, dec, tot = wf_colors(gewinn)

            fig_eug = go.Figure(go.Waterfall(
                orientation="v",
                x=labels,
                y=values,
                measure=measures,
                text=[f"{v:.4f}" for v in values],
                textposition="outside",
                increasing=dict(marker=dict(color=inc)),
                decreasing=dict(marker=dict(color=dec)),
                totals=dict(marker=dict(color=tot)),
            ))
            fig_eug.update_layout(
                title="Eugster",
                yaxis_title="CHF/kWh",
                margin=dict(t=90, b=40, l=40, r=10),
                height=420,
                showlegend=False,
            )
            st.plotly_chart(fig_eug, use_container_width=True, key="wf_eugster")

        # --- 4) Standard LEG ---
        with col_leg:
            verkaufspreis = float(kwh10["DELV"])
            gestehung     = float(kwh10["GKosten"])
            indirekt      = float(kwh10["DELI"])
            zins          = float(kwh10["DELZ"])
            steuer        = float(kwh10["DELS"])

            gewinn = verkaufspreis - gestehung - indirekt - zins - steuer

            labels   = ["Verkaufspreis", "Gestehungskosten", "Indirekte Kosten", "Zins", "Steuer", "Gewinn"]
            values   = [verkaufspreis, -gestehung, -indirekt, -zins, -steuer, gewinn]
            measures = ["relative", "relative", "relative", "relative", "relative", "total"]

            inc, dec, tot = wf_colors(gewinn)

            fig_leg = go.Figure(go.Waterfall(
                orientation="v",
                x=labels,
                y=values,
                measure=measures,
                text=[f"{v:.4f}" for v in values],
                textposition="outside",
                increasing=dict(marker=dict(color=inc)),
                decreasing=dict(marker=dict(color=dec)),
                totals=dict(marker=dict(color=tot)),
            ))
            fig_leg.update_layout(
                title="Standard LEG",
                yaxis_title="CHF/kWh",
                margin=dict(t=90, b=40, l=40, r=10),
                height=420,
                showlegend=False,
            )
            st.plotly_chart(fig_leg, use_container_width=True, key="wf_standard_leg")


st.markdown(
    """
    <style>
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #f9fafb;
        color: #6b7280;
        text-align: center;
        padding: 8px;
        font-size: 12px;
        border-top: 1px solid #e5e7eb;
        z-index: 999;
    }
    </style>

    <div class="footer">
        © 2025 – Stromverbrauch TB Thal & Solarstrahlung Wetterstaion Altenrhein: Stundenwerte Jahr 2024  -  Tarif TB Thal: Jahr 2026
    </div>
    """,
    unsafe_allow_html=True
)