#!/bin/bash

set -e  # Exit on error

# Load environment variables if available
[ -f /etc/default/weightd ] && . /etc/default/weightd

# Default values
SSID=${WIFI_AP_SSID:-rpi-weight-gateway}
PASSPHRASE=${WIFI_AP_PASS:-rpi-weight-2025!}
COUNTRY=${AP_COUNTRY:-NO}
CHANNEL=6

# Create necessary directories
mkdir -p /etc/hostapd /etc/iptables /var/run/hostapd /var/lib/misc

# Generate hostapd configuration
cat > /etc/hostapd/hostapd.conf << EOF
# Basic configuration
interface=wlan0
driver=nl80211
ssid=${SSID}
hw_mode=g
channel=${CHANNEL}
wmm_enabled=1
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0

# WPA2 configuration
wpa=2
wpa_passphrase=${PASSPHRASE}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP

# Country code (ISO/IEC 3166-1)
country_code=${COUNTRY}

# 802.11n support
ieee80211n=1

# QoS support
wmm_enabled=1

# Logging
logger_syslog=1
logger_syslog_level=2
logger_stdout=1
logger_stdout_level=2
EOF

# Configure hostapd to use our config file
cat > /etc/default/hostapd << EOF
# Defaults for hostapd initscript
# See /usr/share/doc/hostapd/README.Debian for more information.
#
# This is a POSIX shell fragment, not a bash script.

# Set to yes to start hostapd
RUN_DAEMON=yes

# Set to yes to enable debugging
DAEMON_OPTS="-d -t"

# Additional options that will be passed to hostapd
DAEMON_CONF="/etc/hostapd/hostapd.conf"
EOF

# Configure dnsmasq
cat > /etc/dnsmasq.conf << EOF
# Basic dnsmasq configuration for WiFi access point

# Interface to listen on
interface=wlan0

# DHCP range and lease time
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h

# DNS server to use
server=8.8.8.8
server=8.8.4.4

# No DNS caching
cache-size=0

# Logging
log-queries
log-dhcp

# Don't forward short names
domain-needed

# Don't forward plain names (without a dot or domain part)
bogus-priv

# Don't forward the local .local domain
domain=local
local=/local/

# Don't read /etc/resolv.conf or /etc/hosts
no-resolv
no-hosts

# Enable DHCPv4
dhcp-leasefile=/var/lib/misc/dnsmasq.leases

# Log to stderr
log-facility=-
EOF

# Configure network interfaces
cat > /etc/network/interfaces.d/wlan0 << EOF
auto wlan0
iface wlan0 inet static
    address 192.168.4.1
    netmask 255.255.255.0
    network 192.168.4.0
    broadcast 192.168.4.255
    post-up iptables-restore < /etc/iptables/rules.v4
EOF

# Enable IP forwarding
echo 1 > /proc/sys/net/ipv4/ip_forward

# Configure NAT
iptables -t nat -F
iptables -F
iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
iptables -A FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT

# Save iptables rules
mkdir -p /etc/iptables/
iptables-save > /etc/iptables/rules.v4

# Ensure services are enabled and started
systemctl unmask hostapd
systemctl enable hostapd
systemctl enable dnsmasq

# Restart services
systemctl daemon-reload
systemctl restart dnsmasq

# Start hostapd if not already running
if ! systemctl is-active --quiet hostapd; then
    systemctl start hostapd
fi

echo "Access point configuration complete. SSID: ${SSID}"
