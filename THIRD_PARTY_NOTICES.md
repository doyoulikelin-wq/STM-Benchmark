# Third-party notices and provenance

`stm_bench/demo_catalog.json` contains a limited set of declarative Nanonis command names, argument names, and wire-type signatures. These signatures were extracted from **nanonis_spm 1.0.9**, with protocol corrections checked against the Nanonis Mimea V5e TCP protocol manual, revision R14573. The SDK implementation, simulator executable, and protocol manual are not included in this repository.

The local extraction source was `D:/STM/tools/nanonis_diagnostics/build_catalog.py`, and the catalog was reduced from `D:/STM/tools/nanonis_diagnostics/catalog.json`. Its recorded SDK SHA-256, `97ffd7bb0c148a40cc3b913dcb82696bd05d8e7e215e9173f2efc44fc4150fd6`, matches the installed `nanonis_spm/NanonisClass.py` from version 1.0.9. The MIT notice below is reproduced from that distribution's `nanonis_spm-1.0.9.dist-info/licenses/LICENSE` (SHA-256 `e26193e434b2f0be6c420493896da74f60d3e0928e545460c12ff678f301cc23`).

`stm_bench/demo_wire.py` and `stm_bench/demo_identity.py` are project code carried forward from earlier tools in the user's workspace: `D:/STM/tools/nanonis_diagnostics/protocol.py` and `D:/STM/针尖修复实验室/源码/设备接口/安全身份.py`, respectively. Their provenance is also recorded in their module docstrings. The notice below applies to the third-party SDK-derived material; it does not assign a license to the newly authored project code or to the vendor's manual and simulator.

## nanonis_spm 1.0.9

MIT License

Copyright (c) 2024 Samuel O'Neill

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
