#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from .evm import EVM

class Emulator:
    def __init__(self, provider, block, debug=False):
        self._evm = EVM(debug)
        self._evm.set_vm(provider, block)

    def execute_transaction(self, transaction):
        return self._evm.deploy_transaction(transaction)

    def dump_archive_state(self):
        self._evm.dump_archive_state()

    def load_archive_state(self):
        self._evm.load_archive_state()
