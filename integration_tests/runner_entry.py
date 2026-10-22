"""Run the unchanged pinned Runner; deny external sockets in the test process."""
import os
import runpy
import socket
import sys

if __name__ == "__main__":
    from integration_tests.support import verify_source
    verify_source()
    port = int(os.environ["MAIBOT_IPC_ADDRESS"].rsplit(":", 1)[1])
    pair_code = socket.socketpair.__code__
    def guard(event, args):
        if event == "socket.connect" and sys._getframe(1).f_code is not pair_code:
            address = args[1]
            if not (isinstance(address, tuple) and address[0] == "127.0.0.1" and address[1] == port):
                raise PermissionError("TEST_NETWORK_DENIED")
    sys.addaudithook(guard)
    runpy.run_module("src.plugin_runtime.runner.runner_main", run_name="__main__")
