import html

import streamlit as st

import db
from agent import EssilorAgent, FIELD_QUESTIONS, LocalDocRAG, apply_price_downgrade, build_document_recommendation


st.set_page_config(page_title="Optiflow Best Solution", page_icon="👁️", layout="wide", initial_sidebar_state="collapsed")


@st.cache_resource
def get_shared_rag():
    """Read-only scenario corpus, safe to share across sessions/users."""
    return LocalDocRAG()


def new_agent():
    """One agent per Streamlit session so client profiles never collide."""
    return EssilorAgent(rag=get_shared_rag())


st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',-apple-system,Segoe UI,Roboto,sans-serif}
.block-container{padding-top:1.4rem}
.header-box{background:linear-gradient(135deg,#0F6E56 0%,#14876C 100%);border-radius:16px;padding:18px 24px;margin-bottom:20px;display:flex;align-items:center;gap:14px;box-shadow:0 6px 18px rgba(15,110,86,.18)}
.header-title{color:white;font-size:19px;font-weight:700;margin:0;letter-spacing:.2px}
.header-sub{color:rgba(255,255,255,.78);font-size:13px;margin:6px 0 0}
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;margin-right:6px}
.badge-sf{background:#EAF3DE;color:#3B6D11}.badge-ey{background:#E6F1FB;color:#185FA5}.badge-vx{background:#EEEDFE;color:#534AB7}
/* --- Bulles de chat avec avatars --- */
.msg-row{display:flex;align-items:flex-end;gap:8px;margin:7px 0}
.msg-row.bot{justify-content:flex-start}.msg-row.user{justify-content:flex-end}
.avatar{width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0;box-shadow:0 1px 3px rgba(0,0,0,.12)}
.avatar-bot{background:#0F6E56;color:#fff}.avatar-user{background:#E6F1FB}
.user-msg{background:#0F6E56;color:white;border-radius:16px 16px 4px 16px;padding:10px 15px;font-size:14px;line-height:1.55;max-width:78%;box-shadow:0 1px 4px rgba(15,110,86,.2)}
.bot-msg{background:#fff;color:#1a2b26;border:1px solid #e7ece9;border-radius:16px 16px 16px 4px;padding:10px 15px;font-size:14px;line-height:1.55;max-width:78%;box-shadow:0 1px 4px rgba(0,0,0,.05)}
.rx-form-wrap{background:#fff;border:1px solid #e7ece9;border-radius:12px;padding:12px 14px 14px;margin:10px 0;box-shadow:0 1px 4px rgba(0,0,0,.05)}
.rx-form-title{color:#0F6E56;font-size:16px;font-weight:700;margin:0}
.rx-head{color:#555;font-size:12px;font-weight:700;padding:0 0 2px}.rx-eye{font-size:13px;font-weight:700;color:#111;padding-top:7px}
.live-preview{border:1px solid #dce7e3;border-radius:14px;overflow:hidden;margin:0 0 14px;background:#fff;position:sticky;top:14px;box-shadow:0 2px 10px rgba(0,0,0,.05)}
.live-preview-head{background:#f5faf8;border-bottom:1px solid #dce7e3;padding:12px 16px;display:flex;align-items:center;justify-content:space-between;gap:10px}
.live-preview-title{color:#0F6E56;font-size:14px;font-weight:700;margin:0}.live-preview-step{color:#66736f;font-size:12px;margin:0}
.live-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));border-bottom:1px solid #eee}.live-item{padding:11px 14px;border-right:1px solid #eee;min-height:58px}.live-item:nth-child(2n),.live-item:last-child{border-right:0}
.live-label{color:#7b8582;font-size:11px;margin:0 0 4px}.live-value{color:#1a1a1a;font-size:13px;font-weight:650;margin:0;word-break:break-word}.live-muted{color:#9a9a9a;font-weight:500}.live-question{padding:12px 16px;color:#26332f;font-size:13px}
.reco-card{border:1.5px solid;border-radius:16px;overflow:hidden;margin:12px 0;box-shadow:0 4px 16px rgba(0,0,0,.07)}.reco-header{padding:14px 18px}.reco-body{padding:14px 18px;background:white}.reco-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.reco-item{background:#f5f7f6;border-radius:12px;padding:10px 12px}.reco-label{font-size:11px;color:#888;margin:0 0 3px}.reco-value{font-size:14px;font-weight:600;margin:0}.reco-just{border-radius:12px;padding:10px 14px;margin-top:10px;font-size:13px;line-height:1.55}
/* --- Responsive mobile --- */
@media (max-width:640px){
  .header-box{padding:14px 16px;border-radius:14px}
  .header-title{font-size:16px}.header-sub{font-size:12px}
  .user-msg,.bot-msg{max-width:88%;font-size:13.5px}
  .live-preview{position:static}
  .live-grid{grid-template-columns:1fr}
  .live-item{border-right:0;border-bottom:1px solid #eee;min-height:auto}
  .reco-grid{grid-template-columns:1fr}
}
</style>
""",
    unsafe_allow_html=True,
)


def html_text(text: object) -> str:
    return html.escape(str(text or "")).replace("\n", "<br>")


def question_step_label(question: str) -> str:
    normalized = question.lower()
    if "correction" in normalized or "ordonnance" in normalized or "od/og" in normalized:
        return "Correction / ordonnance"
    if "montage" in normalized:
        return "Montage"
    if "besoin" in normalized:
        return "Besoin principal"
    if "soleil" in normalized or "transition" in normalized or "solaire" in normalized:
        return "Transition / soleil"
    if "oculaire" in normalized:
        return "Sante oculaire"
    if "ordinateur" in normalized:
        return "Geometrie"
    return "Question suivante"


def current_agent_field() -> str | None:
    agent = st.session_state.get("agent")
    return getattr(agent, "current_field", None) if agent else None


def current_agent_profile() -> dict:
    agent = st.session_state.get("agent")
    return dict(getattr(agent, "profile", {}) or {}) if agent else {}


def current_agent_family() -> str:
    age = current_agent_profile().get("age")
    if isinstance(age, (int, float)):
        if age <= 30:
            return "Simple Foyer"
        if age <= 41:
            return "Eyezen"
        return "Varilux"
    return "En attente"


def live_value_html(value: object) -> str:
    if value in (None, ""):
        return '<span class="live-muted">En attente</span>'
    return html_text(value)


LIVE_DEFAULTS = {
    "Varilux": {"type": "Varilux liberty", "indice": "1.50", "traitement": "Crizal Easy Pro", "transition": "blanc", "geometrie": "Regular"},
    "Eyezen": {"type": "Eyzen", "indice": "1.50", "traitement": "Crizal Easy Pro", "transition": "blanc", "geometrie": ""},
    "Simple Foyer": {"type": "simple foyer", "indice": "1.50", "traitement": "Crizal Easy Pro", "transition": "blanc", "geometrie": ""},
}


def preview_reco() -> dict:
    profile = current_agent_profile()
    family_map = {"Simple Foyer": "simple_foyer", "Eyezen": "eyezen", "Varilux": "varilux"}
    family = family_map.get(current_agent_family())
    if not profile.get("age"):
        return {}
    return build_document_recommendation(profile, family)


def render_live_progress():
    """Barre de progression + questions restantes, dans l'apercu live."""
    agent = st.session_state.get("agent")
    if agent is None:
        return
    progress = agent.progress()
    total = progress["total"] or 1
    answered = progress["answered"]
    if progress["done"]:
        st.progress(1.0, text="Recommandation prete")
        return
    step = min(answered + 1, total)
    st.progress(progress["ratio"], text=f"Question {step}/{total} · {answered} repondue(s)")
    remaining = progress["remaining_questions"]
    if remaining:
        with st.expander(f"Questions restantes ({len(remaining)})", expanded=False):
            for index, question in enumerate(remaining, start=1):
                st.markdown(f"{index}. {html_text(question)}", unsafe_allow_html=True)


def render_live_preview():
    profile = current_agent_profile()
    family = current_agent_family()
    field = current_agent_field()
    question = FIELD_QUESTIONS.get(field or "", "En attente")
    has_age = profile.get("age") not in (None, "")
    defaults = LIVE_DEFAULTS.get(family, LIVE_DEFAULTS["Varilux"])
    reco = preview_reco() if has_age else {}
    live_type = reco.get("lens_type", defaults["type"] if has_age else "")
    live_index = reco.get("index", defaults["indice"] if has_age else "")
    live_treatment = reco.get("treatment", defaults["traitement"] if has_age else "")
    live_transition = reco.get("transition", defaults["transition"] if has_age else "")
    live_geometry = reco.get("geometrie", defaults["geometrie"] if has_age else "")
    if has_age and family != "Varilux":
        live_geometry = "Non applicable"

    st.markdown(
        f"""
    <div class="live-preview">
      <div class="live-preview-head">
        <p class="live-preview-title">Apercu live</p>
        <p class="live-preview-step">Etape actuelle : {html_text(question_step_label(question))}</p>
      </div>
      <div class="live-grid">
        <div class="live-item"><p class="live-label">Type</p><p class="live-value">{live_value_html(live_type)}</p></div>
        <div class="live-item"><p class="live-label">Indice</p><p class="live-value">{live_value_html(live_index)}</p></div>
        <div class="live-item"><p class="live-label">Traitement</p><p class="live-value">{live_value_html(live_treatment)}</p></div>
        <div class="live-item"><p class="live-label">Transition</p><p class="live-value">{live_value_html(live_transition)}</p></div>
      </div>
      <div class="live-item" style="margin-top:10px"><p class="live-label">Geometrie</p><p class="live-value">{live_value_html(live_geometry)}</p></div>
      <div class="live-question"><strong>Question en cours :</strong> {html_text(question)}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )


def bot_bubble(text: str) -> str:
    return f'<div class="msg-row bot"><div class="avatar avatar-bot">👁️</div><div class="bot-msg">{html_text(text)}</div></div>'


def user_bubble(text: str) -> str:
    return f'<div class="msg-row user"><div class="user-msg">{html_text(text)}</div><div class="avatar avatar-user">🧑</div></div>'


def render_bot_message(text: str):
    st.markdown(bot_bubble(text), unsafe_allow_html=True)


def render_trace_message(question: str, answer: str):
    st.markdown(bot_bubble(question) + user_bubble(answer), unsafe_allow_html=True)


def render_reco(reco: dict):
    lens_type = reco.get("lens_type", "")
    family = "Varilux" if "Varilux" in lens_type else ("Eyezen" if "Eyezen" in lens_type else "Simple Foyer")
    palette = {"Simple Foyer": ("#EAF3DE", "#3B6D11", "#639922"), "Eyezen": ("#E6F1FB", "#185FA5", "#378ADD"), "Varilux": ("#EEEDFE", "#534AB7", "#7F77DD")}
    bg, txt, border = palette[family]
    rationale = reco.get("rationale", [])
    rationale_items = "".join(f"<li>{html_text(item)}</li>" for item in rationale)
    geometry = reco.get("geometrie", "") if family == "Varilux" else "Non applicable"
    st.markdown(
        f"""
    <div class="reco-card" style="border-color:{border}">
      <div class="reco-header" style="background:{bg}"><strong style="color:{txt}">Recommandation finalisee</strong><br><span style="color:{txt};opacity:.75;font-size:13px">{html_text(lens_type)}</span></div>
      <div class="reco-body">
        <div class="reco-grid">
          <div class="reco-item"><p class="reco-label">Type</p><p class="reco-value">{html_text(lens_type)}</p></div>
          <div class="reco-item"><p class="reco-label">Indice</p><p class="reco-value">{html_text(reco.get("index", ""))}</p></div>
          <div class="reco-item"><p class="reco-label">Traitement</p><p class="reco-value">{html_text(reco.get("treatment", ""))}</p></div>
          <div class="reco-item"><p class="reco-label">Transition</p><p class="reco-value">{html_text(reco.get("transition", ""))}</p></div>
        </div>
        <div class="reco-item" style="margin-top:10px"><p class="reco-label">Geometrie</p><p class="reco-value">{html_text(geometry)}</p></div>
        <div class="reco-just"><p class="reco-label">Justification</p><ul style="margin:6px 0 0 18px;padding:0">{rationale_items}</ul></div>
      </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    optimization = reco.get("priceOptimization", {}) if isinstance(reco.get("priceOptimization"), dict) else {}
    downgrades = optimization.get("availableDowngrades", {}) if isinstance(optimization.get("availableDowngrades"), dict) else {}
    attempts = int(optimization.get("attempts", 0) or 0)
    max_attempts = int(optimization.get("maxAttempts", 2) or 2)
    if downgrades and attempts < max_attempts:
        labels = {"type": "Type de verre", "treatment": "Traitement", "transition": "Transition"}
        current_values = {
            "type": reco.get("lens_type", ""),
            "treatment": reco.get("treatment", ""),
            "transition": reco.get("transition", ""),
        }
        st.markdown(
            f"""
            <div class="rx-form-wrap">
              <p class="rx-form-title">Optimisation prix ({attempts}/{max_attempts})</p>
              <p style="margin:6px 0 0;color:#555;font-size:13px">{html_text(optimization.get("message", ""))}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        columns = st.columns(min(3, len(downgrades)))
        for index, (field, next_value) in enumerate(downgrades.items()):
            label = f"{labels.get(field, field)}\n{current_values.get(field, '')} → {next_value}"
            if columns[index % len(columns)].button(label, key=f"downgrade_{field}_{attempts}", use_container_width=True):
                st.session_state.reco = apply_price_downgrade(reco, field)
                st.rerun()
    elif attempts >= max_attempts:
        st.info("Limite atteinte : deux diminutions ont déjà été appliquées pour cette recommandation.")


CHOICE_FIELDS = {
    "frame_type": [("Perce", "perce"), ("Nylor", "nylor"), ("Plastique", "plastique"), ("Metallique", "metallique")],
    "main_need": [("Transparence", "transparence"), ("Lumiere bleue", "lumiere bleue"), ("Conduite soir/nuit", "conduite soir"), ("Rayures", "rayures"), ("Nettoyage", "nettoyage")],
    "postural_comfort": [("Oui", "oui"), ("Non", "non")],
    "near_intermediate_comfort": [("Oui", "oui"), ("Non", "non")],
    "innovation_sensitive": [("Oui", "oui"), ("Non", "non")],
    "sun_exposure": [("Oui", "oui"), ("Non", "non")],
    "sun_discomfort": [("Oui", "oui"), ("Non", "non")],
    "sun_solution": [("Solaire", "solaire"), ("Transition", "transition")],
    "head_eye_behavior": [("Tete", "tete"), ("Yeux", "yeux")],
    "computer_usage": [("Ordinateur de bureau", "ordinateur de bureau"), ("Ordinateur portable", "ordinateur portable")],
    "ocular_health": [("RAS", "ras"), ("Cataracte", "cataracte"), ("Glaucome", "glaucome"), ("DMLA", "dmla"), ("Pseudophaque", "pseudophaque"), ("Conjonctivite", "conjonctivite"), ("Retinopathie diabetique", "retinopathie diabetique"), ("Arthrose", "arthrose")],
}


def submit_to_agent(user_text: str, display_text: str | None = None):
    asked_field = current_agent_field()
    asked_question = FIELD_QUESTIONS.get(asked_field or "", "")
    st.session_state.messages.append({"role": "trace", "question": asked_question, "answer": display_text or user_text, "text": display_text or user_text})
    reply, reco = st.session_state.agent.chat(user_text)
    structured_field = current_agent_field()
    if reply and not (structured_field == "correction_total" or structured_field in CHOICE_FIELDS):
        st.session_state.messages.append({"role": "bot", "text": reply})
    if reco:
        st.session_state.reco = reco
    st.rerun()


def render_choice_buttons(field: str):
    question = FIELD_QUESTIONS.get(field, "Choisissez une reponse")
    st.markdown(f'<div class="rx-form-wrap"><p class="rx-form-title">{html_text(question)}</p></div>', unsafe_allow_html=True)
    choices = CHOICE_FIELDS[field]
    columns = st.columns(min(4, len(choices)))
    for index, (label, value) in enumerate(choices):
        if columns[index % len(columns)].button(label, key=f"choice_{field}_{index}", use_container_width=True):
            submit_to_agent(value, label)


def render_expert_panel(field: str, question: str):
    """Bloc inline 'expert' sous la question courante : note + verification.

    Collecte les retours expert dans Supabase (jeu de donnees d'amelioration).
    Sans base configuree, le bloc reste visible mais previent que rien n'est
    enregistre.
    """
    store = db.get_store()
    with st.expander(f"🛠️ Expert · {question}", expanded=False):
        if not store.enabled:
            st.info("Supabase non configure : annotations non enregistrees. Voir SETUP_SUPABASE.md.")
        with st.form(f"expert_form_{field}", clear_on_submit=True):
            note = st.text_area("Note / observation", placeholder="Remarque, regle a corriger, cas particulier...", height=90)
            verified = st.checkbox("Question / regle verifiee")
            saved = st.form_submit_button("Enregistrer l'annotation", use_container_width=True)
        if saved:
            author = st.session_state.get("expert_author", "")
            if store.add_annotation(field, question, note, verified, author):
                st.success("Annotation enregistree.")
            else:
                st.error(f"Echec de l'enregistrement : {store.last_error or 'base indisponible'}")


def format_rx_number(value: float) -> str:
    return f"{float(value):.2f}"


def format_axis(value: int) -> str:
    return "---" if int(value) == 0 else str(int(value))


if "messages" not in st.session_state:
    st.session_state.messages = []
if "reco" not in st.session_state:
    st.session_state.reco = None
if "agent" not in st.session_state:
    st.session_state.agent = new_agent()

st.markdown(
    """
<div class="header-box">
  <div style="width:44px;height:44px;border-radius:11px;background:rgba(255,255,255,.2);display:flex;align-items:center;justify-content:center;font-size:22px;flex-shrink:0">👁️</div>
  <div><p class="header-title">Optiflow Best Solution</p><p class="header-sub"><span class="badge badge-sf">Simple Foyer</span><span class="badge badge-ey">Eyezen</span><span class="badge badge-vx">Varilux</span></p></div>
</div>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
    if st.button("Nouveau client", use_container_width=True):
        st.session_state.messages = []
        st.session_state.reco = None
        st.session_state.agent = new_agent()
        st.rerun()
    st.divider()
    st.session_state.expert_mode = st.toggle("Mode expert", value=st.session_state.get("expert_mode", False))
    if st.session_state.expert_mode:
        st.session_state.expert_author = st.text_input(
            "Expert", value=st.session_state.get("expert_author", ""), placeholder="Votre nom"
        )
        st.caption("Base : " + ("Supabase connecte" if db.get_store().enabled else "non configuree"))

main_col, preview_col = st.columns([1.25, 1], gap="large")

with preview_col:
    agent_mode = "LLM + RAG + tools" if getattr(st.session_state.agent, "llm", None) is not None else "Fallback local"
    st.caption(f"Mode agent : {agent_mode}")
    render_live_progress()
    render_live_preview()

with main_col:
    if not st.session_state.messages and not st.session_state.reco:
        render_bot_message(
            "Bonjour 👋 Je suis Optiflow, votre assistant verres Essilor. "
            "Repondez aux quelques questions ci-contre et je construis la recommandation adaptee. "
            "Pour commencer : quel age avez-vous ?"
        )
    for msg in st.session_state.messages:
        if msg["role"] == "trace":
            render_trace_message(msg.get("question", ""), msg.get("answer", ""))
        elif msg["role"] == "user":
            st.markdown(user_bubble(msg["text"]), unsafe_allow_html=True)
        else:
            render_bot_message(msg["text"])
    if st.session_state.reco:
        render_reco(st.session_state.reco)

disabled = st.session_state.reco is not None
current_field = current_agent_field()

if not disabled and current_field == "correction_total":
    st.markdown('<div class="rx-form-wrap"><p class="rx-form-title">Ordonnance OD / OG</p></div>', unsafe_allow_html=True)
    with st.form("rx_form", clear_on_submit=True):
        h0, h1, h2, h3 = st.columns([0.8, 1.6, 1.6, 1.6])
        h0.markdown("")
        h1.markdown('<div class="rx-head">Sph</div>', unsafe_allow_html=True)
        h2.markdown('<div class="rx-head">Axe</div>', unsafe_allow_html=True)
        h3.markdown('<div class="rx-head">Add</div>', unsafe_allow_html=True)
        r0, r1, r2, r3 = st.columns([0.8, 1.6, 1.6, 1.6])
        r0.markdown('<div class="rx-eye">OD</div>', unsafe_allow_html=True)
        od_sph = r1.number_input("OD Sph", min_value=-20.0, max_value=20.0, value=0.0, step=0.25, format="%.2f", label_visibility="collapsed")
        od_axis = r2.number_input("OD Axe", min_value=0, max_value=180, value=0, step=1, label_visibility="collapsed")
        od_add = r3.number_input("OD Add", min_value=0.0, max_value=4.0, value=0.0, step=0.25, format="%.2f", label_visibility="collapsed")
        g0, g1, g2, g3 = st.columns([0.8, 1.6, 1.6, 1.6])
        g0.markdown('<div class="rx-eye">OG</div>', unsafe_allow_html=True)
        og_sph = g1.number_input("OG Sph", min_value=-20.0, max_value=20.0, value=0.0, step=0.25, format="%.2f", label_visibility="collapsed")
        og_axis = g2.number_input("OG Axe", min_value=0, max_value=180, value=0, step=1, label_visibility="collapsed")
        og_add = g3.number_input("OG Add", min_value=0.0, max_value=4.0, value=0.0, step=0.25, format="%.2f", label_visibility="collapsed")
        submit_rx = st.form_submit_button("Valider l'ordonnance", use_container_width=True)
    if submit_rx:
        add_value = max(float(od_add), float(og_add))
        message = f"OD Sph {format_rx_number(od_sph)} Axe {format_axis(od_axis)} OG Sph {format_rx_number(og_sph)} Axe {format_axis(og_axis)}"
        display = f"OD Sph {format_rx_number(od_sph)} | OD Axe {format_axis(od_axis)} | OG Sph {format_rx_number(og_sph)} | OG Axe {format_axis(og_axis)}"
        if add_value > 0:
            message += f" ADD {format_rx_number(add_value)}"
            display += f" | Add {format_rx_number(add_value)}"
        submit_to_agent(message, display)
elif not disabled and current_field in CHOICE_FIELDS:
    render_choice_buttons(current_field)
else:
    with st.form("chat_form", clear_on_submit=True):
        col1, col2 = st.columns([5, 1])
        user_input = col1.text_input("", placeholder="Votre reponse...", disabled=disabled, label_visibility="collapsed")
        submit = col2.form_submit_button("Envoyer", disabled=disabled, use_container_width=True)
    if submit and user_input.strip():
        submit_to_agent(user_input.strip())

if st.session_state.get("expert_mode"):
    if not disabled and current_field:
        render_expert_panel(current_field, FIELD_QUESTIONS.get(current_field, ""))
    elif disabled:
        render_expert_panel("recommendation", "Recommandation finale")
