> translated from en/architecture.md

# Architecture de la passerelle AnonReq

Ce document fournit un résumé de l'architecture de la passerelle AnonReq. Il détaille la topologie des composants, le cycle de vie des requêtes et les invariants de sécurité fondamentaux.

## Présentation du système

AnonReq est une passerelle de sécurité et d'anonymisation de l'IA auto-hébergée conçue pour s'interposer entre les applications d'entreprise et les fournisseurs de LLM (Large Language Model) externes ou locaux. En agissant comme un proxy d'interception, elle garantit que les données sensibles (telles que les PII, PHI, PCI ou les secrets d'entreprise) sont classifiées, tokenisées et nettoyées avant de franchir la limite de confiance du réseau d'entreprise.

```
┌─────────────────┐       ┌─────────────────┐       ┌───────────────────┐
│                 │       │                 │       │                   │
│   Application   │──────>│ Passerelle      │──────>│ Fournisseurs LLM  │
│   d'entreprise  │<──────│ AnonReq         │<──────│ (OpenAI, Gemini)  │
│                 │       │ (Auto-hébergée) │       │                   │
└─────────────────┘       └─────────────────┘       └───────────────────┘
```

## Cycle de vie des requêtes

Chaque requête envoyée à un fournisseur externe via AnonReq passe par un pipeline de traitement structuré :

1. **Réception et distribution du contenu :** La requête arrive à la passerelle. Le distributeur de types de contenu inspecte les en-têtes et dirige le contenu vers l'analyseur approprié (Text, JSON ou Multipart).
2. **Classification :** Le moteur de classification évalue la requête par rapport aux niveaux de sécurité configurés. Si un contenu contient des données restreintes non autorisées, le moteur bloque la requête ou détermine s'il faut utiliser le routage local, l'anonymisation ou la transmission directe.
3. **Détection :** Le moteur de détection combine des filtres regex/checksum, l'intégration de Presidio et des algorithmes d'amélioration de contexte pour identifier les données sensibles (e-mails, numéros de téléphone, cartes bancaires).
4. **Tokenisation :** Les valeurs sensibles identifiées sont extraites et remplacées par des jetons anonymes (par exemple, `[EMAIL_0]`, `[PERSON_1]`). Les mappages uniques et aléatoires sont stockés dans le gestionnaire de cache Valkey/Redis associé à la session.
5. **Adaptateur de fournisseur :** La requête nettoyée et tokenisée est traduite par l'adaptateur dans le format de l'API LLM cible (par exemple, conversion du format OpenAI vers Anthropic/Gemini) et transmise.
6. **Réponse LLM :** Le modèle externe renvoie sa réponse contenant les jetons.
7. **Restauration :** Le moteur de restauration récupère les mappages correspondants dans le gestionnaire de cache et remplace les jetons par les valeurs d'origine dans la réponse (compatible avec les flux SSE).
8. **Sortie :** La réponse originale et restaurée est renvoyée à l'application cliente.

## Composants principaux

- **Proxy/Passerelle :** Application FastAPI exécutant une boucle réseau ASGI.
- **Moteur de classification :** PDP (Policy Decision Point) et PEP (Policy Enforcement Point) évaluant la conformité et les politiques de risque.
- **Moteur de détection :** Analyseur multi-locale avec détection regex et Microsoft Presidio.
- **Moteurs de tokenisation et de restauration :** Code chargé de la substitution et de la restauration des jetons.
- **Gestionnaire de cache :** Instance Valkey/Redis éphémère conservant les mappages en mémoire avec un TTL strict.
- **Adaptateurs de fournisseurs :** Couche de compatibilité traduisant les requêtes API en temps réel.

## Invariants de sécurité fondamentaux

- **Zéro exposition :** Les données PII brutes ne doivent en aucun cas franchir la limite du réseau d'entreprise vers les fournisseurs externes.
- **Comportement Fail-Secure (sécurisé par défaut) :** Toute exception, dépassement de délai, indisponibilité du cache ou erreur de classification doit bloquer immédiatement la transmission sortante et renvoyer une réponse HTTP 503 ou 403 à l'application cliente.
- **Télémétrie sans PII :** Les pistes d'audit, les journaux système et les métriques Prometheus contiennent uniquement des métadonnées. Aucune valeur brute ou clé de jeton n'est enregistrée.
- **Stockage éphémère :** Les mappages sont conservés uniquement en mémoire cache temporaire et supprimés immédiatement après le traitement de la transaction.

---
*Ce document est une traduction de l'original en anglais. En cas de divergence, la version anglaise prévaut.*
