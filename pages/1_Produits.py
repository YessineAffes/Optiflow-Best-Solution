"""Interface produits d'Optiflow Best Solution.

Page secondaire (multipage Streamlit) destinee a l'expert : ajouter et gerer
le catalogue de verres stocke dans Supabase. Le catalogue alimente la base de
connaissance produit du projet.

Les listes de valeurs (Design, Indices, Traitements, Couleur, Geometrie) sont
importees depuis agent.py : source unique, pas de valeurs ecrites en dur ici.
"""

import streamlit as st

import db
from agent import (
    DESIGN_VALUES,
    GEOMETRY_VALUES,
    INDEX_VALUES,
    TRANSITION_LABEL,
    TRANSITION_VALUES,
    TREATMENT_VALUES,
)

st.set_page_config(page_title="Produits · Optiflow", page_icon="👓", layout="wide")

FAMILIES = {
    "Simple Foyer": "simple_foyer",
    "Eyezen": "eyezen",
    "Varilux": "varilux",
}

PLACEHOLDER = "Selectionner une valeur"

# Cles des cases a cocher multi-selection.
IDX_KEYS = {value: f"idx_{value}" for value in INDEX_VALUES}
TRT_KEYS = {value: f"trt_{value}" for value in TREATMENT_VALUES}

# Toutes les cles de widgets du formulaire (pour reinitialisation apres envoi).
FORM_KEYS = (
    ["prod_family", "prod_design", "prod_description", "prod_transition",
     "prod_geometry", "prod_reco_for", "idx_all", "trt_all"]
    + list(IDX_KEYS.values())
    + list(TRT_KEYS.values())
)


# --- Callbacks "Selectionner tout" / synchronisation des cases individuelles --
def _select_all(all_key: str, item_keys: list[str]):
    checked = st.session_state.get(all_key, False)
    for key in item_keys:
        st.session_state[key] = checked


def _sync_all(all_key: str, item_keys: list[str]):
    # "Selectionner tout" se coche seulement si toutes les cases sont cochees.
    st.session_state[all_key] = all(st.session_state.get(key, False) for key in item_keys)


def _render_checkbox_group(title: str, all_key: str, keys_by_value: dict[str, str]):
    item_keys = list(keys_by_value.values())
    st.markdown(f"**{title}**")
    st.checkbox(
        "Selectionner tout",
        key=all_key,
        on_change=_select_all,
        args=(all_key, item_keys),
    )
    for value, key in keys_by_value.items():
        st.checkbox(value, key=key, on_change=_sync_all, args=(all_key, item_keys))


def _reset_form():
    for key in FORM_KEYS:
        st.session_state.pop(key, None)


# Reinitialisation demandee au tour precedent : doit avoir lieu AVANT que les
# widgets ne soient instancies (sinon Streamlit interdit de modifier leur etat).
if st.session_state.pop("_reset_product_form", False):
    _reset_form()
for key in list(IDX_KEYS.values()) + list(TRT_KEYS.values()) + ["idx_all", "trt_all"]:
    st.session_state.setdefault(key, False)

st.title("👓 Catalogue produits")
st.caption("Ajouter et gerer les verres de la base Optiflow Best Solution.")

store = db.get_store()
if not store.enabled:
    st.warning(
        "Supabase n'est pas configure : impossible d'enregistrer ou de lister les produits. "
        "Renseigne SUPABASE_URL / SUPABASE_KEY (voir SETUP_SUPABASE.md)."
    )
    if store.last_error:
        st.error(store.last_error)

if st.session_state.pop("_product_saved", None):
    st.success("Produit enregistre.")

st.subheader("Ajouter un produit")

# Ligne 1 : Famille + Design.
c_family, c_design = st.columns(2)
family_label = c_family.selectbox(
    "Famille", list(FAMILIES.keys()), index=None, placeholder=PLACEHOLDER, key="prod_family"
)
lens_type = c_design.selectbox(
    "Design", DESIGN_VALUES, index=None, placeholder=PLACEHOLDER, key="prod_design"
)

# Ligne 2 : Description du produit.
description = st.text_area(
    "Description du produit",
    placeholder="Saisir la description, les caracteristiques et les principaux avantages du produit...",
    height=120,
    key="prod_description",
)

# Ligne 3 : Indices + Traitements (groupes de cases a cocher multi-selection).
c_index, c_treatment = st.columns(2)
with c_index:
    _render_checkbox_group("Indices", "idx_all", IDX_KEYS)
with c_treatment:
    _render_checkbox_group("Traitements", "trt_all", TRT_KEYS)

# Ligne 4 : Couleur + Geometrie.
c_transition, c_geometry = st.columns(2)
transition = c_transition.selectbox(
    TRANSITION_LABEL, TRANSITION_VALUES, index=None, placeholder=PLACEHOLDER, key="prod_transition"
)
geometry = c_geometry.selectbox(
    "Geometrie", GEOMETRY_VALUES, index=None, placeholder=PLACEHOLDER, key="prod_geometry"
)

# Ligne 5 : A qui recommander.
recommended_for = st.text_area(
    "A qui recommander", placeholder="Profils, besoins, indications...", key="prod_reco_for"
)

# Derniere ligne : bouton d'enregistrement.
if st.button("Enregistrer le produit", use_container_width=True, type="primary"):
    selected_indices = [value for value, key in IDX_KEYS.items() if st.session_state.get(key)]
    selected_treatments = [value for value, key in TRT_KEYS.items() if st.session_state.get(key)]
    if not family_label:
        st.error("La famille est obligatoire.")
    elif not lens_type:
        st.error("Le champ Design est obligatoire.")
    else:
        product = {
            "advantage": (description or "").strip() or None,
            "family": FAMILIES[family_label],
            "lens_type": lens_type,
            "index": ", ".join(selected_indices) or None,
            "treatment": ", ".join(selected_treatments) or None,
            "transition": transition or None,
            "geometry": geometry or None,
            "recommended_for": (recommended_for or "").strip() or None,
        }
        if store.add_product(product):
            st.session_state["_product_saved"] = True
            st.session_state["_reset_product_form"] = True
            st.rerun()
        else:
            st.error(f"Echec de l'enregistrement : {store.last_error or 'base indisponible'}")

st.divider()
st.subheader("Produits enregistres")

filter_label = st.selectbox("Filtrer par famille", ["Toutes"] + list(FAMILIES.keys()))
family_filter = None if filter_label == "Toutes" else FAMILIES[filter_label]
products = store.list_products(family_filter)

if not products:
    st.info("Aucun produit pour l'instant.")
else:
    label_by_value = {value: label for label, value in FAMILIES.items()}
    for product in products:
        cols = st.columns([3, 2, 1.5, 1.5, 1.5, 1])
        cols[0].markdown(f"**{product.get('lens_type', '')}**  \n{product.get('advantage') or ''}")
        cols[1].write(label_by_value.get(product.get("family"), product.get("family") or "-"))
        cols[2].write(f"Indice {product.get('index') or '-'}")
        cols[3].write(product.get("treatment") or "-")
        cols[4].write(product.get("recommended_for") or "-")
        if cols[5].button("🗑️", key=f"del_{product.get('id')}", help="Supprimer"):
            if store.delete_product(product.get("id")):
                st.rerun()
            else:
                st.error(store.last_error or "Suppression impossible.")
