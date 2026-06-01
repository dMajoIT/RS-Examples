"""
R&S RTP Signal Integrity Analysis - Backend

All instrument automation functions, structured for GUI integration.
Import this module and call functions directly — no CLI prompts.

Sections:
    - Connection helpers
    - Signal configuration
    - Eye diagram: SW CDR (whole / specific / selected eye)
    - Eye diagram: HW CDR with zoom
    - Jitter: Quick Start
    - Jitter: Manual components
    - Jitter: Transition-dependent PAM-N results

All ADVJitter commands use instance ADVJitter1 as required by manual.
Heavy commands (CLEJitcomp, CATegory:ADD) use 600 s timeouts because
the instrument computation time grows with component complexity.
"""

import time
from RsInstrument import RsInstrument
from typing import Optional, Callable

# ============================================================================
# CONSTANTS
# ============================================================================

AUTO_ETH_STANDARD = {
    "2.5": "TPFGBTO",
    "5":   "FGBTO",
    "10":  "TGBTO",
}

PAMN_EYE_MODE = {
    "whole":    "WHOLe",
    "specific": "SPECific",
    "selected": "SELected",
}

SPECIFIC_EYE_MAP = {
    "0-1": "EYE1",
    "1-2": "EYE2",
    "2-3": "EYE3",
}

JITTER_COMPONENTS = {
    "DDJ":    {"index": 9,  "description": "Data-Dependent Jitter"},
    "RJ":     {"index": 5,  "description": "Random Jitter"},
    "TJ":     {"index": 7,  "description": "Total Jitter"},
    "DJ":     {"index": 8,  "description": "Deterministic Jitter"},
    "PJ":     {"index": 11, "description": "Periodic Jitter"},
    "DCD":    {"index": 10, "description": "Duty Cycle Distortion"},
    "TJ@BER": {"index": 4,  "description": "Total Jitter at BER"},
    "ISI":    {"index": 12, "description": "Inter-Symbol Interference"},
}

TRANSITION_COLORS = [
    "16739179",  # #FF6B6B - Red
    "5098436",   # #4ECDC4 - Cyan
    "9823699",   # #95E1D3 - Light cyan
    "15958401",  # #F38181 - Pink
    "11179482",  # #AA96DA - Purple
    "16633710"   # #FDCB6E - Yellow
]

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

POLL_INTERVAL_MS = 5000  # Short VISA window per poll — never hits a hard VISA timeout


def opc_poll(
    instr: RsInstrument,
    total_timeout_s: int = 600,
    label: str = "operation",
    log_callback_fn: Optional[Callable] = None
) -> None:

    log = lambda msg: log_callback(msg, log_callback_fn)
    deadline   = time.monotonic() + total_timeout_s
    last_tick  = time.monotonic()
    start_time = time.monotonic()
    tick_every = 15

    old_timeout = instr.visa_timeout
    instr.visa_timeout = POLL_INTERVAL_MS
    try:
        while True:
            now = time.monotonic()
            if now >= deadline:
                raise TimeoutError(f"'{label}' did not complete within {total_timeout_s} s")
            try:
                result = instr.query_str("*OPC?").strip()
                if result == "1":
                    elapsed = time.monotonic() - start_time
                    log(f"  ✅ {label} complete ({elapsed:.1f} s)")
                    return
            except Exception:
                pass  # VISA timeout on this poll — instrument still busy
            if now - last_tick >= tick_every:
                waited    = now - start_time
                remaining = deadline - now
                log(f"  ⏳ {label} — waiting... ({waited:.0f} s elapsed, {remaining:.0f} s remaining)")
                last_tick = now
            time.sleep(0.5)
    finally:
        instr.visa_timeout = old_timeout


def log_callback(message: str, callback=None):
    if callback:
        callback(message)
    else:
        print(message)


def factory_preset(instr: RsInstrument, log_callback_fn=None) -> None:
    log = lambda msg: log_callback(msg, log_callback_fn)
    log("Performing factory preset...")
    instr.write_str("SYSTem:PRESet")
    instr.query_opc(600000)
    log("✅ Factory preset complete!")


# ============================================================================
# SIGNAL CONFIGURATION
# ============================================================================

def setup_signal_config(
    instr: RsInstrument,
    channel_pair: str,
    technology: str,
    v_scale: float,
    h_scale: float,
    log_callback_fn=None
) -> None:
    log = lambda msg: log_callback(msg, log_callback_fn)

    used_channels = (1, 3) if channel_pair == "13" else (2, 4)
    ch_a, ch_b = used_channels
    unused = {1, 2, 3, 4} - {ch_a, ch_b}
    pos, neg = (ch_a, ch_b) if ch_a < ch_b else (ch_b, ch_a)

    log("Applying factory preset...")
    instr.write_str("SYSTem:PRESet")
    instr.query_opc(600000)

    log(f"Configuring channels {ch_a} and {ch_b}...")
    for ch in (ch_a, ch_b):
        instr.write_str(f"CHANnel{ch}:STATe ON")
    for ch in sorted(unused):
        instr.write_str(f"CHANnel{ch}:STATe OFF")

    log(f"Setting scales: {v_scale} V/div, {h_scale} s/div...")
    for ch in (ch_a, ch_b):
        instr.write_str(f"CHANnel{ch}:SCALe {v_scale}")
    instr.write_str(f"TIMebase:SCALe {h_scale}")
    instr.query_opc()

    log("Creating differential signal DIFF1...")
    instr.write_str(f"DIFFerential1:PSIGnal:SELect C{pos}W1")
    instr.write_str(f"DIFFerential1:NSIGnal:SELect C{neg}W1")
    instr.write_str("DIFFerential1:AOUTput DIFF")
    instr.write_str("DIFFerential1:STATe ON")
    instr.query_opc()

    log("Setting trigger to DIFF1...")
    instr.write_str("TRIGger1:SOURce DIFF1")
    instr.query_opc()

    log(f"Configuring signal for {technology}GBASE-T1...")
    ser_std = AUTO_ETH_STANDARD[technology]

    try:
        count = int(float(instr.query_str("SIGNalconfig:SETup:COUNt?")))
        for idx in range(1, count + 1):
            instr.write_str(f"SIGNalconfig:SETup:REMove {idx}")
    except Exception:
        pass

    instr.write_str(f"SIGNalconfig:SETup:ADD DIFF1,{ser_std}")
    instr.query_opc()
    log("✅ Signal configuration complete!")


# ============================================================================
# EYE DIAGRAM - CLEANUP HELPERS
# ============================================================================

def cleanup_jitter_state(instr: RsInstrument, log_callback_fn=None) -> None:
    """
    Turn off jitter results display before switching to eye diagram.

    ADVJitter1:RESult:ENABle OFF hides the results panel without
    destroying the decomposition — it can be re-enabled later.
    Confirmed command from R&S RTP manual page 2552.
    """
    log = lambda msg: log_callback(msg, log_callback_fn)
    log("  • Turning off jitter results display...")
    try:
        instr.write_str("ADVJitter1:RESult:ENABle OFF")
        instr.query_opc(30000)
        log("    Jitter results: OFF")
    except Exception as e:
        log(f"    Warning: could not disable jitter results — {e}")


def cleanup_hw_cdr_state(instr: RsInstrument, log_callback_fn=None) -> None:
    """
    Clean up HW CDR state before switching to SW CDR.
    Removes the zoom window and resets trigger from CDR back to EDGE.
    No full preset or signal config needed.
    """
    log = lambda msg: log_callback(msg, log_callback_fn)
    log("  • Cleaning up HW CDR state...")

    try:
        instr.write_str(":LAYout:ZOOM:REMove 'HW_CDR_Zoom'")
        instr.query_opc(30000)
        log("    Zoom window 'HW_CDR_Zoom' removed")
    except Exception:
        log("    No zoom window to remove (skipping)")

    try:
        instr.write_str("TRIGger1:SOURce DIFF1")
        instr.write_str("TRIGger1:TYPE EDGE")
        instr.query_opc(30000)
        log("    Trigger reset to EDGE/DIFF1")
    except Exception as e:
        log(f"    Warning: trigger reset failed — {e}")


# ============================================================================
# EYE DIAGRAM - SOFTWARE CDR
# ============================================================================

def setup_eye_sw_cdr(
    instr: RsInstrument,
    eye_mode: str,
    specific_eye: Optional[str] = None,
    base_level: Optional[int] = None,
    target_level: Optional[int] = None,
    enable_measurements: bool = False,
    coming_from_hw_cdr: bool = False,
    log_callback_fn=None
) -> None:
    """
    Configure Eye Diagram with Software CDR.

    If coming_from_hw_cdr is True, the zoom window and CDR trigger are
    cleaned up first — no full preset or signal config required.
    Jitter cleanup is handled by the GUI before this is called.

    Args:
        instr: RsInstrument instance
        eye_mode: "whole", "specific", or "selected"
        specific_eye: For specific mode: "0-1", "1-2", or "2-3"
        base_level: For selected mode: 0, 1, or 2
        target_level: For selected mode: valid target for base
        enable_measurements: Enable eye measurements (height/width/amplitude)
        coming_from_hw_cdr: If True, clean up HW CDR artifacts first
        log_callback_fn: Optional callback for status messages
    """
    log = lambda msg: log_callback(msg, log_callback_fn)
    log("Configuring Eye Diagram with SW CDR...")

    if coming_from_hw_cdr:
        cleanup_hw_cdr_state(instr, log_callback_fn)

    log("  • Setting up SW CDR...")
    instr.write_str("EYE1:SOURce DIFF1")
    instr.write_str("EYE1:TIMReference:SOURce CDR")
    instr.write_str("EYE1:TIMReference:CDR:SELect SW")
    instr.write_str("EYE1:TIMReference:CDR:SOFTware SW1")
    instr.write_str("CDR:SOFTware1:ESSRate:SOURce DIFF1")
    instr.query_opc()

    log(f"  • Configuring {eye_mode} eye mode...")
    instr.write_str(f"EYE1:FILTer:PAMN:EMODe {PAMN_EYE_MODE[eye_mode]}")

    if eye_mode == "specific":
        if not specific_eye:
            raise ValueError("specific_eye required for specific mode")
        instr.write_str(f"EYE1:FILTer:PAMN:SEYE {SPECIFIC_EYE_MAP[specific_eye]}")
        instr.write_str("EYE1:FILTer:STATe ON")

    elif eye_mode == "selected":
        if base_level is None or target_level is None:
            raise ValueError("base_level and target_level required for selected mode")
        instr.write_str(f"EYE1:FILTer:PAMN:BLEVel LEVEL{base_level}")
        instr.write_str(f"EYE1:FILTer:PAMN:TLEVel LEVEL{target_level}")
        instr.write_str("EYE1:FILTer:STATe ON")

    else:  # whole
        instr.write_str("EYE1:FILTer:STATe ON")

    instr.query_opc()

    log("  • Enabling eye diagram...")
    try:
        instr.write_str("EYE1:STATe OFF")
        instr.query_opc()
    except:
        pass
    instr.write_str("EYE1:STATe ON")
    instr.query_opc()

    if enable_measurements:
        log("  • Enabling eye measurements...")
        try:
            instr.write_str("MEASurement1:ENABle OFF")
            instr.write_str("MEASurement1:CLEar")
        except:
            pass
        instr.write_str("MEASurement1:CATegory EYEJitter")
        instr.write_str("MEASurement1:SOURce EYE1")
        instr.write_str("MEASurement1:MAIN EHEight")
        instr.write_str("MEASurement1:ADDitional EWIDth,ON")
        instr.write_str("MEASurement1:ADDitional EAMPlitude,ON")
        instr.write_str("MEASurement1:ENABle ON")
        instr.query_opc()

    log("✅ Eye Diagram (SW CDR) configured!")


# ============================================================================
# EYE DIAGRAM - HARDWARE CDR WITH ZOOM
# ============================================================================

def setup_eye_hw_cdr_with_zoom(
    instr: RsInstrument,
    xstart_ns: float = 60.0,
    xstop_ns: float = 62.0,
    signal_already_configured: bool = True,
    enable_zoom: bool = True,
    log_callback_fn=None
) -> None:
    """
    Configure Hardware CDR Eye Diagram with optional Zoom.
    Jitter cleanup is handled by the GUI before this is called.

    Args:
        instr: RsInstrument instance
        xstart_ns: Zoom window start in nanoseconds (default: 60)
        xstop_ns: Zoom window stop in nanoseconds (default: 62)
        signal_already_configured: Informational — logs warning if False
        enable_zoom: If True, create zoom window. If False, skip zoom entirely.
        log_callback_fn: Optional callback for status messages
    """
    log = lambda msg: log_callback(msg, log_callback_fn)
    log("Configuring HW CDR Eye Diagram..." if not enable_zoom
        else "Configuring HW CDR Eye Diagram with Zoom...")

    HW_OPC_MS = 180000

    if not signal_already_configured:
        log("  ⚠️  No prior signal config detected — run signal config first.")

    # Turn off SW CDR eye if it was active
    try:
        eye_state = instr.query_str("EYE1:STATe?").strip()
        if eye_state in ("1", "ON"):
            log("  • Turning off SW CDR eye diagram...")
            instr.write_str("EYE1:STATe OFF")
            instr.query_opc(HW_OPC_MS)
    except Exception:
        pass

    log("  • Setting trigger source to DIFF1...")
    instr.write_str("TRIGger1:SOURce DIFF1")

    log("  • Setting trigger type to CDR (Hardware Clock Data Recovery)...")
    instr.write_str("TRIGger1:TYPE CDR")
    instr.query_opc(HW_OPC_MS)

    if enable_zoom:
        log("  • Setting horizontal scale to 400 ns/div...")
        instr.write_str("TIMebase:SCALe 400E-9")
        instr.query_opc(HW_OPC_MS)

        zoom_center = (xstart_ns + xstop_ns) / 2 * 1e-9
        log(f"  • Adjusting horizontal position ({zoom_center * 1e9:.1f} ns)...")
        instr.write_str(f"TIMebase:HORizontal:POSition {zoom_center}")
        instr.query_opc(HW_OPC_MS)

        log("\nConfiguring Zoom Window...")
        xstart_s  = xstart_ns * 1e-9
        xstop_s   = xstop_ns  * 1e-9
        window_ns = xstop_ns - xstart_ns

        log(f"  • Creating zoom window: {xstart_ns} ns to {xstop_ns} ns ({window_ns} ns total)...")

        try:
            diff_scale = float(instr.query_str("DIFFerential1:SCALe?"))
            log(f"    DIFF1 scale: {diff_scale} V/div")
            v_span  = diff_scale * 10
            v_start = -v_span / 2
            v_stop  =  v_span / 2
            log(f"    Vertical range: {v_start} V to {v_stop} V (full height)")
        except Exception:
            v_start = -0.5
            v_stop  =  0.5
            log("    Using default vertical range")

        log("  • Adding zoom diagram...")
        instr.write_str(
            f":LAYout:ZOOM:ADD 'Diagram1',VERT,OFF,"
            f"{xstart_s},{xstop_s},{v_start},{v_stop},'HW_CDR_Zoom'"
        )
        instr.query_opc()

        log("\n✅ HW CDR Eye Diagram with Zoom configured!")
        log(f"  • Horizontal Window: {xstart_ns} ns to {xstop_ns} ns ({window_ns} ns total)")
        log(f"  • Vertical: {v_start} V to {v_stop} V (full height)")
        log(f"  • Zoom diagram: 'HW_CDR_Zoom'")
        log(f"  ℹ️  The zoom window may take a few seconds to appear — this is normal instrument behaviour.")
    else:
        log("\n✅ HW CDR configured (zoom skipped).")
        log("   Trigger is set to CDR. Add zoom manually on the scope if needed.")


# ============================================================================
# JITTER ANALYSIS - QUICK START
# ============================================================================

def setup_jitter_quick_start(
    instr: RsInstrument,
    log_callback_fn=None
) -> None:
    """
    Configure Advanced Jitter Analysis using Quick Start.
    Automatically configures bit rate, CDR, and enables all jitter components.
    Note: Quick Start command does NOT use instance suffix.
    """
    log = lambda msg: log_callback(msg, log_callback_fn)
    log("Configuring Quick Start Jitter Analysis...")

    log("  • Setting source to DIFF1...")
    instr.write_str("ADVJitter:SIGNal:SOURce DIFF1")
    instr.query_opc(30000)

    log("  • Running Quick Start (auto-configuring)...")
    log("    This may take 30-60 seconds...")
    instr.write_str("ADVJitter:SIGNal:QUICkmeas")
    instr.query_opc(120000)

    log("✅ Quick Start Jitter configured!")
    log("   Auto-enabled: TJ@BER, RJ, TJ, DJ, PJ, DDJ")


# ============================================================================
# JITTER ANALYSIS - SHARED HELPER
# ============================================================================

def _disable_quick_start_extras(instr: RsInstrument, log_callback_fn=None) -> None:
    """
    Turn off the three display results that Quick Start enables automatically:
      - Step Response  : ADVJitter1:RESult:STEPresponse OFF
      - DDJ Bathtub    : ADVJitter1:RESult:BATHtub OFF
      - DDN Bathtub    : ADVJitter1:RESult:NBAThtub OFF

    Correct syntax confirmed from R&S RTP manual — no :ENABle suffix.
    BERScan does NOT exist in the manual and is never sent.
    """
    log = lambda msg: log_callback(msg, log_callback_fn)
    for cmd, label in [
        ("ADVJitter1:RESult:STEPresponse OFF", "Step Response"),
        ("ADVJitter1:RESult:BATHtub OFF",      "DDJ Bathtub"),
        ("ADVJitter1:RESult:NBAThtub OFF",      "DDN Bathtub"),
    ]:
        try:
            instr.write_str(cmd)
            instr.query_opc(30000)
            log(f"    {label}: OFF")
        except Exception as e:
            log(f"    {label}: could not disable — {e}")


# ============================================================================
# JITTER ANALYSIS - MANUAL COMPONENTS
# ============================================================================

def setup_jitter_manual_components(
    instr: RsInstrument,
    components: list[str],
    enable_step_response: bool = False,
    enable_ber_curve: bool = False,
    log_callback_fn=None
) -> None:
    """
    Configure Advanced Jitter with manually selected components.

    The GUI reset block has already run CLEJitcomp before this is called.
    This function goes straight to disabling Quick Start display extras,
    then enabling only the selected components.

    Args:
        instr: RsInstrument instance
        components: List of component names e.g. ['DDJ', 'RJ', 'TJ']
        enable_step_response: Re-enable Step Response after disabling (default: False)
        enable_ber_curve: Unused — kept for API compatibility (BERScan does not exist)
        log_callback_fn: Optional callback for status messages
    """
    log = lambda msg: log_callback(msg, log_callback_fn)
    log("Configuring Manual Jitter Components...")

    log("  [1/3] Setting source to DIFF1...")
    instr.write_str("ADVJitter1:SIGNal:SOURce DIFF1")
    instr.query_opc(30000)

    log("  [2/3] Enabling Results display...")
    instr.write_str("ADVJitter1:RESult:ENABle ON")
    instr.query_opc(30000)

    log("  Disabling Quick Start display extras...")
    _disable_quick_start_extras(instr, log_callback_fn)

    if enable_step_response:
        log("    Re-enabling Step Response (user requested)...")
        try:
            instr.write_str("ADVJitter1:RESult:STEPresponse ON")
            instr.query_opc(30000)
        except Exception as e:
            log(f"    Step Response enable failed — {e}")

    log(f"  [3/3] Enabling {len(components)} component(s)...")
    for i, comp_name in enumerate(components, 1):
        info = JITTER_COMPONENTS[comp_name]
        idx  = info['index']
        log(f"    [{i}/{len(components)}] {comp_name} (Index {idx})...")
        instr.write_str(f"ADVJitter1:DCOMposition:COMPonents{idx}:ENABle ON")
        instr.query_opc(30000)
        instr.write_str(f"ADVJitter1:RESult:COMPonents{idx}:HISTogram ON")
        instr.query_opc(30000)

    log(f"✅ Manual Jitter configured! {len(components)} components enabled.")
    if not enable_step_response:
        log("   Step Response: OFF")
    log("   DDJ Bathtub: OFF  |  DDN Bathtub: OFF")


# ============================================================================
# JITTER ANALYSIS - TRANSITION-DEPENDENT PAM-N RESULTS
# ============================================================================

def setup_jitter_component_for_pamn(
    instr: RsInstrument,
    component: str,
    log_callback_fn=None
) -> None:
    """
    Initialise Advanced Jitter and enable exactly one decomposition component.

    Must be called before setup_jitter_pamn_results().
    The GUI reset block has already run CLEJitcomp before this is called.
    Quick Start display extras are disabled here.

    Args:
        instr: RsInstrument instance
        component: Component key from JITTER_COMPONENTS e.g. "DDJ"
        log_callback_fn: Optional callback for status messages
    """
    log = lambda msg: log_callback(msg, log_callback_fn)
    idx = JITTER_COMPONENTS[component]["index"]

    log(f"Enabling jitter component: {component}")

    log("  [1/3] Setting source to DIFF1...")
    instr.write_str("ADVJitter1:SIGNal:SOURce DIFF1")
    instr.query_opc(30000)

    log("  [2/3] Enabling Results display...")
    instr.write_str("ADVJitter1:RESult:ENABle ON")
    instr.query_opc(30000)

    log("  Disabling Quick Start display extras...")
    _disable_quick_start_extras(instr, log_callback_fn)

    log(f"  [3/3] Enabling {component} (index {idx}) + histogram...")
    instr.write_str(f"ADVJitter1:DCOMposition:COMPonents{idx}:ENABle ON")
    instr.query_opc(30000)
    instr.write_str(f"ADVJitter1:RESult:COMPonents{idx}:HISTogram ON")
    instr.query_opc(30000)

    log(f"✅ {component} ready for PAM-N Results.")


def setup_jitter_pamn_results(
    instr: RsInstrument,
    component: str,
    transitions: list[dict],
    log_callback_fn=None
) -> None:
    """
    Configure PAM-N transition-dependent jitter results.
    Call setup_jitter_component_for_pamn() first.

    Args:
        instr: RsInstrument instance
        component: Component key from JITTER_COMPONENTS e.g. "DDJ"
        transitions: List of {'base': int, 'target': int} dicts (PAM-4: 0-3)
        log_callback_fn: Optional callback for status messages
    """
    log = lambda msg: log_callback(msg, log_callback_fn)
    log(f"Configuring PAM-N Results for {component}...")

    log("  [1/2] Enabling PAM-N Results...")
    instr.write_str("ADVJitter1:RESult:PAMJitter:CONFig:ENABle ON")
    instr.query_opc()

    log(f"  [2/2] Adding {len(transitions)} transition(s)...")
    for i, trans in enumerate(transitions):
        base      = trans['base']
        target    = trans['target']
        color_dec = TRANSITION_COLORS[i % len(TRANSITION_COLORS)]
        color_hex = hex(int(color_dec))[2:].upper().zfill(6)

        log(f"    [{i+1}/{len(transitions)}] {base}→{target} (#{color_hex})")

        instr.write_str(
            f"ADVJitter1:RESult:PAMJitter:CONFig:CATegory1:ADD "
            f"{component},{base},{target},RISING,{color_dec}"
        )
        opc_poll(instr, total_timeout_s=600,
                 label=f"CATegory1:ADD {base}→{target}",
                 log_callback_fn=log_callback_fn)
        log(f"      ✅ Numerical")

        instr.write_str(
            f"ADVJitter1:RESult:PAMJitter:CONFig:CATegory2:ADD "
            f"{component},{base},{target},RISING,{color_dec}"
        )
        opc_poll(instr, total_timeout_s=600,
                 label=f"CATegory2:ADD {base}→{target}",
                 log_callback_fn=log_callback_fn)
        log(f"      ✅ Histogram")

    log(f"✅ PAM-N Results configured: {component}, {len(transitions)} transition(s).")


# ============================================================================
# CONNECTION HELPER
# ============================================================================

def connect_instrument(
    ip_address: str,
    timeout_ms: int = 120000,
    log_callback_fn=None
) -> RsInstrument:
    """
    Connect to oscilloscope and return instrument handle.

    Args:
        ip_address: IP address of oscilloscope
        timeout_ms: VISA timeout in milliseconds
        log_callback_fn: Optional callback for status messages

    Returns:
        RsInstrument instance
    """
    log = lambda msg: log_callback(msg, log_callback_fn)
    resource = f"TCPIP::{ip_address}::INSTR"
    log(f"Connecting to {ip_address}...")

    try:
        instr = RsInstrument(resource, id_query=False, reset=False)
        instr.visa_timeout = timeout_ms
        instr.opc_timeout  = timeout_ms
        idn = instr.query_str("*IDN?")
        log(f"✅ Connected: {idn}")
        return instr
    except Exception as e:
        log(f"❌ Connection failed: {e}")
        raise