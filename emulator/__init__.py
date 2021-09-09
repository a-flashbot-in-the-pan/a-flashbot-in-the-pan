#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from .evm import EVM

class Emulator:
    def __init__(self, provider, block, debug=False):
        self._evm = EVM(debug)
        self._evm.set_vm(provider, block)

    def execute_transaction(self, transaction):
        return self._evm.deploy_transaction(transaction)
