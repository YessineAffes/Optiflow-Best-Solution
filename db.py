"""Couche d'acces Supabase pour Optiflow Best Solution.

Stocke deux choses :
- les produits (catalogue de verres) ;
- les annotations expert (note + verification associees a chaque question du
  parcours), collectees comme jeu de donnees d'amelioration.

Tout est optionnel : si Supabase n'est pas configure (variables vides) ou
indisponible, les fonctions renvoient des valeurs vides / False au lieu de
lever une exception. C'est le meme repli gracieux que l'agent applique au LLM,
pour que l'app tourne en local sans base.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv

try:
    from supabase import Client, create_client
except Exception:  # pragma: no cover - dependance optionnelle
    Client = None  # type: ignore
    create_client = None  # type: ignore

load_dotenv()
logger = logging.getLogger("optiflow.db")

PRODUCTS_TABLE = "products"
ANNOTATIONS_TABLE = "expert_annotations"
LOGS_TABLE = "recommendation_logs"


class SupabaseStore:
    """Acces fin a Supabase, sans jamais faire planter l'appelant."""

    def __init__(self, url: str = "", key: str = ""):
        self.client: Client | None = None
        self.last_error: str | None = None
        if not (url and key):
            return
        if create_client is None:
            self.last_error = "Le paquet 'supabase' n'est pas installe."
            logger.info("%s", self.last_error)
            return
        try:
            self.client = create_client(url, key)
        except Exception as exc:  # pragma: no cover - depend du reseau
            self.last_error = str(exc)
            logger.warning("Connexion Supabase impossible: %s", exc)

    @property
    def enabled(self) -> bool:
        return self.client is not None

    # ---- Produits -------------------------------------------------------
    def list_products(self, family: str | None = None) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        try:
            query = self.client.table(PRODUCTS_TABLE).select("*").order("created_at", desc=True)
            if family:
                query = query.eq("family", family)
            return query.execute().data or []
        except Exception as exc:
            logger.warning("list_products a echoue: %s", exc)
            return []

    def add_product(self, product: dict[str, Any]) -> bool:
        if not self.enabled:
            self.last_error = "Supabase non configure."
            return False
        try:
            self.client.table(PRODUCTS_TABLE).insert(product).execute()
            return True
        except Exception as exc:
            self.last_error = str(exc)
            logger.warning("add_product a echoue: %s", exc)
            return False

    def delete_product(self, product_id: Any) -> bool:
        if not self.enabled:
            return False
        try:
            self.client.table(PRODUCTS_TABLE).delete().eq("id", product_id).execute()
            return True
        except Exception as exc:
            self.last_error = str(exc)
            logger.warning("delete_product a echoue: %s", exc)
            return False

    # ---- Annotations expert --------------------------------------------
    def add_annotation(
        self,
        field: str,
        question: str,
        note: str,
        verified: bool,
        author: str = "",
    ) -> bool:
        if not self.enabled:
            self.last_error = "Supabase non configure."
            return False
        payload = {
            "field": field,
            "question": question,
            "note": note,
            "verified": verified,
            "author": author,
        }
        try:
            self.client.table(ANNOTATIONS_TABLE).insert(payload).execute()
            return True
        except Exception as exc:
            self.last_error = str(exc)
            logger.warning("add_annotation a echoue: %s", exc)
            return False

    def list_annotations(self, field: str | None = None) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        try:
            query = self.client.table(ANNOTATIONS_TABLE).select("*").order("created_at", desc=True)
            if field:
                query = query.eq("field", field)
            return query.execute().data or []
        except Exception as exc:
            logger.warning("list_annotations a echoue: %s", exc)
            return []

    # ---- Journal des recommandations (optionnel) -----------------------
    def log_recommendation(self, profile: dict[str, Any], reco: dict[str, Any], family: str | None) -> bool:
        if not self.enabled:
            return False
        try:
            self.client.table(LOGS_TABLE).insert(
                {"family": family, "profile": profile, "reco": reco}
            ).execute()
            return True
        except Exception as exc:
            logger.warning("log_recommendation a echoue: %s", exc)
            return False


def _resolve_config() -> tuple[str, str]:
    """Lit la config depuis l'environnement (.env) puis, en repli, depuis les
    secrets Streamlit (Streamlit Cloud) sans dependance dure a streamlit."""
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_KEY", "").strip()
    if url and key:
        return url, key
    try:  # pragma: no cover - depend du contexte d'execution
        import streamlit as st

        url = url or str(st.secrets.get("SUPABASE_URL", "") or "").strip()
        key = key or str(st.secrets.get("SUPABASE_KEY", "") or "").strip()
    except Exception:
        pass
    return url, key


@lru_cache(maxsize=1)
def get_store() -> SupabaseStore:
    """Instance partagee (lecture/ecriture sans etat client mutable)."""
    url, key = _resolve_config()
    return SupabaseStore(url, key)
