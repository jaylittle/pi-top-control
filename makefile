SYSTEMCTL := $(shell which systemctl)
UDEVADM := $(shell which udevadm)

install: ptctl.py
	test -d /opt/ptctl || mkdir /opt/ptctl
	install -m 755 -g i2c ptctl.py /opt/ptctl/
	install -m 644 -g i2c speaker.i2c /opt/ptctl/
	test $(shell grep "i2c:" /etc/group | wc -l) -gt 0 || groupadd i2c
	test -x $(SYSTEMCTL) && install -m 644 ./systemd/ptctl-poweroff.service /lib/systemd/system/
	test -x $(SYSTEMCTL) && systemctl enable ptctl-poweroff.service
	test -x $(UDEVADM) && install -m 644 ./udev/10-i2c_group.rules /etc/udev/rules.d/
