ROOTDIR :=
TARGETDIR := /opt/ptctl
SERVICEDIR := /lib/systemd/system
RULESDIR := /etc/udev/rules.d

SYSTEMCTL := $(shell which systemctl)
UDEVADM := $(shell which udevadm)

SHELL := /bin/bash

install: ptctl.py
	test -d ${ROOTDIR}/${TARGETDIR} || mkdir -p ${ROOTDIR}/${TARGETDIR}
	@if [ -f ${ROOTDIR}/etc/group ]; then \
		test [ grep "i2sc:" ${ROOTDIR}/etc/group | wc -l ] -get 0 || groupadd i2c;\
		install -m 755 -g i2c ptctl.py ${ROOTDIR}/${TARGETDIR} ;\
	        install -m 644 -g i2c speaker.i2c ${ROOTDIR}/${TARGETDIR} ;\
	else \
		install -m 755 -g users ptctl.py ${ROOTDIR}/${TARGETDIR} ;\
		install -m 644 -g users speaker.i2c ${ROOTDIR}/${TARGETDIR} ;\
	fi
	test -d ${ROOTDIR}/${SERVICEDIR} || mkdir -p ${ROOTDIR}/${SERVICEDIR}
	test -x ${SYSTEMCTL} && install -m 644 ./systemd/ptctl-poweroff.service ${ROOTDIR}/${SERVICEDIR}
	@if [ ${ROOTDIR} = ""]; then test -x ${SYSTEMCTL} && systemctl enable ptctl-poweroff.service; fi
	test -d ${ROOTDIR}/${RULESDIR} || mkdir -p ${ROOTDIR}/${RULESDIR}
	test -x ${UDEVADM} && install -m 644 ./udev/10-i2c_group.rules ${ROOTDIR}/${RULESDIR}

uninstall:
	test -d ${ROOTDIR}/${TARGETDIR} && rm -rf ${ROOTDIR}/${TARGETDIR}
	test $(shell grep "i2c:" ${ROOTDIR}/etc/group | wc -l) -gt 0 && groupdel i2c
	test -x ${SYSTEMCTL} && systemctl disable ptctl-poweroff.service
	test -x ${SYSTEMCTL} && rm ${ROOTDIR}/${SERVICEDIR}/ptctl-poweroff.service
	test -x ${UDEVADM} && rm ${ROOTDIR}/${RULESDIR}/10-i2c_group.rules

