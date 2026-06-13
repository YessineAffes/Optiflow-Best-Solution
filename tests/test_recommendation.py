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
    [("solaire", "Solaire"), ("transition", "Transition")],
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
    assert lens_type == "Varilux Comfort"


def test_varilux_postural_comfort_upgrades_to_comfort_max():
    lens_type, _ = _recommend_varilux_type({"head_eye_behavior": "eyes", "postural_comfort": True})
    assert lens_type == "Varilux Comfort Max"


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
    assert reco["lens_type"] == "Varilux Comfort Max"
    before_index, before_geo = reco["index"], reco["geometrie"]

    downgraded = apply_price_downgrade(reco, "type")
    assert downgraded["lens_type"] == "Varilux Comfort"
    assert downgraded["index"] == before_index
    assert downgraded["geometrie"] == before_geo


def test_downgrade_type_follows_full_varilux_hierarchy():
    # Hierarchie demandee, du plus premium au moins cher.
    assert _downgrade_type("Varilux XR Design") == "Varilux X Design"
    assert _downgrade_type("Varilux X Design") == "Varilux S Design"
    assert _downgrade_type("Varilux S Design") == "Varilux Physio"
    assert _downgrade_type("Varilux Physio") == "Varilux Comfort"
    assert _downgrade_type("Varilux Comfort") == "Varilux Liberty"
    assert _downgrade_type("Varilux Liberty") is None
    # Comfort Max redescend sur Comfort.
    assert _downgrade_type("Varilux Comfort Max") == "Varilux Comfort"


def test_every_proposed_type_keeps_varilux_prefix():
    chain = ["Varilux XR Design", "Varilux X Design", "Varilux S Design", "Varilux Comfort Max"]
    for lens_type in chain:
        nxt = _downgrade_type(lens_type)
        assert nxt is not None and nxt.startswith("Varilux ")


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
    assert updates["add_power"] == 2.50


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
