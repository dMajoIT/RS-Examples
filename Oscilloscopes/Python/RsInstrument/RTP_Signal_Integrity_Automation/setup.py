from cx_Freeze import setup, Executable

build_options = {
    "packages": [
        "tkinter",
        "RsInstrument",
        "threading",
        "datetime",
        "time",
        "os",
        "sys",
    ],
    "excludes": [],
    "include_files": [],
}

setup(
    name="Signal Integrity Automator",
    version="1.0",
    description="R&S RTP PAM-N Automotive Ethernet Signal Integrity Tool",
    options={"build_exe": build_options},
    executables=[
        Executable(
            "PAM_AE_SignalIntegrity_GUI.py",
            base="gui",
            target_name="SignalIntegrityAutomator.exe",
            icon=None,
        )
    ],
)

