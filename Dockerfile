ARG VLLM_IMAGE=vllm/vllm-openai:v0.13.0
FROM ${VLLM_IMAGE}@sha256:d623253f2ba246378421c9642e20885e65257f38418ff26d48c81aea1702521b

ARG SOURCE_REVISION=local
ARG VLLM_VERSION=0.13.0
ARG MODEL_PROFILE=phase-1-qwen3-4b-awq
ARG BUILD_TIMESTAMP=unset

LABEL org.opencontainers.image.title="llm-inference-lab vLLM wrapper" \
      org.opencontainers.image.description="Thin Phase 1 wrapper around the official vLLM OpenAI-compatible image" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      org.opencontainers.image.source-revision="${SOURCE_REVISION}" \
      org.opencontainers.image.version="${VLLM_VERSION}" \
      org.opencontainers.image.vendor="llm-inference-lab-infra" \
      io.llm-inference-lab.model-profile="${MODEL_PROFILE}" \
      io.llm-inference-lab.build-timestamp="${BUILD_TIMESTAMP}"

RUN if ! getent group 1000 >/dev/null; then groupadd --gid 1000 vllm-lab; fi \
    && if ! getent passwd 1000 >/dev/null; then \
         useradd --uid 1000 --gid 1000 --no-create-home --home-dir /tmp \
           --shell /usr/sbin/nologin vllm-lab; \
       fi

ENV HOME=/tmp
USER 1000:1000
ENTRYPOINT ["vllm"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"]
