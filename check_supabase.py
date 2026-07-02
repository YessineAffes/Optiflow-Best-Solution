"""Diagnostic de connexion Supabase pour Optiflow Best Solution.

Usage :
    python check_supabase.py

Verifie, avec la MEME configuration que l'application (db._resolve_config) :
  1. la presence et la validite (ASCII) des identifiants ;
  2. la lecture (count) sur chaque table ;
  3. une ecriture aller-retour (insert + delete) sur la table products.

N'affiche jamais la cle en clair (masquee). La ligne de test inseree est
immediatement supprimee.
"""
from __future__ import annotations

import db

TABLES = ["products", "evaluations", "expert_annotations", "recommendation_logs"]


def _mask(secret: str) -> str:
    if not secret:
        return "(vide)"
    return f"{secret[:8]}...{secret[-4:]} ({len(secret)} caracteres)" if len(secret) > 14 else "***"


def main() -> int:
    url, key = db._resolve_config()
    print("== Identifiants ==")
    print("  SUPABASE_URL :", _mask(url), "| ASCII:", url.isascii() if url else "n/a")
    print("  SUPABASE_KEY :", _mask(key), "| ASCII:", key.isascii() if key else "n/a")

    store = db.get_store()
    if not store.enabled:
        print("\n[X] Supabase NON connecte.")
        print("   Raison :", store.last_error or "identifiants manquants (voir SETUP_SUPABASE.md).")
        return 1
    print("\n[OK] Client Supabase initialise.")

    print("\n== Lecture (count) ==")
    read_ok = True
    for table in TABLES:
        try:
            res = store.client.table(table).select("*", count="exact").limit(1).execute()
            print(f"  [OK] {table:22s} {res.count} enregistrement(s)")
        except Exception as exc:
            read_ok = False
            print(f"  [X]  {table:22s} {type(exc).__name__}: {str(exc)[:140]}")

    print("\n== Ecriture aller-retour (products) ==")
    write_ok = True
    try:
        inserted = store.client.table("products").insert(
            {"lens_type": "__TEST_CONNEXION__", "family": "varilux"}
        ).execute()
        row_id = inserted.data[0]["id"]
        store.client.table("products").delete().eq("id", row_id).execute()
        print("  [OK] insert + delete reussis (ligne de test nettoyee).")
    except Exception as exc:
        write_ok = False
        print(f"  [X]  {type(exc).__name__}: {str(exc)[:200]}")

    print()
    if read_ok and write_ok:
        print(">>> Supabase FONCTIONNEL (lecture + ecriture).")
        return 0
    print(">>> Probleme detecte : voir les erreurs ci-dessus (RLS, cle, ou incident Supabase).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
