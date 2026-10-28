# =============================================================================
# AnonReq demo Presidio Analyzer — English + German
# =============================================================================
# DevOps owns publishing this image and must run the first real
# `docker compose build presidio-analyzer`. A quoted heredoc used to leave
# the wheel URL and sha256 unexpanded, and renamed /tmp/*.whl files were
# rejected by pip. This Dockerfile passes ARGs as environment variables and
# keeps canonical wheel filenames. Confirm that build in your registry
# pipeline before dropping the compose `build` key.
#
# Base (pinned): mcr.microsoft.com/presidio-analyzer:2.2.354
#   - Python 3.9.19, spaCy 3.7.4, listens on port 3000
#   - Already about 9 GB. 3.7.x model wheels are compatible.
#   - Ships an unpinned en_core_web_lg and English recognizers only
#   - Runs as root until this image drops to uid 10001
#
# The e235aa3 build failed: a quoted Python heredoc left the wheel URL
# unexpanded, and pip rejected renamed /tmp/*.whl files.
# DevOps runs the real rebuild of this Dockerfile.
#
# This image:
#   - Reinstalls en_core_web_lg==3.7.1 and de_core_news_lg==3.7.0 from
#     exact wheel URLs checked with sha256 (spaCy 3.7 line; do not float these)
#   - Loads both models via conf/default.yaml
#   - Adds conf/german_recognizers.yaml (street line and PLZ+city)
#   - Patches app.py so supported languages are ["en", "de"]
#   - Drops to USER presidio (uid 10001) after the installs
#   - Healthcheck POSTs /analyze with language=de and requires a PERSON span
#
# Size and runtime:
#   - Each lg model is about 540–560 MB on disk
#   - Budget at least 4 GB RAM once both models are loaded
#   - Cold start is slower than the stock image; start period is 120s
#
# Build (from the repo root, also what docker compose does):
#   docker compose build presidio-analyzer
# Tag written by compose: anonreq/presidio-analyzer:2.2.354-de
#
# Publishing to a registry (replace the compose `build` block afterwards):
#   docker tag anonreq/presidio-analyzer:2.2.354-de <registry>/anonreq/presidio-analyzer:2.2.354-de
#   docker push <registry>/anonreq/presidio-analyzer:2.2.354-de
#
# If the base tag moves off spaCy 3.7, bump both wheel versions together.
# The version assert below fails the build when they do not match.
# =============================================================================

FROM mcr.microsoft.com/presidio-analyzer:2.2.354

USER root
WORKDIR /usr/bin/presidio-analyzer

# Exact wheels. en_core_web_lg in the base image was installed by
# `spacy download` with no version pin. Reinstall both from pinned URLs.
# ARG values are passed as environment variables on the RUN line (not inside
# a quoted heredoc). fetch_models.py writes each wheel under its canonical
# filename; pip rejects a renamed .whl.
ARG EN_CORE_WEB_LG_VERSION=3.7.1
ARG EN_CORE_WEB_LG_URL=https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.7.1/en_core_web_lg-3.7.1-py3-none-any.whl
ARG EN_CORE_WEB_LG_SHA256=ab70aeb6172cde82508f7739f35ebc9918a3d07debeed637403c8f794ba3d3dc
ARG DE_CORE_NEWS_LG_VERSION=3.7.0
ARG DE_CORE_NEWS_LG_URL=https://github.com/explosion/spacy-models/releases/download/de_core_news_lg-3.7.0/de_core_news_lg-3.7.0-py3-none-any.whl
ARG DE_CORE_NEWS_LG_SHA256=1451e06dedb5c3bb096127bf7c2117c253265fdfcad29ee488ff57bec5f78eaa
COPY fetch_models.py /tmp/fetch_models.py
RUN EN_CORE_WEB_LG_URL="${EN_CORE_WEB_LG_URL}" \
    EN_CORE_WEB_LG_SHA256="${EN_CORE_WEB_LG_SHA256}" \
    DE_CORE_NEWS_LG_URL="${DE_CORE_NEWS_LG_URL}" \
    DE_CORE_NEWS_LG_SHA256="${DE_CORE_NEWS_LG_SHA256}" \
    WHEEL_DEST=/tmp \
    python /tmp/fetch_models.py \
    && pipenv run python -m pip install --no-deps --disable-pip-version-check \
        /tmp/en_core_web_lg-3.7.1-py3-none-any.whl \
        /tmp/de_core_news_lg-3.7.0-py3-none-any.whl \
    && rm -f /tmp/fetch_models.py /tmp/en_core_web_lg-3.7.1-py3-none-any.whl /tmp/de_core_news_lg-3.7.0-py3-none-any.whl \
    && pipenv run python -c "import importlib.metadata as m; assert m.version('en-core-web-lg') == '${EN_CORE_WEB_LG_VERSION}'; assert m.version('de-core-news-lg') == '${DE_CORE_NEWS_LG_VERSION}'; import spacy; spacy.load('en_core_web_lg'); spacy.load('de_core_news_lg')"

COPY default.yaml /usr/bin/presidio-analyzer/conf/default.yaml
COPY german_recognizers.yaml /usr/bin/presidio-analyzer/conf/german_recognizers.yaml
COPY healthcheck.py /usr/bin/presidio-analyzer/healthcheck.py
COPY enable_german.py /tmp/enable_german.py

RUN pipenv run python /tmp/enable_german.py /usr/bin/presidio-analyzer/app.py \
    && rm /tmp/enable_german.py \
    && grep -F "supported_languages=['en', 'de']" /usr/bin/presidio-analyzer/app.py \
    && grep -F "de_core_news_lg" /usr/bin/presidio-analyzer/conf/default.yaml \
    && groupadd --system --gid 10001 presidio \
    && useradd --system --uid 10001 --gid presidio --home-dir /home/presidio --create-home --shell /usr/sbin/nologin presidio \
    && chown -R presidio:presidio /usr/bin/presidio-analyzer /home/presidio

ENV HOME=/home/presidio
USER presidio

# Bypass pipenv at runtime so the non-root user does not need to write a venv.
CMD ["/usr/bin/presidio-analyzer/.venv/bin/python", "app.py", "--host", "0.0.0.0"]

HEALTHCHECK --interval=15s --timeout=15s --start-period=120s --retries=10 \
    CMD python /usr/bin/presidio-analyzer/healthcheck.py
