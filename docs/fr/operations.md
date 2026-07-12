> translated from en/operations.md

# Guide des opérations AnonReq

Ce guide fournit des runbooks opérationnels, des structures de configuration, des spécifications de surveillance et des étapes de dépannage pour les administrateurs de la passerelle AnonReq.

## Gestion de la configuration

Les configurations de la passerelle sont gérées via des fichiers YAML chargés au démarrage du conteneur. Les fichiers principaux sont :

- **Politique du moteur (`config/policy.yaml`) :** Définit les règles des tenants, les limites de débit, les budgets de dépenses et les limites géographiques.
- **Configuration des SLO (`config/slo.yaml`) :** Déclare les cibles pour le taux de réussite, la latence, les états fail-secure et les enregistrements d'audit.
- **Trust Center (`config/trust_center.yaml`) :** Contrôle l'accès aux portails publics de conformité.

Les configurations sont rechargées automatiquement à la réception d'un signal `SIGHUP`.

### Exemple de configuration de politique

```yaml
version: "1.0"
rules:
  - rule_id: "block_restricted_pii"
    name: "Block Restricted Data"
    action: "BLOCK"
    priority: 100
    enabled: true
    conditions:
      classification_level: "Restricted"
rate_limits:
  enabled: true
  rpm: 1000
```

## Surveillance des objectifs de niveau de service (SLO)

AnonReq suit 4 SLO principaux pour garantir la sécurité et les performances du système :

1. **Taux de réussite :** Au moins 99,9 % des requêtes de la passerelle doivent réussir.
2. **Latence P95 :** Le délai de traitement doit rester inférieur ou égal à 100 ms.
3. **Taux de fail-secure :** Moins de 0,1 % des transactions doivent déclencher des blocages de sécurité.
4. **Taux d'écriture d'audit :** Au moins 99,99 % des écritures de journaux d'audit doivent réussir.

### Infrastructure de surveillance

- **Tableau de bord Prometheus :** Récupère les métriques depuis `/metrics` sur le port `8080`.
- **Tableau de bord Grafana :** Visualise le respect des SLO et les budgets d'erreur.

## Opérations d'administration CLI

Les administrateurs système utilisent des requêtes curl pour interroger l'état, collecter les métriques et effectuer des mises à jour.

### 1. Consulter les politiques actives
```bash
curl -X GET http://localhost:8080/v1/admin/policies   -H "Authorization: Bearer <ADMIN_API_KEY>"   -H "X-AnonReq-Role: operator"   -H "X-AnonReq-Tenant-ID: default"
```

### 2. Interroger la conformité SLO en temps réel
```bash
curl -H "Authorization: Bearer <ADMIN_API_KEY>"      -H "X-AnonReq-Role: administrator"      http://localhost:8080/v1/governance/status
```

### 3. Vérifier l'intégrité de la chaîne d'audit
```bash
curl -X POST http://localhost:8080/v1/governance/audit/verify   -H "Authorization: Bearer <ADMIN_API_KEY>"   -H "X-AnonReq-Role: administrator"
```

## Dépannage et résolution d'incidents

Lorsqu'un SLO est enfreint, la passerelle émet des alertes. Les opérateurs doivent vérifier les éléments suivants :

- **Baisse du taux de réussite :** Vérifier la connectivité aux fournisseurs (OpenAI/Gemini) et la charge CPU de Valkey.
- **Pics de latence :** Surveiller l'utilisation du CPU/mémoire des conteneurs de la passerelle et augmenter le nombre d'instances si nécessaire.
- **Hausse du taux de fail-secure :** Inspecter les journaux pour vérifier si le conteneur Presidio Analyzer répond ou si des expressions régulières posent problème.
- **Échecs d'écriture d'audit :** Vérifier la connexion avec Valkey ou le pool de connexion de la base de données SQL. Vérifier l'espace disque restant.

---
*Ce document est une traduction de l'original en anglais. En cas de divergence, la version anglaise prévaut.*
