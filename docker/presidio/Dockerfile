# =============================================================================
# AnonReq demo Presidio Analyzer — English + German
# =============================================================================
# DevOps owns publishing this image. It is not the stock Microsoft image.
#
# Base (pinned): mcr.microsoft.com/presidio-analyzer:2.2.354
#   - Listens on port 3000 (PRESIDIO default in that tag)
#   - Ships spaCy en_core_web_lg only
#   - AnalyzerEngine() loads English recognizers only
#
# This image adds:
#   - spaCy de_core_news_lg (German NER: PER -> PERSON, LOC -> LOCATION)
#   - conf/default.yaml so both en and de models load at startup
#   - conf/german_recognizers.yaml for street lines and PLZ+city
#   - an app.py patch so supported languages are ["en", "de"]
#
# Size and runtime:
#   - de_core_news_lg is about 540 MB on disk, on top of en_core_web_lg
#   - Budget at least 4 GB RAM for this container once both models are loaded
#   - Cold start is slower than the stock image; compose start_period is 120s
#
# Build (from the repo root, also what docker compose does):
#   docker compose build presidio-analyzer
# Tag written by compose: anonreq/presidio-analyzer:2.2.354-de
#
# Publishing to a registry (replace the compose `build` block afterwards):
#   docker tag anonreq/presidio-analyzer:2.2.354-de <registry>/anonreq/presidio-analyzer:2.2.354-de
#   docker push <registry>/anonreq/presidio-analyzer:2.2.354-de
#
# The model must match the base image's spaCy 3.x. `spacy download` resolves
# that. If the base tag moves, re-check this Dockerfile before bumping it.
# =============================================================================

FROM mcr.microsoft.com/presidio-analyzer:2.2.354

USER root
WORKDIR /usr/bin/presidio-analyzer

# German NER model, installed into the image's pipenv (PIPENV_VENV_IN_PROJECT).
RUN pipenv run python -m spacy download de_core_news_lg \
    && pipenv run python -c "import spacy; spacy.load('en_core_web_lg'); spacy.load('de_core_news_lg')"

COPY default.yaml /usr/bin/presidio-analyzer/conf/default.yaml
COPY german_recognizers.yaml /usr/bin/presidio-analyzer/conf/german_recognizers.yaml
COPY enable_german.py /tmp/enable_german.py

RUN pipenv run python /tmp/enable_german.py /usr/bin/presidio-analyzer/app.py \
    && rm /tmp/enable_german.py \
    && grep -F "supported_languages=['en', 'de']" /usr/bin/presidio-analyzer/app.py \
    && grep -F "de_core_news_lg" /usr/bin/presidio-analyzer/conf/default.yaml
