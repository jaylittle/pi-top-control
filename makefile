TARGETDIR := /opt/ptctl
SERVICEDIR := /lib/systemd/system
RULESDIR := /etc/udev/rules.d

SYSTEMCTL := $(shell which systemctl)
UDEVADM := $(shell which udevadm)

install: ptctl.py
	test -d $(TARGETDIR) || mkdir $(TARGETDIR)
	install -m 755 -g i2c ptctl.py $(TARGETDIR)
	install -m 644 -g i2c speaker.i2c $(TARGETDIR)
	test $(shell grep "i2c:" /etc/group | wc -l) -gt 0 || groupadd i2c
	test -x $(SYSTEMCTL) && install -m 644 ./systemd/ptctl-poweroff.service $(SERVICEDIR)
	test -x $(SYSTEMCTL) && systemctl enable ptctl-poweroff.service
	test -x $(UDEVADM) && install -m 644 ./udev/10-i2c_group.rules $(RULESDIR)

uninstall:
	test -d $(TARGETDIR) && rm -rf $(TARGETDIR)
	test $(shell grep "i2c:" /etc/group | wc -l) -gt 0 && groupdel i2c
	test -x $(SYSTEMCTL) && systemctl disable ptctl-poweroff.service
	test -x $(SYSTEMCTL) && rm $(SERVICEDIR)/ptctl-poweroff.service
	test -x $(UDEVADM) && rm $(RULESDIR)/10-i2c_group.rules

