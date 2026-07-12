> translated from en/security.md

# Politique de sécurité AnonReq

Ce document présente la posture de sécurité, les garanties de traitement des données et les procédures de réponse aux incidents pour la passerelle AnonReq.

## Posture de sécurité

AnonReq repose sur une architecture Zero-Trust. Nous considérons que tous les serveurs de modèles externes et les réseaux publics sont non fiables, et nous appliquons des limites de sécurité strictes :

- **Privilège minimal :** Toutes les routes administratives et les modifications de configuration nécessitent une autorisation validée via des clés API à haute entropie.
- **Sécurisation par défaut (Fail-Secure) :** Tous les paramètres de configuration adoptent par défaut l'état le plus restrictif (par exemple, le portail Trust Center désactivé par défaut, presets de conformité obligatoires, blocages par défaut).
- **Isolation :** Les données des tenants, les définitions de politiques et les caches associés aux sessions sont isolés dans Valkey par des préfixes.

## Garanties d'anonymisation et de traitement des données

AnonReq garantit que les données sensibles brutes ne sont jamais exposées à des réseaux externes :

1. **Protection des données sortantes :** La passerelle intercepte toutes les requêtes de texte, JSON et formulaires multipart. Les données sensibles sont remplacées par des jetons (par exemple, `[EMAIL_N]`) avant d'être envoyées sur le réseau.
2. **Modèle de mémoire éphémère :** Les mappages des jetons sont stockés exclusivement dans la mémoire cache Valkey/Redis. Ils ont un TTL limité et sont supprimés immédiatement après le traitement de la réponse ou l'expiration de la session.
3. **Pas de PII dans les journaux :** Les journaux système et les métriques Prometheus contiennent uniquement des métadonnées. Les contenus bruts et les clés de jetons ne sont jamais enregistrés sur disque.

## Protocole de réponse aux incidents

AnonReq maintient un protocole actif pour gérer les incidents de sécurité et de conformité. Les incidents sont classés en trois niveaux :

### Niveaux de gravité

- **Gravité 1 (Critique) :** Fuite de PII en texte clair ou faille de données ; échec de la vérification de la signature cryptographique de la chaîne d'audit. Résolution requise sous 1 heure.
- **Gravité 2 (Majeure) :** Panne de service ou interruption complète du pipeline de nettoyage. Résolution requise sous 4 heures.
- **Gravité 3 (Mineure) :** Alertes opérationnelles ou ralentissements de performances mineurs (dépassement de délai, croissance de la file d'attente DLQ). Investigation requise sous 24 heures.

### Déroulement de la réponse

1. **Détection :** Détectée via les alertes Prometheus ou les vérifications d'intégrité de la chaîne d'audit.
2. **Triage :** L'ingénieur de garde confirme l'incident et assigne le niveau de gravité.
3. **Confinement :** Suspension immédiate de la passerelle ou blocage des clés API du tenant concerné.
4. **Remédiation :** Correction de la faille par l'équipe de développement et déploiement d'un conteneur mis à jour.
5. **Rétablissement :** Reprise du trafic et vérification finale de l'intégrité de la chaîne d'audit.

---
*Ce document est une traduction de l'original en anglais. En cas de divergence, la version anglaise prévaut.*
