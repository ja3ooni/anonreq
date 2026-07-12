> translated from en/faq.md

# Preguntas frecuentes

## ¿Qué ocurre cuando falla la detección de PII?

La pasarela es segura por defecto en caso de fallo (fail-secure). Si se producen errores de detección, caché o tiempo de espera del proveedor, la solicitud devuelve HTTP 5xx y no se reenvía ningún dato río arriba. Consulte la arquitectura de seguridad en el archivo README del proyecto para obtener más detalles.

## ¿Se conservan mis datos en algún lugar?

No. Todos los mapeos de PII a token se almacenan en Valkey sin persistencia (`save ""`). Los mapeos se eliminan después de que se envía la respuesta. Los registros contienen metadatos solamente — no hay valores brutos de PII.

## ¿Qué proveedores de LLM son compatibles?

OpenAI, Azure OpenAI, Anthropic (Claude), Google Gemini y Ollama (modelos locales). La pasarela traduce el formato de solicitud compatible con OpenAI al protocolo nativo de cada proveedor.

## ¿Cómo funciona la transmisión (streaming)?

La pasarela utiliza una FSM de tipo Tail_Buffer para manejar los tokens divididos a través de los límites de los fragmentos de SSE. Los tokens se restauran en tiempo real a medida que llegan los fragmentos. La respuesta es idéntica byte por byte al modo que no es de transmisión.

## ¿Cuál es el formato del token?

La PII detectada se reemplaza con marcadores de posición `[TYPE_N]`, donde `TYPE` es el tipo de entidad (por ejemplo, `EMAIL`, `PHONE`) y `N` es un índice único. La coincidencia del token no distingue entre mayúsculas y minúsculas y los corchetes son opcionales durante la restauración.

## ¿Cómo se manejan las configuraciones regionales (locales)?

Establezca la cabecera `X-AnonReq-Locale` para activar la detección específica de una configuración regional. Se pueden combinar múltiples configuraciones regionales (separadas por comas). Las configuraciones regionales no compatibles devuelven HTTP 400.

## ¿Puedo añadir patrones de detección personalizados?

Sí, se pueden añadir reconocedores regex personalizados a través de un archivo de configuración YAML y recargarse en caliente sin reiniciar. Consulte la documentación de configuración para conocer el formato de la regla.

## ¿Cómo contribuyo?

Las contribuciones son bienvenidas bajo la licencia Apache 2.0. Consulte la guía de contribución en el repositorio para conocer las pautas de solicitud de extracción y las instrucciones de configuración del desarrollo.

---
*Este documento es una traducción del original en inglés. En caso de discrepancia, prevalecerá la versión en inglés.*
