#!/bin/bash
# Drops all outbound traffic except DNS and the Anthropic API, then checks both sides.
# Usage: sudo init-firewall.sh  (run by postStartCommand; adapted from the Claude Code
# reference devcontainer)
set -euo pipefail
IFS=$'\n\t'

ALLOWED_DOMAINS=(api.anthropic.com)
SET=allowed-domains

# Keep Docker's embedded DNS (127.0.0.11) working through the flush.
docker_dns_rules=$(iptables-save -t nat | grep "127\.0\.0\.11" || true)

iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X
iptables -t mangle -F
iptables -t mangle -X
ipset destroy "$SET" 2>/dev/null || true

if [ -n "$docker_dns_rules" ]; then
  iptables -t nat -N DOCKER_OUTPUT 2>/dev/null || true
  iptables -t nat -N DOCKER_POSTROUTING 2>/dev/null || true
  echo "$docker_dns_rules" | xargs -L 1 iptables -t nat
fi

iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A INPUT -p udp --sport 53 -j ACCEPT
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

ipset create "$SET" hash:net
for domain in "${ALLOWED_DOMAINS[@]}"; do
  ips=$(dig +noall +answer A "$domain" | awk '$4 == "A" {print $5}')
  if [ -z "$ips" ]; then
    echo "ERROR: failed to resolve $domain" >&2
    exit 1
  fi
  for ip in $ips; do
    ipset add "$SET" "$ip"
  done
done

iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m set --match-set "$SET" dst -j ACCEPT
iptables -A OUTPUT -j REJECT --reject-with icmp-admin-prohibited

if curl -s --connect-timeout 5 https://example.com >/dev/null; then
  echo "ERROR: firewall check failed: https://example.com is reachable" >&2
  exit 1
fi
# Any HTTP status means the connection got through; curl fails only when blocked.
if ! curl -s --connect-timeout 5 -o /dev/null https://api.anthropic.com; then
  echo "ERROR: firewall check failed: https://api.anthropic.com is unreachable" >&2
  exit 1
fi
echo "Firewall up: only ${ALLOWED_DOMAINS[*]} is reachable"
