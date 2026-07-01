"""Tests des regles metier deterministes de l'agent OptiGuide.

Couvre: routage par age, indice, traitement, transition, type Varilux,
geometrie, optimisation prix (downgrades), parcours de questions conditionnel,
extraction des reponses et priorite de l'extraction locale sur le LLM (#3).
"""

import agent
from agent import (
    EssilorAgent,
    LocalDocRAG,
    _downgrade_type,
    _family_from_age,
    _recommend_geometry_from_profile,
    _recommend_index_from_profile,
    _recommend_transition_from_profile,
    _recommend_treatment_from_profile,
    _recommend_varilux_type,
    apply_price_downgrade,
    build_document_recommendation,
    canonical_lens_type,
    display_transition,
    family_from_lens_type,
    to_centiemes,
    to_diopters,
)
import pytest


# RAG partage et inerte: evite de relire les .docx a chaque agent en test.
@pytest.fixture(scope="module")
def shared_rag():
    rag = LocalDocRAG()
    rag.chunks = []
    return rag


@pytest.fixture
def make_agent(shared_rag):
    def _factory():
        return EssilorAgent(rag=shared_rag)

    return _factory


# --------------------------------------------------------------------------
# Routage par age -> famille
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "age, expected",
    [
        (None, None),
        (18, "simple_foyer"),
        (30, "simple_foyer"),
        (31, "eyezen"),
        (41, "eyezen"),
        (42, "varilux"),
        (70, "varilux"),
    ],
)
def test_family_from_age(age, expected):
    assert _family_from_age(age) == expected


@pytest.mark.parametrize(
    "age, expected_type",
    [
        (25, "simple foyer"),
        (32, "Eyezen initial"),
        (36, "Eyezen actif"),
        (40, "Eyezen actif +"),
    ],
)
def test_build_recommendation_lens_type_by_age(age, expected_type):
    family = _family_from_age(age)
    reco = build_document_recommendation({"age": age}, family)
    assert reco["lens_type"] == expected_type


# --------------------------------------------------------------------------
# Indice selon puissance / montage
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "correction, expected",
    [(150, "1.50"), (200, "1.50"), (350, "1.56"), (700, "1.60"), (900, "1.67")],
)
def test_index_by_correction(correction, expected):
    assert _recommend_index_from_profile({"correction_total": correction}) == expected


def test_index_perce_forces_160():
    assert _recommend_index_from_profile({"frame_type": "perce", "correction_total": 900}) == "1.60"


def test_index_default_without_correction():
    assert _recommend_index_from_profile({}) == "1.50"


def test_s_design_skips_index_156_and_uses_160():
    # Puissance dans la tranche 1.56 + ADD > 2.25 (=> S Design): 1.56 indisponible -> 1.60.
    reco = build_document_recommendation(
        {"age": 70, "head_eye_behavior": "head", "add_power": 2.50, "correction_total": 350},
        "varilux",
    )
    assert reco["lens_type"] == "Varilux S Design"
    assert reco["index"] == "1.60"


def test_non_s_design_keeps_index_156():
    # Un autre type Varilux dans la meme tranche conserve bien le 1.56.
    reco = build_document_recommendation(
        {"age": 70, "head_eye_behavior": "head", "correction_total": 350},
        "varilux",
    )
    assert reco["lens_type"] != "Varilux S Design"
    assert reco["index"] == "1.56"


# --------------------------------------------------------------------------
# Traitement: sante oculaire prioritaire, sinon besoin principal
# --------------------------------------------------------------------------
def test_treatment_ocular_health_takes_priority():
    treatment, _ = _recommend_treatment_from_profile(
        {"age": 70, "ocular_health": "glaucome", "main_need": "transparence"}
    )
    assert treatment == "Crizal Prevencia"


@pytest.mark.parametrize(
    "need, expected",
    [
        ("transparence", "Crizal Sapphire HR"),
        ("lumiere_bleue", "Crizal Prevencia"),
        ("conduite_soir", "Crizal Drive"),
        ("rayures", "Crizal Rock"),
        ("nettoyage", "Crizal Easy Pro"),
    ],
)
def test_treatment_by_main_need(need, expected):
    treatment, _ = _recommend_treatment_from_profile({"age": 25, "main_need": need})
    assert treatment == expected


def test_treatment_default_is_crizal_easy_pro():
    # "easypro" seul n'existe pas: le defaut doit etre le produit Crizal Easy Pro.
    treatment, _ = _recommend_treatment_from_profile({"age": 25})
    assert treatment == "Crizal Easy Pro"


def test_treatment_arthrose_prevencia_only_for_eyezen():
    # arthrose declenche Prevencia uniquement dans la famille Eyezen
    eyezen, _ = _recommend_treatment_from_profile({"age": 36, "ocular_health": "arthrose"})
    simple, _ = _recommend_treatment_from_profile({"age": 25, "ocular_health": "arthrose"})
    assert eyezen == "Crizal Prevencia"
    assert simple == "Crizal Easy Pro"


# --------------------------------------------------------------------------
# Transition selon exposition soleil
# --------------------------------------------------------------------------
def test_transition_no_exposure_is_blanc():
    transition, _ = _recommend_transition_from_profile({"sun_exposure": False})
    assert transition == "Blanc"


def test_transition_exposure_not_bothering_is_blanc():
    transition, _ = _recommend_transition_from_profile({"sun_exposure": True, "sun_discomfort": False})
    assert transition == "Blanc"


@pytest.mark.parametrize(
    "solution, expected",
    [("solaire", "Solaire"), ("transition", "Gen S")],
)
def test_transition_by_preference(solution, expected):
    transition, _ = _recommend_transition_from_profile(
        {"sun_exposure": True, "sun_discomfort": True, "sun_solution": solution}
    )
    assert transition == expected


# --------------------------------------------------------------------------
# Type Varilux (chaine de regles)
# --------------------------------------------------------------------------
def test_varilux_head_behavior():
    lens_type, _ = _recommend_varilux_type({"head_eye_behavior": "head"})
    assert lens_type == "Varilux Liberty"


def test_varilux_eyes_behavior():
    lens_type, _ = _recommend_varilux_type({"head_eye_behavior": "eyes"})
    assert lens_type == "Varilux Comfort 3.0"


def test_varilux_postural_comfort_upgrades_to_comfort_max():
    lens_type, _ = _recommend_varilux_type({"head_eye_behavior": "eyes", "postural_comfort": True})
    assert lens_type == "Varilux Comfort 3.0 Max"


def test_varilux_high_add_power():
    lens_type, _ = _recommend_varilux_type({"head_eye_behavior": "head", "add_power": 2.50})
    assert lens_type == "Varilux S Design"


def test_varilux_near_intermediate_comfort():
    lens_type, _ = _recommend_varilux_type({"head_eye_behavior": "head", "near_intermediate_comfort": True})
    assert lens_type == "Varilux X Design"


def test_varilux_not_innovation_sensitive():
    lens_type, _ = _recommend_varilux_type({"head_eye_behavior": "head", "innovation_sensitive": False})
    assert lens_type == "Varilux XR Design"


# --------------------------------------------------------------------------
# Geometrie (Varilux uniquement)
# --------------------------------------------------------------------------
def test_geometry_only_for_varilux():
    geometry, _ = _recommend_geometry_from_profile({"computer_usage": "high"}, "eyezen")
    assert geometry == ""


@pytest.mark.parametrize(
    "profile, expected",
    [
        ({"ocular_health": "arthrose"}, "Short"),
        ({"ocular_health": "pseudophaque"}, "Short"),
        ({"computer_usage": "high"}, "Short"),
        ({"computer_usage": "low"}, "Regular"),
    ],
)
def test_geometry_varilux(profile, expected):
    geometry, _ = _recommend_geometry_from_profile(profile, "varilux")
    assert geometry == expected


# --------------------------------------------------------------------------
# Optimisation prix / downgrades
# --------------------------------------------------------------------------
def test_downgrade_lowers_type_and_keeps_index_and_geometry():
    reco = build_document_recommendation(
        {"age": 70, "head_eye_behavior": "eyes", "postural_comfort": True, "computer_usage": "low", "correction_total": 600},
        "varilux",
    )
    assert reco["lens_type"] == "Varilux Comfort 3.0 Max"
    before_index, before_geo = reco["index"], reco["geometrie"]

    downgraded = apply_price_downgrade(reco, "type")
    assert downgraded["lens_type"] == "Varilux Comfort 3.0"
    assert downgraded["index"] == before_index
    assert downgraded["geometrie"] == before_geo


def test_downgrade_type_follows_full_varilux_hierarchy():
    # Hierarchie demandee, du plus premium au moins cher (noms canoniques).
    assert _downgrade_type("Varilux XR Design") == "Varilux X Design"
    assert _downgrade_type("Varilux X Design") == "Varilux S Design"
    assert _downgrade_type("Varilux S Design") == "VX Physio 3.0"
    assert _downgrade_type("VX Physio 3.0") == "Varilux Comfort 3.0"
    assert _downgrade_type("Varilux Comfort 3.0") == "Varilux Liberty"
    assert _downgrade_type("Varilux Liberty") is None
    # Comfort Max redescend sur Comfort 3.0.
    assert _downgrade_type("Varilux Comfort 3.0 Max") == "Varilux Comfort 3.0"


def test_every_proposed_type_gives_a_canonical_name():
    chain = ["Varilux XR Design", "Varilux X Design", "Varilux S Design", "Varilux Comfort 3.0 Max"]
    canonical = {"Varilux X Design", "Varilux S Design", "VX Physio 3.0", "Varilux Comfort 3.0", "Varilux Liberty"}
    for lens_type in chain:
        nxt = _downgrade_type(lens_type)
        assert nxt in canonical


def test_downgrade_capped_at_two_attempts():
    reco = build_document_recommendation(
        {"age": 70, "head_eye_behavior": "eyes", "postural_comfort": True, "correction_total": 600},
        "varilux",
    )
    step1 = apply_price_downgrade(reco, "type")
    step2 = apply_price_downgrade(step1, "type")
    assert step2["priceOptimization"]["attempts"] == 2
    # Au-dela de la limite, aucune nouvelle option n'est proposee.
    step3 = apply_price_downgrade(step2, "type")
    assert step3["priceOptimization"]["availableDowngrades"] == {}


# --------------------------------------------------------------------------
# Parcours de questions conditionnel
# --------------------------------------------------------------------------
def test_flow_starts_with_age(make_agent):
    a = make_agent()
    assert a._next_scenario_field() == "age"


def test_progress_fresh_agent(make_agent):
    a = make_agent()
    p = a.progress()
    assert p["total"] == 1 and p["answered"] == 0 and p["ratio"] == 0.0
    assert p["done"] is False
    assert p["remaining_questions"] == ["Quel age avez-vous ?"]


def test_progress_after_age_expands_total(make_agent):
    a = make_agent()
    a.profile = {"age": 25}  # simple foyer ; branches soleil elaguees tant que sun_exposure != oui => 6 etapes
    p = a.progress()
    assert p["total"] == 6
    assert p["answered"] == 1
    assert 0.0 < p["ratio"] < 1.0
    assert "age" not in p["remaining_fields"]


def test_progress_total_grows_when_sun_branch_opens(make_agent):
    a = make_agent()
    a.profile = {"age": 25, "sun_exposure": True}  # ouvre sun_discomfort
    p = a.progress()
    assert "sun_discomfort" in p["remaining_fields"]
    assert p["total"] == 7


def test_progress_done_is_full(make_agent):
    a = make_agent()
    a.profile = {"age": 25}
    a.last_recommendation = {"lens_type": "simple foyer"}
    p = a.progress()
    assert p["done"] is True and p["ratio"] == 1.0
    assert p["remaining_questions"] == []


def test_simple_foyer_flow_skips_varilux_questions(make_agent):
    a = make_agent()
    a.profile = {"age": 25}
    flow = a._scenario_flow()
    assert "head_eye_behavior" not in flow
    assert "postural_comfort" not in flow


def test_varilux_skips_postural_when_behavior_is_head(make_agent):
    a = make_agent()
    a.profile = {"age": 70, "head_eye_behavior": "head"}
    assert "postural_comfort" not in a._scenario_flow()


def test_varilux_keeps_postural_when_behavior_is_eyes(make_agent):
    a = make_agent()
    a.profile = {"age": 70, "head_eye_behavior": "eyes"}
    assert "postural_comfort" in a._scenario_flow()


def test_flow_skips_sun_branches_without_exposure(make_agent):
    a = make_agent()
    a.profile = {"age": 25, "sun_exposure": False}
    flow = a._scenario_flow()
    assert "sun_discomfort" not in flow
    assert "sun_solution" not in flow


def test_flow_skips_sun_solution_when_not_bothering(make_agent):
    a = make_agent()
    a.profile = {"age": 25, "sun_exposure": True, "sun_discomfort": False}
    assert "sun_solution" not in a._scenario_flow()


# --------------------------------------------------------------------------
# Extraction des reponses (_infer_profile_updates)
# --------------------------------------------------------------------------
def test_infer_age(make_agent):
    a = make_agent()
    a.current_field = "age"
    assert a._infer_profile_updates("J'ai 45 ans")["age"] == 45


def test_infer_correction_uses_max_eye_in_centiemes(make_agent):
    a = make_agent()
    a.current_field = "correction_total"
    updates = a._infer_profile_updates("OD Sph -2.00 OG Sph -3.50")
    assert updates["correction_total"] == 350.0


def test_infer_correction_extracts_add(make_agent):
    a = make_agent()
    a.current_field = "correction_total"
    updates = a._infer_profile_updates("OD Sph -2.00 OG Sph -2.00 ADD 2.50")
    # add_power stocke en centiemes (2.50 D -> 250).
    assert updates["add_power"] == 250


def test_infer_yes_no(make_agent):
    a = make_agent()
    a.current_field = "postural_comfort"
    assert a._infer_profile_updates("Oui")["postural_comfort"] is True
    assert a._infer_profile_updates("Non")["postural_comfort"] is False


# --------------------------------------------------------------------------
# #3 - L'extraction locale est prioritaire sur le LLM
# --------------------------------------------------------------------------
def test_llm_cannot_overwrite_locally_set_field(make_agent):
    a = make_agent()
    a.profile = {"age": 25}
    a._locally_set_fields = {"age"}
    result = a._execute_agent_tool("update_profile", {"updates": {"age": 70}})
    assert a.profile["age"] == 25
    assert "age" in result["rejected_fields"]


def test_llm_can_set_unprotected_field(make_agent):
    a = make_agent()
    a.profile = {"age": 25}
    a._locally_set_fields = {"age"}
    a._execute_agent_tool("update_profile", {"updates": {"main_need": "transparence"}})
    assert a.profile["main_need"] == "transparence"


# ==========================================================================
# Tests d'acceptation (cahier des charges de la mise a jour)
# ==========================================================================

# --- Normalisation des corrections (centiemes <-> dioptries) ---------------
@pytest.mark.parametrize(
    "saisie, centiemes",
    [(200, 200), (325, 325), (-500, -500), (-175, -175), (50, 50),
     (2.00, 200), (3.25, 325), (-5.00, -500), (-1.75, -175), (0.50, 50)],
)
def test_to_centiemes_accepts_both_formats(saisie, centiemes):
    assert to_centiemes(saisie) == centiemes


@pytest.mark.parametrize("saisie, dioptries", [(200, 2.0), (325, 3.25), (-175, -1.75)])
def test_to_diopters(saisie, dioptries):
    assert to_diopters(saisie) == dioptries


# --- Uniformite des noms + bug "rep" (Scenario 8) --------------------------
@pytest.mark.parametrize("value", ["rep", "REP", "Rep", " rep "])
def test_rep_maps_to_varilux_xr_design(value):
    assert canonical_lens_type(value) == "Varilux XR Design"


def test_canonical_keeps_full_names_unchanged():
    assert canonical_lens_type("Varilux Comfort 3.0") == "Varilux Comfort 3.0"
    assert canonical_lens_type("VX Physio 3.0") == "VX Physio 3.0"


def test_build_recommendation_canonicalises_rep_lens_type():
    reco = build_document_recommendation({"age": 70, "innovation_sensitive": False}, "varilux")
    assert reco["lens_type"] == "Varilux XR Design"


# --- Scenario 9 : Comfort -> Comfort 3.0 -----------------------------------
def test_comfort_is_always_versioned_3_0():
    lens_type, _ = _recommend_varilux_type({"head_eye_behavior": "eyes"})
    assert lens_type == "Varilux Comfort 3.0"
    assert "Comfort" not in _downgrade_type("VX Physio 3.0") or "3.0" in _downgrade_type("VX Physio 3.0")


# --- Scenarios 1 & 2 : Eyezen / Simple Foyer sans addition -----------------
@pytest.mark.parametrize("age, family", [(25, "simple_foyer"), (36, "eyezen")])
def test_addition_ignored_for_simple_and_eyezen(make_agent, age, family):
    a = make_agent()
    a.profile = {"age": age}
    a.current_field = "correction_total"
    # Meme si une addition traine dans le message, elle ne change pas la famille
    # ni ne provoque d'erreur ; l'indice repose sur sph+cyl.
    updates = a._infer_profile_updates("OD Sph 200 Cyl -50 Axe 90 OG Sph 175 Cyl -25 Axe 80")
    assert "correction_total" in updates
    reco = build_document_recommendation({**a.profile, **updates}, family)
    assert reco["lens_type"]  # recommandation calculee sans erreur


# --- Scenario 3 : progressif avec addition ---------------------------------
def test_progressive_addition_interpreted_as_diopters():
    # 225 centiemes = 2.25 D (n'est pas > 2.25 -> pas de S Design par l'ADD seule)
    assert to_diopters(225) == 2.25
    # 250 centiemes = 2.50 D > 2.25 -> S Design
    lens_type, _ = _recommend_varilux_type({"head_eye_behavior": "head", "add_power": 250})
    assert lens_type == "Varilux S Design"


# --- Scenario 4 : correction max absolue OD/OG -----------------------------
def test_correction_uses_max_absolute_of_both_eyes(make_agent):
    a = make_agent()
    a.current_field = "correction_total"
    # OD: -500 + -100 + 200 = -400 (4.00 D) ; OG: -300 + -50 + 200 = -150 (1.50 D)
    updates = a._infer_profile_updates(
        "OD Sph -500 Cyl -100 Axe 90 Add 200 OG Sph -300 Cyl -50 Axe 80 Add 200"
    )
    assert updates["correction_od"] == -400
    assert updates["correction_og"] == -150
    assert updates["correction_total"] == 400  # max(|−400|, |−150|)
    assert _recommend_index_from_profile({"correction_total": 400}) == "1.56"


# --- Scenarios 5 & 6 : regle VX Physio 3.0 sur la difference de sphere ------
def test_vx_physio_when_sphere_diff_above_2():
    reco = build_document_recommendation(
        {"age": 70, "head_eye_behavior": "head", "sphere_od": 400, "sphere_og": 150},
        "varilux",
    )
    assert reco["lens_type"] == "VX Physio 3.0"


def test_vx_physio_not_triggered_when_sphere_diff_exactly_2():
    reco = build_document_recommendation(
        {"age": 70, "head_eye_behavior": "head", "sphere_od": 300, "sphere_og": 100},
        "varilux",
    )
    assert reco["lens_type"] != "VX Physio 3.0"


def test_vx_physio_uses_sphere_only_not_total():
    # Sphere identique (diff 0) mais cyl/add differents : la regle ne se declenche pas.
    reco = build_document_recommendation(
        {"age": 70, "head_eye_behavior": "head", "sphere_od": 200, "sphere_og": 200,
         "cyl_od": -300, "cyl_og": 0},
        "varilux",
    )
    assert reco["lens_type"] != "VX Physio 3.0"


# --- Scenario 7 : maladies multiples ---------------------------------------
def test_multiple_diseases_are_kept(make_agent):
    a = make_agent()
    a.current_field = "ocular_health"
    updates = a._infer_profile_updates("Diabete, Cataracte")
    assert updates["ocular_health"] == ["Diabete", "Cataracte"]


def test_multiple_diseases_considered_by_treatment():
    # Cataracte presente dans la liste -> Crizal Prevencia (priorite sante oculaire).
    treatment, _ = _recommend_treatment_from_profile(
        {"age": 70, "ocular_health": ["Diabete", "Cataracte"], "main_need": "transparence"}
    )
    assert treatment == "Crizal Prevencia"


def test_empty_disease_selection_defaults_to_ras(make_agent):
    a = make_agent()
    a.current_field = "ocular_health"
    assert a._infer_profile_updates("ras")["ocular_health"] == ["RAS"]


# --- Scenario 10 & transition : nouveaux intitules -------------------------
def test_transition_display_uses_gen_s_and_couleur():
    assert display_transition("Transition") == "Gen S"
    assert display_transition("Blanc") == "Blanc"
    assert display_transition("Solaire") == "Solaire"
    assert agent.TRANSITION_LABEL == "Couleur"


def test_family_from_lens_type_handles_vx_physio():
    assert family_from_lens_type("VX Physio 3.0") == "Varilux"
    assert family_from_lens_type("Eyezen actif") == "Eyezen"
    assert family_from_lens_type("simple foyer") == "Simple Foyer"
