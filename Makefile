ifneq (,$(wildcard .env))
include .env
endif

PLUGIN_NAME   = fritz_home
PACKAGE_NAME  = enigma2-plugin-extensions-fritz-home
VERSION := $(shell cat VERSION 2>/dev/null | tr -d '[:space:]')

BUILD_DIR       = build
IPK_WORK_DIR    = $(BUILD_DIR)/ipk
DATA_STAGING    = $(IPK_WORK_DIR)/data
CONTROL_STAGING = $(IPK_WORK_DIR)/control

PLUGIN_PATH = usr/lib/enigma2/python/Plugins/Extensions/$(PLUGIN_NAME)
OUTPUT_IPK  = $(BUILD_DIR)/$(PACKAGE_NAME)_$(VERSION)_all.ipk

DOS2UNIX_BIN := $(shell command -v dos2unix 2>/dev/null)
MSGFMT_BIN   := $(shell command -v msgfmt 2>/dev/null)

BOX_HOST ?=
BOX_USER ?=
BOX_PORT ?= 22

.PHONY: all build clean normalize assets compile-locales prepare ipk install copy-settings apply restart deploy

all: ipk

clean:
	rm -rf $(BUILD_DIR)

normalize:
ifneq ($(DOS2UNIX_BIN),)
	find src control -type f -exec dos2unix {} \;
endif

# Copy shared assets (QR code, plugin icons) from adjacent repository or
# from the parent folder.  Silently skipped when the sources are missing.
assets:
	mkdir -p src/$(PLUGIN_NAME)/res
	@if [ -f "../qr_buymeacoffee.png" ]; then \
		cp ../qr_buymeacoffee.png src/$(PLUGIN_NAME)/res/qr_buymeacoffee.png; \
		echo "Copied qr_buymeacoffee.png"; \
	else \
		echo "WARNING: ../qr_buymeacoffee.png not found – QR code will not be shown"; \
	fi
	@echo "Plugin icons are maintained in src/$(PLUGIN_NAME)/res/ – skipping copy"

compile-locales:
ifneq ($(MSGFMT_BIN),)
	@for lang in de en it es; do \
		po=src/$(PLUGIN_NAME)/locale/$$lang/LC_MESSAGES/$(PLUGIN_NAME).po; \
		mo=src/$(PLUGIN_NAME)/locale/$$lang/LC_MESSAGES/$(PLUGIN_NAME).mo; \
		if [ -f "$$po" ]; then \
			$(MSGFMT_BIN) -o "$$mo" "$$po"; \
		fi; \
	done
else
	@echo "msgfmt not found - skipping locale compilation"
endif

prepare: normalize assets compile-locales
	mkdir -p $(DATA_STAGING)/$(PLUGIN_PATH)
	mkdir -p $(CONTROL_STAGING)
	cp -r src/$(PLUGIN_NAME)/* $(DATA_STAGING)/$(PLUGIN_PATH)/
	cp control/control  $(CONTROL_STAGING)/
	sed -i 's/^Version:.*/Version: $(VERSION)/' $(CONTROL_STAGING)/control
	cp control/postinst $(CONTROL_STAGING)/
	cp control/prerm    $(CONTROL_STAGING)/
	chmod 755 $(CONTROL_STAGING)/postinst $(CONTROL_STAGING)/prerm

ipk: clean prepare
	cd $(IPK_WORK_DIR) && \
	tar -czf data.tar.gz    -C data    . && \
	tar -czf control.tar.gz -C control . && \
	echo "2.0" > debian-binary && \
	ar r $(PACKAGE_NAME)_$(VERSION)_all.ipk debian-binary control.tar.gz data.tar.gz
	mv $(IPK_WORK_DIR)/$(PACKAGE_NAME)_$(VERSION)_all.ipk $(OUTPUT_IPK)
	@echo ""
	@echo "Built: $(OUTPUT_IPK)"

install: ipk
	@test -n "$(BOX_HOST)" || (echo "BOX_HOST not set"; exit 1)
	@test -n "$(BOX_USER)" || (echo "BOX_USER not set"; exit 1)
	scp -P $(BOX_PORT) $(OUTPUT_IPK) $(BOX_USER)@$(BOX_HOST):/tmp/
	ssh -p $(BOX_PORT) $(BOX_USER)@$(BOX_HOST) \
	    "opkg install --force-reinstall /tmp/$(PACKAGE_NAME)_$(VERSION)_all.ipk"

copy-settings:
	@test -n "$(BOX_HOST)" || (echo "BOX_HOST not set"; exit 1)
	@if grep -qE '^FRITZ_(HOST|USER|PASSWORD|PORT)=' .env 2>/dev/null; then \
		scp -P $(BOX_PORT) .env $(BOX_USER)@$(BOX_HOST):/tmp/_plugin_env; \
		ssh -p $(BOX_PORT) $(BOX_USER)@$(BOX_HOST) 'set -e; \
			SF=/etc/enigma2/settings; TMP=/tmp/_settings_tmp; \
			touch $$SF; \
			grep -v "^config\.plugins\.fritzhome\." $$SF > $$TMP || true; \
			HOST=$$(grep "^FRITZ_HOST=" /tmp/_plugin_env | head -1 | cut -d= -f2-); \
			PORT=$$(grep "^FRITZ_PORT=" /tmp/_plugin_env | head -1 | cut -d= -f2-); \
			USER=$$(grep "^FRITZ_USER=" /tmp/_plugin_env | head -1 | cut -d= -f2-); \
			PASS=$$(grep "^FRITZ_PASSWORD=" /tmp/_plugin_env | head -1 | cut -d= -f2-); \
			[ -n "$$HOST" ] && printf "%s\n" "config.plugins.fritzhome.host=$$HOST" >> $$TMP; \
			[ -n "$$PORT" ] && printf "%s\n" "config.plugins.fritzhome.port=$$PORT" >> $$TMP; \
			[ -n "$$USER" ] && printf "%s\n" "config.plugins.fritzhome.username=$$USER" >> $$TMP; \
			[ -n "$$PASS" ] && printf "%s\n" "config.plugins.fritzhome.password=$$PASS" >> $$TMP; \
			mv $$TMP $$SF; rm -f /tmp/_plugin_env; \
			echo "Settings applied"'; \
	else \
		echo "No Fritz!Box credentials in .env – skipping settings push"; \
	fi

build: ipk

deploy: install copy-settings apply

apply:
	@test -n "$(BOX_HOST)" || (echo "BOX_HOST not set"; exit 1)
	ssh -p $(BOX_PORT) $(BOX_USER)@$(BOX_HOST) \
	    "init 4 >/dev/null 2>&1 || killall -9 enigma2 >/dev/null 2>&1 || true; sleep 2; init 3 >/dev/null 2>&1 || true"

restart: apply
