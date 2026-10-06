import os
import sys
import shutil
import zipfile
import ctypes
import re

# [EoTS 1.0 - Rename]: release name and pk3 names. Keep in sync with EOTS_VERSION in src/game/bg_public.h.
EOTS_VERSION = "1.0.7b"
BIN_PK3 = f"nqeots_b_v{EOTS_VERSION}.pk3"
ASSET_PK3 = f"nqeots_v{EOTS_VERSION}.pk3"
# pk3s the EoTS ones replace. Removed from the release folder and test installs.
OLD_PK3S = ["nq_b_v1.3.1_64.pk3", "nq_b_v1.3.1_32.pk3", "nq_b_v1.3.1b6.pk3", "nq_v1.3.1b6.pk3",
            "nq_b_v1.3.1b7.pk3", "nq_v1.3.1b7.pk3"]

def check_dll_exports(dll_path, expected_exports):
    print(f"Checking {dll_path}...")
    try:
        lib = ctypes.CDLL(dll_path)
        for sym in expected_exports:
            has_sym = hasattr(lib, sym)
            print(f"  Export '{sym}': {'OK' if has_sym else 'MISSING'}")
            if not has_sym:
                return False
        return True
    except Exception as e:
        print(f"  Failed to load DLL {dll_path}: {e}")
        return False

# Paths
SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
SOURCE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
TRUNK_DIR = os.path.abspath(os.path.join(SOURCE_DIR, ".."))

def pick_build_dir(env_name, candidates, marker):
    """Use env override if set, else whichever candidate folder has the newest build."""
    if os.environ.get(env_name):
        return os.environ[env_name]
    found = [d for d in candidates if os.path.exists(os.path.join(d, marker))]
    if not found:
        sys.exit(f"ERROR: {marker} not found in any of: {candidates}. Build first, or set {env_name}.")
    return max(found, key=lambda d: os.path.getmtime(os.path.join(d, marker)))

# Windows build output: command-line builds (build64/build32) or Visual Studio "Open Folder" builds (out/build/...)
BUILD64_DIR = pick_build_dir("NQ_BUILD64_DIR", [
    os.path.join(SOURCE_DIR, "build64", "src", "Release"),
    os.path.join(SOURCE_DIR, "out", "build", "x64-Release", "src")], "qagame_mp_x64.dll")
BUILD32_DIR = pick_build_dir("NQ_BUILD32_DIR", [
    os.path.join(SOURCE_DIR, "build32", "src", "Release"),
    os.path.join(SOURCE_DIR, "out", "build", "x86-Release", "src")], "qagame_mp_x86.dll")
print(f"Using Windows 64-bit build: {BUILD64_DIR}")
print(f"Using Windows 32-bit build: {BUILD32_DIR}")
LINUX64_DIR = os.path.join(SOURCE_DIR, "build64", "Release", "linux")
LINUX32_DIR = os.path.join(SOURCE_DIR, "build32", "Release", "linux")

# Where the release is assembled. Defaults to <repo>/release (git-ignored);
# set NQ_RELEASE_DIR to use another folder.
# macOS build output (cgame_mac / ui_mac). Copy them here from the Mac build, or set NQ_MAC_DIR.
MAC_DIR = os.environ.get("NQ_MAC_DIR", os.path.join(SOURCE_DIR, "build_mac", "src"))
RELEASE_DIR = os.environ.get("NQ_RELEASE_DIR", os.path.join(SOURCE_DIR, "release"))
# Optional local installs to copy the new build into for testing.
# Nothing is copied unless these environment variables are set.
ET64_NQ_DIR = os.environ.get("ET64_DIR", "")
ET32_NQ_DIR = os.environ.get("ET32_DIR", "")
CLIENT_NQ_DIR = os.environ.get("NQ_CLIENT_DIR", "")

# 1. Verify 64-bit and 32-bit DLL exports
cgame64 = os.path.join(BUILD64_DIR, "cgame_mp_x64.dll")
ui64 = os.path.join(BUILD64_DIR, "ui_mp_x64.dll")
qagame64 = os.path.join(BUILD64_DIR, "qagame_mp_x64.dll")

cgame32 = os.path.join(BUILD32_DIR, "cgame_mp_x86.dll")
ui32 = os.path.join(BUILD32_DIR, "ui_mp_x86.dll")
qagame32 = os.path.join(BUILD32_DIR, "qagame_mp_x86.dll")

assert check_dll_exports(cgame64, ["vmMain", "dllEntry"]), "cgame_mp_x64.dll exports missing!"
assert check_dll_exports(ui64, ["vmMain", "dllEntry"]), "ui_mp_x64.dll exports missing!"
assert check_dll_exports(qagame64, ["vmMain", "dllEntry"]), "qagame_mp_x64.dll exports missing!"

# Helper to build Universal (Multi-Architecture) Binary PK3
def build_universal_binary_pk3(pk3_path):
    print(f"\nBuilding Universal Multi-Architecture PK3: {pk3_path}...")
    os.makedirs(os.path.dirname(pk3_path), exist_ok=True)
    with zipfile.ZipFile(pk3_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        # Windows 64-bit Client DLLs
        z.write(cgame64, "cgame_mp_x64.dll")
        z.write(ui64, "ui_mp_x64.dll")

        # Windows 32-bit Client DLLs
        z.write(cgame32, "cgame_mp_x86.dll")
        z.write(ui32, "ui_mp_x86.dll")

        # Linux 64-bit Client SOs
        cgame64_so = os.path.join(LINUX64_DIR, "cgame.mp.x86_64.so")
        ui64_so = os.path.join(LINUX64_DIR, "ui.mp.x86_64.so")
        if os.path.exists(cgame64_so):
            z.write(cgame64_so, "cgame.mp.x86_64.so")
        if os.path.exists(ui64_so):
            z.write(ui64_so, "ui.mp.x86_64.so")

        # Linux 32-bit Client SOs
        cgame32_so = os.path.join(LINUX32_DIR, "cgame.mp.i386.so")
        ui32_so = os.path.join(LINUX32_DIR, "ui.mp.i386.so")
        if os.path.exists(cgame32_so):
            z.write(cgame32_so, "cgame.mp.i386.so")
        if os.path.exists(ui32_so):
            z.write(ui32_so, "ui.mp.i386.so")

        # macOS universal (Intel + Apple Silicon) client modules, if built.
        # ET:Legacy loads these extension-less names on macOS.
        for mac_name in ("cgame_mac", "ui_mac"):
            mac_path = os.path.join(MAC_DIR, mac_name)
            if os.path.exists(mac_path):
                z.write(mac_path, mac_name)
    print(f"Built {pk3_path} successfully.")

# 2. Build the unified binary pk3 (nqeots_b_v<ver>.pk3)
pk3_unified_path = os.path.join(RELEASE_DIR, BIN_PK3)
build_universal_binary_pk3(pk3_unified_path)

# 3. Build the asset pk3 (nqeots_v<ver>.pk3) from the previous asset pk3, with menudef files,
#    menus, meyer.shader and texture fixes swapped in. The first EoTS build starts from nq_v1.3.1b7.pk3.
src_base_asset_pk3 = None
for base_name in [ASSET_PK3, "nq_v1.3.1b7.pk3", "nq_v1.3.1b6.pk3", "nq_v1.3.1_b.pk3"]:
    if os.path.exists(os.path.join(RELEASE_DIR, base_name)):
        src_base_asset_pk3 = os.path.join(RELEASE_DIR, base_name)
        break
if not src_base_asset_pk3:
    sys.exit(f"ERROR: no base asset pk3 ({ASSET_PK3} or nq_v1.3.1b7.pk3) found in {RELEASE_DIR}. "
             "Copy the current one there, or set NQ_RELEASE_DIR to your release folder.")
print(f"Using base asset pk3: {src_base_asset_pk3}")
asset_pk3_path = os.path.join(RELEASE_DIR, ASSET_PK3)

menudef_h = os.path.join(TRUNK_DIR, "etmain", "ui", "menudef.h")
menudef2_h = os.path.join(TRUNK_DIR, "etmain", "ui", "menudef2.h")
vote_map_menu = os.path.join(TRUNK_DIR, "assets", "ui", "ingame_vote_map.menu")
meyer_shader = os.path.join(TRUNK_DIR, "assets", "scripts", "meyer.shader")

overrides = {
    "ui/menudef.h": menudef_h,
    "ui/menudef2.h": menudef2_h,
    "ui/ingame_vote_map.menu": vote_map_menu,
    "scripts/meyer.shader": meyer_shader,
    # [NQ EoTS - Options]: ET: Legacy system settings page (kept in the repo, etmain/ui)
    "ui/options.menu": os.path.join(SOURCE_DIR, "etmain", "ui", "options.menu"),
    "ui/options_system_etl.menu": os.path.join(SOURCE_DIR, "etmain", "ui", "options_system_etl.menu"),
    "ui/menus.txt": os.path.join(SOURCE_DIR, "etmain", "ui", "menus.txt"),
    # Talk balloon (sprites/nq_talk) and buy icon shaders restored from the original NQ file,
    # merged with the EoTS server-browser filter icon fix
    "scripts/shaderfix.shader": os.path.join(SOURCE_DIR, "etmain", "scripts", "shaderfix.shader"),
}

# Add texture fixes (ctf_pool, pool, etc.)
for sub_dir in ["ctf_pool", "pool"]:
    tex_dir = os.path.join(TRUNK_DIR, "assets", "textures", sub_dir)
    if os.path.exists(tex_dir):
        for fname in os.listdir(tex_dir):
            fpath = os.path.join(tex_dir, fname)
            if os.path.isfile(fpath):
                arcname = f"textures/{sub_dir}/{fname}".replace("\\", "/")
                overrides[arcname] = fpath

# [EoTS 1.0 - Rename]: NQ logo and version text in the in-game (ESC) and NQ options menus.
# Patched inside the pk3's own copy of each menu, so nothing else in those menus changes.
# The logo is centered under the menu window and the version text is centered on its own
# line below it. Everything stays in menu coordinates (640x480 virtual screen), so it
# scales with resolution and widescreen exactly like the rest of the menu.
# Safe to run again on an already patched pk3.
VERSION_MENUS = ["ui/ingame_main.menu", "ui/options_nq.menu"]
ITEMDEF_RE = re.compile(rb'itemDef\s*\{[^{}]*\}', re.S)
# Both menus are 160 wide (WINDOW_WIDTH). The visible logo sits at x 139..370 of the 512-wide
# logo_nq.tga, so in a 232-wide rect its middle is 115 from the left: x = 80 - 115 = -35.
# (A plain number, as the original -58 was; negative $evalfloat results are best avoided.)
LOGO_RECT = b'rect      -35 200 232 32'
VERSION_LINES = {
    rb'rect\s+[^\r\n]*': b'rect      0 232 WINDOW_WIDTH 12',
    rb'textalign\s+[^\r\n]*': b'textalign   ITEM_ALIGN_CENTER',
    rb'textalignx\s+[^\r\n]*': b'textalignx   $evalfloat(.5*WINDOW_WIDTH)',
    rb'text\s+"[^"]*"': f'text      "^7EoTS {EOTS_VERSION}"'.encode(),
}

def _set_line(block, pattern, value):
    # replace a "key value" line at the start of a line (so "text" doesn't hit "textalign")
    return re.sub(rb'(?m)^(\s*)' + pattern + rb'[ \t]*(?=\r?$)', lambda m: m.group(1) + value, block, count=1)

def patch_version_text(data):
    count = 0
    def fix_item(m):
        nonlocal count
        block = m.group(0)
        if re.search(rb'background\s+"ui/assets/logo_nq"', block):
            block = _set_line(block, rb'rect\s+[^\r\n]*', LOGO_RECT)
            count += 1
        elif re.search(rb'name\s+"versionString2?"', block):
            for pattern, value in VERSION_LINES.items():
                block = _set_line(block, pattern, value)
            count += 1
        return block
    return ITEMDEF_RE.sub(fix_item, data), count

print(f"\nBuilding {asset_pk3_path} with menudef headers, menus, caduceus fix, and texture fixes ({len(overrides)} overrides)...")
temp_asset_pk3 = asset_pk3_path + ".tmp"
written_arcnames = set()
with zipfile.ZipFile(src_base_asset_pk3, 'r') as zin, zipfile.ZipFile(temp_asset_pk3, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        norm_name = item.filename.replace("\\", "/")
        if norm_name in overrides:
            zout.write(overrides[norm_name], norm_name)
            written_arcnames.add(norm_name)
        else:
            buffer = zin.read(item.filename)
            if norm_name in VERSION_MENUS:
                buffer, count = patch_version_text(buffer)
                print(f"  Set NQ logo and version text in {norm_name} ({count} item(s))")
            zout.writestr(item, buffer)
    
    # Add any new files that weren't in the original pk3
    for arcname, fpath in overrides.items():
        if arcname not in written_arcnames:
            zout.write(fpath, arcname)
            written_arcnames.add(arcname)
            print(f"  Added new asset to pk3: {arcname}")

os.replace(temp_asset_pk3, asset_pk3_path)
print(f"Built {asset_pk3_path} successfully.")

# 4. Clean up obsolete/legacy pk3s from RELEASE_DIR
for old_file in OLD_PK3S:
    old_p = os.path.join(RELEASE_DIR, old_file)
    if os.path.exists(old_p):
        os.remove(old_p)
        print(f"Removed legacy release pk3: {old_file}")

# 5. Copy release binaries to DLL's subfolders
win64_dir = os.path.join(RELEASE_DIR, "DLL's", "Windows", "64 Bit")
win32_dir = os.path.join(RELEASE_DIR, "DLL's", "Windows", "32 Bit")
lin64_dir = os.path.join(RELEASE_DIR, "DLL's", "Linux", "64 Bit")
lin32_dir = os.path.join(RELEASE_DIR, "DLL's", "Linux", "32 Bit")
for d in [win64_dir, win32_dir, lin64_dir, lin32_dir]:
    os.makedirs(d, exist_ok=True)

def copy_if_exists(src, dst):
    if os.path.exists(src):
        shutil.copy2(src, dst)

# Server files only; client cgame/ui ship inside the binary pk3. Names are exactly what ET:Legacy loads:
# Windows = underscore names (qagame_mp_x64.dll), Linux = dot names (qagame.mp.x86_64.so).
shutil.copy2(qagame64, os.path.join(win64_dir, "qagame_mp_x64.dll"))
# lua5.1.dll goes next to etlded.exe; the LuaSQL driver goes where
# require("luasql.sqlite3") looks: nq/lualibs/luasql/sqlite3.dll
for build_dir, out_dir in ((BUILD64_DIR, win64_dir), (BUILD32_DIR, win32_dir)):
    copy_if_exists(os.path.join(build_dir, "lua5.1.dll"), os.path.join(out_dir, "lua5.1.dll"))
    luasql_dir = os.path.join(out_dir, "lualibs", "luasql")
    os.makedirs(luasql_dir, exist_ok=True)
    copy_if_exists(os.path.join(build_dir, "sqlite3.dll"), os.path.join(luasql_dir, "sqlite3.dll"))
shutil.copy2(pk3_unified_path, os.path.join(win64_dir, BIN_PK3))

shutil.copy2(qagame32, os.path.join(win32_dir, "qagame_mp_x86.dll"))
shutil.copy2(pk3_unified_path, os.path.join(win32_dir, BIN_PK3))

if os.path.exists(os.path.join(LINUX64_DIR, "qagame.mp.x86_64.so")):
    shutil.copy2(os.path.join(LINUX64_DIR, "qagame.mp.x86_64.so"), os.path.join(lin64_dir, "qagame.mp.x86_64.so"))
# Linux: Lua and LuaSQL/SQLite are built into qagame (NQ_BUILTIN_LUASQL), so the
# small liblua5.1.so / sqlite3.so stubs build_linux.py writes are not shipped.
shutil.copy2(pk3_unified_path, os.path.join(lin64_dir, BIN_PK3))

if os.path.exists(os.path.join(LINUX32_DIR, "qagame.mp.i386.so")):
    shutil.copy2(os.path.join(LINUX32_DIR, "qagame.mp.i386.so"), os.path.join(lin32_dir, "qagame.mp.i386.so"))
shutil.copy2(pk3_unified_path, os.path.join(lin32_dir, BIN_PK3))

# Clean old pk3s in DLL's subfolders
for d in [win64_dir, win32_dir, lin64_dir, lin32_dir]:
    for old_name in OLD_PK3S:
        op = os.path.join(d, old_name)
        if os.path.exists(op):
            os.remove(op)

def safe_copy(src, dst):
    try:
        shutil.copy2(src, dst)
        print(f"  Copied {os.path.basename(src)} -> {dst}")
    except PermissionError:
        print(f"  [NOTICE] Could not copy {os.path.basename(src)} to {dst} (game/server is currently running). Restart game/server to apply.")
    except Exception as e:
        print(f"  [WARN] Copy failed: {e}")

# 6. Copy to active test game directories and remove legacy pk3s
for target_dir in [ET64_NQ_DIR, CLIENT_NQ_DIR, ET32_NQ_DIR]:
    if target_dir and os.path.exists(target_dir):
        print(f"\nUpdating {target_dir}...")
        safe_copy(pk3_unified_path, os.path.join(target_dir, BIN_PK3))
        safe_copy(asset_pk3_path, os.path.join(target_dir, ASSET_PK3))
        # Remove the pk3s the EoTS ones replace
        for legacy in OLD_PK3S:
            lp = os.path.join(target_dir, legacy)
            if os.path.exists(lp):
                try:
                    os.remove(lp)
                    print(f"  Removed obsolete {legacy} from {target_dir}")
                except Exception as e:
                    print(f"  [WARN] Could not remove {legacy}: {e}")

if ET64_NQ_DIR and os.path.exists(ET64_NQ_DIR):
    safe_copy(qagame64, os.path.join(ET64_NQ_DIR, "qagame_mp_x64.dll"))

if CLIENT_NQ_DIR and os.path.exists(CLIENT_NQ_DIR):
    safe_copy(cgame64, os.path.join(CLIENT_NQ_DIR, "cgame_mp_x64.dll"))
    safe_copy(ui64, os.path.join(CLIENT_NQ_DIR, "ui_mp_x64.dll"))
    safe_copy(cgame32, os.path.join(CLIENT_NQ_DIR, "cgame_mp_x86.dll"))
    safe_copy(ui32, os.path.join(CLIENT_NQ_DIR, "ui_mp_x86.dll"))
    safe_copy(qagame64, os.path.join(CLIENT_NQ_DIR, "qagame_mp_x64.dll"))

if ET32_NQ_DIR and os.path.exists(ET32_NQ_DIR):
    safe_copy(cgame32, os.path.join(ET32_NQ_DIR, "cgame_mp_x86.dll"))
    safe_copy(ui32, os.path.join(ET32_NQ_DIR, "ui_mp_x86.dll"))
    safe_copy(qagame32, os.path.join(ET32_NQ_DIR, "qagame_mp_x86.dll"))

print("\nAll unified packaging and deployments completed successfully!")
