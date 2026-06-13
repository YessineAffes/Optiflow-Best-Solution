"""Interface produits d'Optiflow Best Solution.

Page secondaire (multipage Streamlit) destinee a l'expert : ajouter et gerer
le catalogue de verres stocke dans Supabase. Le catalogue alimente la base de
connaissance produit du projet.
"""

import streamlit as st

import db

st.set_page_config(page_title="Produits · Optiflow", page_icon="👓", layout="wide")

FAMILIES = {
    "Simple Foyer": "simple_foyer",
    "Eyezen": "eyezen",
    "Varilux": "varilux",
}

st.title("👓 Catalogue produits")
st.caption("Ajouter et gerer les verres de la base Optiflow Best Solution.")

store = db.get_store()
if not store.enabled:
    st.warning(
        "Supabase n'est pas configure : impossible d'enregistrer ou de lister les produits. "
        "Renseigne SUPABASE_URL / SUPABASE_KEY (voir SETUP_SUPABASE.md)."
    )

with st.form("add_product", clear_on_submit=True):
    st.subheader("Ajouter un produit")
    c1, c2, c3 = st.columns(3)
    reference = c1.text_input("Reference", placeholder="ex: VX-XR-160")
    family_label = c2.selectbox("Famille", list(FAMILIES.keys()))
    lens_type = c3.text_input("Type de verre", placeholder="ex: Varilux XR Design")

    c4, c5, c6 = st.columns(3)
    index = c4.selectbox("Indice", ["", "1.50", "1.56", "1.60", "1.67"])
    treatment = c5.text_input("Traitement", placeholder="ex: Crizal Easy Pro")
    transition = c6.selectbox("Transition", ["", "Blanc", "Transition", "Solaire"])

    c7, c8 = st.columns(2)
    geometry = c7.selectbox("Geometrie", ["", "Regular", "Short"])
    price = c8.number_input("Prix (DT)", min_value=0.0, step=1.0, format="%.2f")

    notes = st.text_area("Notes", placeholder="Details, indications, restrictions...")
    submitted = st.form_submit_button("Enregistrer le produit", use_container_width=True)

if submitted:
    if not lens_type.strip():
        st.error("Le type de verre est obligatoire.")
    else:
        product = {
            "reference": reference.strip() or None,
            "family": FAMILIES[family_label],
            "lens_type": lens_type.strip(),
            "index": index or None,
            "treatment": treatment.strip() or None,
            "transition": transition or None,
            "geometry": geometry or None,
            "price": float(price) if price else None,
            "notes": notes.strip() or None,
        }
        if store.add_product(product):
            st.success(f"Produit « {lens_type} » enregistre.")
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
        cols[0].markdown(f"**{product.get('lens_type', '')}**  \n{product.get('reference') or ''}")
        cols[1].write(label_by_value.get(product.get("family"), product.get("family") or "-"))
        cols[2].write(f"Indice {product.get('index') or '-'}")
        cols[3].write(product.get("treatment") or "-")
        price = product.get("price")
        cols[4].write(f"{float(price):.2f} DT" if price is not None else "-")
        if cols[5].button("🗑️", key=f"del_{product.get('id')}", help="Supprimer"):
            if store.delete_product(product.get("id")):
                st.rerun()
            else:
                st.error(store.last_error or "Suppression impossible.")
