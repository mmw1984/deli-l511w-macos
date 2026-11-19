# L511W Windows language-monitor transport audit

## Verdict and limits

**Keep `socket://IP:9100`; no Deli handshake backend is required by this LM.**
The LM passes print bytes unchanged, either to the installed port monitor or
directly to TCP/9100. It never reads the print socket, never waits for an
application acknowledgement, and never inserts PJL or binary framing into it.
Thus CUPS socket is equivalent for the **ordered print payload**, assuming the
Windows underlying port is configured for raw TCP/9100 to the same printer.
The installed Windows port-monitor configuration was not supplied/observed;
this assumption is not a claim that arbitrary Windows ports (e.g. LPR) are raw.

It is **not an identical network trace**: Windows also probes identity over
UDP/9300, can search the old IP's /24-like prefix after an address change, and
can bypass an out-of-date underlying port with a direct TCP connection. CUPS
socket does not reproduce that recovery, Windows spooler bookkeeping, packet
boundaries, or Windows timeouts/error-handling bugs. None supplies a print
handshake. Use a stable address/DHCP reservation and update the URI if it changes.

Static analysis and a Linux CUPS loopback test are not printer acceptance tests.
No physical printer, Windows execution, or macOS backend execution was available.
The external underlying port monitor, renderer bidi provider, and any separately
installed status utility are not implementations contained in this LM.

## Binary and method

Official v1.0.1.4 x64 `DELIINKPRNDRVLM.dll`, SHA256:
`f5a123888af268d0110e46e9c46da1275cd0d451590e2eec6fda70dff117f3fa`.
Addresses below are image VAs (preferred base `0x180000000`). Local evidence:
`~/work/deli/monitor.asm`, `monitor.c`, `monitor-deep.c`, and the Ghidra
`ghidra-project/monitor` project. `LMDeep.java` explicitly decompiles callback
entries missing from the original whole-binary export. Ghidra inferred some
return types incorrectly as void; the pseudocode below is normalized from the
decompilation **and checked against assembly**, not a verbatim typed C export.

`objdump -p` resolves Winsock imports by ordinal as well as name:
3=closesocket, 4=connect, 9=htons, 19=send, 23=socket,
111=WSAGetLastError, 115=WSAStartup, 116=WSACleanup. Named overlapped
WSASend/WSARecv calls belong to UDP discovery, not to the print TCP stream.

## MONITOR2 dispatch, not guessed from function order

`InitializePrintMonitor2` at `0x180001750` checks its two arguments, writes
`*phMonitor = pMonitorInit`, and returns `0x180027000`; otherwise error 87.
The table's `cbSize` is `0xb0`, with these x64 offsets:

| Offset | Callback | Entry / behavior |
|---|---|---|
| 0x18 | OpenPortEx | `0x180001000` |
| 0x20 | StartDocPort | `0x1800011e0` |
| 0x28 | WritePort | `0x180001440` |
| 0x30 | ReadPort | `0x180001400` |
| 0x38 | EndDocPort | `0x1800014c0` |
| 0x40 | ClosePort | `0x1800015a0` |
| 0x68 | GetPrinterDataFromPort | `0x180001600` |
| 0x90 | Shutdown | `0x180001680`, immediate return |
| 0x98 | SendRecvBidiDataFromPort | **NULL**, not implemented |

EnumPorts/OpenPort, administrative port callbacks, SetPortTimeOuts, Xcv callbacks,
and NotifyUsed/Unused are also NULL. Do not mistake object offset `+0x98` for
the table's bidi slot: it contains the copied underlying **GetPrinterDataFromPort**.

`OpenPortEx` validates the supplied underlying OpenPort/StartDoc/Write/Read/Close
callbacks, allocates state (`0x180002b00`, magic `0x524c`), calls underlying
OpenPort, and copies its MONITOR2 table to state `+0x30`; underlying handle is
at `+0x28`. It optionally calls underlying SetPortTimeOuts (object `+0xa0`):
read-total multiplier=0, constant=500 ms; write-total multiplier=0,
constant=900000 ms (15 min). Assembly does not initialize the read-interval
member of the stack COMMTIMEOUTS. These are delegated settings, not a direct
socket receive/ack timeout. Allocation initializes `use_underlying` at `+0xe0`
to 1, socket `+0xe8` to INVALID_SOCKET, and job-active state to zero.

## Destination selection and discovery reachability

`StartDocPort` validates document level 1/2, printer name, handle magic, and no
already-active job; opens the Windows printer and creates a local job record.
Its actual branch at `0x180001297..0x1800012d9` is:

```c
if (state->use_underlying != 0)
    refresh_address(state, printer);     // 0x180001a50
if (state->use_underlying == 0) {
    s = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP); // 0x1800012eb
    addr.sin_port = htons(9100);                 // 0x180001319
    inet_pton(AF_INET, state + 0x150, &addr.sin_addr);
    if (s == INVALID_SOCKET || connect(s, &addr, 16) == SOCKET_ERROR)
        state->use_underlying = 1;
}
if (state->use_underlying)
    underlying.StartDocPort(underlying_handle, printer, job_id, level, doc);
```

Failed direct connect closes the socket and tries underlying StartDocPort;
if that fails StartDocPort fails and clears active-job state. There is no
LM-level ready/busy request on TCP before returning. No explicit connect or
send timeout is set on the direct socket: Winsock/OS defaults apply.

`refresh_address` (`0x180001a50`) starts by setting use_underlying=1, then
`0x1800020b0` reads Unicode printer data with GetPrinterDataExW:

```c
GetPrinterDataExW(printer, L"DsSpooler", L"SerialNumber", ...); // +0x190
GetPrinterDataExW(printer, L"DsSpooler", L"IPAddress", ...);    // +0x110
GetPrinterDataExW(printer, L"DsSpooler", L"IPChgAddr", ...);    // +0x150
```

All three must be present, nonempty, and convertible to the bounded narrow
buffers for discovery to run. Missing data/event allocation failure leaves the
underlying path selected. This is why the direct TCP branch is **not** the
unconditional network path, and why FILE-port goldens do not establish it ran.
No actual printer registry capture was supplied to determine which branch a
particular Windows queue selected.

1. `0x1800017d0` launches `0x180001d00` against IPChgAddr and waits 500 ms.
   The worker creates `WSASocketW(AF_INET=2, SOCK_DGRAM=2, protocol=0, ...,
   WSA_FLAG_OVERLAPPED=1)`, connects UDP to `htons(0x2454)` = **9300**, and
   issues one identity query (WSASend at `0x180001ea6`, WSARecv at
   `0x180001f27`). Send completion wait is 100 ms, receive wait 450 ms.
2. If that fails, `0x180002330` takes IPAddress through its third dot and
   launches `0x1800025a0` for suffixes **1 through 254** (not a netmask-aware
   network calculation). These are connected unicast UDP/9300 probes, not
   broadcasts, multicast, mDNS or SNMP. Each startup event wait is 150 ms;
   the final result wait is 3500 ms. Workers wait up to 1000 ms for send and
   3000 ms for receive completion. These are individual waits, not a single
   global upper bound on StartDocPort. No retries per individual probe.
3. Both workers call serial matcher `0x1800018d0`; a match selects the
   address. On scan success the LM may write the new IPChgAddr using
   DsSpooler's `driverName` as the name passed to OpenPrinterW, at
   `0x180001c1e..0x180001cc0`.
4. If the cached address replies and equals IPAddress, keep underlying.
   If a matching device is found at a different address, set use_underlying=0
   (`0x180001cc5`) and use direct TCP/9100. A failed scan leaves underlying.
   The scan-success branch selects direct even if it rediscovered the old IP.

This establishes the conditional chain all the way from StartDocPort to
network calls. It also disproves the tempting hypothesis that presence of
WSARecv means a mandatory print-data handshake. **There are no WSARecv calls
on the print socket**; its only operations are socket/connect/send/close.
No LM HTTP, IPP, LPD, DNS lookup, UDP/161 SNMP, or broadcast path was found
in the callback/helper call graph or the complete Winsock call-site audit.
Those protocols could still exist in a separately configured port monitor.

## Query and response format (identity, not ink/paper status)

Both UDP workers send exactly 15 bytes from `0x18001d428`:

```text
a5 00 0c 50 e0 74 08 03 00 00 00 00 00 00 00
```

This resembles a 3-byte header plus 12-byte body, but the LM does not validate
that interpretation of a reply. Each worker receives at most 256 bytes.
The serial matcher (`0x1800018d0..0x180001a1b`) requires at least 14 bytes,
then performs bounded big-endian length walking:

```python
p = 12
for field in range(3):
    length = (reply[p] << 8) | reply[p + 1]
    p += 2
    value = reply[p:p + length]  # every boundary checked against received size
    p += length
# third field must have exactly strlen(configured_serial) bytes and match it
```

The first two fields are skipped; assigning names to them would be speculation.
There is no LM parse of paper-out, ink-empty, busy, ready, job-complete, or
chunk-ack status codes. State `+0x100` values -1 / positive integer are the
local discovery result/suffix, not printer error codes. Discovery failure does
not establish the device is busy or that printing must abort.

Implementation quirks: reply matching is inside the ERROR_IO_PENDING receive
completion branch, not the immediate-success branch; completion-wait errors
are not fully checked. This audit does not propose reproducing those bugs.

## Print bytes, reads, and job termination

WritePort at `0x180001440` checks handle magic and the output byte-count
pointer, then has just these two data paths (`0x180001468..0x18000149b`):

```c
*written = 0;
if (state->use_underlying)
    return underlying.WritePort(state->underlying_handle, buffer, size, written);
int n = send(state->socket, buffer, size, 0); // ordinal 19, 0x18000148e
*written = n;
return n != 0;
```

The original buffer pointer and length pass unchanged in **both** branches.
No prefix, suffix, escape/unescape, PJL USTATUS/INFO/ECHO, UEL, file/job-ID
rewrite, private chunk headers, per-chunk reads, or data-dependent branching.
One send per WritePort; no internal partial-send loop. Its return test even
treats SOCKET_ERROR (-1) as true and writes 0xffffffff: a Windows bug, not a
reason to imitate unreliable delivery in a CUPS backend.

ReadPort (`0x180001400`) forwards unchanged to underlying ReadPort at object
`+0x60` after validating magic, **even in direct mode**. It does not read the
direct TCP socket. It is not called from StartDocPort/WritePort/EndDocPort.
GetPrinterDataFromPort (`0x180001600`) validates buffers/control ID, zeroes
the returned count, and tail-calls underlying GetPrinterDataFromPort at
object `+0x98`; unsupported/invalid requests fail with error 87. It does not
parse or synthesize status. SendRecvBidiDataFromPort has no callback at all.
Consequently external status/bidi requests are not evidence of a required
protocol implemented here. The renderer has separate PrintCtrl.SendRecv
helpers (e.g. `0x18000fbe0`); their existence does not make them a reachable
LM print handshake. Their external provider/runtime invocation is unverified.

EndDocPort (`0x1800014c0`) either calls underlying EndDocPort (object `+0x68`)
or closes the direct socket (`0x180001506`) and discovery event handles.
No final send, read, acknowledgement, linger setting, or success-status poll.
It removes local job records through `0x180002f10`: SetJobW commands
6=JOB_CONTROL_SENT_TO_PRINTER (direct mode), 7=JOB_CONTROL_LAST_PAGE_EJECTED
(both). These are **local spooler controls**, not bytes sent to the printer.
It resets use_underlying=1 and active-job=0 and returns success after cleanup.
ClosePort forwards underlying ClosePort and frees state/job records.

No printer response during TCP printing therefore has no LM-specific timeout
or abort consequence. Discovery replies only decide address/path, with fallback
on failure. Delegated ReadPort timeouts/status, underlying transport behavior,
OS TCP failures, and CUPS cancellation/retry policy remain separate concerns.

## Reproducible transport check

`tools/test_socket.py` executes a **real CUPS socket backend**, not a Python
reimplementation of its client, against a silent loopback fake printer. It
checks a binary golden, empty and truncated transport input byte-for-byte,
using 1023-byte server reads to avoid assuming WritePort/packet boundaries.
Truncation is intentionally transported verbatim, not validated by a backend.
A bound but non-listening port tests connection failure, with class failover
enabled to prevent the backend's normal retry loop. No UDP scanner is run.

```sh
python3 tools/test_socket.py --backend /usr/lib/cups/backend/socket
# macOS backend is normally /usr/libexec/cups/backend/socket
make test
```

The test selects `waiteof=false`: there is no LM-required application response
at job end. This is also a useful queue URI option if firmware holds TCP open
after a job: `socket://IP:9100/?waiteof=false`. It does not change payload bytes
or imply hardware confirmation of the printer's close behavior. The test also
disables CUPS' own optional SNMP (`snmp=false`) and supplies the scheduler's
otherwise-missing side-channel socket on fd 4. Neither is a Deli handshake.
