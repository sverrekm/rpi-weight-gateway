#!/bin/bash

set +e

CURRENT_HOSTNAME=`cat /etc/hostname | tr -d " \t\n\r"`
if [ -f /usr/lib/raspberrypi-sys-mods/imager_custom ]; then
   /usr/lib/raspberrypi-sys-mods/imager_custom set_hostname rpi-weight-gateway
else
   echo rpi-weight-gateway >/etc/hostname
   sed -i "s/127.0.1.1.*$CURRENT_HOSTNAME/127.0.1.1\trpi-weight-gateway/g" /etc/hosts
fi
FIRSTUSER=`getent passwd 1000 | cut -d: -f1`
FIRSTUSERHOME=`getent passwd 1000 | cut -d: -f6`
if [ -f /usr/lib/raspberrypi-sys-mods/imager_custom ]; then
   /usr/lib/raspberrypi-sys-mods/imager_custom enable_ssh
else
   systemctl enable ssh
fi
if [ -f /usr/lib/userconf-pi/userconf ]; then
   /usr/lib/userconf-pi/userconf 'admin' '$5$.eIB7B1KDt$Yh1HDzOeUjukyyUzvYF3eVQ6I27In0.5rQ.XTeQjKr/'
else
   echo "$FIRSTUSER:"'$5$.eIB7B1KDt$Yh1HDzOeUjukyyUzvYF3eVQ6I27In0.5rQ.XTeQjKr/' | chpasswd -e
   if [ "$FIRSTUSER" != "admin" ]; then
      usermod -l "admin" "$FIRSTUSER"
      usermod -m -d "/home/admin" "admin"
      groupmod -n "admin" "$FIRSTUSER"
      if grep -q "^autologin-user=" /etc/lightdm/lightdm.conf ; then
         sed /etc/lightdm/lightdm.conf -i -e "s/^autologin-user=.*/autologin-user=admin/"
      fi
      if [ -f /etc/systemd/system/getty@tty1.service.d/autologin.conf ]; then
         sed /etc/systemd/system/getty@tty1.service.d/autologin.conf -i -e "s/$FIRSTUSER/admin/"
      fi
      if [ -f /etc/sudoers.d/010_pi-nopasswd ]; then
         sed -i "s/^$FIRSTUSER /admin /" /etc/sudoers.d/010_pi-nopasswd
      fi
   fi
fi
if [ -f /usr/lib/raspberrypi-sys-mods/imager_custom ]; then
   /usr/lib/raspberrypi-sys-mods/imager_custom set_wlan  -h 'Merodningen' 'c1e936f08966e41bf357efd4bc19485ae070fde0f5328a8253fe37fbede41dea' 'NO'
else
cat >/etc/wpa_supplicant/wpa_supplicant.conf <<'WPAEOF'
country=NO
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
ap_scan=1

update_config=1
network={
	scan_ssid=1
	ssid="Merodningen"
	psk=c1e936f08966e41bf357efd4bc19485ae070fde0f5328a8253fe37fbede41dea
}

WPAEOF
   chmod 600 /etc/wpa_supplicant/wpa_supplicant.conf
   rfkill unblock wifi
   for filename in /var/lib/systemd/rfkill/*:wlan ; do
       echo 0 > $filename
   done
fi
if [ -f /usr/lib/raspberrypi-sys-mods/imager_custom ]; then
   /usr/lib/raspberrypi-sys-mods/imager_custom set_keymap 'no'
   /usr/lib/raspberrypi-sys-mods/imager_custom set_timezone 'Europe/Oslo'
else
   rm -f /etc/localtime
   echo "Europe/Oslo" >/etc/timezone
   dpkg-reconfigure -f noninteractive tzdata
cat >/etc/default/keyboard <<'KBEOF'
XKBMODEL="pc105"
XKBLAYOUT="no"
XKBVARIANT=""
XKBOPTIONS=""

KBEOF
   dpkg-reconfigure -f noninteractive keyboard-configuration
fi

# Install rpi-weight-gateway automatically
echo "Installing rpi-weight-gateway..."
cd /home/admin
curl -fsSL https://raw.githubusercontent.com/sverrekm/rpi-weight-gateway/main/install.sh | bash --with-mqtt --with-wifi
chown -R admin:admin /home/admin/rpi-weight-gateway

rm -f /boot/firstrun.sh
sed -i 's| systemd.run.*||g' /boot/cmdline.txt
exit 0
