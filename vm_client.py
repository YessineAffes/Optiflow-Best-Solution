"""Client minimal pour le LLM de recommandation tournant dans la VM (devtunnel).

Le serveur VM ("Configurable Call Center LLM v3.0") expose son scenario de
recommandation cote serveur via POST /chat/recommendation. Il n'est PAS compatible
OpenAI : le champ `system` de /chat est ignore par le fine-tune. On parle donc a
l'endpoint natif.

Usage:
    from vm_client import VMRecommendationClient
    c = VMRecommendationClient()
    d = c.recommend("sess-1", profile={"age": 45, ...})
    print(d["recommendation"])      # None tant que missing_fields non vide
    print(d["next_questions"])      # questions a poser au client
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

VM_BASE_URL = os.environ.get(
    "VM_BASE_URL", "https://zf04gvh1-8020.uks1.devtunnels.ms"
).rstrip("/")
# Saute la page anti-phishing des devtunnels VS Code (sinon HTML au lieu du JSON).
_HEADERS = {
    "Content-Type": "application/json",
    "X-Tunnel-Skip-AntiPhishing-Page": "true",
}

# Champs attendus par le scenario VM + valeurs valides (decouvert empiriquement).
VM_FIELD_VALUES: dict[str, Any] = {
    "age": "entier",
    "head_eye_behavior": ["tete", "yeux"],
    "postural_comfort": [True, False],              # uniquement si head_eye_behavior == "yeux"
    "correction_total": "nombre (centiemes, ex 350)",
    "near_intermediate_comfort": [True, False],
    "innovation_sensitive": [True, False],
    "work_env": ["interieur", "exterieur", "mixte"],
    "light_discomfort": ["faible", "moyenne", "forte"],
    "sun_exposure": [True, False],
    "sun_solution": ["blanc", "transition", "solaire"],
    "frame_type": ["nylor", "plastique", "metallique", "perce"],
    "main_need": ["transparence", "lumiere_bleue", "conduite_soir", "rayures", "nettoyage"],
    "ocular_health": "texte libre (ras, glaucome, cataracte, ...)",
}


class VMRecommendationClient:
    def __init__(self, base_url: str = VM_BASE_URL, timeout: float = 180.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + path, data=body, method="POST", headers=_HEADERS
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.load(resp)

    def recommend(
        self,
        session_id: str,
        message: str | None = None,
        profile: dict[str, Any] | None = None,
        reset: bool = False,
        top_k: int = 4,
    ) -> dict[str, Any]:
        """Avance le parcours de reco. Renvoie response / profile / missing_fields /
        next_questions / recommendation / rag_results."""
        payload: dict[str, Any] = {"session_id": session_id, "top_k": top_k, "reset": reset}
        if message is not None:
            payload["message"] = message
        if profile is not None:
            payload["profile"] = profile
        return self._post("/chat/recommendation", payload)

    def health(self) -> dict[str, Any]:
        req = urllib.request.Request(self.base_url + "/health", headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)


if __name__ == "__main__":
    client = VMRecommendationClient()
    result = client.recommend(
        "demo-session",
        reset=True,
        profile={
            "age": 45, "head_eye_behavior": "yeux", "postural_comfort": True,
            "correction_total": 350, "near_intermediate_comfort": False,
            "innovation_sensitive": True, "work_env": "interieur",
            "light_discomfort": "faible", "sun_exposure": False, "sun_solution": "blanc",
            "frame_type": "nylor", "main_need": "transparence", "ocular_health": "ras",
        },
    )
    print("missing_fields:", result.get("missing_fields"))
    print(json.dumps(result.get("recommendation"), ensure_ascii=False, indent=2))
