> translated from en/faq.md

# Foire Aux Questions

## Que se passe-t-il lorsque la détection des PII échoue ?

La passerelle est sécurisée en cas de panne (fail-secure). En cas d'erreur de détection, de cache ou de dépassement de délai du fournisseur, la requête renvoie une erreur HTTP 5xx et aucune donnée n'est transmise en amont. Consultez la section sur l'architecture fail-secure dans le fichier README pour plus de détails.

## Mes données sont-elles conservées quelque part ?

Non. Tous les mappages de PII vers des jetons sont stockés dans Valkey sans persistance (`save ""`). Les mappages sont supprimés une fois la réponse envoyée. Les journaux ne contiennent que des métadonnées, aucune valeur de PII brute.

## Quels fournisseurs de LLM sont pris en charge ?

OpenAI, Azure OpenAI, Anthropic (Claude), Google Gemini et Ollama (modèles locaux). La passerelle traduit le format de requête compatible OpenAI vers le protocole natif de chaque fournisseur.

## Comment fonctionne le streaming ?

La passerelle utilise une machine à états finis (FSM) de type Tail_Buffer pour gérer les jetons divisés entre les limites des blocs SSE. Les jetons originaux sont restaurés en temps réel au fur et à mesure de l'arrivée des blocs de données. La réponse finale est identique, octet par octet, à celle du mode standard.

## Quel est le format du jeton ?

Les PII détectées sont remplacées par des espaces réservés de type `[TYPE_N]`, où `TYPE` est le type de l'entité (par exemple, `EMAIL`, `PHONE`) et `N` est un index unique. Le traitement des jetons lors de la restauration est insensible à la casse et accepte l'absence de crochets.

## Comment les paramètres de langue (locales) sont-ils gérés ?

Définissez l'en-tête `X-AnonReq-Locale` pour activer la détection spécifique à une langue. Plusieurs langues peuvent être combinées (séparées par des virgules). Les langues non prises en charge renvoient HTTP 400.

## Puis-je ajouter des modèles de détection personnalisés ?

Oui, des analyseurs regex personnalisés peuvent être ajoutés via un fichier de configuration YAML et rechargés à chaud sans redémarrage. Consultez la documentation de configuration pour connaître le format des règles.

## Comment puis-je contribuer ?

Les contributions sont les bienvenues sous licence Apache 2.0. Consultez le guide de contribution dans le dépôt pour connaître les directives relatives aux pull requests et la configuration du développement.

---
*Ce document est une traduction de l'original en anglais. En cas de divergence, la version anglaise prévaut.*
