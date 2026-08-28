FROM ghcr.io/netbox-community/netbox:v4.6@sha256:3a105e0cc585aa823f327e1034dc5fb7a6e1cea6d210c5bf61badd68d784650d

COPY netbox/plugin_requirements.txt /opt/netbox/plugin_requirements.txt
RUN /usr/local/bin/uv pip install -r /opt/netbox/plugin_requirements.txt

COPY netbox/plugins.py /etc/netbox/config/plugins.py
