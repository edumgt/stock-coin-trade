FROM quantconnect/lean:latest

USER root

COPY GenericBuyAndHold.py /module/GenericBuyAndHold.py
COPY config.json /module/config.json
COPY entrypoint.sh /module/entrypoint.sh

RUN chmod +x /module/entrypoint.sh \
    && mkdir -p /results

ENTRYPOINT ["/module/entrypoint.sh"]
